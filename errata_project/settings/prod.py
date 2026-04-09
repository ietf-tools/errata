# Copyright The IETF Trust 2026, All Rights Reserved
import botocore.config

from .base import *  # noqa
from .base import STORAGES, STORAGE_BUCKETS
from email.utils import parseaddr
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
DATATRACKER_RPC_API_BASE = DATATRACKER_BASE
DATATRACKER_RPC_API_TOKEN = os.environ["ERRATA_RPC_API_TOKEN"]

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


# Email
_email_host = os.environ.get("ERRATA_EMAIL_HOST", None)
if _email_host is not None:
    # Email is configured via the ERRATA_EMAIL_* settings. Use those.
    _email_port = os.environ.get("ERRATA_EMAIL_PORT", None)
else:
    # Use the mailpit k8s service settings if present
    _email_host = os.environ.get("MAILPIT_SERVICE_HOST", None)
    _email_port = os.environ.get("MAILPIT_SERVICE_PORT", None)

# Set up mail if it is configured
if _email_host is not None:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = _email_host
    if _email_port is not None:
        EMAIL_PORT = _email_port


_admins_str = os.environ.get("ERRATA_ADMINS", None)
if _admins_str is not None:
    ADMINS = [parseaddr(admin) for admin in _multiline_to_list(_admins_str)]
else:
    raise RuntimeError("ERRATA_ADMINS must be set")

# Red precomputer configuration
TRIGGER_RED_PRECOMPUTE_MULTIPLE_URL = os.environ.get("ERRATA_RED_PRECOMPUTE_MULTIPLE_URL", None)

# Storages configuration
# Configure storages for the replica blob store
_blob_store_endpoint_url = os.environ.get("ERRATA_BLOB_STORE_ENDPOINT_URL")
_blob_store_access_key = os.environ.get("ERRATA_BLOB_STORE_ACCESS_KEY")
_blob_store_secret_key = os.environ.get("ERRATA_BLOB_STORE_SECRET_KEY")
if None in (_blob_store_endpoint_url, _blob_store_access_key, _blob_store_secret_key):
    raise RuntimeError(
        "All of ERRATA_BLOB_STORE_ENDPOINT_URL, ERRATA_BLOB_STORE_ACCESS_KEY, "
        "and ERRATA_BLOB_STORE_SECRET_KEY must be set"
    )

_blob_store_max_attempts = int(os.environ.get("ERRATA_BLOB_STORE_MAX_ATTEMPTS", 5))
_blob_store_connect_timeout = float(
    os.environ.get("ERRATA_BLOB_STORE_CONNECT_TIMEOUT", 10)
)
_blob_store_read_timeout = float(os.environ.get("ERRATA_BLOB_STORE_READ_TIMEOUT", 10))

for _bucket in STORAGE_BUCKETS:
    # expect env var like ERRATA_BLOB_STORE_BUCKET_NAME_RED
    _envvar = f"ERRATA_BLOB_STORE_BUCKET_NAME_{_bucket.upper()}"
    _blob_store_bucket_name = os.environ.get(_envvar, None).strip()
    if _blob_store_bucket_name is None:
        raise RuntimeError(f"{_envvar} must be set")
    STORAGES[f"{_bucket}_bucket"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": dict(
            bucket_name=_blob_store_bucket_name,
            endpoint_url=_blob_store_endpoint_url,
            access_key=_blob_store_access_key,
            secret_key=_blob_store_secret_key,
            security_token=None,
            client_config=botocore.config.Config(
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
                signature_version="s3v4",
                connect_timeout=_blob_store_connect_timeout,
                read_timeout=_blob_store_read_timeout,
                retries={"total_max_attempts": _blob_store_max_attempts},
            ),
            verify=False,
        ),
    }
