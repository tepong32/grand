from .base import *
from .cron import *


DEBUG = False
ALLOWED_HOSTS = ['abutchikikz.online', 'www.abutchikikz.online']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('MYSQL_DATABASE'),
        'USER': os.environ.get('MYSQL_USER'),
        'PASSWORD': os.environ.get('MYSQL_PASSWORD'),
        'HOST': os.environ.get('MYSQL_HOST', 'localhost'),
        'PORT': os.environ.get('MYSQL_PORT', '3306'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

