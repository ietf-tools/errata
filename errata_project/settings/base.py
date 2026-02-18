# Copyright The IETF Trust 2025-2026, All Rights Reserved

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

BASE_URL = "https://errata.rfc-editor.org"


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

AUTH_USER_MODEL = "errata_auth.User"


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-^#+dk-4mxjas+4@q@_44skjb4@zs)g9!_!7*%30*f=&!%#ifwd"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "mozilla_django_oidc",  # load after auth
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_bootstrap5",
    "django_celery_beat",
    "rules.apps.AutodiscoverRulesConfig",
    "errata_auth.apps.ErrataAuthConfig",
    "errata.apps.ErrataConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "errata_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "errata_project.wsgi.application"

# TODO - verify rules.permissions are needed/used
AUTHENTICATION_BACKENDS = (
    "errata_auth.backends.ErrataOIDCAuthBackend",
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
)

# OIDC configuration (see also prod.py/dev.py)
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid profile roles email"
OIDC_STORE_ID_TOKEN = True  # store id_token in session (used for RP-initiated logout)
ALLOW_LOGOUT_GET_METHOD = True  # for now anyway
OIDC_OP_LOGOUT_URL_METHOD = "errata_auth.utils.op_logout_url"

SESSION_COOKIE_NAME = (
    "erratasessionid"  # need to set this if oidc provider is on same domain as client
)

# How often to renew tokens? Default is 15 minutes. Needs SessionRefresh middleware.
# OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 15 * 60

# Misc
LOGIN_REDIRECT_URL = "/user-info/"
LOGOUT_REDIRECT_URL = "/"

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"

# Caches - disabled by default, create as appropriate in per-environment config
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# email - disabled in base config
EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
DEFAULT_FROM_EMAIL = os.getenv("ERRATA_DEFAULT_FROM_EMAIL", "errata@rfc-editor.org")
MESSAGE_ID_DOMAIN = "rfc-editor.org"

ADMINS = [("Some Admin", "admin@example.org")]

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# TODO configure logging
# This is a stub configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    #
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
        },
        "django.security": {
            "handlers": [
                "console",
            ],
            "level": "INFO",
        },
        "errata": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "celery_task_console": {
            "class": "logging.StreamHandler",
            "formatter": "celery_task",
        },
    },
    "formatters": {
        "default": {
            "()": "utils.log.SimpleFormatter",
            "format": "[{asctime}] ({levelname}) {message} ({name})",
            "style": "{",
        },
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[%(server_time)s] %(message)s",
        },
        "plain": {
            "style": "{",
            "format": "{levelname}: {name}:{lineno}: {message}",
        },
        "celery_task": {
            "()": "utils.log.CeleryTaskFormatter",
            "format": (
                "[%(asctime)s] (%(levelname)s) "
                "Task %(task_name)s[%(task_id)s] log: %(message)s"
            ),
        },
    },
}

# Celery
CELERY_TIMEZONE = "UTC"
CELERY_BROKER_URL = os.environ.get("ERRATA_BROKER_URL", "amqp://mq/")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_IGNORE_RESULT = True  # ignore results unless specifically enabled

# Celery Beat
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SYNC_EVERY = 1  # update DB after every event
# Window after after a missed deadline before abandoning a cron task
CELERY_BEAT_CRON_STARTING_DEADLINE = 1800  # seconds
