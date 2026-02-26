# Copyright The IETF Trust 2025-2026, All Rights Reserved
from .base import *  # noqa
from .base import STORAGES
import os

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "errata",
        "USER": "django",
        "PASSWORD": "dev-not-a-secret",
        "HOST": "db",
    }
}

ALLOWED_HOSTS = ["*"]

# OIDC configuration (see also base.py)
OIDC_RP_CLIENT_ID = os.environ["ERRATA_OIDC_RP_CLIENT_ID"]
OIDC_RP_CLIENT_SECRET = os.environ["ERRATA_OIDC_RP_CLIENT_SECRET"]
OIDC_OP_ISSUER_ID = "http://localhost:8000/api/openid"
OIDC_OP_JWKS_ENDPOINT = "http://host.docker.internal:8000/api/openid/jwks/"
OIDC_OP_AUTHORIZATION_ENDPOINT = (
    "http://localhost:8000/api/openid/authorize/"  # URL for user agent
)
OIDC_OP_TOKEN_ENDPOINT = "http://host.docker.internal:8000/api/openid/token/"
OIDC_OP_USER_ENDPOINT = "http://host.docker.internal:8000/api/openid/userinfo/"
OIDC_OP_END_SESSION_ENDPOINT = "http://localhost:8000/api/openid/end-session/"

DEPLOYMENT_MODE = "development"

# email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("ERRATA_EMAIL_HOST", "mailpit")
EMAIL_PORT = int(os.getenv("ERRATA_EMAIL_PORT", 1025))

# datatracker
DATATRACKER_BASE = "http://localhost:8000"
DATATRACKER_RPC_API_BASE = "http://host.docker.internal:8000"
DATATRACKER_RPC_API_TOKEN = "redtoken"  # not a real secret

APP_API_TOKENS = {
    "errata.views.api_rfc_metadata_update": ["not a real secret"],
}

for _bucket in STORAGE_BUCKETS:
    STORAGES[f"{_bucket}_bucket"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": _bucket,
            "endpoint_url": "http://blobstore:9000",
            "access_key": "minioroot",
            "secret_key": "miniopass",
            "security_token": None,
            "verify": False,
        },
    }
