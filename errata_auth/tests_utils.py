# Copyright The IETF Trust 2026, All Rights Reserved

from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings

from errata.factories import UserFactory
from errata_auth.utils import (
    GROUP_ROLES,
    IETF_AREAS,
    STREAM_ROLES,
    VerificationScope,
    has_role,
    is_rpc,
    is_verifier,
    op_logout_url,
    verification_scope,
)


# ---------------------------------------------------------------------------
# op_logout_url
# ---------------------------------------------------------------------------


class OpLogoutUrlTest(TestCase):
    def _mock_request(self, *, id_token=None, redirect="http://localhost/"):
        req = MagicMock()
        req.build_absolute_uri.return_value = redirect
        req.session.get.return_value = id_token
        return req

    @override_settings(OIDC_OP_END_SESSION_ENDPOINT=None)
    def test_no_endpoint_returns_logout_redirect_url(self):
        result = op_logout_url(self._mock_request())
        self.assertEqual(result, "/")

    @override_settings(
        OIDC_OP_END_SESSION_ENDPOINT="http://idp.example.com/end-session/",
        DEPLOYMENT_MODE="production",
    )
    def test_production_http_endpoint_warns_and_returns_redirect(self):
        with self.assertWarns(UserWarning) as cm:
            result = op_logout_url(self._mock_request())
        self.assertIn("https", str(cm.warning))
        self.assertEqual(result, "/")

    @override_settings(
        OIDC_OP_END_SESSION_ENDPOINT="http://idp.example.com/end-session/?client_id=foo",
        DEPLOYMENT_MODE="development",
    )
    def test_inappropriate_query_param_warns_and_returns_redirect(self):
        with self.assertWarns(UserWarning) as cm:
            result = op_logout_url(self._mock_request())
        self.assertIn("inappropriate", str(cm.warning))
        self.assertEqual(result, "/")

    @override_settings(
        OIDC_OP_END_SESSION_ENDPOINT="http://idp.example.com/end-session/",
        DEPLOYMENT_MODE="development",
    )
    def test_normal_flow_builds_end_session_url(self):
        result = op_logout_url(self._mock_request())
        self.assertIn("post_logout_redirect_uri", result)
        self.assertNotIn("id_token_hint", result)

    @override_settings(
        OIDC_OP_END_SESSION_ENDPOINT="http://idp.example.com/end-session/",
        DEPLOYMENT_MODE="development",
    )
    def test_id_token_hint_appended_when_session_has_token(self):
        result = op_logout_url(self._mock_request(id_token="my-oidc-token"))
        self.assertIn("id_token_hint", result)
        self.assertIn("my-oidc-token", result)

    @override_settings(
        OIDC_OP_END_SESSION_ENDPOINT="https://idp.example.com/end-session/",
        DEPLOYMENT_MODE="production",
    )
    def test_production_https_endpoint_builds_url(self):
        result = op_logout_url(self._mock_request())
        self.assertIn("post_logout_redirect_uri", result)


# ---------------------------------------------------------------------------
# has_role
# ---------------------------------------------------------------------------


class HasRoleTest(TestCase):
    def test_unauthenticated_user_returns_false(self):
        self.assertFalse(has_role(AnonymousUser(), ["rpc"]))

    def test_superuser_returns_true_for_any_role(self):
        user = UserFactory(is_superuser=True)
        self.assertTrue(has_role(user, ["rpc"]))

    def test_staff_user_returns_true_for_any_role(self):
        user = UserFactory(is_staff=True)
        self.assertTrue(has_role(user, ["verifier"]))

    def test_rpc_user_returns_true_for_rpc_role(self):
        user = UserFactory(roles=[["auth", "rpc"]])
        self.assertTrue(has_role(user, ["rpc"]))

    def test_verifier_user_returns_true_for_verifier_role(self):
        user = UserFactory(roles=[["chair", "iab"]])
        self.assertTrue(has_role(user, ["verifier"]))

    def test_regular_user_returns_false(self):
        user = UserFactory()
        self.assertFalse(has_role(user, ["rpc", "verifier"]))

    def test_rpc_check_skipped_when_not_in_role_names(self):
        user = UserFactory(roles=[["auth", "rpc"]])
        self.assertFalse(has_role(user, ["verifier"]))


# ---------------------------------------------------------------------------
# is_rpc / is_verifier (branch coverage for completeness)
# ---------------------------------------------------------------------------


class IsRpcTest(TestCase):
    def test_superuser_is_rpc(self):
        user = UserFactory(is_superuser=True)
        self.assertTrue(is_rpc(user))

    def test_user_with_rpc_role_is_rpc(self):
        user = UserFactory(roles=[["auth", "rpc"]])
        self.assertTrue(is_rpc(user))

    def test_user_without_rpc_role_is_not_rpc(self):
        user = UserFactory(roles=[])
        self.assertFalse(is_rpc(user))


class IsVerifierTest(TestCase):
    def test_each_verifier_role_passes(self):
        verifier_roles = [
            ["ad", "iesg"],
            ["chair", "iab"],
            ["delegate_stream_manager", "iab"],
            ["chair", "irtf"],
            ["delegate_stream_manager", "irtf"],
            ["chair", "rsab"],
            ["delegate_stream_manager", "rsab"],
            ["chair", "ise"],
            ["chair", "cfrg"],
        ]
        for role in verifier_roles:
            with self.subTest(role=role):
                user = UserFactory(roles=[role])
                self.assertTrue(is_verifier(user))

    def test_user_without_verifier_role_is_not_verifier(self):
        user = UserFactory(roles=[["auth", "rpc"]])
        self.assertFalse(is_verifier(user))


# ---------------------------------------------------------------------------
# verification_scope
# ---------------------------------------------------------------------------


class VerificationScopeTest(TestCase):
    def test_no_roles_grants_empty_scope(self):
        scope = verification_scope(UserFactory(roles=[]))
        self.assertEqual(scope, VerificationScope())
        self.assertFalse(scope)

    def test_iesg_ad_without_area_role_grants_empty_scope(self):
        self.assertFalse(verification_scope(UserFactory(roles=[["ad", "iesg"]])))

    def test_area_role_requires_iesg_role(self):
        self.assertFalse(verification_scope(UserFactory(roles=[["ad", "ops"]])))

    def test_iesg_ad_gets_their_area(self):
        user = UserFactory(roles=[["ad", "iesg"], ["ad", "ops"]])
        self.assertEqual(
            verification_scope(user), VerificationScope(areas=frozenset({"ops"}))
        )

    def test_each_area_is_granted_by_its_ad_role(self):
        for area in IETF_AREAS:
            with self.subTest(area=area):
                scope = verification_scope(
                    UserFactory(roles=[["ad", "iesg"], ["ad", area]])
                )
                self.assertIn(area, scope.areas)

    def test_art_ad_gets_successor_areas(self):
        user = UserFactory(roles=[["ad", "iesg"], ["ad", "art"]])
        self.assertEqual(verification_scope(user).areas, {"art", "app", "rai"})

    def test_group_ad_role_grants_ietf_group(self):
        user = UserFactory(roles=[["ad", "iesg"], ["ad", "ops"], ["ad", "ntp"]])
        scope = verification_scope(user)
        self.assertEqual(scope.areas, {"ops"})
        self.assertEqual(scope.ietf_groups, {"ntp"})

    def test_group_ad_role_requires_iesg_role(self):
        self.assertFalse(verification_scope(UserFactory(roles=[["ad", "ntp"]])))

    def test_area_and_iesg_roles_are_not_groups(self):
        roles = [["ad", "iesg"], *[["ad", area] for area in IETF_AREAS]]
        scope = verification_scope(UserFactory(roles=roles))
        self.assertEqual(scope.ietf_groups, set())

    def test_non_ad_group_role_is_not_a_group(self):
        user = UserFactory(roles=[["ad", "iesg"], ["chair", "ntp"]])
        self.assertEqual(verification_scope(user).ietf_groups, set())

    def test_stream_roles_grant_streams(self):
        for role, stream in STREAM_ROLES.items():
            with self.subTest(role=role):
                user = UserFactory(roles=[list(role)])
                self.assertEqual(
                    verification_scope(user),
                    VerificationScope(streams=frozenset({stream})),
                )

    def test_cfrg_chair_gets_cfrg_group_only(self):
        user = UserFactory(roles=[["chair", "cfrg"]])
        self.assertEqual(
            verification_scope(user), VerificationScope(groups=frozenset({"cfrg"}))
        )

    def test_roles_combine(self):
        user = UserFactory(
            roles=[["ad", "iesg"], ["ad", "sec"], ["chair", "ise"], ["chair", "cfrg"]]
        )
        self.assertEqual(
            verification_scope(user),
            VerificationScope(
                areas=frozenset({"sec"}),
                groups=frozenset({"cfrg"}),
                streams=frozenset({"ise"}),
            ),
        )

    def test_every_role_granting_scope_passes_is_verifier(self):
        # Guards against the scope and the verifier gate drifting apart.
        roles = [
            *STREAM_ROLES,
            *GROUP_ROLES,
            *[("ad", area) for area in IETF_AREAS],
            ("ad", "ntp"),
        ]
        for role in roles:
            with self.subTest(role=role):
                # AD roles only grant anything alongside ["ad", "iesg"]
                extra = [["ad", "iesg"]] if role[0] == "ad" else []
                user = UserFactory(roles=[*extra, list(role)])
                self.assertTrue(verification_scope(user))
                self.assertTrue(is_verifier(user))
