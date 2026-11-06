from django.conf import settings
from .policies import can_post, development_access_allowed
from .models import JournalAccessSettings
from allauth.socialaccount.models import SocialApp

def site(request):
    member = getattr(request, 'membership', None)
    journal = JournalAccessSettings.current() if member else None
    return {'child_name': (journal.child_name or settings.CHILD_NAME) if journal else 'your child',
            'setup_needed': bool(member and member.role == 'owner' and not journal.setup_completed),
            'member': member,
            'can_post': can_post(getattr(request, 'membership', None)),
            'development_login': development_access_allowed(request),
            'google_configured': bool(settings.SOCIALACCOUNT_PROVIDERS['google'].get('APP') or
                                      SocialApp.objects.filter(provider='google').exclude(client_id='').exclude(secret='').exists())}
