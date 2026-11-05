# Status — 2026-11-05

## Implemented

- Django 5.2.19 LTS, PostgreSQL, pinned dependencies, migrations, responsive templates, Docker/Compose, and deployment/recovery documentation.
- Production Google admission: approved exact email, provider verification, subject binding, owner bootstrap, role/history/access controls, and per-request revocation.
- Private author drafts, parent access to submitted entries, explicit audience review, comments, author-only edits, revisions, idempotent submission, version conflicts, and stale-draft protection.
- PWA manifest/icons/install help, explicit public-only cache, dynamic no-store headers, no HTMX history snapshots, memory-only unsaved text.
- User explicitly authorized local development username/password login after the original milestone. Added marked development accounts, opt-in configuration, loopback-only login, production startup guard, and existing-session invalidation when disabled. Production remains Google-only.

## Running local setup

- Native PostgreSQL 17.11 from EDB's official binary archive is running on 127.0.0.1:55432 with SCRAM authentication. Binaries/data/backups live under ignored .local; no system service or public DB port was created.
- Native Django development server running at http://127.0.0.1:8000. Sign in at /development/login/ as test-parent (display name Test Parent). Generated password: ignored .local/development-account.txt. Secrets were generated in ignored .env without printing values.
- Both migrations applied to persistent PostgreSQL. Three disabled fictional sample identities/entries seeded; real-server browser smoke created one additional fictional home entry.
- Restart/management commands are in README's native-development section. Compose overrides the native DB host/port for its container database.

## Actual verification

- 23 tests passed against PostgreSQL, zero skipped, including real headless Chrome and simultaneous duplicate/conflicting writes. Log: test-results/postgres-tests.txt (ignored).
- Development tests cover named login, disabled-mode sessions, revoked accounts, nonlocal clients, Google-account exclusion, and production denial.
- Separate real-server Chrome smoke passed actual named password login, owner controls, draft save, audience review, submit, named authorship, mobile layout, logout, and anonymous-entry denial. Screenshot test-results/named-account-timeline.png visually inspected.
- Browser suite also verified reload persistence, offline failed saves with retained text, reconnect/retry, comments, revisions, public-only cache contents, generic offline navigation, and no JavaScript errors.
- Actual PostgreSQL backup/restore verified into a unique throwaway DB: migration/Django checks passed; record counts and SHA-256 digests of entries, memberships, revisions, comments, and users matched exactly. Dump: .local/backups; report: .local/restore-report.json. Verification DB removed; original DB unchanged.
- Django checks, migration-drift check, Python compilation, static collection, and dependency check passed. Earlier SQLite-only results are superseded by PostgreSQL verification.
- Prior production-style check --deploy: no errors, two documented HSTS subdomain/preload warnings. Proxy behavior still needs the target environment.

## Pending

- Google credentials/real owner Google email remain unconfigured. Actual OAuth is unverified; provider tests use mocked identities. Named-account testing exercises the separately authorized development login.
- Docker and WSL are absent. Compose image build/startup and Linux Gunicorn remain unverified. Local PostgreSQL and backup/restore checks are complete.
- Linux VM/domain/proxy, HTTPS behavior, secure cookies, off-machine backup storage, and physical iPhone/Android installation need deployment configuration.
- Before production: DEV_LOGIN_ENABLED=false, DEBUG=false, real Google credentials/secrets, correct host/CSRF/proxy settings, and deployment acceptance checks. Do not use the development server or credentials for real child records.
- Review reran all 23 PostgreSQL tests successfully. Three additional isolated reproductions confirmed uncovered defects (application fixes pending):
  - Existing-member datetime input truncates history-start seconds; a role-only update unintentionally made a previously denied entry readable (404 to 200).
  - Two concurrent owners can demote each other, leaving zero active owners despite the row locks.
  - Back to edit remains enabled during submission; typing new text before the pending submission redirects causes that newer text to disappear.
- Reproduction scripts are under ignored .local/review_cases.py and .local/review_browser.cjs. They use a separate Django test database and fictional identities.
- Draft saving is explicit; history starts at approval; old versions remain limited to parent and author.
