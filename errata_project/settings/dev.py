from .base import *  # noqa
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
