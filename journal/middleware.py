from django.contrib.auth import logout
from django.http import HttpResponse
from .policies import membership_for


class MembershipMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = membership_for(request.user)
        if request.membership and request.membership.is_development and request.META.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
            request.membership = None
        if request.user.is_authenticated and request.membership is None:
            logout(request)
            response = HttpResponse('Access revoked or not approved. Contact the parent.', status=403)
        else:
            response = self.get_response(request)
        # All dynamic responses, including OAuth/errors/redirects, are non-cacheable.
        response['Cache-Control'] = 'no-store, private, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Vary'] = ', '.join(filter(None, [response.get('Vary'), 'Cookie']))
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
