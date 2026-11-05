import getpass
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from journal.models import Membership


class Command(BaseCommand):
    help = 'Create a named fictional owner for loopback-only development login.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--name', default='Test Parent')
        parser.add_argument('--password-stdin', action='store_true')

    @transaction.atomic
    def handle(self, username, name, password_stdin, **options):
        if not (settings.DEBUG and settings.DEV_LOGIN_ENABLED):
            raise CommandError('Requires DEBUG=true and DEV_LOGIN_ENABLED=true.')
        if not username.isascii() or not username.replace('-', '').replace('_', '').isalnum() or len(username) > 100:
            raise CommandError('Use 1–100 ASCII letters, digits, hyphens, or underscores.')
        if get_user_model().objects.filter(username=username).exists():
            raise CommandError('Username already exists; existing accounts will not be modified.')
        if password_stdin:
            import sys
            password = sys.stdin.readline().rstrip('\r\n')
        else:
            password = getpass.getpass('Development password: ')
            if password != getpass.getpass('Confirm password: '):
                raise CommandError('Passwords do not match.')
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages))
        if len(password) < 12:
            raise CommandError('Use at least 12 characters.')
        email = f'{username.lower()}@example.invalid'
        if Membership.objects.filter(email=email).exists():
            raise CommandError('A membership already uses this development email.')
        user = get_user_model().objects.create_user(username=username, email=email, password=password, first_name=name)
        Membership.objects.create(email=email, user=user, role='owner', is_development=True)
        self.stdout.write(self.style.SUCCESS(f'Created development owner {username}. Login is loopback-only.'))
