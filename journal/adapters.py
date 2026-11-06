from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.db import transaction
from django.shortcuts import render
from .models import Membership
from allauth.socialaccount.models import SocialApp


def deny(request):
    raise ImmediateHttpResponse(render(request, 'journal/access_denied.html', status=403))


class ClosedAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class ApprovedGoogleAdapter(DefaultSocialAccountAdapter):
    def get_app(self, request, provider, client_id=None):
        try:
            return super().get_app(request, provider, client_id)
        except SocialApp.DoesNotExist:
            raise ImmediateHttpResponse(render(request, 'socialaccount/authentication_error.html', status=503))

    def approved(self, sociallogin):
        account = sociallogin.account
        if account.provider != 'google' or not account.uid:
            deny(self.request)
        emails = {e.email.strip().lower() for e in sociallogin.email_addresses if e.verified}
        primary = str(account.extra_data.get('email', '')).strip().lower()
        if not primary or primary not in emails:
            deny(self.request)
        member = Membership.objects.filter(email=primary, active=True).first()
        if not member or member.is_development or (member.google_subject and member.google_subject != account.uid):
            deny(self.request)
        if member.user_id and (not sociallogin.is_existing or sociallogin.user.pk != member.user_id):
            deny(self.request)
        if sociallogin.is_existing and member.user_id != sociallogin.user.pk:
            deny(self.request)
        return member

    def pre_social_login(self, request, sociallogin):
        # allauth has validated OAuth state and fetched Google's authenticated identity.
        if request.user.is_authenticated:
            deny(request)  # No account-linking flow in this single-identity app.
        self.approved(sociallogin)

    def is_open_for_signup(self, request, sociallogin):
        self.approved(sociallogin)
        return True

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        member = Membership.objects.select_for_update().get(pk=self.approved(sociallogin).pk)
        if not member.active or member.user_id or (member.google_subject and member.google_subject != sociallogin.account.uid):
            deny(request)
        user = super().save_user(request, sociallogin, form)
        user.set_unusable_password()
        user.save(update_fields=['password'])
        member.user = user
        member.google_subject = sociallogin.account.uid
        member.save(update_fields=['user', 'google_subject'])
        return user
