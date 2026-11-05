# Careloop

A private daily journal that helps a child's parent, teachers, and therapists share the moments that matter.

Write about school, therapy, or home. Save a private draft, choose who can read it, and review the audience before submitting.

## What you can do

- Record a daily summary, observations, what helped, and any follow-up.
- Read submitted entries in a timeline grouped by event date.
- Comment on entries you can access.
- Revise your own entries while preserving previous submitted versions.
- Approve care-team members, assign roles, and revoke access as the owner.
- Install Careloop on a phone's home screen.

Careloop uses Django 5.2 LTS, PostgreSQL 17, server-rendered templates, and a small amount of JavaScript. It needs an internet connection; private entries are never cached for offline reading. Times are displayed in Asia/Manila.

## Who can see what?

| Content | Who can read it? |
| --- | --- |
| Draft | Its author only |
| Parent + author entry | Its author and the parent |
| Care-team entry | Its author, the parent, and approved professionals within their allowed history |
| Comments | Anyone who can read the entry |
| Previous versions | The author and parent only |

**Parent + author** is the default audience. Only authors can edit their entries. New professionals start without past shared history; the owner can deliberately adjust their history access.

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

See the [development guide](docs/development.md) for local accounts, testing, and backup verification.

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

Optional fictional sample entries are available with `docker compose exec web python manage.py seed_fictional` while `DEBUG=true`. Their sample identities cannot sign in.

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

The last full PostgreSQL run passed **23 tests**, including the browser workflow and concurrent-write tests. Local backup/restore verification also passed.

Three reproduced review findings still need fixes: history timestamps can be rounded earlier during membership edits, concurrent owner changes can leave no owner, and returning to edit during a pending submission can discard newer text. Actual Google sign-in, Docker image startup, and production HTTPS remain unverified. Check [STATUS.md](STATUS.md) for the current details before using real child data.

## Deployment and maintenance

Read the [deployment guide](docs/deployment.md) for Google callback URLs, HTTPS and proxy settings, database isolation, backups, and restore verification.

For production, disable development login and debug mode, configure real Google credentials and your domain, and run the documented deployment checks. Keep `.env`, `.local`, credentials, databases, and backups out of Git.

Attachments, notifications, reminders, PDF export, analytics, rich-text editing, and offline synchronization are outside this version.
