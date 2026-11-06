import hashlib
import os
from pathlib import Path
import subprocess
from unittest import skipUnless
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from allauth.socialaccount.models import SocialApp
from journal.models import Membership
from .test_journal import identity


@skipUnless(os.getenv('BROWSER_NODE'), 'Set BROWSER_NODE to run browser integration checks.')
@override_settings(DEBUG=True, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
                   SOCIALACCOUNT_PROVIDERS={'google': {}},
                   DEPLOYMENT_CODE_HASH=hashlib.sha256(b'fictional-wizard-code').hexdigest(),
                   DEPLOYMENT_CODE_EXPIRES=4102444800)
class FirstDeploymentBrowserTests(StaticLiveServerTestCase):
    def run_browser(self, **extra):
        env = dict(os.environ, JOURNAL_BROWSER_URL=self.live_server_url, **extra)
        result = subprocess.run([os.environ['BROWSER_NODE'], str(Path(__file__).with_name('deployment.cjs'))],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_database_browser_setup(self):
        self.run_browser(SETUP_TEST_CODE='fictional-wizard-code')
        self.assertEqual(Membership.objects.get().email, 'first-owner@example.invalid')
        self.assertIsNone(Membership.objects.get().user_id)

    def test_revoked_session_displays_recovery_actions(self):
        user, member = identity('teacher', 'browser-revoked')
        SocialApp.objects.create(provider='google', name='Careloop', client_id='fake', secret='fake')
        self.client.force_login(user)
        member.active = False
        member.save()
        self.run_browser(DENIAL_SESSION=self.client.cookies['sessionid'].value)
