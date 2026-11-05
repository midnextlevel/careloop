from django.test import TestCase
from django.utils import timezone
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
