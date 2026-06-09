# Copyright The IETF Trust 2026, All Rights Reserved

from types import SimpleNamespace

from django.test import TestCase

from errata.factories import (
    ErratumFactory,
    RfcMetadataFactory,
    RpcUserFactory,
    UserFactory,
)
from errata.templatetags.filters import (
    has_role as has_role_filter,
    is_classifiable_by,
    month_name,
    suppress_strings_starting_with_99,
    txt_errata_section,
    txt_errata_verifying_party,
)


def _fetch_erratum(erratum):
    from errata.models import Erratum

    return Erratum.objects.select_related("rfc_metadata", "status", "erratum_type").get(
        pk=erratum.pk
    )


class SuppressStringsStartingWith99Test(TestCase):
    def test_string_starting_with_99_returns_dash(self):
        self.assertEqual(suppress_strings_starting_with_99("99anything"), "-")

    def test_string_starting_with_99_and_short_returns_dash(self):
        self.assertEqual(suppress_strings_starting_with_99("99"), "-")

    def test_other_string_returned_unchanged(self):
        self.assertEqual(suppress_strings_starting_with_99("3.1"), "3.1")

    def test_non_string_returned_unchanged(self):
        self.assertEqual(suppress_strings_starting_with_99(42), 42)


class MonthNameTest(TestCase):
    def test_returns_correct_month_name(self):
        self.assertEqual(month_name(3), "March")
        self.assertEqual(month_name(12), "December")


class HasRoleFilterTest(TestCase):
    def test_none_user_returns_false(self):
        self.assertFalse(has_role_filter(None, "rpc"))

    def test_rpc_user_with_rpc_role_string_returns_true(self):
        user = RpcUserFactory()
        self.assertTrue(has_role_filter(user, "rpc"))

    def test_regular_user_with_rpc_role_string_returns_false(self):
        user = UserFactory()
        self.assertFalse(has_role_filter(user, "rpc"))

    def test_comma_separated_role_names_parsed(self):
        user = RpcUserFactory()
        self.assertTrue(has_role_filter(user, "verifier,rpc"))


class IsClassifiableByTest(TestCase):
    def test_rpc_user_can_classify_reported_erratum(self):
        user = RpcUserFactory()
        erratum = _fetch_erratum(ErratumFactory())
        self.assertTrue(is_classifiable_by(erratum, user))

    def test_regular_user_cannot_classify(self):
        user = UserFactory()
        erratum = _fetch_erratum(ErratumFactory())
        self.assertFalse(is_classifiable_by(erratum, user))


class TxtErrataSectionTest(TestCase):
    def _e(self, section):
        return SimpleNamespace(section=section)

    def test_global_section_uppercase(self):
        self.assertEqual(
            txt_errata_section(self._e("GLOBAL")),
            "Throughout the document, when it says:",
        )

    def test_global_section_lowercase(self):
        self.assertEqual(
            txt_errata_section(self._e("global")),
            "Throughout the document, when it says:",
        )

    def test_normal_section_returns_section_prefix(self):
        self.assertEqual(txt_errata_section(self._e("3.1")), "Section 3.1 says:")

    def test_99_prefix_section_strips_prefix(self):
        self.assertEqual(txt_errata_section(self._e("99Introduction")), "Introduction")

    def test_99_prefix_with_just_two_chars_returns_empty(self):
        self.assertEqual(txt_errata_section(self._e("99")), "")


class TxtErrataVerifyingPartyTest(TestCase):
    def _make(self, stream, area_assignment=""):
        rfc = RfcMetadataFactory(stream=stream, area_assignment=area_assignment)
        return _fetch_erratum(
            ErratumFactory(rfc_metadata=rfc, rfc_number=rfc.rfc_number)
        )

    def test_ietf_stream_returns_iesg(self):
        self.assertEqual(txt_errata_verifying_party(self._make("ietf")), "IESG")

    def test_area_assignment_returns_iesg(self):
        self.assertEqual(
            txt_errata_verifying_party(self._make("iab", area_assignment="ops")), "IESG"
        )

    def test_irtf_stream_returns_irsg(self):
        self.assertEqual(txt_errata_verifying_party(self._make("irtf")), "IRSG")

    def test_iab_stream_returns_iab(self):
        self.assertEqual(txt_errata_verifying_party(self._make("iab")), "IAB")

    def test_ise_stream_returns_ise_and_editorial_board(self):
        self.assertEqual(
            txt_errata_verifying_party(self._make("ise")), "ISE & Editorial Board"
        )

    def test_editorial_stream_returns_rsab(self):
        self.assertEqual(txt_errata_verifying_party(self._make("editorial")), "RSAB")

    def test_other_stream_returns_rfc_editor(self):
        self.assertEqual(txt_errata_verifying_party(self._make("legacy")), "RFC-Editor")
