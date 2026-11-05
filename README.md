# Careloop

A private daily journal that helps a child's parent, teachers, and therapists share the moments that matter.

Teachers and therapists write about school and therapy. Parents follow the shared timeline and manage access. Professionals save private drafts and review the audience before submitting, with Care team selected by default.

## What you can do

- Teachers and therapists record a daily summary, observations, what helped, and any follow-up.
- Parents review their child’s behaviour outside home, discuss entries, and manage access; they do not create or revise journal entries.
- Read submitted entries in a timeline grouped by event date.
- Comment on entries you can access.
- Revise your own entries while preserving previous submitted versions.
- Approve care-team members, assign roles, and revoke access as the owner.
- Switch between light and dark mode; your device preference is used initially.
- Install Careloop on a phone's home screen.

Careloop uses Django 5.2 LTS, PostgreSQL 17, server-rendered templates, and a small amount of JavaScript. It needs an internet connection; private entries are never cached for offline reading. Times are displayed in Asia/Manila.

## Who can see what?

| Content | Who can read it? |
| --- | --- |
| Draft | Its author only |
| Parent + author entry | The parent, and its author while professional access is allowed |
| Care-team entry | The parent and approved professionals within their allowed history and access deadline |
| Comments | Anyone who can read the entry |
| Previous versions | The parent, and the author while they can access the entry |

**Care team** is the default audience for new entries. Existing Parent + author entries retain their audience. Drafts remain private. Only teachers and therapists can create entries or revise their own accessible entries. Their new posts default to sharing with all three care-team members, subject to owner access controls. New professionals start without past shared history; the owner can deliberately adjust it.

## Control access as the owner

Open **Data access** and either choose a fixed deadline with the date picker or leave it blank and set a number of days after submission (30 by default). Access expires for teachers and therapists, including their own submitted entries; owner access remains available. Changing these settings affects existing and new entries on the next request.

To restore or close access to a particular entry, open it as owner and use its **Data access** panel. Set a new deadline, choose **Hide now**, or clear the deadline to use the journal-wide setting. Entry-specific deadlines take precedence over the global deadline. Audience and membership history restrictions still apply, and editing an entry does not restart its original submission clock.

## Find or revise an earlier day

1. The journal opens on **today** (Asia/Manila). Tap the date in the compact toolbar, choose another day, and select **Go to date**. Previous/next arrows move one day at a time.
2. Open the entry and choose **Edit your entry**. Only its author can revise it.
3. Make the changes, review the audience, and submit. The previous submitted version is preserved.

To add an entry for a missed day, select that date and choose **Write an entry**. The event date is filled in for you. **Show all dates** returns to the full timeline. Open **Drafts** to see your private drafts for that day. **Access info** explains the active expiry rule in a dialog; it is informational, not an account error. Entry-specific owner access controls also open in a dialog. The same privacy and history-access rules apply.

## Try the existing local setup

On the Windows machine where this project was prepared:

1. Open [Careloop](http://127.0.0.1:8000/development/login/).
2. Sign in as **test-parent** (display name **Test Parent**).
3. Find the generated password in `.local/development-account.txt`.

The password, local database, and sample content are **not included in this repository**. This login only works locally when development mode is explicitly enabled. Use fictional data for testing.

If the local services have stopped, run these commands from the project folder in PowerShell. Skip the first command if PostgreSQL is already running.

```powershell
.\.venv\Scripts\python.exe tools\local.py start
.\.venv\Scripts\python.exe tools\local.py manage runserver 127.0.0.1:8000 --noreload
```

See the [development guide](docs/development.md) for local accounts, [phone testing over Wi-Fi](docs/development.md#test-on-a-phone-over-wi-fi), and backup verification.

## Quick start with Docker

For a fresh installation, you need Docker with Compose v2 and Google OAuth credentials. Production sign-in uses approved Google accounts.

```sh
git clone https://github.com/midnextlevel/careloop.git
cd careloop
cp .env.example .env
```

On PowerShell, use `Copy-Item .env.example .env` for the last command. Edit `.env` before continuing:

| Setting | Value to provide |
| --- | --- |
| `SECRET_KEY` | A long, random secret |
| `POSTGRES_PASSWORD` | A strong, unique database password |
| `GOOGLE_CLIENT_ID` | Your Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Your Google OAuth client secret |
| `CHILD_NAME` | The child's display name |

Follow the [Google sign-in setup](docs/deployment.md#google-sign-in), then start Careloop:

```sh
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py bootstrap_owner your.exact.email@gmail.com
docker compose up -d web
```

Open [localhost:8000](http://localhost:8000), sign in with the approved Google email, and use **Care team** to approve others. The bootstrap command approves an email; it does not create a password. For an existing database with an owner, approve new users through **Care team** instead.

Optional fictional sample entries are available with `docker compose exec web python manage.py seed_fictional` while `DEBUG=true`. Their sample identities cannot sign in. New seed runs create teacher and therapist observations only; older demo home entries are preserved as historical records.

## Run the tests

With the native Windows setup:

```powershell
.\.venv\Scripts\python.exe tools\local.py manage test --verbosity 2
```

With Docker:

```sh
docker compose run --rm -e JOURNAL_TESTING=1 web python manage.py test --verbosity 2
```

The tests use a separate database. Browser tests require optional Playwright configuration; without it, that test is skipped. See the [testing instructions](docs/development.md#tests-and-checks) for browser tests, startup checks, and a test-only SQLite fallback.

## Current status

The last full PostgreSQL run passed **52 tests**, including the browser workflow and concurrent-write tests. Local backup/restore verification also passed.

The three earlier review findings are fixed and covered by regression tests: membership edits preserve exact history timestamps, concurrent owner updates retain an authorized owner, and pending submissions prevent returning to edit until completion or failure. Actual Google sign-in, Docker image startup, and production HTTPS remain unverified. Check [STATUS.md](STATUS.md) for the current details before using real child data.

## Deployment and maintenance

Read the [deployment guide](docs/deployment.md) for Google callback URLs, HTTPS and proxy settings, database isolation, backups, and restore verification.

For production, disable development login and debug mode, configure real Google credentials and your domain, and run the documented deployment checks. Keep `.env`, `.local`, credentials, databases, and backups out of Git.

Attachments, notifications, reminders, PDF export, analytics, rich-text editing, and offline synchronization are outside this version.
