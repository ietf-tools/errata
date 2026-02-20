# Copyright The IETF Trust 2025-2026, All Rights Reserved
# based on github.com/ietf-tools/purple/rpcauth/utils.py

from functools import WRAPPER_ASSIGNMENTS, wraps
import warnings
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.core.exceptions import PermissionDenied


def op_logout_url(request):
    """Construct URI for initiating logout from OIDC provider"""
    end_session_endpoint = getattr(settings, "OIDC_OP_END_SESSION_ENDPOINT", None)
    logout_redirect_url = getattr(settings, "LOGOUT_REDIRECT_URL", "/")
    if end_session_endpoint is None:
        # No END_SESSION_ENDPOINT is configured so we can't initiate an OP logout
        return logout_redirect_url

    # Per the OIDC spec, end_session_endpoint can include a query string of
    # its own, so parse and preserve it and append our parameters to the end.
    # https://openid.net/specs/openid-connect-rpinitiated-1_0.html
    endpoint_parts = urlsplit(end_session_endpoint)

    if settings.DEPLOYMENT_MODE == "production" and endpoint_parts.scheme != "https":
        warnings.warn(
            "OIDC_OP_END_SESSION_ENDPOINT must be an https URI. Not initiating logout "
            "from OP.",
            stacklevel=2,
        )
        return logout_redirect_url

    query_params = parse_qsl(endpoint_parts.query)
    # make sure the URL did not already contain any of the params we are about to use
    if any(
        name in ["client_id", "post_logout_redirect_url", "id_token_hint"]
        for name, _ in query_params
    ):
        warnings.warn(
            "OIDC_OP_END_SESSION_ENDPOINT has an inappropriate query param. "
            "Not initiating logout from OP.",
            stacklevel=2,
        )
        return logout_redirect_url

    # Construct the end-session URL
    query_params.append(
        ("post_logout_redirect_uri", request.build_absolute_uri(logout_redirect_url)),
    )
    # hint with the id token if we have it
    id_token = request.session.get("oidc_id_token", None)
    if id_token is not None:
        query_params.append(("id_token_hint", id_token))
    return urlunsplit(endpoint_parts._replace(query=urlencode(query_params)))


def has_role(user, role_names, *args, **kwargs):
    """Check if the user has at least one of the specified roles."""
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    if "rpc" in role_names:
        if is_rpc(user):
            return True
    if "verifier" in role_names:
        if is_verifier(user):
            return True
    return False


def is_rpc(user):
    user_roles = getattr(user, "roles", [])
    passes_test = user.is_superuser or ["auth", "rpc"] in user_roles
    return passes_test


def is_verifier(user):
    user_roles = getattr(user, "roles", [])
    # "delegate_stream_manager" is a datatracker role
    # that is coming into existance to support the
    # errata system. It will have to created as a
    # RoleName and roles assigned before the related
    # passing_roles below will have effect.
    passing_roles = [
        # IESG stream
        ["ad", "iesg"],
        # IAB stream
        ["chair", "iab"],
        ["delegate_stream_manager", "iab"],
        # IRTF stream
        ["chair", "irtf"],
        ["delegate_stream_manager", "irtf"],
        # Editorial stream
        ["chair", "rsab"],
        ["delegate_stream_manager", "rsab"],
        # Independent stream
        ["chair", "ise"],
    ]
    passes_test = any([role in user_roles for role in passing_roles])
    return passes_test


def passes_test_decorator(test_func, message):
    """Decorator creator that creates a decorator for checking that
    user passes the test

    Returns a 403 error if the user is not logged in or does not pass
    the test.

    The test function should be on the form fn(user) -> true/false.
    """

    def decorate(view_func):
        @wraps(view_func, assigned=WRAPPER_ASSIGNMENTS)
        def inner(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied(message)
            elif test_func(request.user, *args, **kwargs):
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied(message)

        return inner

    return decorate


def role_required(*role_names):
    """View decorator for checking that the user is logged in and
    has one of the listed roles."""
    return passes_test_decorator(
        lambda u, *args, **kwargs: has_role(u, role_names, *args, **kwargs),
        "Restricted to role%s: %s"
        % ("s" if len(role_names) != 1 else "", ", ".join(role_names)),
    )
