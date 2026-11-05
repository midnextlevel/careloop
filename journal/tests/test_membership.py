from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from journal.forms import MemberForm
from journal.models import Entry
from .test_journal import identity


class MembershipHistoryTests(TestCase):
    def setUp(self):
        self.owner, _ = identity('owner', 'history-owner')
        self.teacher, self.member = identity('teacher', 'history-teacher')
        therapist, _ = identity('therapist', 'history-therapist')
        self.original_start = timezone.now().replace(second=45, microsecond=123456)
        self.member.history_start = self.original_start
        self.member.save()
        self.entry = Entry.objects.create(author=therapist, summary='Earlier care-team entry',
            audience='team', submitted_at=self.original_start - timedelta(seconds=15))

    def update(self, **changes):
        # Submit exactly the value rendered by the minute-resolution browser widget.
        displayed = MemberForm(instance=self.member)['history_start'].as_widget()
        value = timezone.localtime(self.original_start).strftime('%Y-%m-%dT%H:%M')
        self.assertIn(value, displayed)
        self.client.force_login(self.owner)
        return self.client.post(f'/team/{self.member.pk}/', {
            'email': self.member.email, 'role': 'therapist', 'active': 'on',
            'history_start': value, **changes})

    def test_role_change_preserves_exact_history_and_denial(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(f'/entries/{self.entry.pk}/').status_code, 404)
        self.assertEqual(self.update().status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, 'therapist')
        self.assertEqual(self.member.history_start, self.original_start)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(f'/entries/{self.entry.pk}/').status_code, 404)

    def test_explicit_history_change_still_grants_older_access(self):
        earlier = timezone.localtime(self.original_start) - timedelta(minutes=1)
        self.assertEqual(self.update(history_start=earlier.strftime('%Y-%m-%dT%H:%M')).status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.history_start, earlier.replace(second=0, microsecond=0))
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(f'/entries/{self.entry.pk}/').status_code, 200)
