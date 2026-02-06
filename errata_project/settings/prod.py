from .base import *  # noqa
import json
import os

DEPLOYMENT_MODE = "production"

def _multiline_to_list(s):
    """Helper to split at newlines and convert to list"""
    return [item.strip() for item in s.split("\n") if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["ERRATA_DJANGO_SECRET_KEY"]
assert not SECRET_KEY.startswith(
    "django-insecure"
)  # be sure we didn't get the dev secret

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# ERRATA_ALLOWED_HOSTS is a newline-separated list of allowed hosts
ALLOWED_HOSTS = _multiline_to_list(os.environ["ERRATA_ALLOWED_HOSTS"])

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("ERRATA_DB_NAME"),
        "USER": os.environ.get("ERRATA_DB_USER"),
        "PASSWORD": os.environ.get("ERRATA_DB_PASS"),
        "HOST": os.environ.get("ERRATA_DB_HOST"),
        "PORT": int(os.environ.get("ERRATA_DB_PORT")),
        "OPTIONS": json.loads(os.environ.get("ERRATA_DB_OPTS_JSON", "{}")),
    }
}

DATATRACKER_BASE = os.environ.get(
    "NUXT_PUBLIC_DATATRACKER_BASE", "https://datatracker.ietf.org"
)

# OIDC configuration (see also base.py)
OIDC_RP_CLIENT_ID = os.environ["ERRATA_OIDC_RP_CLIENT_ID"]
OIDC_RP_CLIENT_SECRET = os.environ["ERRATA_OIDC_RP_CLIENT_SECRET"]
OIDC_OP_ISSUER_ID = os.environ.get(
    "ERRATA_OIDC_OP_ISSUER_ID", f"{DATATRACKER_BASE}/api/openid"
)
OIDC_OP_JWKS_ENDPOINT = os.environ.get(
    "ERRATA_OIDC_OP_JWKS_ENDPOINT", f"{OIDC_OP_ISSUER_ID}/jwks/"
)
OIDC_OP_AUTHORIZATION_ENDPOINT = os.environ.get(
    "ERRATA_OIDC_OP_AUTHORIZATION_ENDPOINT", f"{OIDC_OP_ISSUER_ID}/authorize/"
)
OIDC_OP_TOKEN_ENDPOINT = os.environ.get(
    "ERRATA_OIDC_OP_TOKEN_ENDPOINT", f"{OIDC_OP_ISSUER_ID}/token/"
)
OIDC_OP_USER_ENDPOINT = os.environ.get(
    "ERRATA_OIDC_OP_USER_ENDPOINT", f"{OIDC_OP_ISSUER_ID}/userinfo/"
)
OIDC_OP_END_SESSION_ENDPOINT = os.environ.get(
    "ERRATA_OIDC_OP_END_SESSION_ENDPOINT", f"{OIDC_OP_ISSUER_ID}/end-session/"
)

# Config for Cloudflare service token auth
_CF_SERVICE_TOKEN_HOSTS = os.environ.get("ERRATA_SERVICE_TOKEN_HOSTS", None)
if _CF_SERVICE_TOKEN_HOSTS is not None:
    # include token id/secret headers for these hosts
    CF_SERVICE_TOKEN_HOSTS = _multiline_to_list(_CF_SERVICE_TOKEN_HOSTS)
    CF_SERVICE_TOKEN_ID = os.environ.get("ERRATA_SERVICE_TOKEN_ID", None)
    CF_SERVICE_TOKEN_SECRET = os.environ.get("ERRATA_SERVICE_TOKEN_SECRET", None)
