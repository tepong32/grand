import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from .base import *


# Already set in base.py
BASE_DIR = Path(__file__).resolve().parent.parent.parent

def _required_environment(primary, *legacy_names):
    for name in (primary, *legacy_names):
        value = os.getenv(name)
        if value:
            return value
    aliases = ", ".join((primary, *legacy_names))
    raise ImproperlyConfigured(f"Production requires one of these environment variables: {aliases}")


def _comma_separated_environment(name, defaults=()):
    raw = os.getenv(name, "")
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return values or list(defaults)


SECRET_KEY = _required_environment("SKEY")

DEBUG = False

ALLOWED_HOSTS = _comma_separated_environment(
    "GRAND_ALLOWED_HOSTS",
    (
        "abutchikikz.online",
        "www.abutchikikz.online",
        "test.abutchikikz.online",
        "www.test.abutchikikz.online",
    ),
)
render_hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)
CSRF_TRUSTED_ORIGINS = _comma_separated_environment("GRAND_CSRF_TRUSTED_ORIGINS")

# Production traffic is served over HTTPS. Keep the initial HSTS window short so
# operators can validate the rollout before increasing it at the edge.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
# The probe is deliberately non-sensitive and must remain reachable from the
# container-local HTTP health check before any TLS-terminating proxy exists.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv("GRAND_SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv(
    "GRAND_SECURE_HSTS_INCLUDE_SUBDOMAINS", "false"
).lower() in {"1", "true", "yes", "on"}
SECURE_HSTS_PRELOAD = os.getenv("GRAND_SECURE_HSTS_PRELOAD", "false").lower() in {
    "1", "true", "yes", "on"
}
USE_X_FORWARDED_HOST = True

# WhiteNoise serves collected assets from the release image. Compression-only
# storage avoids unsafe URL rewriting in legacy AdminLTE CSS whose optional
# source maps are not shipped. Runtime data remains in separate roots.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
MEDIA_ROOT = Path(os.getenv("GRAND_MEDIA_ROOT", MEDIA_ROOT))

database_options = {
    "connect_timeout": int(os.getenv("GRAND_DB_CONNECT_TIMEOUT", "10")),
    "read_timeout": int(os.getenv("GRAND_DB_READ_TIMEOUT", "30")),
    "write_timeout": int(os.getenv("GRAND_DB_WRITE_TIMEOUT", "30")),
}
database_connection_age = int(os.getenv("GRAND_DB_CONN_MAX_AGE", "60"))

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': _required_environment("DEFAULT_DB_NAME", "TEST_DB_NAME"),
        'USER': _required_environment("DEFAULT_DB_USER", "TEST_DB_UN"),
        'PASSWORD': _required_environment("DEFAULT_DB_PASSWORD", "TEST_DB_PW"),
        'HOST': os.getenv("DEFAULT_DB_HOST", os.getenv("TEST_DB_HOST", "localhost")),
        'PORT': os.getenv("DEFAULT_DB_PORT", os.getenv("TEST_DB_PORT", "3306")),
        'CONN_MAX_AGE': database_connection_age,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': database_options.copy(),
    },
    'finance': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': _required_environment('FINANCE_DB_NAME'),
        'USER': _required_environment('FINANCE_DB_USER', 'FINANCE_DB_UN'),
        'PASSWORD': _required_environment('FINANCE_DB_PASSWORD', 'FINANCE_DB_PW'),
        'HOST': os.getenv('FINANCE_DB_HOST', 'localhost'),
        'PORT': os.getenv('FINANCE_DB_PORT', '3306'),
        'CONN_MAX_AGE': database_connection_age,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': database_options.copy(),
    },
}

# Container logs belong on stdout/stderr. Persistent operational files are not
# used as an application-log transport on Render.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "production": {
            "format": "[{levelname}] {asctime} {name} - {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "production",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("GRAND_LOG_LEVEL", "INFO").upper(),
    },
}

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "abutchikikz.online")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "true").lower() in {"1", "true", "yes", "on"}
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

# Custom system email addresses
PWRESET_EMAIL = os.getenv("PWRESET_EMAIL")
PWRESET_PW = os.getenv("PWRESET_PW")
ASSISTANCE_FROM_EMAIL = os.getenv("ASSISTANCE_FROM_EMAIL")
NOTIFICATIONS_FROM_EMAIL = os.getenv("NOTIFICATIONS_FROM_EMAIL")
PW_RESET_FROM_EMAIL = os.getenv("PW_RESET_FROM_EMAIL")

# Google Auth
GAUTH_CLIENTID = os.getenv("GAUTH_CLIENTID")
GAUTH_SECRET = os.getenv("GAUTH_SECRET")
