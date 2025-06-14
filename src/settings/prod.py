import os
from pathlib import Path
from .base import *
from .cron import *

# Already set in base.py
BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("SKEY")

DEBUG = False

ALLOWED_HOSTS = ["abutchikikz.online", "www.abutchikikz.online", "test.abutchikikz.online"]

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv("PROT_DB_NAME"),
        'USER': os.getenv("PROT_DB_UN"),
        'PASSWORD': os.getenv("PROT_DB_PW"),
        'HOST': 'localhost',
        'PORT': '3306',
    }
}

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "abutchikikz.online"
EMAIL_PORT = 465
EMAIL_USE_SSL = True
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
