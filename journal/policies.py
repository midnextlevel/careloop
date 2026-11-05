from django.db.models import Q
from ipaddress import ip_address
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Entry, Membership, JournalAccessSettings


def development_access_allowed(request):
    if not (settings.DEBUG and settings.DEV_LOGIN_ENABLED):
        return False
    try:
        address = ip_address(request.META.get('REMOTE_ADDR', ''))
    except ValueError:
        return False
    # Trust the direct connection only, never a client-supplied forwarded address.
    return address.is_loopback or any(address in network for network in settings.DEV_LOGIN_NETWORKS)


def membership_for(user):
    if not user.is_authenticated:
        return None
    member = Membership.objects.filter(user=user, active=True).first()
    if member and member.is_development and not (settings.DEBUG and settings.DEV_LOGIN_ENABLED):
        return None
    return member


def visible_entries(member):
    if not member or not member.active:
        return Entry.objects.none()
    own = Q(author_id=member.user_id)
    submitted = Q(submitted_at__isnull=False)
    if member.role == Membership.Role.OWNER:
        return Entry.objects.filter(own | submitted)
    policy = JournalAccessSettings.current()
    now = timezone.now()
    if policy.access_until:
        default_access = Q(professional_access_until__isnull=True) if now < policy.access_until else Q(pk__in=[])
    else:
        default_access = Q(professional_access_until__isnull=True,
                           submitted_at__gt=now - timedelta(days=policy.access_days))
    unexpired = Q(professional_access_until__gt=now) | default_access
    # Use original submission time, not event date or date the audience was widened.
    shared = Q(audience=Entry.Audience.TEAM, submitted_at__gte=member.history_start)
    own_submitted = own & submitted
    if policy.expire_authors:
        own_submitted &= unexpired
    return Entry.objects.filter((own & ~submitted) | own_submitted | (submitted & shared & unexpired))


def can_edit(member, entry):
    if not (member and member.active and entry.author_id == member.user_id):
        return False
    return visible_entries(member).filter(pk=entry.pk).exists()


def is_owner(member):
    return bool(member and member.active and member.role == Membership.Role.OWNER)
