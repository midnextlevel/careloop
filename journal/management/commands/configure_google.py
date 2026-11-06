import getpass
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from allauth.socialaccount.models import SocialApp
from journal.models import Membership, JournalAccessSettings


class Command(BaseCommand):
    help = 'Privately repair Google credentials for a browser-configured deployment.'

    def handle(self, **options):
        if settings.SOCIALACCOUNT_PROVIDERS['google'].get('APP'):
            raise CommandError('Google credentials are environment-configured; edit .env and recreate web.')
        if not Membership.objects.filter(role='owner').exists():
            raise CommandError('Complete first deployment before repairing credentials.')
        client_id = input('Google Web application client ID: ').strip()
        if not client_id.endswith('.apps.googleusercontent.com') or len(client_id) > 191:
            raise CommandError('Provide a valid Google OAuth client ID.')
        secret = getpass.getpass('Google client secret: ').strip()
        if not secret or len(secret) > 191:
            raise CommandError('Provide a client secret of at most 191 characters.')
        with transaction.atomic():
            JournalAccessSettings.objects.select_for_update().get_or_create(pk=1)
            apps = list(SocialApp.objects.select_for_update().filter(provider='google'))
            if len(apps) != 1:
                raise CommandError('Expected one Google application. Review the database configuration.')
            app = apps[0]
            app.client_id, app.secret = client_id, secret
            app.save(update_fields=['client_id', 'secret'])
        self.stdout.write(self.style.SUCCESS('Google credentials updated. Retry Google sign-in.'))
