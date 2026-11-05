# Developing Careloop

## Existing Windows setup

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

Set `BROWSER_NODE` and `NODE_PATH` as described in the tests section to include Playwright in the suite. `tools/smoke_local.cjs` separately verifies the actual named login against the running app and checks owner tracking and dark mode without creating entries. `backup-verify` creates a timestamped dump in `.local/backups`, restores it into a unique throwaway database, checks migrations and Django configuration, and compares counts and a SHA-256 digest of all entries, memberships, revisions, comments, users, and journal access settings. The successful report is saved to `.local/restore-report.json`; only that throwaway database is then removed. Failed verification leaves it available for inspection.

Local password login requires **both** `DEBUG=true` and `DEV_LOGIN_ENABLED=true`, accepts only explicitly marked development accounts, and defaults to loopback addresses. Explicit private subnets in `DEV_LOGIN_NETWORKS` also allow phone testing. Connections outside those networks are rejected; disabling the flag invalidates existing development sessions on their next request. Startup refuses to enable this login with `DEBUG=false`. Before deploying, set `DEV_LOGIN_ENABLED=false`; the named development account cannot sign in through Google. It can also be revoked using Care team. Native helpers deliberately refuse nonloopback or nondevelopment environments. This is a development server, not the Linux production deployment.

To create another fictional development owner interactively:

```powershell
.\.venv\Scripts\python.exe tools\local.py manage create_dev_owner another-test-parent --name "Another Test Parent"
```

The command prompts for a password and refuses to overwrite existing users. Keep `.env`, `.local` (including passwords/data/backups), and generated browser artifacts out of version control and shared files.

## Test on a phone over Wi-Fi

The phone and development computer must be on the same trusted local network. On the phone, `127.0.0.1` refers to the phone itself.

1. Find the computer's LAN address (for example, `192.168.1.50`) and subnet (`192.168.1.0/24`).
2. Keep `DEBUG=true` and `DEV_LOGIN_ENABLED=true`. Add that subnet as `DEV_LOGIN_NETWORKS=192.168.1.0/24` in the untracked `.env`.
3. Add the computer's IP to `ALLOWED_HOSTS`, and `http://192.168.1.50:8000` to `CSRF_TRUSTED_ORIGINS`.
4. Run `.\.venv\Scripts\python.exe tools\local.py manage runserver 0.0.0.0:8000 --noreload`.
5. Allow inbound TCP port 8000 in Windows Firewall only on the Private profile, scoped to the LAN subnet. Leave PostgreSQL on loopback.
6. Open `http://192.168.1.50:8000` on the phone and sign in with the existing test account.

Use your actual LAN address and subnet, not the examples above. This machine is currently configured as `192.168.99.95` on `192.168.99.0/24`. Its firewall rule is named `Careloop-Development-LAN`. If DHCP changes the computer's address, update the allowed hosts, origin, and firewall rule. Guest Wi-Fi, client isolation, or a VPN can prevent devices from reaching each other.

Login and every development session request check the direct client IP; forwarded headers cannot grant access. Clearing `DEV_LOGIN_NETWORKS` returns login to loopback-only access. After phone testing, stop the LAN-bound server, return to the loopback command above, and disable the firewall rule from an administrator terminal with `Disable-NetFirewallRule -Name Careloop-Development-LAN`.

This HTTP setup is for fictional development data. HTTPS is needed for normal phone PWA installation, service workers, and production use. Never port-forward this development server to the internet.

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

Optional browser test uses Node.js, Playwright, and installed Chrome. Install Playwright in an external tooling directory (`npm install playwright` there), set `NODE_PATH` to its `node_modules`, and set `BROWSER_NODE` to the absolute Node executable. Then rerun `manage.py test`. For Playwright-managed Chromium, install it (`npx playwright install chromium`) and set `BROWSER_CHANNEL=chromium`. Screenshots are written to ignored `test-results/`. The browser uses a session created solely inside Django's isolated automated test; this test does not use the separate local development login. See [STATUS.md](../STATUS.md) for actual results and unverified checks.

## Journal behavior

The homepage defaults to today in Asia/Manila. Tap the compact date button → choose a day → Go to date to filter by event date (not submission time). Previous/next links move one day; Show all dates uses ?all=1. Entries and the author’s drafts are filtered together. Drafts are listed in a private dialog, and Access info explains the current expiry policy on demand. Native dialogs support focus containment, Escape dismissal, explicit close controls, and trigger-focus restoration. The date form and draft links have a noscript fallback. Write an entry uses the selected date, so missed days can be recorded later. To revise, open an entry and use Edit your entry; authorship, audience, history, conflict, and revision rules still apply.

- Sign in → Write an entry → Save draft when useful → Review audience → Confirm & submit.
- New school and therapy entries have an event date, summary, observations, what helped, and optional follow-up. A nonempty summary is required to submit. Each text field is limited to 10,000 characters; comments to 5,000.
- Drafts are visible only to their author, including when the viewer is the parent. The parent reads all submitted entries. Only a professional author edits their own entry while access is permitted. Parent/owner accounts can read, comment, and manage access but cannot create or revise journal entries; the rule is enforced by the server, including legacy owner-authored records.
- New entries default to **Care team**, with an explicit audience review. Existing Parent + author entries retain their audience. Comments inherit the entry's current audience. Only submitted entries accept comments.
- Membership joining time is the approval time. History access initially starts at that time. Professional access, including authors’ own submitted entries by default, ends at the configured deadline; other care-team entries must have an original submission timestamp at or after their history start. Backdating an event date or later widening an audience does not grant old history. Owners can deliberately adjust history access. Role and access changes apply on the next authenticated request, including existing sessions. Owners cannot revoke/demote themselves.
- Submitted edits preserve the previous content, audience, event date, and timestamps. Previous versions are visible only to the parent and author, so an earlier private version is not exposed by later sharing. The timeline labels entries as revised only when a submitted revision exists.
- Draft saves are explicit, not automatic. Status becomes **Saved** only after a successful server response. Typing during an in-flight save leaves the newer text marked unsaved. Network errors and conflicts retain text in the open editor. Submission retries use a signed review ticket and an operation UUID; row locks and version numbers reject stale writes. After an ambiguous timeout, retry the same confirmation or reload the server entry before making another edit.
- Timestamps are timezone-aware and displayed in Asia/Manila. Event dates are independent of submission time. Review tickets expire after one hour. All private screens disable HTMX history snapshots; HTMX is otherwise unnecessary for this milestone.
- No private content is put in localStorage, IndexedDB, or a service-worker cache. The worker caches only explicitly selected public assets, including the theme script. Dynamic pages, auth, redirects, and private endpoints are network-only with no-store headers. Generic offline navigation contains no journal content. Installation instructions are available at `/install/`.

## Owner-controlled data access

**Data access** offers a fixed Asia/Manila deadline (`access_until`) or, when blank, a rolling number of days after original submission (`access_days`, initially 30). The owner keeps all submitted history. Author access also expires by default; the owner can change that option. Drafts never become visible to others.

Each submitted entry has an optional `professional_access_until` override. An owner can restore access until a chosen date, hide it immediately, or clear the override to return to the global policy. An override changes expiry only; it cannot bypass audience, historical membership boundaries, or revocation. Read, list, date-filter, comment, edit, and publish endpoints all enforce the policy, including existing sessions and HTMX requests. A professional can still submit a draft when access is closed, but is redirected to the timeline rather than to an inaccessible detail page. Revisions never reset the original submission timestamp.

`create_dev_user <username> --role teacher|therapist|owner --name "Display name"` creates another named local test account and prompts for its password. It requires development mode and never overwrites an existing account. `create_dev_owner` remains compatible with the earlier setup commands. Actual local test-account credentials live under ignored `.local/`, not in this public guide.

## Light and dark mode

Careloop follows the device’s light/dark preference initially. The header toggle switches mode; a `careloop_theme` cookie remembers only `light` or `dark` for one year on that browser. It contains no identity or journal content and uses SameSite=Lax plus Secure on HTTPS. No localStorage or IndexedDB is used. Theme CSS covers timeline cards, entry forms, native date inputs, badges, notices, and owner controls. Without JavaScript, the device color scheme still applies. The theme script is public and included in the static cache allowlist.

## Architecture

`journal/policies.py` centralizes visibility and author/owner policies; every entry/comment endpoint applies them. `journal/middleware.py` checks active membership on every authenticated request and sets dynamic no-store headers. `journal/adapters.py` gates Google admission and binds identities transactionally. `journal/services.py` serializes writes with PostgreSQL row locks, version checks, and revision snapshots. Review tickets bind content, audience, author, entry, version, and retry token with Django signing. No Django admin is exposed. The explicitly enabled native development login is restricted to marked test accounts and explicitly allowed development networks; production uses Google. `STATUS.md` tracks completed work and deployment acceptance checks.
