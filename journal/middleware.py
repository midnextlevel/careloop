from django.contrib.auth import logout
from django.shortcuts import render
from .policies import development_access_allowed, membership_for


class MembershipMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = membership_for(request.user)
        if request.membership and request.membership.is_development and not development_access_allowed(request):
            request.membership = None
        if request.user.is_authenticated and request.membership is None:
            logout(request)
            response = render(request, 'journal/access_denied.html', status=403)
        else:
            response = self.get_response(request)
        # All dynamic responses, including OAuth/errors/redirects, are non-cacheable.
        response['Cache-Control'] = 'no-store, private, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Vary'] = ', '.join(filter(None, [response.get('Vary'), 'Cookie']))
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
