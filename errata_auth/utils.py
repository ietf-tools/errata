# Copyright The IETF Trust 2025-2026, All Rights Reserved
# based on github.com/ietf-tools/purple/rpcauth/utils.py

from dataclasses import dataclass
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


# Roles are [role_name, group_acronym] pairs as claimed by the datatracker.
#
# IESG ADs verify IETF stream errata by area, and need ["ad", "iesg"] plus
# ["ad", <area>] for the area.
IETF_AREAS = ["gen", "wit", "art", "ops", "rtg", "int", "sec"]
# Closed areas whose RFCs are now verified by the ADs of a current area.
SUCCESSOR_AREAS = {"art": ["app", "rai"]}

# Roles that make their holder a verifier for a whole stream.
# "delegate_stream_manager" is a datatracker role
# that is coming into existence to support the
# errata system. It will have to created as a
# RoleName and roles assigned before the related
# roles below will have effect.
STREAM_ROLES = {
    ("chair", "iab"): "iab",
    ("delegate_stream_manager", "iab"): "iab",
    ("chair", "irtf"): "irtf",
    ("delegate_stream_manager", "irtf"): "irtf",
    ("chair", "rsab"): "editorial",
    ("delegate_stream_manager", "rsab"): "editorial",
    ("chair", "ise"): "ise",
}

# Roles that make their holder a verifier for a single group's RFCs.
GROUP_ROLES = {
    # The CFRG chair may verify their own group's errata. This is
    # specific to CFRG; research group chairs do not get this in general.
    ("chair", "cfrg"): "cfrg",
}


@dataclass(frozen=True)
class VerificationScope:
    """The RFCs whose errata a user may verify

    An RFC is in scope if it matches any of the fields.
    """

    # IETF areas, matched against an RFC's area acronym or area assignment
    areas: frozenset = frozenset()
    # Groups whose IETF stream RFCs are in scope
    ietf_groups: frozenset = frozenset()
    # Groups whose RFCs are in scope, whatever the stream
    groups: frozenset = frozenset()
    streams: frozenset = frozenset()

    def __bool__(self):
        return any([self.areas, self.ietf_groups, self.groups, self.streams])


def verification_scope(user):
    """Return the VerificationScope that the user's roles grant"""
    user_roles = {tuple(role) for role in getattr(user, "roles", [])}
    areas = set()
    ietf_groups = set()
    if ("ad", "iesg") in user_roles:
        for area in IETF_AREAS:
            if ("ad", area) in user_roles:
                areas.add(area)
                areas.update(SUCCESSOR_AREAS.get(area, []))
        # An AD may be assigned to a group outside their area (e.g. a
        # temporary AD for a working group). Area and IESG roles are
        # excluded so they don't match RFCs whose group is the area itself.
        ietf_groups = {
            group
            for name, group in user_roles
            if name == "ad" and group not in IETF_AREAS + ["iesg"]
        }
    return VerificationScope(
        areas=frozenset(areas),
        ietf_groups=frozenset(ietf_groups),
        groups=frozenset(g for r, g in GROUP_ROLES.items() if r in user_roles),
        streams=frozenset(s for r, s in STREAM_ROLES.items() if r in user_roles),
    )


def is_verifier(user):
    user_roles = {tuple(role) for role in getattr(user, "roles", [])}
    # ["ad", "iesg"] passes on its own, even though it grants an empty
    # VerificationScope without an area or group role.
    passing_roles = [("ad", "iesg"), *STREAM_ROLES, *GROUP_ROLES]
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
