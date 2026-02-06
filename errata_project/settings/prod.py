from .base import *  # noqa
import json
import os

DEPLOYMENT_MODE = "production"

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
