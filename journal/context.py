from django.conf import settings
from .policies import can_post, development_access_allowed

def site(request):
    return {'child_name': settings.CHILD_NAME, 'member': getattr(request, 'membership', None),
            'can_post': can_post(getattr(request, 'membership', None)),
            'development_login': development_access_allowed(request),
            'google_configured': bool(settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id'] and
                                      settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['secret'])}
