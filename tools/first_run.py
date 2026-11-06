"""Prepare a fresh Careloop deployment; application setup then happens in the browser."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def prepare(origin, folder=ROOT):
    url = urlsplit(origin)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password or url.query
            or url.fragment or url.path not in ('', '/')
            or not re.fullmatch(r'[a-zA-Z0-9.-]+', url.hostname)):
        raise ValueError('Provide the exact HTTPS origin, for example https://careloop.example.com')
    # Accessing port also rejects malformed values before any settings are written.
    port = url.port
    origin = 'https://' + url.hostname.lower() + (f':{port}' if port and port != 443 else '')
    code = secrets.token_urlsafe(32)
    values = {
        'SECRET_KEY': secrets.token_urlsafe(64), 'DEBUG': 'false', 'DEV_LOGIN_ENABLED': 'false',
        'ALLOWED_HOSTS': url.hostname.lower() + ',localhost,127.0.0.1',
        'CSRF_TRUSTED_ORIGINS': origin, 'POSTGRES_DB': 'journal', 'POSTGRES_USER': 'journal',
        'POSTGRES_PASSWORD': secrets.token_urlsafe(48), 'POSTGRES_HOST': 'db', 'POSTGRES_PORT': '5432',
        'GOOGLE_CLIENT_ID': '', 'GOOGLE_CLIENT_SECRET': '', 'CHILD_NAME': 'your child',
        'TRUST_PROXY': 'true', 'ENABLE_HSTS': 'false',
        'DEPLOYMENT_CODE_HASH': hashlib.sha256(code.encode()).hexdigest(),
        'DEPLOYMENT_CODE_EXPIRES': str(int(time.time()) + 86400),
    }
    fd = os.open(Path(folder) / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    return origin, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True, help='The HTTPS domain handled by your reverse proxy.')
    parser.add_argument('--prepare-only', action='store_true', help='Write fresh settings without starting Docker.')
    args = parser.parse_args()
    try:
        origin, code = prepare(args.origin)
    except (ValueError, FileExistsError) as exc:
        parser.exit(1, f'Not prepared: {exc}. Existing .env files are never overwritten.\n')
    print(f'Private deployment code (valid 24 hours): {code}', flush=True)
    print(f'Keep this code private. Open {origin}/deployment/ after HTTPS and the app are running.', flush=True)
    print('The backend is loopback-only by default. For a separate proxy VM, follow docs/first-deployment.md.', flush=True)
    if not args.prepare_only:
        docker = ['docker', 'compose']
        for command in (['build'], ['up', '-d', 'db'],
                        ['run', '--rm', '-T', '--interactive=false', 'web', 'python', 'manage.py', 'migrate', '--noinput'],
                        ['up', '-d', 'web']):
            subprocess.run(docker + command, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
