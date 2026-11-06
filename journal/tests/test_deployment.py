import hashlib
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from django.test import TestCase, Client, RequestFactory, override_settings
from django.contrib.auth.models import AnonymousUser
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialApp
from journal.models import JournalAccessSettings, Membership
from journal.tests.test_journal import identity
from journal.adapters import deny
from tools.first_run import prepare
from django.core.management import call_command, CommandError
from io import StringIO

CODE = 'fictional-private-bootstrap-code'
GOOGLE = {'google': {'SCOPE': ['openid', 'email', 'profile'],
                     'AUTH_PARAMS': {'prompt': 'select_account'}}}


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False, SOCIALACCOUNT_PROVIDERS=GOOGLE,
                   DEPLOYMENT_CODE_HASH=hashlib.sha256(CODE.encode()).hexdigest(),
                   DEPLOYMENT_CODE_EXPIRES=4102444800)
class DeploymentTests(TestCase):
    def unlock(self, client=None):
        return (client or self.client).post('/deployment/', {'code': CODE}, secure=True)

    def config(self):
        return {'owner_email': 'Parent@example.invalid', 'child_name': 'Sam',
                'client_id': 'test-client.apps.googleusercontent.com',
                'client_secret': 'fictional-secret', 'confirmed': 'on'}

    def test_fresh_install_unlock_configure_and_lock(self):
        self.assertRedirects(self.client.get('/login/', secure=True), '/deployment/', fetch_redirect_response=False)
        self.assertEqual(self.unlock().status_code, 302)
        page = self.client.get('/deployment/', secure=True)
        self.assertContains(page, 'https://testserver/accounts/google/login/callback/')
        result = self.client.post('/deployment/', self.config(), secure=True)
        self.assertContains(result, 'deployment wizard is locked')
        self.assertNotContains(result, 'fictional-secret')
        owner = Membership.objects.get()
        self.assertEqual((owner.email, owner.role, owner.user_id), ('parent@example.invalid', 'owner', None))
        self.assertEqual(JournalAccessSettings.current().child_name, 'Sam')
        self.assertTrue(JournalAccessSettings.current().deployment_completed)
        self.assertEqual(self.client.get('/deployment/', secure=True).status_code, 404)
        self.assertEqual(self.client.post('/deployment/', self.config(), secure=True).status_code, 404)
        app = get_adapter().get_app(RequestFactory().get('/'), 'google')
        self.assertEqual(app.client_id, self.config()['client_id'])
        self.assertContains(self.client.get('/login/', secure=True), 'Continue with Google')
        response = self.client.post('/accounts/google/login/', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn('prompt=select_account', response.url)

    def test_code_tls_expiry_and_csrf_are_required(self):
        self.assertContains(self.client.get('/deployment/'), 'Open setup over HTTPS', status_code=403)
        response = self.client.post('/deployment/', {'code': 'wrong-secret'}, secure=True)
        self.assertContains(response, 'setup code is incorrect')
        self.assertNotContains(response, 'wrong-secret')
        self.client.post('/deployment/', self.config(), secure=True)
        self.assertFalse(Membership.objects.exists())
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.unlock(csrf_client).status_code, 403)
        with override_settings(DEPLOYMENT_CODE_EXPIRES=1):
            self.assertEqual(self.client.get('/deployment/', secure=True).status_code, 404)
        self.unlock()
        session = self.client.session
        session['deployment_until'] = time.time() - 1
        session.save()
        self.assertContains(self.client.get('/deployment/', secure=True), 'Unlock setup')

    def test_existing_installation_is_never_claimable(self):
        _, member = identity('owner', 'existing-owner')
        member.active = False
        member.save()
        self.assertEqual(self.unlock().status_code, 404)
        self.assertEqual(Membership.objects.count(), 1)

    def test_second_authorized_session_cannot_replace_owner(self):
        second = Client()
        self.unlock()
        self.unlock(second)
        self.client.post('/deployment/', self.config(), secure=True)
        self.assertEqual(second.post('/deployment/', {**self.config(), 'owner_email': 'other@example.invalid'}, secure=True).status_code, 404)
        self.assertEqual(Membership.objects.get().email, 'parent@example.invalid')

    def test_invalid_fields_do_not_create_partial_configuration(self):
        self.unlock()
        result = self.client.post('/deployment/', {**self.config(), 'client_id': 'not-google'}, secure=True)
        self.assertContains(result, 'Web application OAuth client')
        self.assertNotContains(result, 'fictional-secret')
        self.assertFalse(Membership.objects.exists())
        self.assertFalse(SocialApp.objects.exists())


class FirstRunPreparationTests(TestCase):
    def test_generated_config_is_private_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            origin, code = prepare('https://careloop.example.com/', folder)
            content = (Path(folder) / '.env').read_text()
            self.assertEqual(origin, 'https://careloop.example.com')
            self.assertNotIn(code, content)
            self.assertIn(hashlib.sha256(code.encode()).hexdigest(), content)
            self.assertIn('DEBUG=false', content)
            self.assertIn('DEV_LOGIN_ENABLED=false', content)
            self.assertGreater(len(code), 40)
            with self.assertRaises(FileExistsError):
                prepare(origin, folder)
            self.assertEqual((Path(folder) / '.env').read_text(), content)
            for invalid in ['http://example.com', 'https://user:password@example.com', 'https://example.com/path', 'https://example.com?query=1']:
                with self.assertRaises(ValueError):
                    prepare(invalid, folder)


class BrandedDenialTests(TestCase):
    @override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE)
    def test_console_repair_updates_only_google_credentials(self):
        _, owner = identity('owner', 'repair-owner')
        SocialApp.objects.create(provider='google', name='Careloop', client_id='old', secret='old')
        with patch('builtins.input', return_value='fixed.apps.googleusercontent.com'), patch('getpass.getpass', return_value='new-private-secret'):
            output = StringIO()
            call_command('configure_google', stdout=output)
        self.assertNotIn('new-private-secret', output.getvalue())
        self.assertEqual(SocialApp.objects.get().secret, 'new-private-secret')
        self.assertEqual(Membership.objects.get().pk, owner.pk)

    def test_console_repair_refuses_environment_credentials(self):
        with override_settings(SOCIALACCOUNT_PROVIDERS={'google': {'APP': {'client_id': 'existing', 'secret': 'existing'}}}):
            with self.assertRaises(CommandError):
                call_command('configure_google', stdout=StringIO())

    def test_rejected_google_identity_gets_branded_retry_without_private_data(self):
        SocialApp.objects.create(provider='google', name='Careloop', client_id='fake', secret='fake')
        request = RequestFactory().get('/accounts/google/login/callback/')
        request.user = AnonymousUser()
        with self.assertRaises(ImmediateHttpResponse) as caught:
            deny(request)
        response = caught.exception.response
        self.assertEqual(response.status_code, 403)
        html = response.content.decode()
        self.assertIn('careloop-logo.webp', html)
        self.assertIn('Try another Google account', html)
        self.assertIn('Back to Careloop sign-in', html)
        self.assertFalse(Membership.objects.exists())

    def test_revoked_session_uses_the_same_branded_page(self):
        user, member = identity('teacher', 'revoked-branding')
        self.client.force_login(user)
        member.active = False
        member.save()
        response = self.client.get('/')
        self.assertContains(response, 'This account can’t access Careloop', status_code=403)
        self.assertContains(response, 'careloop-logo.webp', status_code=403)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertIn('no-store', response['Cache-Control'])
