# Little moments

A private daily journal for one child, built with Django 5.2 LTS, PostgreSQL 17, Django templates, responsive CSS, and small JavaScript enhancements. The default child and all seed records are fictional. No attachments, notifications, reminders, PDF export, analytics, rich text, or offline synchronization are included.

## Native development on this machine

A named local test account was added at the owner's explicit request. The app is currently configured for native PostgreSQL on `127.0.0.1:55432` and Django on `127.0.0.1:8000`. Open [local test sign-in](http://127.0.0.1:8000/development/login/). Username: **test-parent**, display name: **Test Parent**. The generated password is in the ignored `.local/development-account.txt`; it is not committed or printed by setup tools. Sample content is fictional.

The PostgreSQL 17.11 binaries were downloaded from [EDB's official Windows binary distribution](https://www.enterprisedb.com/download-postgresql-binaries), extracted under ignored `.local/postgres`, and initialized with SCRAM password authentication and a loopback-only listener. No Windows service, Docker installation, WSL installation, or public database port was added.

After stopping the app or restarting Windows, use these PowerShell commands from `C:\nonoy-journal` (skip `start` if PostgreSQL is already running):

```powershell
.\.venv\Scripts\python.exe tools\local.py start
.\.venv\Scripts\python.exe tools\local.py manage runserver 127.0.0.1:8000 --noreload
```

In a separate terminal:

```powershell
.\.venv\Scripts\python.exe tools\local.py manage test --verbosity 2
.\.venv\Scripts\python.exe tools\local.py backup-verify
# Stop the web process with Ctrl+C before stopping PostgreSQL:
.\.venv\Scripts\python.exe tools\local.py stop
```

Set `BROWSER_NODE` and `NODE_PATH` as described in the tests section to include Playwright in the suite. `tools/smoke_local.cjs` separately verifies the actual named login against the running app and writes one fictional home entry. `backup-verify` creates a timestamped dump in `.local/backups`, restores it into a unique throwaway database, checks migrations and Django configuration, and compares counts and a SHA-256 digest of all entries, memberships, revisions, comments, and users. The successful report is saved to `.local/restore-report.json`; only that throwaway database is then removed. Failed verification leaves it available for inspection.

Local password login requires **both** `DEBUG=true` and `DEV_LOGIN_ENABLED=true`, accepts only explicitly marked development accounts, and is available only from loopback addresses. Nonlocal access is rejected; disabling the flag invalidates existing development sessions on their next request. Startup refuses to enable this login with `DEBUG=false`. Before deploying, set `DEV_LOGIN_ENABLED=false`; the named development account cannot sign in through Google. It can also be revoked using Care team. Native helpers deliberately refuse nonloopback or nondevelopment environments. This is a development server, not the Linux production deployment.

To create another fictional development owner interactively:

```powershell
.\.venv\Scripts\python.exe tools\local.py manage create_dev_owner another-test-parent --name "Another Test Parent"
```

The command prompts for a password and refuses to overwrite existing users. Keep `.env`, `.local` (including passwords/data/backups), and generated browser artifacts out of version control and shared files.

## Run locally with Docker Compose

Install Docker Engine/Desktop with the Compose v2 plugin. In this directory:

```sh
cp .env.example .env
# Edit .env: replace SECRET_KEY and POSTGRES_PASSWORD with unique random secrets.
# Configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET as described below.
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py bootstrap_owner your.exact.email@gmail.com
docker compose up -d web
```

Open [the local journal](http://localhost:8000). `DEBUG=true` enables HTTP development. Google must be configured for normal sign-in. The separately opted-in native development login above is the only password login. The bootstrap command approves an email; it does not create a user or a password. It refuses to run when an active owner already exists. If using the existing native development database, approve your real Google email through its Care team screen instead.

PowerShell: use `Copy-Item .env.example .env` instead of `cp`. Docker reads `.env`; native Python commands do not load it automatically. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(50))"` on a machine with Python installed.

Optional fictional development content:

```sh
docker compose exec web python manage.py seed_fictional
```

This idempotent command requires `DEBUG=true`. It creates three disabled, unusable-password identities at `example.invalid`; it does not grant anyone login access. The actual owner can see the submitted examples after Google sign-in.

## Google OAuth configuration

1. In Google Cloud, create/select a project and configure Google Auth Platform branding, audience/consent, and data access for `openid`, `email`, `profile`. Add permitted Google test users if the consent app is in testing mode.
2. Create an OAuth client with application type **Web application**. Add the site's exact origin, for example `http://localhost:8000` for development or `https://journal.example.com` for production.
3. Add these exact authorized redirect URIs for the environments you use:
   - `http://localhost:8000/accounts/google/login/callback/`
   - `https://journal.example.com/accounts/google/login/callback/`
4. Put the client ID and secret into `.env`, then recreate web: `docker compose up -d --force-recreate web`. Do not also create a database SocialApp: this app configures the provider through settings.
5. Bootstrap your exact owner email, sign in with that Google identity, and use **Care team** to approve other exact addresses and assign their roles. Approval is not an email invitation. Share the site URL separately.

Authentication uses allauth's OAuth code flow and PKCE, server-side sessions, provider-verified emails, and Google's stable subject identifier. Addresses are trimmed and lowercased only; dots, plus tags, and domains are never broadened. Existing accounts must continue to match both their approved email and bound Google subject. Provider tokens are not retained. Within the normal allauth flow, local signup and email/password login are disabled by social-only mode; local email verification is `none` because verification is required from Google in the custom adapter instead.

**Pending live integration:** mocked provider identity tests do not verify an actual Google authorization-code exchange. With credentials, verify owner login, approved professional login, unapproved and wrong-email denial, and revocation through an already-open session. This remains a deployment acceptance check.

## Daily workflow and defaults

- Sign in → Write an entry → Save draft when useful → Review audience → Confirm & submit.
- School, therapy, and home entries have an event date, summary, observations, what helped, and optional follow-up. A nonempty summary is required to submit. Each text field is limited to 10,000 characters; comments to 5,000.
- Drafts are visible only to their author, including when the viewer is the parent. The parent reads all submitted entries. Only the author edits an entry.
- The audience defaults to **Parent + author**. **Care team** is an explicit author choice. Comments inherit the entry's current audience. Only submitted entries accept comments.
- Membership joining time is the approval time. History access initially starts at that time. Professionals can always read their own entries; other care-team entries must have an original submission timestamp at or after their history start. Backdating an event date or later widening an audience does not grant old history. Owners can deliberately adjust history access. Role and access changes apply on the next authenticated request, including existing sessions. Owners cannot revoke/demote themselves.
- Submitted edits preserve the previous content, audience, event date, and timestamps. Previous versions are visible only to the parent and author, so an earlier private version is not exposed by later sharing. The timeline labels entries as revised only when a submitted revision exists.
- Draft saves are explicit, not automatic. Status becomes **Saved** only after a successful server response. Typing during an in-flight save leaves the newer text marked unsaved. Network errors and conflicts retain text in the open editor. Submission retries use a signed review ticket and an operation UUID; row locks and version numbers reject stale writes. After an ambiguous timeout, retry the same confirmation or reload the server entry before making another edit.
- Timestamps are timezone-aware and displayed in Asia/Manila. Event dates are independent of submission time. Review tickets expire after one hour. All private screens disable HTMX history snapshots; HTMX is otherwise unnecessary for this milestone.
- No private content is put in localStorage, IndexedDB, or a service-worker cache. The worker caches only five explicit public assets. Dynamic pages, auth, redirects, and private endpoints are network-only with no-store headers. Generic offline navigation contains no journal content. Installation instructions are available at `/install/`.

## Tests and checks

Against PostgreSQL in Compose (required before production):

```sh
docker compose run --rm -e JOURNAL_TESTING=1 web python manage.py test --verbosity 2
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py collectstatic --noinput
docker compose run --rm web python -m pip check
docker compose config --quiet
```

The Compose database user may create the isolated Django test database. No production data is used by tests. `JOURNAL_TESTING=1` relaxes HTTPS only in the test process. Never set it in the deployment environment. SQLite is an explicitly test-only fallback, not an application deployment backend:

```sh
python -m venv .venv
# Linux/macOS:
.venv/bin/python -m pip install -r requirements.txt
JOURNAL_TESTING=1 TEST_SQLITE=1 .venv/bin/python manage.py test --verbosity 2
```

PowerShell equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:JOURNAL_TESTING='1'
$env:TEST_SQLITE='1'
.\.venv\Scripts\python.exe manage.py test --verbosity 2
```

Optional browser test uses Node.js, Playwright, and installed Chrome. Install Playwright in an external tooling directory (`npm install playwright` there), set `NODE_PATH` to its `node_modules`, and set `BROWSER_NODE` to the absolute Node executable. Then rerun `manage.py test`. For Playwright-managed Chromium, install it (`npx playwright install chromium`) and set `BROWSER_CHANNEL=chromium`. Screenshots are written to ignored `test-results/`. The browser uses a session created solely inside Django's isolated automated test; the application has no test-login endpoint. See `STATUS.md` for actual results and unverified checks.

## Linux VM deployment behind HTTPS

Use a dedicated, patched Linux VM on Proxmox. Install Docker/Compose; place this repository and `.env` on the VM. Keep secrets readable only by the deployment account (`chmod 600 .env`) and excluded from source control. Use the commands above to build and migrate before starting web. Dependency versions, including transitive dependencies, are pinned in `requirements.txt`; `requirements.in` records the direct choices. Review and update pins for security releases. Compose uses the supported PostgreSQL 17 image line; resolve and pin its image digest in your production deployment for reproducible upgrades.

Set production values:

```dotenv
DEBUG=false
DEV_LOGIN_ENABLED=false
ALLOWED_HOSTS=journal.example.com
CSRF_TRUSTED_ORIGINS=https://journal.example.com
TRUST_PROXY=true
ENABLE_HSTS=true
```

Use new random secrets, real Google credentials, the production callback URI, and the child's chosen display name. Leave `JOURNAL_TESTING` and `TEST_SQLITE` unset. `DEBUG=false` activates HTTPS redirects and secure session/CSRF cookies. Server-side database sessions expire after 12 hours. Schedule `docker compose exec -T web python manage.py clearsessions` periodically through your VM's system timer.

The web port binds to loopback only; put the reverse proxy on the same VM, or explicitly bind to a protected private interface and firewall it for a remote proxy. The database has **no published host port**. Never expose port 5432 publicly. Allow inbound HTTPS and restricted administration only. Disable proxy/CDN caching for **all** dynamic/auth routes. Do not log request bodies, cookies, or OAuth query strings; redact `/accounts/` query parameters in reverse-proxy logs. Encrypt VM disks and backup storage as appropriate for private child records.

Example nginx location (inside a TLS server block using your certificates):

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_redirect off;
    proxy_no_cache 1;
    proxy_cache_bypass 1;
}
```

The proxy must overwrite untrusted incoming `X-Forwarded-Proto`; only then enable `TRUST_PROXY=true`. Keep HTTP redirecting to HTTPS, forward the original host, and never permit direct public web access that can spoof proxy headers. Turn HSTS on only after HTTPS is verified. Django/WhiteNoise serves bundled public static assets. No private media storage exists in this milestone.

Run `docker compose exec web python manage.py check --deploy` after setting production configuration. Verify HTTPS redirect, secure cookies, allowed-host rejection, correct CSRF behavior, actual Google login, revocation, and the mobile workflow before entering real child data. Deploy checks cannot establish that the surrounding proxy is configured correctly.

The deployment check reports W005/W021 because subdomain-wide HSTS and browser preload are not enabled by default. Enable Django's `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` only after confirming that every affected subdomain supports permanent HTTPS and deciding to pursue browser preload. Ordinary HSTS is controlled separately by `ENABLE_HSTS`.

## Backup, restore, and verify

These commands use a Linux shell on the VM. Never commit backups. Protect and encrypt backups, copy them off the VM to a restricted destination, and apply your retention policy. PostgreSQL dumps include private entries, revisions, memberships, and sessions; keep `.env` separately in secure secret storage.

```sh
mkdir -p backups
chmod 700 backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/journal.dump
chmod 600 backups/journal.dump
docker compose exec -T db pg_restore --list < backups/journal.dump
```

Regularly verify by restoring into a **separate** database:

```sh
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" journal_restore'
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d journal_restore --no-owner --no-privileges --exit-on-error' < backups/journal.dump
docker compose run --rm -e POSTGRES_DB=journal_restore web python manage.py migrate --check
docker compose run --rm -e POSTGRES_DB=journal_restore web python manage.py check
docker compose run --rm -e POSTGRES_DB=journal_restore web python manage.py shell -c "from journal.models import Entry, Membership, Revision, Comment; print({m.__name__: m.objects.count() for m in [Entry, Membership, Revision, Comment]})"
```

Compare counts to those recorded at backup time, inspect a known fictional entry and its revisions on a staging-only app connected to `journal_restore`, and verify permission rules and a login using the staging OAuth callback. Never point the public production app at the verification database. After verification, delete **only** the throwaway database with `docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" journal_restore'`.

For actual recovery, stop web, preserve a fresh backup of the current database, confirm the intended dump and target, then restore to the existing production database with `pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error` and `-U "$POSTGRES_USER" -d "$POSTGRES_DB"` inside the database container. Apply migrations, run checks, compare counts, then start web. A restore can resurrect old sessions and membership states: before reopening access, clear `django_session` (`python manage.py shell -c "from django.contrib.sessions.models import Session; Session.objects.all().delete()"`) and recheck the approved/revoked membership list. Never delete the Compose volume as a substitute for a verified restore.

## Architecture

`journal/policies.py` centralizes visibility and author/owner policies; every entry/comment endpoint applies them. `journal/middleware.py` checks active membership on every authenticated request and sets dynamic no-store headers. `journal/adapters.py` gates Google admission and binds identities transactionally. `journal/services.py` serializes writes with PostgreSQL row locks, version checks, and revision snapshots. Review tickets bind content, audience, author, entry, version, and retry token with Django signing. No Django admin is exposed. The explicitly enabled native development login is restricted to marked test accounts and loopback requests; production uses Google. `STATUS.md` tracks completed work and deployment acceptance checks.
