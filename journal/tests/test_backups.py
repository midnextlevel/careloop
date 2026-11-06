from datetime import datetime, timezone
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch
from tools.backups import prune, validate_destination, systemd_quote


class BackupSafetyTests(TestCase):
    def test_retention_only_removes_old_matching_archives_and_checksums(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            old = folder / 'careloop-20200101T000000Z-abcdef12.tar.gz.age'
            recent = folder / 'careloop-20261106T000000Z-abcdef12.tar.gz.age'
            unrelated = folder / 'family-20200101.tar.gz.age'
            partial = folder / 'careloop-20200101T000000Z-abcdef12.partial'
            checksum = old.with_name(old.name + '.sha256')
            for path in (old, recent, unrelated, partial, checksum):
                path.write_bytes(b'test')
            prune(folder, 30, datetime(2026, 11, 6, tzinfo=timezone.utc))
            self.assertFalse(old.exists())
            self.assertFalse(checksum.exists())
            for path in (recent, unrelated, partial):
                self.assertTrue(path.exists())

    def test_missing_mount_fails_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / 'missing-mount' / 'careloop'
            with patch.object(Path, 'is_mount', return_value=False), self.assertRaises(ValueError):
                validate_destination(destination, Path(root) / 'missing-mount')
            self.assertFalse(destination.exists())

    def test_mount_cannot_be_root_or_an_unrelated_directory(self):
        with patch.object(Path, 'is_mount', return_value=True):
            with self.assertRaises(ValueError):
                validate_destination('/tmp/careloop', '/')
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):
                    validate_destination(Path(root) / 'outside', Path(root) / 'mount')

    def test_systemd_arguments_do_not_expand_percent_or_accept_newlines(self):
        self.assertEqual(systemd_quote('/a%b'), '"/a%%b"')
        with self.assertRaises(ValueError):
            systemd_quote('path\nExecStart=other')
