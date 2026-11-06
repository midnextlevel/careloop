# Deploying Careloop

Use the [README quick start](../README.md#quick-start-with-docker) for a fresh local installation. This guide covers Google sign-in and the Linux VM deployment.

For a fresh production VM, the [first-deployment browser wizard](first-deployment.md) handles initial owner approval and Google credentials using a private VM-generated code. The manual environment configuration below is an alternative; do not configure the same provider in both `.env` and a database SocialApp.

## Google sign-in

1. In Google Cloud, create/select a project and configure Google Auth Platform branding, audience/consent, and data access for `openid`, `email`, `profile`. Add permitted Google test users if the consent app is in testing mode.
2. Create an OAuth client with application type **Web application**. Add the site's exact origin, for example `http://localhost:8000` for development or `https://journal.example.com` for production.
3. Add these exact authorized redirect URIs for the environments you use:
   - `http://localhost:8000/accounts/google/login/callback/`
   - `https://journal.example.com/accounts/google/login/callback/`
4. Put the client ID and secret into `.env`, then recreate web: `docker compose up -d --force-recreate web`. Do not also create a database SocialApp: this app configures the provider through settings.
5. Bootstrap your exact owner email, sign in with that Google identity, and use **Care team** to approve other exact addresses and assign their roles. Approval is not an email invitation. Share the site URL separately.

Authentication uses allauth's OAuth code flow and PKCE, server-side sessions, provider-verified emails, and Google's stable subject identifier. Addresses are trimmed and lowercased only; dots, plus tags, and domains are never broadened. Existing accounts must continue to match both their approved email and bound Google subject. Provider tokens are not retained. Within the normal allauth flow, local signup and email/password login are disabled by social-only mode; local email verification is `none` because verification is required from Google in the custom adapter instead.

**Pending live integration:** mocked provider identity tests do not verify an actual Google authorization-code exchange. With credentials, verify owner login, approved professional login, unapproved and wrong-email denial, and revocation through an already-open session. This remains a deployment acceptance check.

## Production on a Linux VM

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
    client_max_body_size 26m;
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_redirect off;
    proxy_no_cache 1;
    proxy_cache_bypass 1;
}
```

The proxy must overwrite untrusted incoming `X-Forwarded-Proto`; only then enable `TRUST_PROXY=true`. Keep HTTP redirecting to HTTPS, forward the original host, and never permit direct public web access that can spoof proxy headers. Turn HSTS on only after HTTPS is verified. Django/WhiteNoise serves bundled public static assets. Private photo bytes are stored in PostgreSQL and served only through authenticated /entries/.../photos/... endpoints. Do not add a public media route. Configure the reverse proxy with client_max_body_size 26m for the multipart upload form.

Run `docker compose exec web python manage.py check --deploy` after setting production configuration. Verify HTTPS redirect, secure cookies, allowed-host rejection, correct CSRF behavior, actual Google login, revocation, and the mobile workflow before entering real child data. Deploy checks cannot establish that the surrounding proxy is configured correctly.

The deployment check reports W005/W021 because subdomain-wide HSTS and browser preload are not enabled by default. Enable Django's `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD` only after confirming that every affected subdomain supports permanent HTTPS and deciding to pursue browser preload. Ordinary HSTS is controlled separately by `ENABLE_HSTS`.

## Backup and recovery

For encrypted archives, restore verification, mounted off-VM destinations and daily scheduling, use the [backup helper guide](backups.md). The raw dump commands below remain useful for manual database administration.

These commands use a Linux shell on the VM. Never commit backups. Protect and encrypt backups, copy them off the VM to a restricted destination, and apply your retention policy. PostgreSQL dumps include private entries, photos, revisions, memberships, access settings, and sessions; keep `.env` separately in secure secret storage.

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
