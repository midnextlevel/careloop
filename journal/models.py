import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Parent / owner'
        TEACHER = 'teacher', 'Teacher'
        THERAPIST = 'therapist', 'Therapist'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=12, choices=Role.choices)
    active = models.BooleanField(default=True)
    is_development = models.BooleanField(default=False, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    google_subject = models.CharField(max_length=255, unique=True, null=True, blank=True)
    joined_at = models.DateTimeField(default=timezone.now)
    history_start = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        # Canonical exact mailbox matching. Never strip dots, plus tags, or domains.
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class Entry(models.Model):
    class Kind(models.TextChoices):
        SCHOOL = 'school', 'School'
        THERAPY = 'therapy', 'Therapy'
        HOME = 'home', 'Home'

    class Audience(models.TextChoices):
        PARENT = 'parent', 'Parent + author'
        TEAM = 'team', 'Care team'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    event_date = models.DateField(default=timezone.localdate)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SCHOOL)
    summary = models.TextField(blank=True, max_length=10000)
    observations = models.TextField(blank=True, max_length=10000)
    what_helped = models.TextField(blank=True, max_length=10000)
    follow_up = models.TextField(blank=True, max_length=10000)
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.PARENT)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    # Time care-team sharing was first selected; date backdating cannot bypass history.
    shared_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    publish_token = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ['-event_date', '-submitted_at']


class Revision(models.Model):
    entry = models.ForeignKey(Entry, related_name='revisions', on_delete=models.CASCADE)
    version = models.PositiveIntegerField()
    snapshot = models.JSONField()
    replaced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['entry', 'version'], name='unique_entry_revision')]
        ordering = ['-version']


class Comment(models.Model):
    entry = models.ForeignKey(Entry, related_name='comments', on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']
