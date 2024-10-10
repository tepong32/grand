"""
Django settings for src project.

Generated by 'django-admin startproject' using Django 5.1.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-3ax(-&x%)3l)al(6=jy#!@14bxst=@_b2vt3uinuaemomka7cz'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    
    ### 3rd-party apps
    'adminlte3',
    'adminlte3_theme',
    'crispy_forms',
    'crispy_bootstrap4',

    ### custom
    'home.apps.HomeConfig',
    'users.apps.UsersConfig',
    'leave_mgt.apps.LeaveMgtConfig',

    'django.contrib.sites', # "just-in-case". allauth needs this.
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ### allauth
    # "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = 'src.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',

    # `allauth` specific authentication methods, such as login by email
    # 'allauth.account.auth_backends.AuthenticationBackend',
]

WSGI_APPLICATION = 'src.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

USE_L10N = True

import pytz

TIME_ZONE = 'Asia/Manila'  # or 'Asia/Kuala_Lumpur' or 'Asia/Singapore' (adjust according to your location) https://pytz.sourceforge.io/#timezone-classes



####################################################################### personally-preferred & configured settings - tEppy
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATIC_URL = '/static/'
MEDIA_ROOT = os.path.join(BASE_DIR, "media")     # where we want django to save uploaded files
MEDIA_URL = '/media/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SITE_ID = 1
# allauth provider specific settings // not needed atm
# SOCIALACCOUNT_PROVIDERS = {
#     'google': {
#         # For each OAuth based provider, either add a ``SocialApp``
#         # (``socialaccount`` app) containing the required client
#         # credentials, or list them here:
#         'APP': {
#             'client_id': os.environ.get('GAUTH_CLIENTID'), # '960711795493-9vsgskaeg1qk3nc74qp27s9e7uoejitq.apps.googleusercontent.com'
#             'secret': os.environ.get('GAUTH_SECRET'),      # '0-tHwlg4jvax1jt7p-JnvBmj'
#             'key': ''
#         }
#     }
# }

# ACCOUNT_EMAIL_REQUIRED = True
# ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
# ACCOUNT_AUTHENTICATION_METHOD = 'email'
# ACCOUNT_USERNAME_REQUIRED = False


LOGIN_REDIRECT_URL = 'home'     # needed for the login.html success instance
LOGIN_URL = 'login'             # for the @login_required decorator on user.views.profile

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com' # or only your domain name if you have your own mail server
EMAIL_PORT = 587 #587
EMAIL_USE_TLS = True


# TO USE THESE VARIABLES BELOW, USE ENVIRONMENT VARIABLES TO HIDE SENSITIVE INFO
# CHECK CoreyMs' Django TUTORIAL # 12 -- 14:20

EMAIL_HOST_USER = os.environ.get('ADMIN_EMAIL_UN') # var for email username
EMAIL_HOST_PASSWORD = os.environ.get('ADMIN_EMAIL_PW') # var for email pw
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER # for email-sending pw-reset requests
# AUTH_USER_MODEL='auth.User'
AUTH_USER_MODEL='users.User'   # create a custom user model first then use this instead of auth.User


CRISPY_TEMPLATE_PACK = 'bootstrap4'