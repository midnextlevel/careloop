"""PostgreSQL integration checks; deliberately skipped on the SQLite fallback."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.db import close_old_connections
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from journal.forms import MemberForm
from journal.models import Entry, Membership, Revision
from journal.services import Conflict, FIELDS, write_entry
from .test_journal import identity


@skipUnlessDBFeature('has_select_for_update')
class ConcurrentWriteTests(TransactionTestCase):
    def setUp(self):
        self.user, self.member = identity('teacher', 'concurrent')
        self.entry = Entry.objects.create(author=self.user, summary='Original')

    def race(self, *, same_token):
        barrier = Barrier(2)
        operation = uuid.uuid4()
        def writer(index):
            close_old_connections()
            try:
                data = {field: getattr(self.entry, field) for field in FIELDS}
                data['summary'] = f'Writer {index}'
                barrier.wait(timeout=10)
                try:
                    write_entry(self.member, self.entry.pk, data, 1, publish=True,
                                token=operation if same_token else uuid.uuid4())
                    return 'ok'
                except Conflict:
                    return 'conflict'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(writer, [1, 2]))

    def test_simultaneous_same_operation_is_idempotent(self):
        self.assertEqual(self.race(same_token=True), ['ok', 'ok'])
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.version, 2)
        self.assertEqual(Entry.objects.count(), 1)
        self.assertEqual(Revision.objects.count(), 0)

    def test_simultaneous_distinct_edits_detect_conflict(self):
        self.assertCountEqual(self.race(same_token=False), ['ok', 'conflict'])
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.version, 2)


@skipUnlessDBFeature('has_select_for_update')
class ConcurrentOwnerTests(TransactionTestCase):
    def test_cross_demotion_and_revocation_leave_an_authorized_owner(self):
        for active in (True, False):
            with self.subTest(active=active):
                users_and_members = [identity('owner', f'owner-{active}-{i}') for i in range(2)]
                clients = [Client(), Client()]
                for client, (user, _) in zip(clients, users_and_members):
                    client.force_login(user)
                barrier = Barrier(2)
                original = MemberForm.is_valid

                def validated(form):
                    result = original(form)
                    barrier.wait(timeout=10)  # Both requests have passed initial authorization.
                    return result

                def update_other(index):
                    close_old_connections()
                    try:
                        target = users_and_members[1 - index][1]
                        data = {'email': target.email, 'role': 'teacher' if active else 'owner',
                            'history_start': timezone.localtime(target.history_start).strftime('%Y-%m-%dT%H:%M')}
                        if active:
                            data['active'] = 'on'
                        return clients[index].post(f'/team/{target.pk}/', data).status_code
                    finally:
                        close_old_connections()

                with patch.object(MemberForm, 'is_valid', validated), ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(update_other, (0, 1)))
                self.assertCountEqual(results, [302, 403])
                ids = [member.pk for _, member in users_and_members]
                self.assertEqual(Membership.objects.filter(pk__in=ids, active=True, role='owner').count(), 1)
