# Copyright The IETF Trust 2026, All Rights Reserved

from unittest.mock import MagicMock

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from errata.utils_api import is_valid_token, requires_api_token


class IsValidTokenTest(TestCase):
    @override_settings(APP_API_TOKENS={"my.endpoint": ["list-token"]})
    def test_list_token_accepted(self):
        self.assertTrue(is_valid_token("my.endpoint", "list-token"))

    @override_settings(APP_API_TOKENS={"my.endpoint": "scalar-token"})
    def test_scalar_token_is_wrapped_and_accepted(self):
        # When the store holds a plain string rather than list, it is wrapped
        # in a list before matching (line 19).
        self.assertTrue(is_valid_token("my.endpoint", "scalar-token"))

    @override_settings(APP_API_TOKENS={"my.endpoint": "scalar-token"})
    def test_wrong_token_rejected_when_stored_as_scalar(self):
        self.assertFalse(is_valid_token("my.endpoint", "wrong"))

    def test_unknown_endpoint_returns_false(self):
        self.assertFalse(is_valid_token("no.such.endpoint", "any-token"))

    @override_settings(APP_API_TOKENS={})
    def test_empty_token_store_returns_false(self):
        self.assertFalse(is_valid_token("my.endpoint", "any-token"))


class RequiresApiTokenDecoratorTest(TestCase):
    def test_explicit_endpoint_string_sets_endpoint_name(self):
        # @requires_api_token("name") takes lines 73-74 then line 56.
        @requires_api_token("custom.endpoint")
        def my_view(request):
            return HttpResponse("ok")

        rf = RequestFactory()

        # No token → 403
        response = my_view(rf.get("/"))
        self.assertEqual(response.status_code, 403)

        # Valid token for that endpoint → 200
        with override_settings(APP_API_TOKENS={"custom.endpoint": ["tok"]}):
            request = rf.get("/")
            request.META["HTTP_X_API_KEY"] = "tok"
            self.assertEqual(my_view(request).status_code, 200)

    def test_no_parens_form_infers_endpoint_from_qualname(self):
        # @requires_api_token (no parens) takes lines 68-71.
        @requires_api_token
        def my_view(request):
            return HttpResponse("ok")

        module = my_view.__wrapped__.__module__
        qualname = my_view.__wrapped__.__qualname__
        endpoint = f"{module}.{qualname}"

        rf = RequestFactory()

        with override_settings(APP_API_TOKENS={endpoint: ["tok"]}):
            request = rf.get("/")
            request.META["HTTP_X_API_KEY"] = "tok"
            self.assertEqual(my_view(request).status_code, 200)

    def test_callable_without_qualname_raises_type_error(self):
        # Line 50: a callable whose __qualname__ is None triggers TypeError.
        func = MagicMock()
        func.__qualname__ = None
        with self.assertRaises(TypeError):
            requires_api_token(func)
