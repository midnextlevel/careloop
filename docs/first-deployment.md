# First deployment in the browser

Use this for a **fresh VM and empty Careloop database**. Existing installations keep their current owner and Google configuration; the deployment wizard stays locked when memberships or a Google SocialApp already exist, including revoked accounts.

## Prepare the VM

Prerequisites: Python 3, Git, Docker Engine with Compose, a domain resolving to your reverse proxy, and a valid HTTPS certificate. For Nginx Proxy Manager, forward that domain to the Careloop backend on port 8000 and set the upload limit to 26 MB. See [network and proxy configuration](deployment.md#production-on-a-linux-vm).

```sh
git clone https://github.com/midnextlevel/careloop.git
cd careloop
sudo python3 tools/first_run.py --origin https://careloop.example.com
```

Replace the example origin with your exact Careloop HTTPS origin. The helper creates a protected `.env` with random application/database secrets, production settings, and a hash of a private deployment code. It prints the code **once in your terminal**, then builds the image, starts PostgreSQL, applies migrations and starts Careloop. Keep the code private; it is valid for 24 hours and is never put in a URL. Existing `.env` files are never overwritten.

The default Compose port is `127.0.0.1:8000`, for a proxy on the same VM. For a **separate NPM VM**, use `--prepare-only` first, configure the backend binding and source restrictions, then start the containers with the commands below. Allow only your exact NPM host addresses to reach the backend; configure both local and public NPM addresses if you use two proxies. Configure DNS and the two proxy hosts consistently.

```sh
sudo python3 tools/first_run.py --origin https://careloop.example.com --prepare-only
# Configure the protected LAN binding for your remote reverse proxy here.
sudo docker compose build
sudo docker compose up -d db
sudo docker compose run --rm -T --interactive=false web python manage.py migrate --noinput
sudo docker compose up -d web
```

Choose **one** preparation command. If building or starting fails after settings were created, keep your printed code and resume with the Docker commands; do not replace the `.env` or database. The HTTPS proxy must set Host and overwrite X-Forwarded-Proto, and disable dynamic-route caching.

## Complete the wizard

1. Visit `https://your-careloop-domain/deployment/`. The sign-in page also sends a fresh installation here.
2. Enter the private deployment code from the VM terminal. The unlocked browser session lasts 30 minutes.
3. Enter the first owner's exact Google email and the child's first name or nickname.
4. Create a **Web application** OAuth client in Google Auth Platform. The wizard displays the exact origin and callback URI to copy. If Google is in Testing mode, add the owner as a Google test user.
5. Paste the client ID and secret into the wizard and select **Finish deployment**. The secret is never echoed back into the form or confirmation page.
6. Sign in with the approved owner Google account. Review the child's journal setup and approve teachers/therapists through Care team. They fill in their school or therapy center through My profile.

Completing deployment approves an email; Google must still verify that identity. Knowing the setup code does not create a signed-in owner session. Once completed, the wizard returns 404 and cannot be used to replace the owner, even if their account is later deactivated. A second browser session cannot finish deployment again.

## Credentials and recovery

Browser-configured Google credentials are stored in the private PostgreSQL `SocialApp` record used by django-allauth. Backups therefore contain the Google client secret as well as private journal data: protect them accordingly. Keep Google credentials out of source control. Environment-configured installations continue using `.env`; use only one Google configuration source per deployment.

For a browser-configured installation that needs a corrected Google secret, use the VM console:

```sh
sudo docker compose exec web python manage.py configure_google
```

The command prompts privately, validates the client ID, and updates only the Google application credentials. It requires an existing owner and refuses to run when credentials are environment-configured; edit the protected `.env` and recreate web for those installations.

The setup code and unlocked session expire. A VM administrator can extend `DEPLOYMENT_CODE_EXPIRES` in the protected `.env` and recreate web if the original private code is still known. If the code is lost before completion, generate a new random code and SHA-256 hash on the VM, replace the hash/expiry in `.env`, and recreate web. Membership and completion checks still prevent reopening an established installation. Never delete an existing database to recover sign-in.
