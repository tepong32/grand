import os

from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# Keep local development and the test runner usable from a clean checkout.
# Production overrides this value in ``src.settings.prod`` and still requires
# SKEY to be supplied by the deployment environment.
SECRET_KEY = os.environ.get('SKEY', 'grand-unsafe-development-only-key')

# SQLite for local dev
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_SQLITE_PATH', BASE_DIR / 'db.sqlite3'),
    },
    'finance': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('GRAND_FINANCE_SQLITE_PATH', BASE_DIR / 'grand_finance.sqlite3'),
    },
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
