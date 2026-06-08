# Copyright The IETF Trust 2026, All Rights Reserved

from unittest.mock import MagicMock, patch

from django.core.exceptions import SuspiciousOperation
from django.test import TestCase, override_settings
from requests.auth import HTTPBasicAuth

from errata.factories import UserFactory
from errata_auth.backends import (
    ErrataOIDCAuthBackend,
    ServiceTokenOIDCAuthenticationBackend,
)


# Settings required to instantiate the backends in test context.
OIDC_SETTINGS = dict(
    OIDC_OP_ISSUER_ID="http://issuer.example.com/openid",
    OIDC_RP_CLIENT_ID="test-client-id",
    OIDC_RP_CLIENT_SECRET="test-client-secret",
)


@override_settings(**OIDC_SETTINGS)
class ServiceTokenRequestTest(TestCase):
    """Tests for _request_get / _request_post CF header injection."""

    CF_SETTINGS = dict(
        CF_SERVICE_TOKEN_HOSTS=["cf.example.com"],
        CF_SERVICE_TOKEN_ID="cf-id",
        CF_SERVICE_TOKEN_SECRET="cf-secret",
    )

    def _backend(self, **extra):
        return ServiceTokenOIDCAuthenticationBackend()

    @override_settings(**CF_SETTINGS)
    @patch("errata_auth.backends.requests.get")
    def test_request_get_adds_cf_headers_for_cf_host(self, mock_get):
        backend = self._backend()
        backend._request_get("https://cf.example.com/jwks")
        headers = mock_get.call_args.kwargs.get("headers", {})
        self.assertEqual(headers["CF-Access-Client-Id"], "cf-id")
        self.assertEqual(headers["CF-Access-Client-Secret"], "cf-secret")

    @patch("errata_auth.backends.requests.get")
    def test_request_get_no_cf_headers_for_non_cf_host(self, mock_get):
        backend = self._backend()
        backend._request_get("https://other.example.com/jwks")
        headers = mock_get.call_args.kwargs.get("headers", {})
        self.assertNotIn("CF-Access-Client-Id", headers)

    @override_settings(**CF_SETTINGS)
    @patch("errata_auth.backends.requests.post")
    def test_request_post_adds_cf_headers_for_cf_host(self, mock_post):
        backend = self._backend()
        backend._request_post("https://cf.example.com/token")
        headers = mock_post.call_args.kwargs.get("headers", {})
        self.assertEqual(headers["CF-Access-Client-Id"], "cf-id")

    @patch("errata_auth.backends.requests.post")
    def test_request_post_no_cf_headers_for_non_cf_host(self, mock_post):
        backend = self._backend()
        backend._request_post("https://other.example.com/token")
        headers = mock_post.call_args.kwargs.get("headers", {})
        self.assertNotIn("CF-Access-Client-Id", headers)


@override_settings(**OIDC_SETTINGS)
class ServiceTokenHigherLevelTest(TestCase):
    """Tests for retrieve_matching_jwk, get_token, and get_userinfo."""

    def setUp(self):
        self.backend = ServiceTokenOIDCAuthenticationBackend()

    def _mock_jwks_response(self, keys):
        resp = MagicMock()
        resp.json.return_value = {"keys": keys}
        return resp

    def test_retrieve_matching_jwk_returns_matching_key(self):
        key = {"kid": "test-kid", "alg": "RS256", "kty": "RSA"}
        mock_resp = self._mock_jwks_response([key])
        mock_header = MagicMock()
        mock_header.kid = "test-kid"
        mock_header.alg = "RS256"
        with patch.object(self.backend, "_request_get", return_value=mock_resp):
            with patch("errata_auth.backends.JWS.from_compact") as mock_jws:
                mock_jws.return_value.signature.protected = b"{}"
                with patch(
                    "errata_auth.backends.Header.json_loads", return_value=mock_header
                ):
                    result = self.backend.retrieve_matching_jwk(b"compact")
        self.assertEqual(result, key)

    def test_retrieve_matching_jwk_raises_when_kid_does_not_match(self):
        mock_resp = self._mock_jwks_response([{"kid": "other-kid", "alg": "RS256"}])
        mock_header = MagicMock()
        mock_header.kid = "test-kid"
        mock_header.alg = "RS256"
        with patch.object(self.backend, "_request_get", return_value=mock_resp):
            with patch("errata_auth.backends.JWS.from_compact") as mock_jws:
                mock_jws.return_value.signature.protected = b"{}"
                with patch(
                    "errata_auth.backends.Header.json_loads", return_value=mock_header
                ):
                    with self.assertRaises(SuspiciousOperation):
                        self.backend.retrieve_matching_jwk(b"compact")

    def test_retrieve_matching_jwk_raises_when_alg_does_not_match(self):
        # kid matches but alg doesn't — exercises the alg-mismatch continue (line 76)
        mock_resp = self._mock_jwks_response([{"kid": "test-kid", "alg": "ES256"}])
        mock_header = MagicMock()
        mock_header.kid = "test-kid"
        mock_header.alg = "RS256"
        with patch.object(self.backend, "_request_get", return_value=mock_resp):
            with patch("errata_auth.backends.JWS.from_compact") as mock_jws:
                mock_jws.return_value.signature.protected = b"{}"
                with patch(
                    "errata_auth.backends.Header.json_loads", return_value=mock_header
                ):
                    with self.assertRaises(SuspiciousOperation):
                        self.backend.retrieve_matching_jwk(b"compact")

    def test_get_token_posts_payload_and_returns_json(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "tok"}
        with patch.object(self.backend, "_request_post", return_value=mock_resp):
            with patch.object(self.backend, "raise_token_response_error"):
                result = self.backend.get_token(
                    {"client_id": "cid", "client_secret": "s"}
                )
        self.assertEqual(result["access_token"], "tok")

    @override_settings(OIDC_TOKEN_USE_BASIC_AUTH=True)
    def test_get_token_uses_basic_auth_when_configured(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        with patch.object(
            self.backend, "_request_post", return_value=mock_resp
        ) as mock_post:
            with patch.object(self.backend, "raise_token_response_error"):
                self.backend.get_token({"client_id": "cid", "client_secret": "secret"})
        auth = mock_post.call_args.kwargs["auth"]
        self.assertIsInstance(auth, HTTPBasicAuth)
        # client_secret must be removed from the posted data
        data = mock_post.call_args.kwargs["data"]
        self.assertNotIn("client_secret", data)

    def test_get_userinfo_returns_user_details(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"sub": "test-sub", "name": "Test User"}
        with patch.object(
            self.backend, "_request_get", return_value=mock_resp
        ) as mock_get:
            result = self.backend.get_userinfo("access-tok", "id-tok", {})
        self.assertEqual(result["sub"], "test-sub")
        auth_header = mock_get.call_args.kwargs["headers"]["Authorization"]
        self.assertEqual(auth_header, "Bearer access-tok")


@override_settings(**OIDC_SETTINGS)
class ErrataAuthBackendUserTest(TestCase):
    """Tests for create_user, update_user, and filter_users_by_claims."""

    def setUp(self):
        self.backend = ErrataOIDCAuthBackend()

    def _claims(self, **overrides):
        base = {
            "sub": "sub-123",
            "name": "Test User",
            "roles": [["auth", "rpc"]],
            "email": "test@example.com",
            "picture": "https://example.com/pic.jpg",
        }
        base.update(overrides)
        return base

    # --- create_user ---

    def test_create_user_creates_user_with_correct_fields(self):
        user = self.backend.create_user(self._claims())
        self.assertEqual(user.datatracker_subject_id, "sub-123")
        self.assertEqual(user.name, "Test User")
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.avatar, "https://example.com/pic.jpg")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_create_user_grants_admin_for_admin_role(self):
        claims = self._claims(sub="admin-sub", roles=[["leadmaintainer", "tools"]])
        user = self.backend.create_user(claims)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_create_user_raises_on_duplicate_subject_id(self):
        self.backend.create_user(self._claims())
        with self.assertRaises(SuspiciousOperation) as cm:
            self.backend.create_user(self._claims())
        self.assertIn("sub-123", str(cm.exception))

    # --- update_user ---

    def test_update_user_updates_name_when_changed(self):
        user = UserFactory(name="Old Name", email="u@e.com", roles=[])
        claims = self._claims(
            sub=user.datatracker_subject_id,
            name="New Name",
            roles=[],
            email="u@e.com",
            picture=user.avatar,
        )
        self.backend.update_user(user, claims)
        user.refresh_from_db()
        self.assertEqual(user.name, "New Name")

    def test_update_user_updates_avatar_when_changed(self):
        user = UserFactory(email="u@e.com", roles=[])
        user.avatar = ""
        user.save()
        claims = self._claims(
            sub=user.datatracker_subject_id,
            name=user.name,
            roles=[],
            email="u@e.com",
            picture="https://example.com/new.jpg",
        )
        self.backend.update_user(user, claims)
        user.refresh_from_db()
        self.assertEqual(user.avatar, "https://example.com/new.jpg")

    def test_update_user_clears_avatar_when_picture_claim_absent(self):
        user = UserFactory(email="u@e.com", roles=[])
        user.avatar = "https://example.com/old.jpg"
        user.save()
        claims = self._claims(
            sub=user.datatracker_subject_id,
            name=user.name,
            roles=[],
            email="u@e.com",
        )
        del claims["picture"]
        self.backend.update_user(user, claims)
        user.refresh_from_db()
        self.assertEqual(user.avatar, "")

    def test_update_user_updates_roles_when_changed(self):
        user = UserFactory(roles=[], email="u@e.com")
        claims = self._claims(
            sub=user.datatracker_subject_id,
            name=user.name,
            roles=[["auth", "rpc"]],
            email="u@e.com",
            picture=user.avatar,
        )
        self.backend.update_user(user, claims)
        user.refresh_from_db()
        self.assertEqual(user.roles, [["auth", "rpc"]])

    def test_update_user_updates_email_when_changed(self):
        user = UserFactory(email="old@example.com", roles=[])
        claims = self._claims(
            sub=user.datatracker_subject_id,
            name=user.name,
            roles=[],
            email="new@example.com",
            picture=user.avatar,
        )
        self.backend.update_user(user, claims)
        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")

    def test_update_user_updates_is_staff_when_admin_role_added(self):
        user = UserFactory(
            roles=[], email="u@e.com", is_staff=False, is_superuser=False
        )
        claims = self._claims(
            sub=user.datatracker_subject_id,
            name=user.name,
            roles=[["leadmaintainer", "tools"]],
            email="u@e.com",
            picture=user.avatar,
        )
        self.backend.update_user(user, claims)
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_update_user_does_not_save_when_nothing_changed(self):
        user = UserFactory(name="Same Name", email="same@example.com", roles=[])
        user.avatar = ""
        user.save()
        claims = {"name": "Same Name", "roles": [], "email": "same@example.com"}
        with patch.object(user, "save") as mock_save:
            self.backend.update_user(user, claims)
        mock_save.assert_not_called()

    # --- filter_users_by_claims ---

    def test_filter_users_by_claims_returns_matching_user(self):
        user = UserFactory(datatracker_subject_id="find-me")
        result = self.backend.filter_users_by_claims({"sub": "find-me"})
        self.assertIn(user, result)

    def test_filter_users_by_claims_empty_when_no_match(self):
        result = self.backend.filter_users_by_claims({"sub": "no-such-user"})
        self.assertEqual(result.count(), 0)
