from django.conf import settings

def site(request):
    return {'child_name': settings.CHILD_NAME, 'member': getattr(request, 'membership', None),
            'development_login': settings.DEBUG and settings.DEV_LOGIN_ENABLED and request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1'),
            'google_configured': bool(settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id'] and
                                      settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['secret'])}
