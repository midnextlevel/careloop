from django.db import transaction
from django.utils import timezone
from .models import Entry, EntryPhoto, Revision
from .policies import allowed_entry_types, can_edit

FIELDS = ['event_date', 'kind', 'summary', 'observations', 'what_helped', 'follow_up', 'audience']

class Conflict(Exception):
    pass


@transaction.atomic
def write_entry(member, entry_id, data, version, *, publish=False, token=None):
    entry = Entry.objects.select_for_update().get(pk=entry_id)
    if not can_edit(member, entry):
        raise PermissionError
    if data.get('kind') not in dict(allowed_entry_types(member)):
        raise PermissionError('Your role cannot post this entry type.')
    if publish and entry.publish_token == token:
        return entry  # Retry of the same confirmed operation; no duplicate revision.
    if entry.version != version:
        raise Conflict('A newer version exists. Your text is below; open the latest entry in another tab before trying again.')
    if not publish and entry.submitted_at:
        raise Conflict('This entry has already been submitted. Draft saves cannot change it.')
    photo_ids = data.get('photo_ids', entry.photo_ids)
    if not isinstance(photo_ids, list) or len(photo_ids) > 2 or len(set(photo_ids)) != len(photo_ids):
        raise ValueError('An entry can have at most two photos.')
    if EntryPhoto.objects.filter(entry=entry, pk__in=photo_ids).count() != len(photo_ids):
        raise ValueError('Photos must belong to this entry.')
    if entry.submitted_at:
        snapshot = {f: str(getattr(entry, f)) for f in FIELDS}
        snapshot.update(submitted_at=entry.submitted_at.isoformat(), updated_at=entry.updated_at.isoformat())
        snapshot['photo_ids'] = list(entry.photo_ids)
        Revision.objects.create(entry=entry, version=entry.version, snapshot=snapshot)
    for field in FIELDS:
        setattr(entry, field, data[field])
    entry.photo_ids = photo_ids
    now = timezone.now()
    if publish:
        entry.submitted_at = entry.submitted_at or now
        entry.publish_token = token
        if entry.audience == Entry.Audience.TEAM:
            entry.shared_at = entry.shared_at or now
    entry.version += 1
    entry.updated_at = now
    entry.save()
    return entry
