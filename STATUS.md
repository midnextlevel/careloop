# Careloop status — 2026-11-06

## Current implementation

- First-login owner setup wizard saves the child's display name in the database and reviews approved professionals; it can be reopened from Menu. Professional profiles store display name and school/therapy center, editable by their author or the owner. Self-service forms cannot change roles, email identities or access settings. Anonymous pages omit the configured child name. Migration 0006 adds these fields without replacing existing memberships or access policy.

- Phone UI reviewed at 320, 360, 390, 430, 768 and 1280 px. Supplied logo prepared for light/dark headers, favicon and installed-app icons. Header navigation moved into an accessible Menu dialog; Today/all-history shortcuts are in the date dialog, Access info in Menu. The 390 px timeline begins around 298 px instead of 595 px. Header is 72 px instead of 167 px. Touch controls retain at least 44 px targets; writing buttons retain 48 px height and a 12 px gap. Date/type share a row; Save/Review stay reachable together. Desktop date control stays bounded. Public service-worker allowlist includes only the new brand asset alongside existing public files, with a cache version bump.

- Entry-type rules updated: teachers have School only; therapists default to Therapy center with School also available; owners default to Home with all three choices. Central policy supplies form options and enforces write permissions, including revalidation of signed publish reviews. All 64 PostgreSQL/browser tests passed; new tests cover allowed lists, therapist School posts, and forged save/review/publish/service requests. Migration 0005 changes the therapy display label without changing stored values or historical records.

- Django 5.2.19 LTS + PostgreSQL 17, pinned dependencies, migrations, Docker/Compose, fictional samples, and setup/deployment/recovery guides.
- Parent/owner posting restored at the user's request. All three roles can write and revise only their own accessible entries. Owner defaults to Home, teacher to School, therapist to Therapy. New entries default to Care team; existing private audiences remain unchanged. Owner can read all submitted history and only their own drafts.
- Optional photos: maximum two selected photos per entry/version, validated server-side. JPEG/PNG/WebP still images up to 12 MB and 40 MP each are decoded, orientation-corrected, stripped of metadata, resized to at most 1600px, and re-encoded as JPEG at most 512 KB. Originals and filenames are not retained.
- Optimized photo bytes are immutable private PostgreSQL records. Authenticated photo endpoints enforce entry visibility, draft privacy, audience, membership history, revocation, and professional expiry. Staged review uploads are author-only; previous-version photos are parent/author-only. Photos are never service-worker cached. Old unreferenced staging uploads can be pruned after 24 hours without removing current/revision photos.
- Owner Data access: fixed Asia/Manila deadline picker or rolling days (30 initially), including professionals' own submitted entries by default. Individual deadlines restore/hide access; revisions do not restart the clock. Owner access does not expire.
- Comments, private drafts, explicit audience review, immutable submitted-version snapshots, idempotent publishing, version conflicts, and stale-draft protection.
- Compact today-first timeline, date navigation/all history, private drafts/date/access dialogs, accessible touch spacing, numbered entry form, optional follow-up, light/dark theme. Only a UI theme cookie is persisted client-side; journal text/photos remain memory-only in the browser.
- Production Google-only approved-email/verified-identity/subject-binding flow, owner bootstrap/team management, and membership checks on every authenticated request. Explicit development password login supports marked local/LAN test identities only.

## Running locally

- PostgreSQL 17.11 on 127.0.0.1:55432; private development server on 0.0.0.0:8000. Desktop: http://127.0.0.1:8000; same-LAN phone: http://192.168.99.95:8000. User confirmed phone access.
- Development LAN explicitly limited to 192.168.99.0/24 in ignored .env; Windows firewall allows only this subnet to the LAN IP/port on Private profile. Database stays loopback-only. Server uses network-enabled execution permission so the tool sandbox does not block incoming phone requests.
- Owner test-parent and professional teacher/therapist accounts remain available. Credentials, database, backups, screenshots and test artifacts are ignored under .local/.env/test-results; never commit them. Local professional sample history was explicitly granted for testing.
- Journal migrations through 0005 applied. New photo data is in PostgreSQL, so no public media route or extra Docker storage volume is needed.

## Actual verification

- Full PostgreSQL suite: 64 tests passed, zero skipped. Browser photo test rerun successfully after adding explicit checks that private photo URLs are absent from the service-worker cache.
- Latest phone UI checks also cover header wrapping, horizontal overflow, loaded logo, touch target dimensions, date/history navigation, nested modal focus restoration, and the entry form at 320 px. Real named development-owner login, menu controls, history, theme, logout, and anonymous denial passed separately.
- Tests cover two-photo limits including replacements, invalid/oversized uploads, orientation/metadata/size optimization, draft and staged-upload privacy, audience/history/expiry/revocation, revision-photo preservation, cross-entry ID forgery, stale edits, retry-safe publishing, and cleanup retaining referenced history.
- Mobile Chrome photo workflow: owner Home entry, two uploads, failed offline save retaining file inputs, reconnect/save confirmation, cleared upload controls, review without duplicate uploads, submit, photo rendering/no-store headers, removal in revision, and previous photos retained. Existing dark-mode, date, access-control, modal, touch-spacing and concurrency tests also passed.
- Actual named-owner browser login exercised the same two-photo workflow against the local app using fictional image content. It produced a clearly fictional Home test entry, two private optimized photos, and a revision. Entry/photo screenshots generated under ignored test-results.
- PostgreSQL backup/restore verified with photo data: source/restored counts and digests match for entries, memberships, revisions, comments, users, access settings, and EntryPhoto binary content. Restored database passed migration/system checks and was removed after verification; original database unchanged.
- Django checks, migration-drift check, Python compilation, dependency check, and static collection passed. Earlier review defects (history rounding, concurrent owner removal, pending-submit text loss) remain covered and fixed.

## Remaining configuration / limits

- Production Ubuntu VM now has Docker/Compose, PostgreSQL and Gunicorn running. Linux image build/migrations passed; 58 Linux tests passed with six browser tests skipped there. Production uses fresh protected secrets with DEBUG/development login disabled; database port is unpublished and the backend is restricted to the designated Nginx Proxy Manager. Direct HTTPS through the public proxy reaches the app. The user's network has separate local/public proxies; its local DNS route needs independent verification.
- First production owner email approved. Actual Google OAuth remains unverified while setup is in progress. Provider tests use mocked identities; development logins do not replace Google integration checks. Off-machine backup storage, full HTTPS/cookie checks and physical PWA installation remain deployment acceptance tasks.
- HEIC/HEIF, SVG, video, animation, and non-photo attachments are unsupported. Use a compatible still photo. Storage grows with retained photo revisions; schedule prune_unused_photos for abandoned staging uploads. Production proxy upload limit: 26 MB.
- Production must disable DEV_LOGIN_ENABLED and DEBUG, configure real Google credentials/secrets and trusted hosts/proxy/CSRF origins, and complete deployment checks. Use fictional data on the HTTP development server.
