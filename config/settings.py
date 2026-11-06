import os
from ipaddress import ip_network
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
TESTING = os.getenv('JOURNAL_TESTING') == '1'
DEV_LOGIN_ENABLED = os.getenv('DEV_LOGIN_ENABLED', 'false').lower() == 'true'
if DEV_LOGIN_ENABLED and not DEBUG:
    raise ImproperlyConfigured('DEV_LOGIN_ENABLED requires DEBUG=true. Disable it for production.')
try:
    DEV_LOGIN_NETWORKS = tuple(ip_network(value.strip()) for value in
                              os.getenv('DEV_LOGIN_NETWORKS', '').split(',') if value.strip())
except ValueError as exc:
    raise ImproperlyConfigured('DEV_LOGIN_NETWORKS must contain valid CIDR subnets.') from exc
if any(not network.is_private for network in DEV_LOGIN_NETWORKS):
    raise ImproperlyConfigured('DEV_LOGIN_NETWORKS must be private networks, never public ranges.')
SECRET_KEY = os.getenv('SECRET_KEY', '')
if not SECRET_KEY:
    if TESTING:
        SECRET_KEY = 'test-only-key-not-for-deployment'
    else:
        raise ImproperlyConfigured('Set SECRET_KEY; see .env.example (Compose reads .env).')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = list(filter(None, os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')))
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles',
    'allauth', 'allauth.account', 'allauth.socialaccount',
    'allauth.socialaccount.providers.google', 'journal',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'journal.middleware.MembershipMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages', 'journal.context.site',
    ]}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.getenv('POSTGRES_DB', 'journal'), 'USER': os.getenv('POSTGRES_USER', 'journal'),
    'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''), 'HOST': os.getenv('POSTGRES_HOST', 'db'),
    'PORT': os.getenv('POSTGRES_PORT', '5432'), 'CONN_MAX_AGE': 60,
}}
# SQLite is available ONLY for fast automated tests where PostgreSQL is unavailable.
if TESTING and os.getenv('TEST_SQLITE') == '1':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'test.sqlite3'}}
AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend', 'allauth.account.auth_backends.AuthenticationBackend']
ACCOUNT_ADAPTER = 'journal.adapters.ClosedAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'journal.adapters.ApprovedGoogleAdapter'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*']
# Social-only mode has no local verification mail. The adapter requires a
# Google-verified email for every login, including already-bound accounts.
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_ONLY = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_PROVIDERS = {'google': {
    'APP': {'client_id': os.getenv('GOOGLE_CLIENT_ID', ''), 'secret': os.getenv('GOOGLE_CLIENT_SECRET', ''), 'key': ''},
    'SCOPE': ['openid', 'email', 'profile'], 'AUTH_PARAMS': {'access_type': 'online', 'prompt': 'select_account'},
    'OAUTH_PKCE_ENABLED': True,
}}
# A fresh deployment can configure the standard allauth SocialApp through the
# private wizard. Existing environment-configured installations keep working.
if not (os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')):
    SOCIALACCOUNT_PROVIDERS['google'].pop('APP')
DEPLOYMENT_CODE_HASH = os.getenv('DEPLOYMENT_CODE_HASH', '')
DEPLOYMENT_CODE_EXPIRES = int(os.getenv('DEPLOYMENT_CODE_EXPIRES', '0'))
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/welcome/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/login/'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_TZ = True
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 43200
SESSION_COOKIE_SECURE = not DEBUG and not TESTING
CSRF_COOKIE_SECURE = not DEBUG and not TESTING
SECURE_SSL_REDIRECT = not DEBUG and not TESTING
# Enable ONLY behind a proxy which strips incoming X-Forwarded-Proto and sets its own.
if os.getenv('TRUST_PROXY') == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000 if os.getenv('ENABLE_HSTS') == 'true' else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
CHILD_NAME = os.getenv('CHILD_NAME', 'Alex')
DATA_UPLOAD_MAX_MEMORY_SIZE = 26 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
