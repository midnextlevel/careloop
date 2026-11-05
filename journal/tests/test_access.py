from datetime import timedelta
from django.core import signing
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch
import uuid
from journal.models import Entry, JournalAccessSettings, Revision
from journal.services import FIELDS, write_entry
from .test_journal import identity


class DataAccessTests(TestCase):
    def setUp(self):
        self.owner, _ = identity('owner', 'access-owner')
        self.teacher, self.tm = identity('teacher', 'access-teacher')
        self.therapist, self.pm = identity('therapist', 'access-therapist')
        for member in (self.tm, self.pm):
            member.history_start = timezone.now() - timedelta(days=100)
            member.save()
        self.policy = JournalAccessSettings.current()
        self.entry = Entry.objects.create(author=self.teacher, summary='An older shared entry',
            audience='team', submitted_at=timezone.now() - timedelta(days=31))

    def url(self, suffix=''):
        return f'/entries/{self.entry.pk}/{suffix}'

    def owner_post(self, path, data):
        self.client.force_login(self.owner)
        return self.client.post(path, data)

    def ticket(self, entry):
        data = {field: str(getattr(entry, field)) for field in FIELDS}
        return signing.dumps({'id': str(entry.pk), 'author': entry.author_id,
            'version': entry.version, 'data': data, 'token': str(uuid.uuid4())}, salt='review')

    def test_expired_entries_are_hidden_everywhere_including_from_author(self):
        for user in (self.teacher, self.therapist):
            self.client.force_login(user)
            for headers in ({}, {'HTTP_HX_REQUEST': 'true'}):
                response = self.client.get('/', {'date': self.entry.event_date.isoformat()}, **headers)
                self.assertNotContains(response, self.entry.summary)
                self.assertEqual(self.client.get(self.url(), **headers).status_code, 404)
                self.assertEqual(self.client.get(self.url('edit/'), **headers).status_code, 404)
                self.assertEqual(self.client.post(self.url('edit/'), {'action': 'save'}, **headers).status_code, 404)
                self.assertEqual(self.client.post(self.url('comments/'), {'body': 'No access'}, **headers).status_code, 404)
            self.assertEqual(self.client.post(self.url('publish/'), {
                'ticket': self.ticket(self.entry), 'confirmed': 'on'}).status_code, 404)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.url()), self.entry.summary)

    def test_fixed_deadline_takes_effect_on_next_request(self):
        self.policy.access_until = timezone.now() + timedelta(hours=1)
        self.policy.save()
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.policy.access_until = timezone.now() - timedelta(seconds=1)
        self.policy.save()
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertIn('_auth_user_id', self.client.session)  # Membership remains active.
        draft = Entry.objects.create(author=self.teacher)
        self.assertEqual(self.client.get(f'/entries/{draft.pk}/edit/').status_code, 200)

    def test_exact_expiry_boundary_and_recent_entries(self):
        now = timezone.now()
        self.entry.submitted_at = now - timedelta(days=30)
        self.entry.save()
        self.client.force_login(self.teacher)
        with patch('journal.policies.timezone.now', return_value=now):
            self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.entry.submitted_at += timedelta(seconds=1)
        self.entry.save()
        with patch('journal.policies.timezone.now', return_value=now):
            self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_owner_can_restore_hide_and_clear_entry_deadline(self):
        until = (timezone.localtime() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
        self.assertEqual(self.owner_post(self.url('access/'), {'professional_access_until': until}).status_code, 302)
        for user in (self.teacher, self.therapist):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertEqual(self.owner_post(self.url('access/'), {'action': 'hide'}).status_code, 302)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.owner_post(self.url('access/'), {'professional_access_until': ''}).status_code, 302)
        self.entry.refresh_from_db()
        self.assertIsNone(self.entry.professional_access_until)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_entry_deadline_overrides_closed_global_deadline(self):
        self.policy.access_until = timezone.now() - timedelta(days=1)
        self.policy.save()
        self.entry.professional_access_until = timezone.now() + timedelta(days=1)
        self.entry.save()
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertEqual(self.client.post(self.url('comments/'), {'body': 'Restored discussion'}).status_code, 302)

    def test_global_settings_are_owner_only_and_validate_dates(self):
        for user in (self.teacher, self.therapist):
            self.client.force_login(user)
            self.assertEqual(self.client.get('/access/').status_code, 403)
            self.assertEqual(self.client.post('/access/', {'access_days': 90}).status_code, 403)
            self.assertEqual(self.client.post(self.url('access/'), {'action': 'hide'}).status_code, 403)
        self.assertEqual(self.owner_post('/access/', {'access_days': 90, 'expire_authors': 'on'}).status_code, 302)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertEqual(self.owner_post('/access/', {'access_days': 0, 'access_until': 'invalid'}).status_code, 200)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.access_days, 90)

    def test_extension_never_bypasses_audience_history_or_revocation(self):
        self.entry.professional_access_until = timezone.now() + timedelta(days=1)
        self.entry.audience = 'parent'
        self.entry.save()
        self.client.force_login(self.therapist)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.entry.audience = 'team'
        self.entry.save()
        self.pm.history_start = timezone.now()
        self.pm.save()
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.tm.active = False
        self.tm.save()
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_revisions_do_not_restart_original_submission_clock(self):
        original = self.entry.submitted_at
        self.entry.professional_access_until = timezone.now() + timedelta(hours=1)
        self.entry.save()
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post(self.url('publish/'), {
            'ticket': self.ticket(self.entry), 'confirmed': 'on'}).status_code, 302)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.submitted_at, original)
        self.assertEqual(Revision.objects.filter(entry=self.entry).count(), 1)
        self.entry.professional_access_until = None
        self.entry.save()
        with self.assertRaises(PermissionError):
            write_entry(self.tm, self.entry.pk, {field: getattr(self.entry, field) for field in FIELDS},
                        self.entry.version, publish=True, token=uuid.uuid4())

    def test_optional_author_exemption_and_private_drafts(self):
        self.policy.expire_authors = False
        self.policy.save()
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.client.force_login(self.therapist)
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        draft = Entry.objects.create(author=self.teacher)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f'/entries/{draft.pk}/').status_code, 404)
        self.assertEqual(Entry().audience, 'team')
