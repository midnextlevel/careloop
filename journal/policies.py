from django.db.models import Q
from ipaddress import ip_address
from django.conf import settings
from .models import Entry, Membership


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
    # Use original submission time, not event date or date the audience was widened.
    shared = Q(audience=Entry.Audience.TEAM, submitted_at__gte=member.history_start)
    return Entry.objects.filter(own | (submitted & shared))


def can_edit(member, entry):
    return bool(member and member.active and entry.author_id == member.user_id)


def is_owner(member):
    return bool(member and member.active and member.role == Membership.Role.OWNER)
