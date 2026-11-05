"""Optional real-browser integration test. Auth is a test-only session fixture."""
import os
import subprocess
from datetime import date, timedelta
from pathlib import Path
from unittest import skipUnless
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.utils import timezone
from journal.models import Entry
from .test_journal import identity


@skipUnless(os.getenv('BROWSER_NODE'), 'Set BROWSER_NODE and NODE_PATH to run Playwright browser verification.')
class BrowserWorkflowTests(StaticLiveServerTestCase):
    def test_dark_mode_and_owner_overview(self):
        owner, _ = identity('owner', 'browser-theme-owner')
        self.client.force_login(owner)
        env = dict(os.environ, JOURNAL_BROWSER_URL=self.live_server_url,
                   JOURNAL_BROWSER_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run([os.environ['BROWSER_NODE'], str(Path(__file__).with_name('theme.cjs'))],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_owner_closes_and_restores_professional_access(self):
        owner, _ = identity('owner', 'browser-access-owner')
        teacher, tm = identity('teacher', 'browser-access-teacher')
        therapist, pm = identity('therapist', 'browser-access-therapist')
        for member in (tm, pm):
            member.history_start = timezone.now() - timedelta(days=100)
            member.save()
        entry = Entry.objects.create(author=teacher, summary='A shared entry under owner control.',
            submitted_at=timezone.now() - timedelta(days=31), audience='team')
        env = dict(os.environ, JOURNAL_BROWSER_URL=self.live_server_url, ENTRY_ID=str(entry.pk),
                   ACCESS_UNTIL=(timezone.localtime() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'))
        for label, user in [('OWNER', owner), ('TEACHER', teacher), ('THERAPIST', therapist)]:
            client = Client()
            client.force_login(user)
            env[label + '_SESSION'] = client.cookies['sessionid'].value
        result = subprocess.run([os.environ['BROWSER_NODE'], str(Path(__file__).with_name('access.cjs'))],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_find_earlier_entry_revise_and_add_missed_entry(self):
        user, _ = identity('teacher', 'browser-dates')
        Entry.objects.create(author=user, event_date=date(2024, 2, 29),
            summary='An earlier classroom note.', submitted_at=timezone.now())
        self.client.force_login(user)
        env = dict(os.environ, JOURNAL_BROWSER_URL=self.live_server_url,
                   JOURNAL_BROWSER_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run([os.environ['BROWSER_NODE'], str(Path(__file__).with_name('dates.cjs'))],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
