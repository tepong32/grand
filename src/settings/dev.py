import os

from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# SQLite for local dev
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_SQLITE_PATH', BASE_DIR / 'db.sqlite3'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
