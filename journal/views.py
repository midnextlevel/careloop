import uuid
from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django import forms
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from .forms import EntryForm, MemberForm
from .models import Entry, Membership, Comment
from .policies import can_edit, is_owner, visible_entries
from .services import FIELDS, Conflict, write_entry


def owner_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_owner(request.membership):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


@require_GET
def login_page(request):
    if request.user.is_authenticated:
        return redirect('timeline')
    return render(request, 'journal/login.html')


def development_login(request):
    if not (settings.DEBUG and settings.DEV_LOGIN_ENABLED and request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1')):
        return HttpResponse(status=404)
    if request.method not in ('GET', 'POST'):
        return HttpResponse(status=405)
    class DevelopmentForm(forms.Form):
        username = forms.CharField(max_length=150)
        password = forms.CharField(widget=forms.PasswordInput)
    form = DevelopmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        # Use the password backend explicitly; never admit a real Google identity here.
        user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
        member = Membership.objects.filter(user=user, active=True, is_development=True).first() if user else None
        if user and member:
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('timeline')
        form.add_error(None, 'The development username or password is incorrect, or access is revoked.')
    return render(request, 'journal/development_login.html', {'form': form})


@login_required
@require_GET
def timeline(request):
    entries = visible_entries(request.membership).filter(submitted_at__isnull=False).select_related('author')
    drafts = Entry.objects.filter(author=request.user, submitted_at__isnull=True)
    return render(request, 'journal/timeline.html', {'entries': entries, 'drafts': drafts})


@login_required
@require_POST
def new_entry(request):
    entry = Entry.objects.create(author=request.user)
    return redirect('edit', pk=entry.pk)


@login_required
@require_GET
def detail(request, pk):
    entry = get_object_or_404(visible_entries(request.membership).select_related('author'), pk=pk)
    # Old versions may have had a narrower audience. Only author and parent see them.
    revisions = entry.revisions.all() if can_edit(request.membership, entry) or is_owner(request.membership) else []
    return render(request, 'journal/detail.html', {'entry': entry, 'revisions': revisions,
        'can_edit': can_edit(request.membership, entry),
        'comments': entry.comments.select_related('author') if entry.submitted_at else []})


@login_required
def edit(request, pk):
    entry = get_object_or_404(Entry, pk=pk, author=request.user)
    if request.method not in ('GET', 'POST'):
        return HttpResponse(status=405)
    form = EntryForm(request.POST or None, instance=entry, initial={'version': entry.version})
    error = None
    if request.method == 'POST' and form.is_valid():
        action = request.POST.get('action')
        data = {field: form.cleaned_data[field] for field in FIELDS}
        if action == 'review':
            if not data['summary'].strip():
                form.add_error('summary', 'Add a daily summary before submitting.')
            elif form.cleaned_data['version'] != Entry.objects.get(pk=pk).version:
                error = 'A newer version exists. Your text is below; open the latest entry in another tab.'
            else:
                serial = {k: v.isoformat() if k == 'event_date' else v for k, v in data.items()}
                ticket = signing.dumps({'id': str(pk), 'author': request.user.pk,
                    'version': form.cleaned_data['version'], 'data': serial, 'token': str(uuid.uuid4())}, salt='review')
                return render(request, 'journal/review.html', {'entry': entry, 'data': data, 'ticket': ticket,
                    'audience_label': dict(Entry.Audience.choices)[data['audience']]})
        elif action == 'save':
            try:
                saved = write_entry(request.membership, pk, data, form.cleaned_data['version'])
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse({'version': saved.version, 'saved_at': timezone.localtime(saved.updated_at).strftime('%H:%M:%S')})
                messages.success(request, 'Draft saved on the server.')
                return redirect('edit', pk=pk)
            except Conflict as exc:
                error = str(exc)
        else:
            error = 'Choose Save draft or Review audience.'
    if request.method == 'POST' and request.headers.get('Accept') == 'application/json':
        return JsonResponse({'error': error or 'Please check the form fields.', 'fields': form.errors}, status=409 if error else 400)
    return render(request, 'journal/edit.html', {'entry': entry, 'form': form, 'error': error}, status=409 if error else 200)


@login_required
@require_POST
def publish(request, pk):
    get_object_or_404(Entry, pk=pk, author=request.user)
    if request.POST.get('confirmed') != 'on':
        return HttpResponse('Confirm the reviewed audience before submitting.', status=400)
    ticket = request.POST.get('ticket', '')
    try:
        payload = signing.loads(ticket, salt='review', max_age=3600)
        if payload['id'] != str(pk) or payload['author'] != request.user.pk:
            raise signing.BadSignature
        form = EntryForm({**payload['data'], 'version': payload['version']})
        if not form.is_valid() or not form.cleaned_data['summary'].strip():
            raise signing.BadSignature
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return HttpResponse('The review expired or is invalid. Return to the editor and review again.', status=400)
    try:
        entry = write_entry(request.membership, pk, form.cleaned_data, payload['version'], publish=True, token=uuid.UUID(payload['token']))
    except Conflict as exc:
        return render(request, 'journal/edit.html', {'entry': Entry.objects.get(pk=pk), 'form': form, 'error': str(exc)}, status=409)
    messages.success(request, 'Entry submitted.')
    return redirect('detail', pk=entry.pk)


@login_required
@require_POST
def comment(request, pk):
    entry = get_object_or_404(visible_entries(request.membership), pk=pk, submitted_at__isnull=False)
    body = request.POST.get('body', '').strip()
    if not body or len(body) > 5000:
        return HttpResponse('Comments must contain 1–5000 characters.', status=400)
    Comment.objects.create(entry=entry, author=request.user, body=body)
    return redirect('detail', pk=pk)


@owner_required
def members(request, pk=None):
    if request.method not in ('GET', 'POST'):
        return HttpResponse(status=405)
    target = get_object_or_404(Membership, pk=pk) if pk else None
    form = MemberForm(request.POST or None, instance=target)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Serialize owner changes to prevent simultaneous removal of all owners.
            list(Membership.objects.select_for_update().order_by('pk'))
            updated = form.save(commit=False)
            if target and target.pk == request.membership.pk and (not updated.active or updated.role != Membership.Role.OWNER):
                form.add_error(None, 'You cannot revoke or demote your own membership. Ask another owner.')
            else:
                if not target:
                    updated.joined_at = timezone.now()
                    if not form.cleaned_data.get('history_start'):
                        updated.history_start = updated.joined_at
                updated.save()
                messages.success(request, 'Membership updated. Changes apply on the next request.')
                return redirect('members')
    return render(request, 'journal/members.html', {'form': form, 'target': target, 'memberships': Membership.objects.order_by('email')})


@require_GET
def service_worker(request):
    return HttpResponse((settings.BASE_DIR / 'static' / 'sw.js').read_text(), content_type='application/javascript', headers={'Service-Worker-Allowed': '/'})


@require_GET
def install(request):
    return render(request, 'journal/install.html')
