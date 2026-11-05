from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.db import transaction
from django.http import HttpResponseForbidden
from .models import Membership


def deny():
    raise ImmediateHttpResponse(HttpResponseForbidden('This verified Google identity is not approved. Contact the parent.'))


class ClosedAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class ApprovedGoogleAdapter(DefaultSocialAccountAdapter):
    def approved(self, sociallogin):
        account = sociallogin.account
        if account.provider != 'google' or not account.uid:
            deny()
        emails = {e.email.strip().lower() for e in sociallogin.email_addresses if e.verified}
        primary = str(account.extra_data.get('email', '')).strip().lower()
        if not primary or primary not in emails:
            deny()
        member = Membership.objects.filter(email=primary, active=True).first()
        if not member or member.is_development or (member.google_subject and member.google_subject != account.uid):
            deny()
        if member.user_id and (not sociallogin.is_existing or sociallogin.user.pk != member.user_id):
            deny()
        if sociallogin.is_existing and member.user_id != sociallogin.user.pk:
            deny()
        return member

    def pre_social_login(self, request, sociallogin):
        # allauth has validated OAuth state and fetched Google's authenticated identity.
        if request.user.is_authenticated:
            deny()  # No account-linking flow in this single-identity app.
        self.approved(sociallogin)

    def is_open_for_signup(self, request, sociallogin):
        self.approved(sociallogin)
        return True

    @transaction.atomic
    def save_user(self, request, sociallogin, form=None):
        member = Membership.objects.select_for_update().get(pk=self.approved(sociallogin).pk)
        if not member.active or member.user_id or (member.google_subject and member.google_subject != sociallogin.account.uid):
            deny()
        user = super().save_user(request, sociallogin, form)
        user.set_unusable_password()
        user.save(update_fields=['password'])
        member.user = user
        member.google_subject = sociallogin.account.uid
        member.save(update_fields=['user', 'google_subject'])
        return user
