# Copyright The IETF Trust 2026, All Rights Reserved

import datetime
import json

from django.test import TestCase

from errata.factories import ErratumFactory, RfcMetadataFactory, UserFactory
from errata.models import Status
from errata.utils import counts_per_authority, errata_json, unverified_errata


def _verifier(**roles_kwargs):
    """Return a user who passes is_verifier() with the given roles list."""
    return UserFactory(**roles_kwargs)


class UnverifiedErratumVerifierTest(TestCase):
    """
    Tests for the verifier-role query-building path of unverified_errata()
    (lines 31-70).  The rpc and non-verifier paths are already covered by
    UtilsTest in tests.py.
    """

    def setUp(self):
        self.reported = Status.objects.get(slug="reported")
        self.iab_rfc = RfcMetadataFactory(stream="iab")
        self.irtf_rfc = RfcMetadataFactory(stream="irtf")
        self.editorial_rfc = RfcMetadataFactory(stream="editorial")
        self.ise_rfc = RfcMetadataFactory(stream="ise")
        self.ops_rfc = RfcMetadataFactory(
            stream="ietf", area_acronym="ops", area_assignment=""
        )
        self.art_rfc = RfcMetadataFactory(
            stream="ietf", area_acronym="art", area_assignment=""
        )
        self.iab_erratum = ErratumFactory(
            rfc_metadata=self.iab_rfc, rfc_number=self.iab_rfc.rfc_number
        )
        self.irtf_erratum = ErratumFactory(
            rfc_metadata=self.irtf_rfc, rfc_number=self.irtf_rfc.rfc_number
        )
        self.editorial_erratum = ErratumFactory(
            rfc_metadata=self.editorial_rfc, rfc_number=self.editorial_rfc.rfc_number
        )
        self.ise_erratum = ErratumFactory(
            rfc_metadata=self.ise_rfc, rfc_number=self.ise_rfc.rfc_number
        )
        self.ops_erratum = ErratumFactory(
            rfc_metadata=self.ops_rfc, rfc_number=self.ops_rfc.rfc_number
        )
        self.art_erratum = ErratumFactory(
            rfc_metadata=self.art_rfc, rfc_number=self.art_rfc.rfc_number
        )

    def test_iab_chair_sees_iab_errata(self):
        user = UserFactory(roles=[["chair", "iab"]])
        result = unverified_errata(user)
        self.assertIn(self.iab_erratum, result)

    def test_iab_delegate_stream_manager_sees_iab_errata(self):
        user = UserFactory(roles=[["delegate_stream_manager", "iab"]])
        result = unverified_errata(user)
        self.assertIn(self.iab_erratum, result)

    def test_irtf_chair_sees_irtf_errata(self):
        user = UserFactory(roles=[["chair", "irtf"]])
        result = unverified_errata(user)
        self.assertIn(self.irtf_erratum, result)

    def test_irtf_delegate_stream_manager_sees_irtf_errata(self):
        user = UserFactory(roles=[["delegate_stream_manager", "irtf"]])
        result = unverified_errata(user)
        self.assertIn(self.irtf_erratum, result)

    def test_rsab_chair_sees_editorial_errata(self):
        user = UserFactory(roles=[["chair", "rsab"]])
        result = unverified_errata(user)
        self.assertIn(self.editorial_erratum, result)

    def test_rsab_delegate_stream_manager_sees_editorial_errata(self):
        user = UserFactory(roles=[["delegate_stream_manager", "rsab"]])
        result = unverified_errata(user)
        self.assertIn(self.editorial_erratum, result)

    def test_ise_chair_sees_ise_errata(self):
        user = UserFactory(roles=[["chair", "ise"]])
        result = unverified_errata(user)
        self.assertIn(self.ise_erratum, result)

    def test_ise_chair_does_not_see_irtf_errata(self):
        user = UserFactory(roles=[["chair", "ise"]])
        result = unverified_errata(user)
        self.assertNotIn(self.irtf_erratum, result)

    def test_iesg_ad_sees_own_area_errata(self):
        user = UserFactory(roles=[["ad", "iesg"], ["ad", "ops"]])
        result = unverified_errata(user)
        self.assertIn(self.ops_erratum, result)

    def test_iesg_ad_does_not_see_other_area_errata(self):
        user = UserFactory(roles=[["ad", "iesg"], ["ad", "ops"]])
        result = unverified_errata(user)
        self.assertNotIn(self.iab_erratum, result)

    def test_iesg_art_ad_sees_art_area_errata(self):
        user = UserFactory(roles=[["ad", "iesg"], ["ad", "art"]])
        result = unverified_errata(user)
        self.assertIn(self.art_erratum, result)

    def test_iesg_ad_without_area_role_does_not_see_area_errata(self):
        # Has ad/iesg but no specific area role — area queries are not added.
        user = UserFactory(roles=[["ad", "iesg"]])
        result = unverified_errata(user)
        self.assertNotIn(self.ops_erratum, result)

    def test_area_assignment_overrides_area_acronym(self):
        assigned_rfc = RfcMetadataFactory(
            stream="ietf", area_acronym="art", area_assignment="ops"
        )
        assigned_erratum = ErratumFactory(
            rfc_metadata=assigned_rfc, rfc_number=assigned_rfc.rfc_number
        )
        user = UserFactory(roles=[["ad", "iesg"], ["ad", "ops"]])
        result = unverified_errata(user)
        self.assertIn(assigned_erratum, result)


class ErrataJsonTest(TestCase):
    def test_no_errata_returns_empty_json_array(self):
        result = errata_json()
        self.assertEqual(json.loads(result), [])

    def test_erratum_produces_correct_fields(self):
        rfc = RfcMetadataFactory(rfc_number=9999)
        erratum = ErratumFactory(
            rfc_metadata=rfc,
            rfc_number=rfc.rfc_number,
            section="3.1",
            orig_text="Old text",
            corrected_text="New text",
            notes="A note",
            submitter_name="Alice",
            verifier_name=None,
        )
        rows = json.loads(errata_json())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["errata_id"], str(erratum.id))
        self.assertEqual(row["doc-id"], "RFC9999")
        self.assertEqual(row["errata_status_code"], erratum.status.name)
        self.assertEqual(row["errata_type_code"], erratum.erratum_type.name)
        self.assertEqual(row["section"], "3.1")
        self.assertEqual(row["orig_text"], "Old text")
        self.assertEqual(row["correct_text"], "New text")
        self.assertEqual(row["notes"], "A note")
        self.assertEqual(row["submitter_name"], "Alice")
        self.assertEqual(row["verifier_id"], "")
        self.assertIsNone(row["verifier_name"])

    def test_section_starting_with_99_is_stripped(self):
        erratum = ErratumFactory(section="99Introduction")
        rows = json.loads(errata_json())
        row = next(r for r in rows if r["errata_id"] == str(erratum.id))
        self.assertEqual(row["section"], "Introduction")

    def test_updated_at_none_produces_null_update_date(self):
        erratum = ErratumFactory()
        erratum._take_given_updated_at_value = True
        erratum.updated_at = None
        erratum.save()
        rows = json.loads(errata_json())
        row = next(r for r in rows if r["errata_id"] == str(erratum.id))
        self.assertIsNone(row["update_date"])

    def test_updated_at_set_produces_formatted_date_string(self):
        erratum = ErratumFactory()
        fixed = datetime.datetime(2024, 6, 15, 12, 30, 45, tzinfo=datetime.UTC)
        erratum._take_given_updated_at_value = True
        erratum.updated_at = fixed
        erratum.save()
        rows = json.loads(errata_json())
        row = next(r for r in rows if r["errata_id"] == str(erratum.id))
        self.assertEqual(row["update_date"], "2024-06-15 12:30:45")

    def test_submit_date_is_iso_date_string(self):
        erratum = ErratumFactory()
        rows = json.loads(errata_json())
        row = next(r for r in rows if r["errata_id"] == str(erratum.id))
        # Verify it's a valid ISO date (YYYY-MM-DD)
        datetime.date.fromisoformat(row["submit_date"])


class CountsPerAuthorityTest(TestCase):
    def _technical_reported(self, **rfc_kwargs):
        rfc = RfcMetadataFactory(**rfc_kwargs)
        return ErratumFactory(
            rfc_metadata=rfc,
            rfc_number=rfc.rfc_number,
            erratum_type__slug="technical",
            status=Status.objects.get(slug="reported"),
        )

    def test_no_errata_all_counts_zero(self):
        result = counts_per_authority()
        for authority, count in result.items():
            with self.subTest(authority=authority):
                self.assertEqual(count, 0)

    def test_returns_all_expected_authority_keys(self):
        result = counts_per_authority()
        expected = {
            "art",
            "gen",
            "int",
            "ops",
            "rtg",
            "sec",
            "wit",
            "iab",
            "ise",
            "irtf",
            "legacy",
            "editorial",
        }
        self.assertEqual(set(result.keys()), expected)

    def test_iab_stream_counted_under_iab(self):
        self._technical_reported(stream="iab")
        result = counts_per_authority()
        self.assertEqual(result["iab"], 1)
        self.assertEqual(result["ise"], 0)

    def test_ise_stream_counted_under_ise(self):
        self._technical_reported(stream="ise")
        result = counts_per_authority()
        self.assertEqual(result["ise"], 1)
        self.assertEqual(result["iab"], 0)

    def test_irtf_stream_counted_under_irtf(self):
        self._technical_reported(stream="irtf")
        result = counts_per_authority()
        self.assertEqual(result["irtf"], 1)

    def test_editorial_stream_counted_under_editorial(self):
        self._technical_reported(stream="editorial")
        result = counts_per_authority()
        self.assertEqual(result["editorial"], 1)

    def test_legacy_stream_counted_under_legacy(self):
        self._technical_reported(stream="legacy", area_assignment="")
        result = counts_per_authority()
        self.assertEqual(result["legacy"], 1)

    def test_art_area_acronym_counted_under_art(self):
        self._technical_reported(area_acronym="art", area_assignment="")
        result = counts_per_authority()
        self.assertEqual(result["art"], 1)

    def test_app_area_acronym_counted_under_art(self):
        self._technical_reported(area_acronym="app", area_assignment="")
        result = counts_per_authority()
        self.assertEqual(result["art"], 1)

    def test_rai_area_acronym_counted_under_art(self):
        self._technical_reported(area_acronym="rai", area_assignment="")
        result = counts_per_authority()
        self.assertEqual(result["art"], 1)

    def test_ops_area_assignment_counted_under_ops(self):
        self._technical_reported(area_acronym="art", area_assignment="ops")
        result = counts_per_authority()
        self.assertEqual(result["ops"], 1)
        self.assertEqual(result["art"], 0)

    def test_ops_area_acronym_counted_under_ops(self):
        self._technical_reported(area_acronym="ops", area_assignment="")
        result = counts_per_authority()
        self.assertEqual(result["ops"], 1)

    def test_only_technical_reported_are_counted(self):
        from errata.models import ErratumType

        rfc = RfcMetadataFactory(stream="iab")
        # editorial type — should not count
        ErratumFactory(
            rfc_metadata=rfc,
            rfc_number=rfc.rfc_number,
            erratum_type=ErratumType.objects.get(slug="editorial"),
            status=Status.objects.get(slug="reported"),
        )
        # technical but verified — should not count
        ErratumFactory(
            rfc_metadata=rfc,
            rfc_number=rfc.rfc_number,
            erratum_type=ErratumType.objects.get(slug="technical"),
            status=Status.objects.get(slug="verified"),
        )
        result = counts_per_authority()
        self.assertEqual(result["iab"], 0)

    def test_as_of_uses_historical_records(self):
        self._technical_reported(stream="iab")
        future = datetime.datetime(2099, 1, 1, tzinfo=datetime.UTC)
        result = counts_per_authority(as_of=future)
        self.assertEqual(result["iab"], 1)

    def test_as_of_past_excludes_errata_created_after(self):
        self._technical_reported(stream="iab")
        past = datetime.datetime(2000, 1, 1, tzinfo=datetime.UTC)
        result = counts_per_authority(as_of=past)
        self.assertEqual(result["iab"], 0)
