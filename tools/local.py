"""Native local development helpers. Requires portable PostgreSQL in .local/postgres."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local'
BIN = LOCAL / 'postgres' / 'pgsql' / 'bin'
DATA = LOCAL / 'pgdata'


def environment():
    env = os.environ.copy()
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip()
    env['PGPASSWORD'] = env['POSTGRES_PASSWORD']
    env.pop('JOURNAL_TESTING', None)
    env.pop('TEST_SQLITE', None)
    return env


def run(args, env, **kwargs):
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    display = not kwargs.get('capture_output') and 'stdout' not in kwargs
    if display:
        kwargs['capture_output'] = True
        kwargs.setdefault('text', True)
    result = subprocess.run([str(arg) for arg in args], cwd=ROOT, env=env, **flags, **kwargs)
    if display:
        if result.stdout: print(result.stdout, end='')
        if result.stderr: print(result.stderr, end='', file=sys.stderr)
    result.check_returncode()
    return result


def pg(tool):
    return BIN / (tool + ('.exe' if os.name == 'nt' else ''))


def connect(env):
    return ['-h', env['POSTGRES_HOST'], '-p', env['POSTGRES_PORT'], '-U', env['POSTGRES_USER']]


def manage(env, *args, **kwargs):
    return run([sys.executable, ROOT / 'manage.py', *args], env, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'start', 'stop', 'manage', 'backup-verify'])
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    env = environment()
    if env['POSTGRES_HOST'] != '127.0.0.1' or env.get('DEBUG') != 'true':
        parser.error('This helper requires POSTGRES_HOST=127.0.0.1 and DEBUG=true in .env.')
    if args.action == 'init':
        LOCAL.mkdir(exist_ok=True)
        if DATA.exists():
            parser.error('Database directory already exists; use start.')
        fd, name = tempfile.mkstemp(dir=LOCAL, prefix='pg-password-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(env['POSTGRES_PASSWORD'])
            run([pg('initdb'), '-D', DATA, '-U', env['POSTGRES_USER'], '--auth=scram-sha-256', '--encoding=UTF8', '--locale=C', '--pwfile', name], env)
        finally:
            Path(name).unlink(missing_ok=True)
        with (DATA / 'postgresql.conf').open('a') as handle:
            handle.write("\nlisten_addresses = '127.0.0.1'\nport = " + env['POSTGRES_PORT'] + '\n')
        run([pg('pg_ctl'), '-D', DATA, '-l', LOCAL / 'postgres.log', '-w', 'start'], env)
        run([pg('createdb'), *connect(env), env['POSTGRES_DB']], env)
    elif args.action in ('start', 'stop'):
        run([pg('pg_ctl'), '-D', DATA, '-l', LOCAL / 'postgres.log', '-w', args.action], env)
    elif args.action == 'manage':
        manage(env, *args.arguments)
    else:
        folder = LOCAL / 'backups'
        folder.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = folder / f'journal-{stamp}.dump'
        target = 'journal_restore_' + secrets.token_hex(6)
        count_code = ('from journal.models import Entry,Membership,Revision,Comment,JournalAccessSettings,EntryPhoto; '
                      'from django.contrib.auth import get_user_model; '
                      'from django.core.serializers.json import DjangoJSONEncoder; '
                      'import json,hashlib; models=[Entry,Membership,Revision,Comment,get_user_model(),JournalAccessSettings,EntryPhoto]; '
                      'tables={m.__name__:[{k:hashlib.sha256(bytes(v)).hexdigest() if isinstance(v,(bytes,memoryview)) else v for k,v in row.items()} for row in m.objects.order_by("pk").values()] for m in models}; '
                      'print(json.dumps({"counts":{k:len(v) for k,v in tables.items()}, '
                      '"sha256":hashlib.sha256(json.dumps(tables,cls=DjangoJSONEncoder,sort_keys=True).encode()).hexdigest()}))')
        original = manage(env, 'shell', '-c', count_code, capture_output=True, text=True).stdout.splitlines()[-1]
        run([pg('pg_dump'), *connect(env), '-d', env['POSTGRES_DB'], '-Fc', '-f', backup], env)
        run([pg('createdb'), *connect(env), target], env)
        # Never touch the original database. A failed verification retains its DB for inspection.
        run([pg('pg_restore'), *connect(env), '-d', target, '--no-owner', '--no-privileges', '--exit-on-error', backup], env)
        restored_env = dict(env, POSTGRES_DB=target)
        manage(restored_env, 'migrate', '--check')
        manage(restored_env, 'check')
        restored = manage(restored_env, 'shell', '-c', count_code, capture_output=True, text=True).stdout.splitlines()[-1]
        if json.loads(original) != json.loads(restored):
            raise RuntimeError(f'Restore counts differ; retained {target} for inspection.')
        report = {'backup': str(backup), 'original': json.loads(original), 'restored': json.loads(restored), 'verified_at': stamp}
        (LOCAL / 'restore-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        run([pg('dropdb'), *connect(env), target], env)


if __name__ == '__main__':
    main()
