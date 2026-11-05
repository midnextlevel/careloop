from django.test import TestCase
from django.utils import timezone
from django.core import signing
import uuid
from journal.models import Entry
from journal.services import FIELDS, write_entry
from .test_journal import identity


class PostingRoleTests(TestCase):
    def setUp(self):
        self.owner, self.om = identity('owner', 'posting-owner')
        self.teacher, self.tm = identity('teacher', 'posting-teacher')
        self.therapist, self.pm = identity('therapist', 'posting-therapist')

    def test_owner_can_create_home_entries_and_revise_their_own(self):
        self.client.force_login(self.owner)
        self.assertContains(self.client.get('/'), 'Write an entry')
        response = self.client.post('/entries/new/')
        entry = Entry.objects.get(pk=response.url.split('/')[2])
        self.assertEqual(entry.kind, 'home')
        self.assertEqual(entry.author, self.owner)
        self.assertEqual(self.client.get(f'/entries/{entry.pk}/edit/').status_code, 200)
        data = {field: getattr(entry, field) for field in FIELDS}
        data.update(summary='A home observation', version=entry.version, action='review')
        review = self.client.post(f'/entries/{entry.pk}/edit/', data)
        self.assertContains(review, 'Home')
        self.assertEqual(self.client.post(f'/entries/{entry.pk}/publish/', {
            'ticket': review.context['ticket'], 'confirmed': 'on'}).status_code, 302)
        self.assertContains(self.client.get(f'/entries/{entry.pk}/'), 'Edit your entry')

    def test_professional_defaults_share_with_all_three_members(self):
        for user, kind in ((self.teacher, 'school'), (self.therapist, 'therapy'), (self.owner, 'home')):
            self.client.force_login(user)
            response = self.client.post('/entries/new/')
            entry = Entry.objects.get(pk=response.url.split('/')[2])
            self.assertEqual(entry.kind, kind)
            self.assertEqual(entry.audience, 'team')
            data = {field: getattr(entry, field) for field in FIELDS}
            data.update(version=entry.version, action='review', summary=f'Shared {kind} observation')
            review = self.client.post(f'/entries/{entry.pk}/edit/', data)
            self.assertContains(review, 'Care team')
            self.assertEqual(self.client.post(f'/entries/{entry.pk}/publish/', {
                'confirmed': 'on', 'ticket': review.context['ticket']}).status_code, 302)
            for reader in (self.owner, self.teacher, self.therapist):
                self.client.force_login(reader)
                self.assertContains(self.client.get(f'/entries/{entry.pk}/'), data['summary'])

    def test_professionals_cannot_forge_a_home_entry(self):
        self.client.force_login(self.teacher)
        entry = Entry.objects.create(author=self.teacher)
        data = {field: getattr(entry, field) for field in FIELDS}
        response = self.client.post(f'/entries/{entry.pk}/edit/',
            {**data, 'kind': 'home', 'version': entry.version, 'action': 'save'}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 400)
        entry.refresh_from_db()
        self.assertEqual(entry.kind, 'school')

    def test_dropdown_options_are_role_specific(self):
        for user, expected in ((self.teacher, [('school', 'School')]),
                (self.therapist, [('therapy', 'Therapy center'), ('school', 'School')]),
                (self.owner, [('home', 'Home'), ('school', 'School'), ('therapy', 'Therapy center')])):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post('/entries/new/')
                form = self.client.get(response.url).context['form']
                self.assertEqual(list(form.fields['kind'].choices), expected)

    def test_forged_type_rejected_on_save_review_publish_and_write_service(self):
        for user, member, forbidden in ((self.teacher, self.tm, 'therapy'),
                                        (self.therapist, self.pm, 'home')):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                entry = Entry.objects.create(author=user)
                data = {field: getattr(entry, field) for field in FIELDS}
                data.update(kind=forbidden, summary='Forged type')
                for action in ('save', 'review'):
                    response = self.client.post(f'/entries/{entry.pk}/edit/',
                        {**data, 'version': entry.version, 'action': action}, HTTP_ACCEPT='application/json')
                    self.assertEqual(response.status_code, 400)
                serial = {key: str(value) for key, value in data.items()}
                ticket = signing.dumps({'id': str(entry.pk), 'author': user.pk,
                    'version': entry.version, 'data': serial, 'token': str(uuid.uuid4())}, salt='review')
                self.assertEqual(self.client.post(f'/entries/{entry.pk}/publish/',
                    {'ticket': ticket, 'confirmed': 'on'}).status_code, 400)
                with self.assertRaises(PermissionError):
                    write_entry(member, entry.pk, data, entry.version)
                entry.refresh_from_db()
                self.assertIsNone(entry.submitted_at)

    def test_therapist_can_choose_school(self):
        self.client.force_login(self.therapist)
        entry = Entry.objects.create(author=self.therapist, kind='therapy')
        data = {field: getattr(entry, field) for field in FIELDS}
        data.update(kind='school', version=entry.version, action='review', summary='A school visit')
        review = self.client.post(f'/entries/{entry.pk}/edit/', data)
        self.assertEqual(self.client.post(f'/entries/{entry.pk}/publish/',
            {'ticket': review.context['ticket'], 'confirmed': 'on'}).status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.kind, 'school')
