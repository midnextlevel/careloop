import uuid
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, RequestFactory, override_settings
from django.core.management import call_command, CommandError
from io import StringIO
from django.urls import reverse
from django.utils import timezone
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.core.exceptions import ImmediateHttpResponse
from journal.adapters import ApprovedGoogleAdapter
from journal.models import Entry, Membership, Revision, Comment
from journal.services import FIELDS, write_entry, Conflict


def identity(role, name):
    user = get_user_model().objects.create_user(username=name, email=f'{name}@example.invalid')
    member = Membership.objects.create(email=user.email, role=role, user=user,
        google_subject=f'sub-{name}', history_start=timezone.now()-timedelta(days=2))
    return user, member


class SetupCommandTests(TestCase):
    def test_bootstrap_approves_owner_without_login_credentials(self):
        call_command('bootstrap_owner', 'Parent@Example.invalid', stdout=StringIO())
        member = Membership.objects.get(email='parent@example.invalid')
        self.assertEqual(member.role, 'owner')
        self.assertTrue(member.active)
        self.assertIsNone(member.user_id)
        self.assertEqual(get_user_model().objects.count(), 0)
        with self.assertRaises(CommandError):
            call_command('bootstrap_owner', 'second@example.invalid', stdout=StringIO())

    @override_settings(DEBUG=True)
    def test_fictional_seed_is_idempotent_and_never_grants_login(self):
        for _ in range(2):
            call_command('seed_fictional', stdout=StringIO())
        self.assertEqual(Entry.objects.count(), 3)
        self.assertFalse(Membership.objects.filter(active=True).exists())
        self.assertFalse(get_user_model().objects.filter(is_active=True).exists())
        self.assertTrue(all(not user.has_usable_password() for user in get_user_model().objects.all()))
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command('seed_fictional', stdout=StringIO())


class GoogleAdmissionTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get('/accounts/google/login/callback/')
        from django.contrib.auth.models import AnonymousUser
        self.request.user = AnonymousUser()
        self.adapter = ApprovedGoogleAdapter(self.request)

    def social(self, email='approved@example.invalid', verified=True, uid='stable-subject'):
        return SocialLogin(user=get_user_model()(email=email),
            account=SocialAccount(provider='google', uid=uid, extra_data={'email': email}),
            email_addresses=[EmailAddress(email=email, verified=verified, primary=True)])

    def test_unapproved_and_unverified_denied(self):
        for login in [self.social(), self.social('other@example.invalid')]:
            with self.assertRaises(ImmediateHttpResponse):
                self.adapter.pre_social_login(self.request, login)
        Membership.objects.create(email='approved@example.invalid', role='teacher')
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, self.social(verified=False))

    def test_assigned_role_and_stable_subject_binding(self):
        member = Membership.objects.create(email='approved@example.invalid', role='therapist')
        social = self.social()
        self.adapter.pre_social_login(self.request, social)
        # Mock provider identity only: no live Google OAuth exchange in this test.
        from django.contrib.sessions.middleware import SessionMiddleware
        SessionMiddleware(lambda request: None).process_request(self.request)
        user = self.adapter.save_user(self.request, social)
        member.refresh_from_db()
        self.assertEqual(member.user, user)
        self.assertEqual(member.role, 'therapist')
        self.assertEqual(member.google_subject, 'stable-subject')
        self.assertFalse(user.has_usable_password())
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, self.social(uid='different-subject'))

    def test_exact_mailbox_and_revocation(self):
        member = Membership.objects.create(email='approved@example.invalid', role='teacher')
        for email in ['approved+tag@example.invalid', 'another@example.invalid']:
            with self.assertRaises(ImmediateHttpResponse):
                self.adapter.pre_social_login(self.request, self.social(email))
        member.active = False
        member.save()
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, self.social())

    def test_existing_identity_must_still_be_verified_and_bound(self):
        user, member = identity('teacher', 'existing')
        login = self.social(email=user.email, uid=member.google_subject)
        login.user = user
        self.adapter.pre_social_login(self.request, login)
        login.email_addresses[0].verified = False
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, login)
        login.email_addresses[0].verified = True
        login.account.uid = 'replacement-subject'
        with self.assertRaises(ImmediateHttpResponse):
            self.adapter.pre_social_login(self.request, login)


class JournalTests(TestCase):
    def setUp(self):
        self.owner, self.om = identity('owner', 'parent')
        self.teacher, self.tm = identity('teacher', 'teacher')
        self.therapist, self.pm = identity('therapist', 'therapist')
        self.entry = Entry.objects.create(author=self.therapist, summary='Restricted therapist note',
            submitted_at=timezone.now(), audience='parent')
        self.client.force_login(self.teacher)

    def payload(self, entry, summary='A thoughtful daily summary'):
        return {field: getattr(entry, field) for field in FIELDS} | {'summary': summary, 'version': entry.version}

    def ticket(self, entry, **changes):
        payload = self.payload(entry) | changes
        payload['event_date'] = str(payload['event_date'])
        version = payload.pop('version')
        return signing.dumps({'id': str(entry.pk), 'author': entry.author_id, 'version': version,
            'data': payload, 'token': str(uuid.uuid4())}, salt='review')

    def test_restricted_entries_hidden_including_htmx_and_comments(self):
        for headers in [{}, {'HTTP_HX_REQUEST': 'true'}]:
            self.assertNotContains(self.client.get('/', **headers), 'Restricted therapist note')
            self.assertEqual(self.client.get(reverse('detail', args=[self.entry.pk]), **headers).status_code, 404)
            self.assertEqual(self.client.post(reverse('comment', args=[self.entry.pk]), {'body': 'hello'}, **headers).status_code, 404)
        self.assertEqual(Comment.objects.count(), 0)

    def test_parent_sees_submitted_but_not_others_drafts(self):
        draft = Entry.objects.create(author=self.teacher, summary='Secret draft')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('detail', args=[self.entry.pk])), 'Restricted therapist note')
        self.assertEqual(self.client.get(reverse('detail', args=[draft.pk])).status_code, 404)
        self.client.force_login(self.therapist)
        self.assertEqual(self.client.get(reverse('detail', args=[draft.pk])).status_code, 404)
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(reverse('detail', args=[draft.pk])), 'Secret draft')

    def test_other_author_cannot_edit_even_owner(self):
        for user in [self.teacher, self.owner]:
            self.client.force_login(user)
            for name in ['edit', 'publish']:
                self.assertEqual(self.client.post(reverse(name, args=[self.entry.pk]), self.payload(self.entry)).status_code, 404)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.summary, 'Restricted therapist note')

    def test_existing_session_revoked_next_request(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        self.tm.active = False
        self.tm.save()
        self.assertEqual(self.client.get('/').status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_history_uses_submission_not_event_date(self):
        self.entry.audience = 'team'
        self.entry.submitted_at = timezone.now()-timedelta(days=3)
        self.entry.save()
        url = reverse('detail', args=[self.entry.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.tm.history_start = timezone.now()-timedelta(days=4)
        self.tm.save()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.entry.event_date = timezone.localdate()-timedelta(days=100)
        self.entry.submitted_at = timezone.now()
        self.entry.save()
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_own_history_and_narrow_revisions(self):
        self.entry.audience = 'team'
        self.entry.save()
        Revision.objects.create(entry=self.entry, version=1, snapshot={'summary': 'Former private version'})
        self.assertNotContains(self.client.get(reverse('detail', args=[self.entry.pk])), 'Former private version')
        self.client.force_login(self.therapist)
        self.pm.history_start = timezone.now()+timedelta(days=1)
        self.pm.save()
        self.assertContains(self.client.get(reverse('detail', args=[self.entry.pk])), 'Former private version')

    def test_draft_save_review_publish_retry_and_revision(self):
        draft = Entry.objects.create(author=self.teacher)
        url = reverse('edit', args=[draft.pk])
        result = self.client.post(url, self.payload(draft) | {'action': 'save'}, HTTP_ACCEPT='application/json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['version'], 2)
        draft.refresh_from_db()
        review = self.client.post(url, self.payload(draft) | {'action': 'review'})
        self.assertContains(review, 'Parent + author')
        ticket = review.context['ticket']
        pub = reverse('publish', args=[draft.pk])
        for _ in range(2):
            self.assertEqual(self.client.post(pub, {'ticket': ticket, 'confirmed': 'on'}).status_code, 302)
        self.assertEqual(Entry.objects.filter(author=self.teacher).count(), 1)
        self.assertEqual(Revision.objects.count(), 0)
        draft.refresh_from_db()
        self.assertIsNotNone(draft.submitted_at)
        self.assertEqual(draft.version, 3)
        self.assertEqual(self.client.post(pub, {'ticket': self.ticket(draft, summary='Edited entry'), 'confirmed': 'on'}).status_code, 302)
        self.assertEqual(Revision.objects.count(), 1)
        self.assertEqual(Revision.objects.get().snapshot['summary'], 'A thoughtful daily summary')

    def test_conflicting_edits_and_stale_draft_save(self):
        draft = Entry.objects.create(author=self.teacher, summary='Original')
        old = self.payload(draft)
        token = self.ticket(draft)
        write_entry(self.tm, draft.pk, old, 1)
        response = self.client.post(reverse('publish', args=[draft.pk]), {'ticket': token, 'confirmed': 'on'})
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'A thoughtful daily summary', status_code=409)
        draft.refresh_from_db()
        write_entry(self.tm, draft.pk, old, draft.version, publish=True, token=uuid.uuid4())
        draft.refresh_from_db()
        response = self.client.post(reverse('edit', args=[draft.pk]), old | {'action': 'save', 'version': draft.version}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 409)
        draft.refresh_from_db()
        self.assertEqual(draft.version, 3)

    def test_review_tampering_and_author_binding(self):
        draft = Entry.objects.create(author=self.teacher)
        pub = reverse('publish', args=[draft.pk])
        self.assertEqual(self.client.post(pub, {'ticket': self.ticket(draft)+'tampered', 'confirmed': 'on'}).status_code, 400)
        self.assertEqual(self.client.post(pub, {'ticket': self.ticket(draft)}).status_code, 400)

    def test_private_responses_and_cache_configuration(self):
        own = Entry.objects.create(author=self.teacher, summary='Private text')
        for url in ['/', reverse('edit', args=[own.pk]), reverse('detail', args=[own.pk]), '/accounts/google/login/']:
            response = self.client.get(url)
            self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(self.client.get('/'), 'hx-history="false"')
        root = Path(settings.BASE_DIR)
        script = (root/'static/sw.js').read_text()
        self.assertNotIn('cache.put', script)
        self.assertNotIn("caches.match(event.request)", script)
        self.assertIn("PUBLIC_ASSETS.includes(url.pathname)", script)
        self.assertIn("event.request.method !== 'GET'", script)
        js = (root/'static/app.js').read_text()
        self.assertNotIn('localStorage', js)
        self.assertNotIn('indexedDB', js)
        self.assertIn("if (!response.ok) throw", js)

    def test_owner_membership_management(self):
        self.assertEqual(self.client.get('/team/').status_code, 403)
        self.client.force_login(self.owner)
        data = {'email': 'new@example.invalid', 'role': 'teacher', 'active': 'on', 'history_start': '2026-11-05T09:00'}
        self.assertEqual(self.client.post('/team/', data).status_code, 302)
        member = Membership.objects.get(email=data['email'])
        self.assertEqual(member.role, 'teacher')
        self.assertIsNone(member.user_id)
        before = timezone.now()
        self.assertEqual(self.client.post('/team/', data | {'email': 'default-history@example.invalid', 'history_start': ''}).status_code, 302)
        default_member = Membership.objects.get(email='default-history@example.invalid')
        self.assertEqual(default_member.history_start, default_member.joined_at)
        self.assertGreaterEqual(default_member.history_start, before)
        self.assertEqual(self.client.post(reverse('member-edit', args=[self.om.pk]), data | {'email': self.om.email, 'role': 'teacher'}).status_code, 200)
        self.om.refresh_from_db()
        self.assertEqual(self.om.role, 'owner')
