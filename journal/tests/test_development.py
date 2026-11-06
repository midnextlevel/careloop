from io import StringIO
from unittest.mock import patch
from ipaddress import ip_network
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from journal.models import Membership
from .test_journal import identity


@override_settings(DEBUG=True, DEV_LOGIN_ENABLED=True, DEV_LOGIN_NETWORKS=())
class DevelopmentLoginTests(TestCase):
    def setUp(self):
        with patch('sys.stdin', StringIO('Fictional-Strong-Password-123!\n')):
            call_command('create_dev_owner', 'test-parent', password_stdin=True, stdout=StringIO())

    def test_named_login_and_existing_session_disable(self):
        self.assertEqual(self.client.post('/development/login/', {'username': 'test-parent', 'password': 'Fictional-Strong-Password-123!'}).status_code, 302)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertTrue(Membership.objects.get(user__username='test-parent').is_development)
        with override_settings(DEV_LOGIN_ENABLED=False):
            self.assertEqual(self.client.get('/').status_code, 403)
            self.assertEqual(self.client.get('/development/login/').status_code, 404)

    def test_professional_test_accounts_have_assigned_roles_without_owner_controls(self):
        for role in ('teacher', 'therapist'):
            with self.subTest(role=role), patch('sys.stdin', StringIO('Fictional-Strong-Password-123!\n')):
                call_command('create_dev_user', role, role=role, password_stdin=True, stdout=StringIO())
                member = Membership.objects.get(user__username=role)
                self.assertEqual(member.role, role)
                self.assertTrue(member.is_development)
                self.client.logout()
                self.assertEqual(self.client.post('/development/login/', {
                    'username': role, 'password': 'Fictional-Strong-Password-123!'}).status_code, 302)
                self.assertEqual(self.client.get('/team/').status_code, 403)

    def test_google_users_and_nonlocal_clients_denied(self):
        user, _ = identity('owner', 'real-google')
        user.set_password('Fictional-Strong-Password-123!')
        user.save()
        result = self.client.post('/development/login/', {'username': user.username, 'password': 'Fictional-Strong-Password-123!'})
        self.assertContains(result, 'incorrect')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.get('/development/login/', REMOTE_ADDR='192.0.2.1').status_code, 404)
        self.client.post('/development/login/', {'username': 'test-parent', 'password': 'Fictional-Strong-Password-123!'})
        self.assertEqual(self.client.get('/', REMOTE_ADDR='192.0.2.1').status_code, 403)

    def test_production_and_revoked_accounts_denied(self):
        member = Membership.objects.get(user__username='test-parent')
        member.active = False
        member.save()
        result = self.client.post('/development/login/', {'username': 'test-parent', 'password': 'Fictional-Strong-Password-123!'})
        self.assertContains(result, 'incorrect')
        with override_settings(DEBUG=False):
            self.assertEqual(self.client.get('/development/login/').status_code, 404)
            with self.assertRaises(CommandError):
                call_command('create_dev_owner', 'another', stdout=StringIO())

    @override_settings(DEV_LOGIN_NETWORKS=(ip_network('192.168.99.0/24'),))
    def test_explicit_lan_login_and_session_scope(self):
        address = {'REMOTE_ADDR': '192.168.99.42'}
        self.assertContains(self.client.get('/login/', **address), 'Careloop test account sign-in')
        self.assertEqual(self.client.post('/development/login/', {
            'username': 'test-parent', 'password': 'Fictional-Strong-Password-123!'}, **address).status_code, 302)
        self.assertEqual(self.client.get('/', **address).status_code, 200)
        self.assertEqual(self.client.get('/', REMOTE_ADDR='192.168.98.42').status_code, 403)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_forwarded_address_cannot_enable_login(self):
        self.assertEqual(self.client.get('/development/login/', REMOTE_ADDR='192.0.2.1',
            HTTP_X_FORWARDED_FOR='127.0.0.1').status_code, 404)

    @override_settings(DEBUG=False, DEV_LOGIN_NETWORKS=(ip_network('192.168.99.0/24'),))
    def test_lan_configuration_never_enables_production_login(self):
        self.assertEqual(self.client.get('/development/login/', REMOTE_ADDR='192.168.99.42').status_code, 404)
