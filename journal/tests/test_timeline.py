from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from journal.models import Entry
from .test_journal import identity


class TimelineDateTests(TestCase):
    def setUp(self):
        self.user, self.member = identity('teacher', 'date-teacher')
        self.other, _ = identity('therapist', 'date-therapist')
        self.day = date(2024, 2, 29)
        self.own = Entry.objects.create(author=self.user, event_date=self.day,
            summary='Own earlier event', submitted_at=timezone.now())
        Entry.objects.create(author=self.user, event_date=self.day + timedelta(days=1),
            summary='Different event date', submitted_at=timezone.now())
        Entry.objects.create(author=self.user, event_date=self.day, summary='My dated draft')
        self.client.force_login(self.user)

    def test_filter_uses_event_date_and_filters_own_drafts(self):
        response = self.client.get('/', {'date': self.day.isoformat()})
        self.assertContains(response, 'Own earlier event')
        self.assertContains(response, 'My dated draft')
        self.assertNotContains(response, 'Different event date')
        self.assertContains(response, 'Show all dates')
        self.assertContains(self.client.get('/'), 'Different event date')

    def test_filter_preserves_audience_draft_and_history_permissions(self):
        Entry.objects.create(author=self.other, event_date=self.day, summary='Restricted note',
            submitted_at=timezone.now(), audience='parent')
        Entry.objects.create(author=self.other, event_date=self.day, summary='Another author draft')
        Entry.objects.create(author=self.other, event_date=self.day, summary='Outside allowed history',
            submitted_at=self.member.history_start - timedelta(seconds=1), audience='team')
        Entry.objects.create(author=self.other, event_date=self.day, summary='Allowed shared entry',
            submitted_at=timezone.now(), audience='team')
        for headers in ({}, {'HTTP_HX_REQUEST': 'true'}):
            response = self.client.get('/', {'date': self.day.isoformat()}, **headers)
            self.assertContains(response, 'Allowed shared entry')
            for hidden in ('Restricted note', 'Another author draft', 'Outside allowed history'):
                self.assertNotContains(response, hidden)
            self.assertIn('no-store', response['Cache-Control'])

    def test_missing_date_and_empty_day(self):
        self.assertContains(self.client.get('/', {'date': ''}), 'Own earlier event')
        response = self.client.get('/', {'date': '2020-01-01'})
        self.assertContains(response, 'No submitted entries for this date')
        self.assertNotContains(response, 'My dated draft')

    def test_invalid_dates_are_rejected(self):
        for value in ('not-a-date', '2024-02-30', '2024-13-01'):
            self.assertContains(self.client.get('/', {'date': value}), 'Enter a valid date', status_code=400)
        count = Entry.objects.count()
        self.assertEqual(self.client.post('/entries/new/', {'date': 'invalid'}).status_code, 400)
        self.assertEqual(Entry.objects.count(), count)

    def test_missed_entry_starts_with_selected_event_date(self):
        response = self.client.post('/entries/new/', {'date': self.day.isoformat()})
        self.assertEqual(response.status_code, 302)
        created = Entry.objects.get(pk=response.url.split('/')[2])
        self.assertEqual(created.event_date, self.day)
        self.assertIsNone(created.submitted_at)
        self.assertEqual(created.author, self.user)
