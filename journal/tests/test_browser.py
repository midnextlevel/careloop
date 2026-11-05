"""Optional real-browser integration test. Auth is a test-only session fixture."""
import os
import subprocess
from pathlib import Path
from unittest import skipUnless
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from .test_journal import identity


@skipUnless(os.getenv('BROWSER_NODE'), 'Set BROWSER_NODE and NODE_PATH to run Playwright browser verification.')
class BrowserWorkflowTests(StaticLiveServerTestCase):
    def test_mobile_journal_and_public_only_cache(self):
        user, _ = identity('teacher', 'browser-teacher')
        self.client.force_login(user)
        env = dict(os.environ, JOURNAL_BROWSER_URL=self.live_server_url,
                   JOURNAL_BROWSER_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run([os.environ['BROWSER_NODE'], str(Path(__file__).with_name('browser.cjs'))],
                                env=env, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pending_submission_blocks_back_and_failure_restores_editor(self):
        user, _ = identity('teacher', 'browser-submission')
        self.client.force_login(user)
        env = dict(os.environ, JOURNAL_BROWSER_URL=self.live_server_url,
                   JOURNAL_BROWSER_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run([os.environ['BROWSER_NODE'], str(Path(__file__).with_name('submission.cjs'))],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
