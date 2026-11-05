from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from journal.models import Entry, EntryPhoto


class Command(BaseCommand):
    help = 'Delete unreferenced photo uploads older than 24 hours; preserve current and revision photos.'

    def handle(self, **options):
        removed = 0
        for pk in Entry.objects.values_list('pk', flat=True).iterator():
            with transaction.atomic():
                entry = Entry.objects.select_for_update().get(pk=pk)
                referenced = set(entry.photo_ids)
                for revision in entry.revisions.all():
                    referenced.update(revision.snapshot.get('photo_ids', []))
                count, _ = EntryPhoto.objects.filter(entry=entry,
                    created_at__lt=timezone.now() - timedelta(hours=24)).exclude(pk__in=referenced).delete()
                removed += count
        self.stdout.write(f'Removed {removed} unreferenced photo uploads.')
