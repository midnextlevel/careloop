import json
from datetime import timedelta
from io import BytesIO, StringIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from journal.models import Entry, EntryPhoto, Revision
from journal.services import FIELDS
from .test_journal import identity


def image_upload(name='camera.jpg', size=(2400, 1200), orientation=None):
    image = Image.new('RGB', size, 'orange')
    output = BytesIO()
    exif = Image.Exif()
    exif[270] = 'Private camera metadata'
    if orientation:
        exif[274] = orientation
    image.save(output, 'JPEG', exif=exif)
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/jpeg')


class PhotoTests(TestCase):
    def setUp(self):
        self.owner, _ = identity('owner', 'photo-parent')
        self.teacher, self.tm = identity('teacher', 'photo-teacher')
        self.other, self.pm = identity('therapist', 'photo-therapist')
        self.entry = Entry.objects.create(author=self.teacher, summary='Photo observation')
        self.client.force_login(self.teacher)

    def edit(self, action='save', uploads=(), removed=(), version=None):
        self.entry.refresh_from_db()
        data = {field: getattr(self.entry, field) for field in FIELDS}
        data.update(action=action, version=self.entry.version if version is None else version,
                    photo_ids=json.dumps(self.entry.photo_ids), remove_photos=list(removed))
        if uploads:
            data['photos'] = list(uploads)
        return self.client.post(f'/entries/{self.entry.pk}/edit/', data,
            **({'HTTP_ACCEPT': 'application/json'} if action == 'save' else {}))

    def publish(self, review):
        return self.client.post(f'/entries/{self.entry.pk}/publish/',
            {'confirmed': 'on', 'ticket': review.context['ticket']})

    def photo_url(self, photo):
        return f'/entries/{self.entry.pk}/photos/{photo.pk}/'

    def test_optional_photos_are_optimized_and_metadata_removed(self):
        self.assertEqual(self.edit().status_code, 200)
        response = self.edit(uploads=[image_upload(orientation=6), image_upload(size=(100, 60))])
        self.assertEqual(response.status_code, 200)
        self.assertIn('photos_html', response.json())
        self.entry.refresh_from_db()
        self.assertEqual(len(self.entry.photo_ids), 2)
        photo = EntryPhoto.objects.get(pk=self.entry.photo_ids[0])
        self.assertEqual((photo.width, photo.height), (800, 1600))
        self.assertLessEqual(len(photo.content), 512 * 1024)
        with Image.open(BytesIO(bytes(photo.content))) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertFalse(image.getexif())
        response = self.client.get(self.photo_url(photo))
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertIn('no-store', response['Cache-Control'])

    def test_two_photo_limit_including_existing_photos_and_replacement(self):
        self.assertEqual(self.edit(uploads=[image_upload(), image_upload()]).status_code, 200)
        self.entry.refresh_from_db()
        old_ids = self.entry.photo_ids
        version = self.entry.version
        self.assertEqual(self.edit(uploads=[image_upload()]).status_code, 400)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.version, version)
        self.assertEqual(self.edit(uploads=[image_upload()], removed=[old_ids[0]]).status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(len(self.entry.photo_ids), 2)
        self.assertNotIn(old_ids[0], self.entry.photo_ids)

    def test_invalid_oversized_and_three_uploads_are_rejected_without_rows(self):
        for uploads in ([image_upload() for _ in range(3)],
                        [SimpleUploadedFile('fake.jpg', b'<html>not a photo</html>')],
                        [SimpleUploadedFile('big.jpg', b'x' * (12 * 1024 * 1024 + 1))]):
            self.assertEqual(self.edit(uploads=uploads).status_code, 400)
        self.assertEqual(EntryPhoto.objects.count(), 0)

    def test_draft_and_staged_photos_are_author_only(self):
        review = self.edit('review', [image_upload()])
        self.assertEqual(review.status_code, 200)
        photo = EntryPhoto.objects.get()
        for user in (self.owner, self.other):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.photo_url(photo)).status_code, 404)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.photo_url(photo)).status_code, 200)
        self.assertEqual(self.publish(review).status_code, 302)
        # A new unsubmitted revision upload remains private even on a shared entry.
        review = self.edit('review', [image_upload()], removed=[str(photo.pk)])
        staged = EntryPhoto.objects.exclude(pk=photo.pk).get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.photo_url(staged)).status_code, 403)

    def test_photos_follow_audience_history_expiry_and_revocation(self):
        review = self.edit('review', [image_upload()])
        self.publish(review)
        photo = EntryPhoto.objects.get()
        url = self.photo_url(photo)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.entry.refresh_from_db()
        self.entry.audience = 'parent'
        self.entry.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.entry.audience = 'team'
        self.entry.professional_access_until = timezone.now() - timedelta(seconds=1)
        self.entry.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.entry.professional_access_until = timezone.now() + timedelta(days=1)
        self.entry.save()
        self.pm.history_start = timezone.now() + timedelta(days=1)
        self.pm.save()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.tm.active = False
        self.tm.save()
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_submitted_revisions_preserve_removed_photos_privately_and_retries(self):
        first = self.edit('review', [image_upload()])
        self.publish(first)
        old = EntryPhoto.objects.get()
        second = self.edit('review', [image_upload()], removed=[str(old.pk)])
        self.assertEqual(self.publish(second).status_code, 302)
        self.assertEqual(self.publish(second).status_code, 302)
        self.assertEqual(Revision.objects.filter(entry=self.entry).count(), 1)
        self.assertEqual(Revision.objects.get(entry=self.entry).snapshot['photo_ids'], [str(old.pk)])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.photo_url(old)).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.photo_url(old)).status_code, 200)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.photo_url(old)).status_code, 200)

    def test_forged_cross_entry_photo_ids_and_conflicting_uploads_are_rejected(self):
        foreign_entry = Entry.objects.create(author=self.other)
        foreign_photo = EntryPhoto.objects.create(entry=foreign_entry, content=b'private', width=1, height=1)
        data = {field: getattr(self.entry, field) for field in FIELDS}
        data.update(version=self.entry.version, action='save', photo_ids=json.dumps([str(foreign_photo.pk)]))
        self.assertEqual(self.client.post(f'/entries/{self.entry.pk}/edit/', data,
            HTTP_ACCEPT='application/json').status_code, 400)
        self.edit()
        count = EntryPhoto.objects.count()
        self.assertEqual(self.edit(uploads=[image_upload()], version=1).status_code, 409)
        self.assertEqual(EntryPhoto.objects.count(), count)

    def test_cleanup_preserves_current_and_revision_photos(self):
        self.edit(uploads=[image_upload()])
        self.entry.refresh_from_db()
        kept = self.entry.photo_ids[0]
        orphan = EntryPhoto.objects.create(entry=self.entry, content=b'orphan', width=1, height=1)
        archived = EntryPhoto.objects.create(entry=self.entry, content=b'archived', width=1, height=1)
        Revision.objects.create(entry=self.entry, version=1, snapshot={'photo_ids': [str(archived.pk)]})
        EntryPhoto.objects.all().update(created_at=timezone.now() - timedelta(days=2))
        call_command('prune_unused_photos', stdout=StringIO())
        self.assertTrue(EntryPhoto.objects.filter(pk=kept).exists())
        self.assertTrue(EntryPhoto.objects.filter(pk=archived.pk).exists())
        self.assertFalse(EntryPhoto.objects.filter(pk=orphan.pk).exists())
