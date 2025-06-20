"""
Django base settings for src project (used in both dev and prod).

Split from original settings.py to allow environment-specific overrides.
"""
from dotenv import load_dotenv
load_dotenv()  # take environment variables

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(os.path.join(BASE_DIR, ".env"))  # take environment variables

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SKEY')

# Application definition

INSTALLED_APPS = [
    'admin_helper',  # custom admin helpers (e.g. actions, views)

    ### 3rd-party apps
    'adminlte4',
    'adminlte4_theme',
    'crispy_forms',
    'crispy_bootstrap4',
    'django_crontab',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'django_ckeditor_5',

    ### custom
    'home.apps.HomeConfig',
    'users.apps.UsersConfig',
    'profiles.apps.ProfilesConfig',
    'leave_mgt.apps.LeaveMgtConfig',
    'salaries.apps.SalariesConfig',
    'departments.apps.DepartmentsConfig',
    'assistance.apps.AssistanceConfig',

    ### defaults
    'django.contrib.sites',  # allauth needs this
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
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ### allauth
    'allauth.account.middleware.AccountMiddleware',
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
                # Custom global context for dashboard
                'leave_mgt.context_processors.dashboard_context',
            ],
        },
    },
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

WSGI_APPLICATION = 'src.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

USE_I18N = True
USE_TZ = True

LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('en', 'English'),
    ('fil', 'Filipino'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

# Time zone settings
TIME_ZONE = 'Asia/Manila'

#######################################################################
# personally-preferred & configured settings - tEppy

STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATIC_URL = '/static/'
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
MEDIA_URL = '/media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.User'

### DJANGO ALLAUTH
SITE_ID = 1
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GAUTH_CLIENTID'),
            'secret': os.environ.get('GAUTH_SECRET'),
            'key': ''
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'}
    }
}

ACCOUNT_ADAPTER = 'users.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_UNIQUE_EMAIL = True

from django.urls import reverse_lazy
LOGIN_REDIRECT_URL = reverse_lazy('department_dashboard')
LOGOUT_REDIRECT_URL = '/'  # unauthedhome
LOGIN_URL = 'login'

### PASSWORD-RESETS AND MAILINGS
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
ASSISTANCE_FROM_EMAIL = 'assistance@abutchikikz.online'
NOTIFICATIONS_FROM_EMAIL = 'notifs@abutchikikz.online'
PW_RESET_FROM_EMAIL = 'pw-reset@abutchikikz.online'

### Bootstrap settings for Django-AdminLTE4
CRISPY_TEMPLATE_PACK = 'bootstrap4'

### CKEDITOR 5 settings ################################################
customColorPalette = [
    {'color': 'hsl(4, 90%, 58%)', 'label': 'Red'},
    {'color': 'hsl(340, 82%, 52%)', 'label': 'Pink'},
    {'color': 'hsl(291, 64%, 42%)', 'label': 'Purple'},
    {'color': 'hsl(262, 52%, 47%)', 'label': 'Deep Purple'},
    {'color': 'hsl(231, 48%, 48%)', 'label': 'Indigo'},
    {'color': 'hsl(207, 90%, 54%)', 'label': 'Blue'},
]

CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': {
            'items': ['heading', '|', 'bold', 'italic', 'link',
                      'bulletedList', 'numberedList', 'blockQuote', 'imageUpload']
        },
    },
    'extends': {
        'blockToolbar': ['paragraph', 'heading1', 'heading2', 'heading3', '|',
                         'bulletedList', 'numberedList', '|', 'blockQuote'],
        'toolbar': {
            'items': ['heading', '|', 'outdent', 'indent', '|', 'bold', 'italic', 'link',
                      'underline', 'strikethrough', 'code', 'subscript', 'superscript', 'highlight',
                      '|', 'codeBlock', 'sourceEditing', 'insertImage', 'bulletedList', 'numberedList',
                      'todoList', '|', 'blockQuote', 'imageUpload', '|', 'fontSize', 'fontFamily',
                      'fontColor', 'fontBackgroundColor', 'mediaEmbed', 'removeFormat', 'insertTable'],
            'shouldNotGroupWhenFull': 'true'
        },
        'image': {
            'toolbar': ['imageTextAlternative', '|', 'imageStyle:alignLeft',
                        'imageStyle:alignRight', 'imageStyle:alignCenter', 'imageStyle:side', '|'],
            'styles': ['full', 'side', 'alignLeft', 'alignRight', 'alignCenter']
        },
        'table': {
            'contentToolbar': ['tableColumn', 'tableRow', 'mergeTableCells',
                               'tableProperties', 'tableCellProperties'],
            'tableProperties': {
                'borderColors': customColorPalette,
                'backgroundColors': customColorPalette
            },
            'tableCellProperties': {
                'borderColors': customColorPalette,
                'backgroundColors': customColorPalette
            }
        },
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
                {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3'}
            ]
        }
    },
    'list': {
        'properties': {
            'styles': 'true',
            'startIndex': 'true',
            'reversed': 'true'
        }
    }
}

CKEDITOR_5_FILE_UPLOAD_PERMISSION = "staff"

# Logging setup
import logging
logging.basicConfig(level=logging.DEBUG)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module}.{funcName}:{lineno} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'app.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

log_dir = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
