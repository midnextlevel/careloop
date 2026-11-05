"""PostgreSQL integration checks; deliberately skipped on the SQLite fallback."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from journal.models import Entry, Revision
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
