"""One-time bootstrap, gated by a VM-generated code and disabled after accounts exist."""
import hashlib
import hmac
import time
from ipaddress import ip_address
from django import forms
from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from allauth.socialaccount.models import SocialApp
from .models import JournalAccessSettings, Membership


def deployment_open():
    return bool(settings.DEPLOYMENT_CODE_HASH and time.time() < settings.DEPLOYMENT_CODE_EXPIRES
                and not settings.SOCIALACCOUNT_PROVIDERS['google'].get('APP')
                and not JournalAccessSettings.current().deployment_completed
                and not Membership.objects.exists()
                and not SocialApp.objects.filter(provider='google').exists())


class UnlockForm(forms.Form):
    code = forms.CharField(label='Private setup code', max_length=200,
        widget=forms.PasswordInput(attrs={'autocomplete': 'off'}))


class DeploymentForm(forms.Form):
    owner_email = forms.EmailField(label='Owner’s exact Google email', max_length=254)
    child_name = forms.CharField(label='Child’s display name', max_length=80)
    client_id = forms.CharField(label='Google OAuth client ID', max_length=191)
    client_secret = forms.CharField(label='Google OAuth client secret', max_length=191,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    confirmed = forms.BooleanField(label='I have added the exact callback URL shown above to my Google Web application client.')

    def clean_client_id(self):
        value = self.cleaned_data['client_id']
        if not value.endswith('.apps.googleusercontent.com'):
            raise forms.ValidationError('Use the client ID from a Google Web application OAuth client.')
        return value


@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def deployment(request):
    if not deployment_open():
        return HttpResponse(status=404)
    try:
        local_debug = settings.DEBUG and ip_address(request.META.get('REMOTE_ADDR', '')).is_loopback
    except ValueError:
        local_debug = False
    if not (request.is_secure() or local_debug):
        return render(request, 'journal/deployment.html', {'https_required': True}, status=403)
    unlocked = (request.session.get('deployment_hash') == settings.DEPLOYMENT_CODE_HASH and
                request.session.get('deployment_until', 0) > time.time())
    if not unlocked:
        form = UnlockForm(request.POST if request.method == 'POST' else None)
        if request.method == 'POST' and form.is_valid():
            candidate = hashlib.sha256(form.cleaned_data['code'].encode()).hexdigest()
            if hmac.compare_digest(candidate, settings.DEPLOYMENT_CODE_HASH):
                request.session.cycle_key()
                request.session['deployment_hash'] = settings.DEPLOYMENT_CODE_HASH
                request.session['deployment_until'] = time.time() + 1800
                return redirect('deployment')
            form.add_error('code', 'The setup code is incorrect or has expired. Check the code on your VM.')
        return render(request, 'journal/deployment.html', {'form': form})
    form = DeploymentForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            journal = JournalAccessSettings.objects.select_for_update().get(pk=1)
            if not deployment_open():
                return HttpResponse(status=404)
            # A separate lock owner is established before enabling Google sign-in.
            Membership.objects.create(email=form.cleaned_data['owner_email'], role='owner')
            SocialApp.objects.create(provider='google', name='Careloop',
                client_id=form.cleaned_data['client_id'], secret=form.cleaned_data['client_secret'])
            journal.child_name = form.cleaned_data['child_name']
            journal.deployment_completed = True
            journal.save(update_fields=['child_name', 'deployment_completed'])
        request.session.pop('deployment_hash', None)
        request.session.pop('deployment_until', None)
        return render(request, 'journal/deployment_complete.html')
    origin = request.build_absolute_uri('/').rstrip('/')
    return render(request, 'journal/deployment.html', {'form': form, 'unlocked': True,
        'origin': origin, 'callback': origin + '/accounts/google/login/callback/'})
