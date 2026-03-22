import os

from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------

DEBUG = False

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ['SECRET_KEY']

_allowed_hosts_raw = os.environ.get('ALLOWED_HOSTS', '')
if not _allowed_hosts_raw.strip():
    raise ImproperlyConfigured("ALLOWED_HOSTS environment variable is required in production.")
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_raw.split(',') if h.strip()]

# ---------------------------------------------------------------------------
# HTTPS / cookie security
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', '1').lower() in ('1', 'true', 'yes')
# Start with a short HSTS max-age; increase to 31_536_000 after verifying HTTPS works correctly.
SECURE_HSTS_SECONDS = 300
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT

# ---------------------------------------------------------------------------
# CSRF trusted origins
# ---------------------------------------------------------------------------

_csrf_origins_raw = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if not _csrf_origins_raw.strip():
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS environment variable is required in production.")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_raw.split(',') if o.strip()]

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]
