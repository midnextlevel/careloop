"""Encrypted Compose backups with restore verification and optional daily systemd scheduling."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def command(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def validate_destination(destination, mount=None):
    destination = Path(destination).resolve()
    if mount:
        mount = Path(mount).resolve()
        if mount == Path(mount.anchor) or not mount.is_mount() or not destination.is_relative_to(mount):
            raise ValueError('Backup mount is unavailable or destination is outside that mount.')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    return destination


def prune(destination, keep_days, now=None):
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=keep_days)
    for path in Path(destination).iterdir():
        match = re.fullmatch(r'careloop-(\d{8}T\d{6}Z)-[0-9a-f]{8}\.tar\.gz\.age', path.name)
        if not match or path.is_symlink() or not path.is_file():
            continue
        stamp = datetime.strptime(match[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        if stamp < cutoff:
            path.unlink()
            checksum = path.with_name(path.name + '.sha256')
            if checksum.is_file() and not checksum.is_symlink():
                checksum.unlink()


def backup(destination, recipient, keep_days=30, mount=None, project=ROOT, stream=False):
    if keep_days < 1:
        raise ValueError('Retention must be at least one day.')
    if not recipient.startswith('age1') or any(c.isspace() for c in recipient):
        raise ValueError('Provide an age public recipient, never a private recovery key.')
    project = Path(project).resolve()
    if not (project / '.env').is_file():
        raise ValueError('Project .env is missing.')
    for binary in ('docker', 'age'):
        if not shutil.which(binary):
            raise ValueError(f'{binary} must be installed first.')
    destination = None if stream else validate_destination(destination, mount)
    compose = ['docker', 'compose', '--project-directory', str(project)]
    os.umask(0o077)
    name = 'careloop-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(4)
    archive = destination / (name + '.tar.gz.age') if destination else None
    pending = destination / (name + '.partial') if destination else None
    with tempfile.TemporaryDirectory(prefix='careloop-backup-') as work:
        work = Path(work)
        dump = work / 'journal.dump'
        with dump.open('wb') as output:
            command(compose + ['exec', '-T', 'db', 'sh', '-c',
                    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'], stdout=output)
        with dump.open('rb') as source:
            command(compose + ['exec', '-T', 'db', 'pg_restore', '--list'], stdin=source, stdout=subprocess.DEVNULL)
        target = 'careloop_verify_' + secrets.token_hex(6)
        command(compose + ['exec', '-T', 'db', 'sh', '-c', 'createdb -U "$POSTGRES_USER" "$1"', 'sh', target], stdout=sys.stderr)
        try:
            with dump.open('rb') as source:
                command(compose + ['exec', '-T', 'db', 'sh', '-c',
                    'pg_restore -U "$POSTGRES_USER" -d "$1" --no-owner --no-privileges --exit-on-error', 'sh', target], stdin=source, stdout=sys.stderr)
            command(compose + ['run', '--rm', '-T', '--interactive=false', '-e', f'POSTGRES_DB={target}',
                               'web', 'python', 'manage.py', 'migrate', '--check'], stdout=sys.stderr)
        finally:
            command(compose + ['exec', '-T', 'db', 'sh', '-c', 'dropdb -U "$POSTGRES_USER" "$1"', 'sh', target], stdout=sys.stderr)
        revision = command(['git', '-C', str(project), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        (work / 'manifest.json').write_text(json.dumps({'commit': revision, 'created_utc': name,
            'database_restore_verified': True, 'contains': 'Database including photos/OAuth plus deployment settings'}))
        package = work / 'recovery.tar.gz'
        with tarfile.open(package, 'w:gz') as tar:
            tar.add(dump, arcname='journal.dump')
            tar.add(work / 'manifest.json', arcname='manifest.json')
            for filename in ('.env', 'compose.yaml', 'compose.override.yaml'):
                path = project / filename
                if path.is_file():
                    tar.add(path, arcname=filename)
        if stream:
            command(['age', '--encrypt', '-r', recipient, str(package)], stdout=sys.stdout.buffer)
            print('Encrypted stream complete; database restore verified.', file=sys.stderr)
            return None
        try:
            validate_destination(destination, mount)
            command(['age', '--encrypt', '-r', recipient, '-o', str(pending), str(package)])
            validate_destination(destination, mount)
            # Atomic publication: incomplete backups never receive the final name.
            pending.replace(archive)
        finally:
            pending.unlink(missing_ok=True)
    checksum_hash = hashlib.sha256()
    with archive.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            checksum_hash.update(chunk)
    digest = checksum_hash.hexdigest()
    archive.with_name(archive.name + '.sha256').write_text(digest + '  ' + archive.name + '\n')
    prune(destination, keep_days)
    print(f'Encrypted backup created; database restore verified: {archive}')
    return archive


def systemd_quote(value):
    if '\n' in str(value) or '\r' in str(value):
        raise ValueError('Newlines are not allowed in service arguments.')
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination')
    parser.add_argument('--stream', action='store_true', help='Write encrypted bytes to stdout for an off-VM pull.')
    parser.add_argument('--project', default=str(ROOT))
    parser.add_argument('--recipient', required=True)
    parser.add_argument('--keep-days', type=int, default=30)
    parser.add_argument('--mount', help='Mounted off-VM filesystem; fail rather than back up locally if absent.')
    parser.add_argument('--install-timer', action='store_true')
    args = parser.parse_args()
    if not args.stream and not args.destination:
        parser.error('--destination is required unless using --stream.')
    if args.stream and (args.install_timer or args.mount or args.destination):
        parser.error('--stream cannot be combined with --install-timer, --mount or --destination.')
    if args.install_timer and not args.mount:
        parser.error('A verified off-VM --mount is required for automatic backups.')
    backup(args.destination, args.recipient, args.keep_days, args.mount, args.project, args.stream)
    if args.install_timer:
        if os.geteuid() != 0:
            parser.error('Run as root to install systemd units.')
        argv = ['/usr/bin/python3', str(Path(__file__).resolve()), '--destination', str(Path(args.destination).resolve()),
                '--project', str(Path(args.project).resolve()), '--recipient', args.recipient,
                '--keep-days', str(args.keep_days), '--mount', str(Path(args.mount).resolve())]
        unit = '[Unit]\nDescription=Encrypted Careloop backup and restore verification\nRequires=docker.service\nAfter=docker.service network-online.target\n[Service]\nType=oneshot\nUMask=0077\nExecStart=' + ' '.join(map(systemd_quote, argv)) + '\n'
        Path('/etc/systemd/system/careloop-backup.service').write_text(unit)
        Path('/etc/systemd/system/careloop-backup.timer').write_text('[Unit]\nDescription=Daily Careloop backup\n[Timer]\nOnCalendar=*-*-* 02:00:00\nRandomizedDelaySec=15m\nPersistent=true\n[Install]\nWantedBy=timers.target\n')
        command(['systemctl', 'daemon-reload'])
        command(['systemctl', 'enable', '--now', 'careloop-backup.timer'])
        print('Daily timer installed. Confirm its destination is backed by off-VM storage.')


if __name__ == '__main__':
    main()
