# Status — 2026-11-05

## Implemented

- Owner-controlled expiry: Data access offers a fixed Asia/Manila deadline date/time picker or a rolling access-days setting (30 initially). Defaults include authors’ own submitted entries. Per-entry deadlines restore/limit access, Hide now closes it, and clearing an override returns to global rules. Owner submitted-history access never expires; drafts remain author-only.
- New entries default to Care team after the user’s revised sharing request. Existing Parent + author audiences are preserved. Expiry is enforced in lists, date filters, direct detail, edit, comment, publish, and server write policies. Existing sessions obey changes on their next request; revisions do not restart the original clock.
- Generic create_dev_user command supports teacher, therapist, and owner roles; create_dev_owner remains compatible. Local named teacher and therapist accounts created, with explicitly granted history access to the existing shared fictional samples. Their credentials are in ignored .local/professional-accounts.txt, excluded from Git.

- Date navigation added: Find a date / Go to date filters submitted entries and the current author’s drafts by event date. Show all dates clears the filter. Write an entry on a selected day prefills its event date for missed entries. Existing authorship, audience, and history rules remain enforced.

- Product renamed to Careloop across the app header, browser titles, PWA manifest, and public cache name. README reorganized around usage and setup, with detailed development/deployment guides under docs/. All 23 PostgreSQL/browser tests, Django checks, static collection, documentation link targets, and branding checks passed after the rename.

- Django 5.2.19 LTS, PostgreSQL, pinned dependencies, migrations, responsive templates, Docker/Compose, and deployment/recovery documentation.
- Production Google admission: approved exact email, provider verification, subject binding, owner bootstrap, role/history/access controls, and per-request revocation.
- Private author drafts, parent access to submitted entries, explicit audience review, comments, author-only edits, revisions, idempotent submission, version conflicts, and stale-draft protection.
- PWA manifest/icons/install help, explicit public-only cache, dynamic no-store headers, no HTMX history snapshots, memory-only unsaved text.
- User explicitly authorized local development username/password login after the original milestone. Added marked development accounts, opt-in configuration, loopback-default login with explicit private-LAN opt-in, production startup guard, and existing-session invalidation when disabled. Production remains Google-only.

## Running local setup

- Native PostgreSQL 17.11 from EDB's official binary archive is running on 127.0.0.1:55432 with SCRAM authentication. Binaries/data/backups live under ignored .local; no system service or public DB port was created.
- Native Django development server now listens on 0.0.0.0:8000 for user-requested phone testing. Desktop URL http://127.0.0.1:8000; same-LAN phone URL http://192.168.99.95:8000. DEV_LOGIN_NETWORKS is explicitly 192.168.99.0/24 in untracked .env. A Private-profile firewall rule allows only that subnet to this LAN IP on TCP 8000. Server restarted with network-enabled execution permission; the execution sandbox previously blocked incoming LAN connections. LAN URL returns HTTP 200 from the PC; user confirmed the app now opens on their phone. Sign in at /development/login/ as test-parent (display name Test Parent). Generated password: ignored .local/development-account.txt. Secrets were generated in ignored .env without printing values.
- Both migrations applied to persistent PostgreSQL. Three disabled fictional sample identities/entries seeded; real-server browser smoke created one additional fictional home entry.
- Restart/management commands are in README's native-development section. Compose overrides the native DB host/port for its container database.

## Actual verification

- Latest run: 47 tests passed against PostgreSQL, zero skipped, including real headless Chrome, concurrent entry writes, and all review regressions. Django system checks and migration-drift checks passed; static assets collected successfully.
- Development tests cover named login, explicitly allowed LAN clients, denied out-of-subnet sessions, forwarded-header spoofing, disabled-mode sessions, revoked accounts, Google-account exclusion, and production denial. The full 30-test run completed with clean test-database teardown after fixing worker threads to explicitly close persistent connections.
- Separate real-server Chrome smoke passed actual named password login, owner controls, draft save, audience review, submit, named authorship, mobile layout, logout, and anonymous-entry denial. Screenshot test-results/named-account-timeline.png visually inspected.
- Browser suite also verified reload persistence, offline failed saves with retained text, reconnect/retry, comments, revisions, public-only cache contents, generic offline navigation, and no JavaScript errors.
- Actual PostgreSQL backup/restore verified into a unique throwaway DB: migration/Django checks passed; record counts and SHA-256 digests of entries, memberships, revisions, comments, and users matched exactly. Dump: .local/backups; report: .local/restore-report.json. Verification DB removed; original DB unchanged.
- Django checks, migration-drift check, Python compilation, static collection, and dependency check passed. Earlier SQLite-only results are superseded by PostgreSQL verification.
- Prior production-style check --deploy: no errors, two documented HSTS subdomain/preload warnings. Proxy behavior still needs the target environment.

- Date-navigation verification: all 36 PostgreSQL tests passed, including a mobile Chrome workflow finding an earlier entry, revising it with previous-version preservation, adding a missed-day draft, empty-day messaging, and clearing the filter. Server tests cover invalid dates, event/submission date separation, and private/history restrictions including HTMX requests. Migration check reported no changes. Mobile screenshot inspected.

- Access-control verification: all 47 tests passed against PostgreSQL, including the mobile owner deadline picker, both professional roles losing and regaining access, Hide now, author expiry, audience/history/revocation precedence, exact expiry boundary, direct/HTMX endpoint denial, and revision clock preservation. Actual named teacher/therapist logins verified against the running app; each saw shared fictional entries and was denied owner controls. Migration 0003 applied locally; no migration drift. Backup/restore content digests matched, now including JournalAccessSettings.

## Review fixes

- All three review findings are fixed:
  - Unchanged displayed history-start values retain stored seconds/microseconds; role changes preserve historical denial, and deliberate history changes still work.
  - Membership updates recheck the acting owner's current authority under the row locks. Simultaneous demotion/revocation tests confirm one succeeds, the stale request is denied, and an authorized owner remains. Updates also preserve identity bindings established by a concurrent first Google login.
  - Confirming submission disables Back to edit and duplicate confirmation until success or failure. Browser regression covers delayed success and failed requests, restoring editing with the original text retained after failure.
- Regression tests were first run against the previous code and reproduced all three failures, then passed after fixes. Tests live in journal/tests/test_membership.py, test_concurrency.py, test_browser.py, and submission.cjs. Earlier ignored review reproduction scripts describe the pre-fix behavior.

## Pending

- Google credentials/real owner Google email remain unconfigured. Actual OAuth is unverified; provider tests use mocked identities. Named-account testing exercises the separately authorized development login.
- Docker and WSL are absent. Compose image build/startup and Linux Gunicorn remain unverified. Local PostgreSQL and backup/restore checks are complete.
- Linux VM/domain/proxy, HTTPS behavior, secure cookies, off-machine backup storage, and physical iPhone/Android installation need deployment configuration.
- Before production: DEV_LOGIN_ENABLED=false, DEBUG=false, real Google credentials/secrets, correct host/CSRF/proxy settings, and deployment acceptance checks. Do not use the development server or credentials for real child records.
- Draft saving is explicit; history starts at approval; old versions remain limited to parent and author.
