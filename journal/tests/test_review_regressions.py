import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from unittest import skipUnless
from django.test import TestCase, Client
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from journal.forms import JournalAccessForm
from journal.models import JournalAccessSettings, Entry
from journal.tests.test_journal import identity
from django.utils import timezone
from datetime import timedelta


class AccessSettingsRegressionTests(TestCase):
    def test_access_save_preserves_concurrent_setup(self):
        owner, _ = identity('owner', 'review-owner')
        self.client.force_login(owner)
        setup_client = Client()
        setup_client.force_login(owner)
        JournalAccessSettings.current()
        original = JournalAccessForm.is_valid
        def interleave(form):
            result = original(form)
            self.assertEqual(setup_client.post('/setup/', {'child_name': 'Sam'}).status_code, 302)
            self.assertEqual(setup_client.post('/setup/', {'action': 'finish'}).status_code, 302)
            current = JournalAccessSettings.current()
            self.assertEqual((current.child_name, current.setup_completed), ('Sam', True))
            return result
        with patch.object(JournalAccessForm, 'is_valid', interleave):
            response = self.client.post('/access/', {'access_days': 14, 'expire_authors': 'on'})
        self.assertEqual(response.status_code, 302)
        current = JournalAccessSettings.current()
        self.assertEqual((current.child_name, current.setup_completed), ('Sam', True))
        self.assertEqual(current.access_days, 14)


@skipUnless(os.getenv('BROWSER_NODE'), 'Browser runtime required')
class SubmissionRegressionTests(StaticLiveServerTestCase):
    def test_successful_expired_submission_is_confirmed(self):
        user, _ = identity('teacher', 'review-expiry-teacher')
        policy = JournalAccessSettings.current()
        policy.access_until = timezone.now() - timedelta(hours=1)
        policy.save()
        self.client.force_login(user)
        env = dict(os.environ, JOURNAL_BROWSER_URL=self.live_server_url,
                   JOURNAL_BROWSER_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run([os.environ['BROWSER_NODE'], str(Path(__file__).with_name('review_expired.cjs'))],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(Entry.objects.filter(summary='Successfully saved but UI reports failure', submitted_at__isnull=False).exists())

    def test_review_preserves_inflight_text(self):
        user, _ = identity('teacher', 'review-teacher')
        self.client.force_login(user)
        env = dict(os.environ, JOURNAL_BROWSER_URL=self.live_server_url,
                   JOURNAL_BROWSER_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run([os.environ['BROWSER_NODE'], str(Path(__file__).with_name('review_pending.cjs'))],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(Entry.objects.filter(summary='Latest typed text that should be preserved', submitted_at__isnull=False).exists())
        self.assertFalse(Entry.objects.filter(summary='Snapshot sent before the latest edits').exists())
