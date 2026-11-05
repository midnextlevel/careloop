from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from journal.models import Entry, Membership

class Command(BaseCommand):
    help = 'Create fictional journal records with disabled identities; never grants login access.'
    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError('Fictional seed data is restricted to DEBUG=True development.')
        for role, name in [('teacher', 'Ms. Rivera'), ('therapist', 'Dr. Santos'), ('owner', 'Sam')]:
            email = f'fictional-{role}@example.invalid'
            user, _ = get_user_model().objects.get_or_create(username=f'fictional-{role}', defaults={'email': email, 'first_name': name, 'is_active': False})
            user.set_unusable_password()
            user.save()
            Membership.objects.get_or_create(email=email, defaults={'role': role, 'user': user, 'active': False})
            Entry.objects.get_or_create(author=user, summary=f'Alex enjoyed a calm {dict(Entry.Kind.choices)[{"teacher":"school","therapist":"therapy","owner":"home"}[role]].lower()} day.', defaults={
                'event_date': timezone.localdate(), 'kind': {'teacher': 'school', 'therapist': 'therapy', 'owner': 'home'}[role],
                'observations': 'Joined the activity after a short pause.', 'what_helped': 'A visual schedule and quiet encouragement.',
                'audience': 'team', 'submitted_at': timezone.now() - timedelta(hours=1), 'shared_at': timezone.now() - timedelta(hours=1)})
        self.stdout.write('Fictional records created. All sample identities remain disabled.')
