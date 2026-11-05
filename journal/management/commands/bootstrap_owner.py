from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from journal.models import Membership

class Command(BaseCommand):
    help = 'Approve the first owner email. Does not create credentials or bypass Google.'
    def add_arguments(self, parser):
        parser.add_argument('email')
    def handle(self, email, **options):
        email = email.strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError('Provide a valid exact email.')
        if Membership.objects.filter(role='owner', active=True).exists():
            raise CommandError('An active owner already exists. Use the owner team screen.')
        member, _ = Membership.objects.get_or_create(email=email, defaults={'role': 'owner'})
        member.role, member.active = 'owner', True
        member.save()
        self.stdout.write(self.style.SUCCESS(f'Approved owner {email}. Sign in through Google.'))
