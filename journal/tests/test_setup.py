from django.test import TestCase
from journal.models import JournalAccessSettings
from .test_journal import identity


class SetupTests(TestCase):
    def setUp(self):
        self.owner, _ = identity('owner', 'setup-owner')
        self.teacher, self.tm = identity('teacher', 'setup-teacher')
        self.therapist, _ = identity('therapist', 'setup-therapist')

    def test_owner_wizard_persists_name_and_keeps_access_policy(self):
        self.client.force_login(self.owner)
        policy = JournalAccessSettings.current()
        policy.access_days = 7
        policy.save()
        self.assertRedirects(self.client.post('/setup/', {'child_name': 'Sam'}), '/setup/?step=team')
        self.assertRedirects(self.client.post('/setup/', {'action': 'finish'}), '/')
        policy.refresh_from_db()
        self.assertEqual(policy.child_name, 'Sam')
        self.assertTrue(policy.setup_completed)
        self.assertEqual(policy.access_days, 7)
        self.assertContains(self.client.get('/'), 'Sam')
        self.client.logout()
        self.assertNotContains(self.client.get('/login/'), 'Sam')

    def test_professionals_cannot_change_setup_or_roles_through_profile(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.post('/setup/', {'child_name': 'Forged'}).status_code, 403)
        response = self.client.post('/profile/', {'display_name': 'Ms Lee', 'organization': 'Example School',
            'role': 'owner', 'active': '', 'email': 'other@example.invalid'})
        self.assertRedirects(response, '/')
        self.tm.refresh_from_db()
        self.assertEqual(self.tm.role, 'teacher')
        self.assertTrue(self.tm.active)
        self.assertEqual(self.tm.organization, 'Example School')
        self.assertEqual(self.tm.display_name, 'Ms Lee')

    def test_role_specific_profile_labels_and_required_organization(self):
        for user, label in [(self.teacher, 'School name'), (self.therapist, 'Therapy center name')]:
            self.client.force_login(user)
            self.assertContains(self.client.get('/profile/'), label)
            self.assertContains(self.client.post('/profile/', {'display_name': 'Test', 'organization': ''}),
                                'This field is required')

    def test_setup_cannot_finish_without_name(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.post('/setup/', {'action': 'finish'}), '/setup/')
        self.assertFalse(JournalAccessSettings.current().setup_completed)

    def test_first_login_routes_owner_to_setup_and_professionals_to_profile(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.get('/welcome/'), '/setup/')
        self.client.force_login(self.teacher)
        self.assertRedirects(self.client.get('/welcome/'), '/profile/')
        self.tm.display_name, self.tm.organization = 'Teacher', 'School'
        self.tm.save()
        self.assertRedirects(self.client.get('/welcome/'), '/')
