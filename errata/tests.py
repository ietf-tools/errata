# Copyright The IETF Trust 2025-2026, All Rights Reserved

import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from errata.factories import (
    ErratumFactory,
    MailMessageFactory,
    RfcMetadataFactory,
    RpcUserFactory,
    StagedErratumFactory,
    UserFactory,
)
from errata.forms import (
    ChooseRfcForm,
    EditErratumForm,
    EditStagedErratumForm,
    ErrataSearchForm,
    RfcNumberListForm,
)
from errata.models import (
    AddressListField,
    Erratum,
    ErratumType,
    StagedErratum,
    StagedErratumStatus,
    Status,
)
from errata.search import search_errata


class AddressListFieldTest(TestCase):
    def test_parse_valid_single_email(self):
        result = AddressListField._parse_header_value("test@example.com")
        self.assertEqual(result, ["test@example.com"])

    def test_parse_multiple_emails(self):
        result = AddressListField._parse_header_value("a@b.com, c@d.com")
        self.assertIn("a@b.com", result)
        self.assertIn("c@d.com", result)
        self.assertEqual(len(result), 2)

    def test_parse_empty_string(self):
        result = AddressListField._parse_header_value("")
        self.assertEqual(result, [])

    def test_get_prep_value_with_list(self):
        field = AddressListField()
        result = field.get_prep_value(["a@b.com", "c@d.com"])
        self.assertIn("a@b.com", result)
        self.assertIn("c@d.com", result)

    def test_get_prep_value_with_string(self):
        field = AddressListField()
        result = field.get_prep_value("test@example.com")
        self.assertEqual(result, "test@example.com")

    def test_to_python_with_string(self):
        field = AddressListField()
        result = field.to_python("test@example.com")
        self.assertEqual(result, ["test@example.com"])

    def test_to_python_with_list(self):
        field = AddressListField()
        result = field.to_python(["a@b.com", "c@d.com"])
        self.assertIn("a@b.com", result)
        self.assertIn("c@d.com", result)


class RfcMetadataModelTest(TestCase):
    def test_display_source_ise(self):
        rfc = RfcMetadataFactory(stream="ise")
        self.assertEqual(rfc.display_source(), "INDEPENDENT")

    def test_display_source_iab(self):
        rfc = RfcMetadataFactory(stream="iab")
        self.assertEqual(rfc.display_source(), "IAB")

    def test_display_source_ietf_group_none(self):
        rfc = RfcMetadataFactory(
            stream="ietf", group_acronym="none", area_acronym="ops"
        )
        self.assertEqual(rfc.display_source(), "IETF - NON WORKING GROUP")

    def test_display_source_ietf_group_gen(self):
        rfc = RfcMetadataFactory(stream="ietf", group_acronym="gen", area_acronym="")
        self.assertEqual(rfc.display_source(), "IETF - NON WORKING GROUP")

    def test_display_source_ietf_wg_with_area(self):
        rfc = RfcMetadataFactory(
            stream="ietf", group_acronym="httpbis", area_acronym="art"
        )
        self.assertEqual(rfc.display_source(), "httpbis (art)")

    def test_display_source_legacy(self):
        rfc = RfcMetadataFactory(stream="legacy", group_acronym="none")
        self.assertEqual(rfc.display_source(), "Legacy")

    def test_display_source_irtf(self):
        rfc = RfcMetadataFactory(stream="irtf", group_acronym="none")
        self.assertEqual(rfc.display_source(), "IRTF")

    def test_display_source_empty_stream(self):
        rfc = RfcMetadataFactory(stream="", group_acronym="none")
        self.assertEqual(rfc.display_source(), "")

    def test_display_source_with_assignment(self):
        rfc = RfcMetadataFactory(
            stream="ietf",
            group_acronym="httpbis",
            area_acronym="art",
            area_assignment="ops",
        )
        result = rfc.display_source_with_assignment()
        self.assertTrue(result.endswith("(ops)"))

    def test_display_source_with_assignment_empty(self):
        rfc = RfcMetadataFactory(
            stream="ietf",
            group_acronym="httpbis",
            area_acronym="art",
            area_assignment="",
        )
        self.assertEqual(rfc.display_source_with_assignment(), rfc.display_source())

    def test_str(self):
        rfc = RfcMetadataFactory(rfc_number=4321, title="Some Protocol")
        self.assertEqual(str(rfc), "RFC 4321: Some Protocol")


class ErratumModelTest(TestCase):
    def test_save_sets_updated_at(self):
        erratum = ErratumFactory()
        past_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
        Erratum.objects.filter(pk=erratum.pk).update(updated_at=past_time)
        erratum.refresh_from_db()
        original = erratum.updated_at
        erratum.section = "2"
        erratum.save()
        self.assertIsNotNone(erratum.updated_at)
        self.assertGreater(erratum.updated_at, original)

    def test_save_respects_take_given_updated_at_value(self):
        erratum = ErratumFactory()
        fixed_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
        erratum._take_given_updated_at_value = True
        erratum.updated_at = fixed_time
        erratum.save()
        self.assertEqual(erratum.updated_at, fixed_time)

    def test_str(self):
        erratum = ErratumFactory()
        self.assertEqual(
            str(erratum), f"Erratum {erratum.id} for RFC {erratum.rfc_number}"
        )


class StagedErratumModelTest(TestCase):
    def test_default_formats(self):
        staged = StagedErratumFactory()
        self.assertEqual(staged.formats, ["TXT"])

    def test_str(self):
        staged = StagedErratumFactory()
        self.assertEqual(
            str(staged), f"StagedErratum {staged.id} for RFC {staged.rfc_number}"
        )


class MailMessageModelTest(TestCase):
    def test_as_emailmessage_plain(self):
        msg = MailMessageFactory(body="plain text body")
        em = msg.as_emailmessage()
        self.assertEqual(em.subject, msg.subject)
        self.assertNotEqual(em.content_subtype, "html")

    def test_as_emailmessage_html(self):
        msg = MailMessageFactory(body="<html><body>content</body></html>")
        em = msg.as_emailmessage()
        self.assertEqual(em.content_subtype, "html")


class ErrataSearchFormTest(TestCase):
    def test_valid_date_year_only(self):
        form = ErrataSearchForm(data={"date": "2020"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["date"], "2020")

    def test_valid_date_year_month(self):
        form = ErrataSearchForm(data={"date": "2020-06"})
        self.assertTrue(form.is_valid())

    def test_valid_date_year_month_day(self):
        form = ErrataSearchForm(data={"date": "2020-06-15"})
        self.assertTrue(form.is_valid())

    def test_valid_empty_date(self):
        form = ErrataSearchForm(data={"date": ""})
        self.assertTrue(form.is_valid())

    def test_invalid_date_slash_format(self):
        form = ErrataSearchForm(data={"date": "06/2020"})
        self.assertFalse(form.is_valid())
        self.assertIn("date", form.errors)

    def test_invalid_date_no_separators(self):
        form = ErrataSearchForm(data={"date": "20200615"})
        self.assertFalse(form.is_valid())
        self.assertIn("date", form.errors)


class ChooseRfcFormTest(TestCase):
    def setUp(self):
        self.rfc = RfcMetadataFactory()

    def test_valid_existing_rfc_number(self):
        form = ChooseRfcForm(data={"rfc_number": self.rfc.rfc_number})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rfc_number"], self.rfc.rfc_number)

    def test_negative_rfc_number(self):
        form = ChooseRfcForm(data={"rfc_number": -1})
        self.assertFalse(form.is_valid())
        self.assertIn("rfc_number", form.errors)

    def test_zero_rfc_number(self):
        form = ChooseRfcForm(data={"rfc_number": 0})
        self.assertFalse(form.is_valid())
        self.assertIn("rfc_number", form.errors)

    def test_nonexistent_rfc_number(self):
        form = ChooseRfcForm(data={"rfc_number": 999999})
        self.assertFalse(form.is_valid())
        self.assertIn("rfc_number", form.errors)


class EditStagedErratumFormTest(TestCase):
    def _valid_data(self, rfc_number):
        data = {
            "submitter_name": "Test User",
            "submitter_email": "test@example.com",
            "section": "1",
            "orig_text": "Original text",
            "corrected_text": "Corrected text",
            "notes": "Some notes",
        }
        if rfc_number >= 8650:
            data["formats"] = ["TXT"]
        return data

    def test_valid_old_rfc(self):
        form = EditStagedErratumForm(rfc_number=1000, data=self._valid_data(1000))
        self.assertTrue(form.is_valid())

    def test_valid_new_rfc(self):
        form = EditStagedErratumForm(rfc_number=9000, data=self._valid_data(9000))
        self.assertTrue(form.is_valid())

    def test_same_orig_and_corrected_text_is_invalid(self):
        data = self._valid_data(1000)
        data["corrected_text"] = data["orig_text"]
        form = EditStagedErratumForm(rfc_number=1000, data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("corrected_text", form.errors)

    def test_old_rfc_has_no_formats_field(self):
        form = EditStagedErratumForm(rfc_number=1000, data={})
        self.assertNotIn("formats", form.fields)

    def test_new_rfc_has_formats_field(self):
        form = EditStagedErratumForm(rfc_number=9000, data={})
        self.assertIn("formats", form.fields)


class EditErratumFormTest(TestCase):
    def setUp(self):
        self.old_erratum = ErratumFactory(
            rfc_metadata=RfcMetadataFactory(rfc_number=1000),
            rfc_number=1000,
        )
        self.new_erratum = ErratumFactory(
            rfc_metadata=RfcMetadataFactory(rfc_number=9000),
            rfc_number=9000,
        )

    def _valid_data(self, rfc_number):
        data = {
            "erratum_type": "technical",
            "section": "1",
            "orig_text": "Original text",
            "corrected_text": "Corrected text",
            "submitter_name": "Test User",
            "submitter_email": "test@example.com",
            "notes": "",
        }
        if rfc_number >= 8650:
            data["formats"] = ["TXT"]
        return data

    def test_old_rfc_form_has_no_formats_field(self):
        form = EditErratumForm(instance=self.old_erratum)
        self.assertNotIn("formats", form.fields)

    def test_new_rfc_form_has_formats_field(self):
        form = EditErratumForm(instance=self.new_erratum)
        self.assertIn("formats", form.fields)

    def test_same_orig_and_corrected_text_is_invalid(self):
        data = self._valid_data(9000)
        data["corrected_text"] = data["orig_text"]
        form = EditErratumForm(instance=self.new_erratum, data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("corrected_text", form.errors)

    def test_valid_old_rfc_form(self):
        form = EditErratumForm(instance=self.old_erratum, data=self._valid_data(1000))
        self.assertTrue(form.is_valid())

    def test_valid_new_rfc_form(self):
        form = EditErratumForm(instance=self.new_erratum, data=self._valid_data(9000))
        self.assertTrue(form.is_valid())


class RfcNumberListFormTest(TestCase):
    def test_empty_returns_empty_list(self):
        form = RfcNumberListForm(data={"rfc_numbers": ""})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rfc_numbers"], [])

    def test_single_number(self):
        form = RfcNumberListForm(data={"rfc_numbers": "1234"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rfc_numbers"], [1234])

    def test_range(self):
        form = RfcNumberListForm(data={"rfc_numbers": "1234-1236"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rfc_numbers"], [1234, 1235, 1236])

    def test_comma_separated(self):
        form = RfcNumberListForm(data={"rfc_numbers": "1234,5678"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rfc_numbers"], [1234, 5678])

    def test_mixed_single_and_range(self):
        form = RfcNumberListForm(data={"rfc_numbers": "100, 200-202"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rfc_numbers"], [100, 200, 201, 202])

    def test_invalid_non_numeric(self):
        form = RfcNumberListForm(data={"rfc_numbers": "abc"})
        self.assertFalse(form.is_valid())

    def test_reversed_range(self):
        form = RfcNumberListForm(data={"rfc_numbers": "1236-1234"})
        self.assertFalse(form.is_valid())

    def test_non_numeric_range_bounds_are_invalid(self):
        form = RfcNumberListForm(data={"rfc_numbers": "abc-def"})
        self.assertFalse(form.is_valid())


class SearchErrataTest(TestCase):
    def setUp(self):
        self.rfc1 = RfcMetadataFactory(
            stream="ietf", area_acronym="ops", group_acronym="wgone"
        )
        self.rfc2 = RfcMetadataFactory(
            stream="iab", area_acronym="", group_acronym="none"
        )
        self.technical = ErratumType.objects.get(slug="technical")
        self.editorial = ErratumType.objects.get(slug="editorial")
        self.reported = Status.objects.get(slug="reported")
        self.verified = Status.objects.get(slug="verified")
        self.erratum1 = ErratumFactory(
            rfc_metadata=self.rfc1,
            rfc_number=self.rfc1.rfc_number,
            erratum_type=self.technical,
            status=self.reported,
            submitter_name="Alice Smith",
            submitted_at=datetime.datetime(2022, 3, 15, tzinfo=datetime.UTC),
        )
        self.erratum2 = ErratumFactory(
            rfc_metadata=self.rfc2,
            rfc_number=self.rfc2.rfc_number,
            erratum_type=self.editorial,
            status=self.verified,
            submitter_name="Bob Jones",
            submitted_at=datetime.datetime(2021, 7, 20, tzinfo=datetime.UTC),
        )

    def test_unbound_form_returns_empty(self):
        form = ErrataSearchForm()
        self.assertFalse(form.is_bound)
        self.assertEqual(search_errata(form).count(), 0)

    def test_search_by_rfc_number(self):
        form = ErrataSearchForm(data={"rfc_number": self.rfc1.rfc_number})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_errata_id(self):
        form = ErrataSearchForm(data={"errata_id": self.erratum1.pk})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_status_reported(self):
        form = ErrataSearchForm(data={"status": "reported"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_status_verified(self):
        form = ErrataSearchForm(data={"status": "verified"})
        result = search_errata(form)
        self.assertNotIn(self.erratum1, result)
        self.assertIn(self.erratum2, result)

    def test_search_by_status_verified_reported(self):
        form = ErrataSearchForm(data={"status": "verified_reported"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertIn(self.erratum2, result)

    def test_search_by_status_held_for_doc_update(self):
        held = Status.objects.get(slug="held_for_doc_update")
        held_erratum = ErratumFactory(
            rfc_metadata=self.rfc1,
            rfc_number=self.rfc1.rfc_number,
            status=held,
        )
        form = ErrataSearchForm(data={"status": "held_for_doc_update"})
        result = search_errata(form)
        self.assertIn(held_erratum, result)
        self.assertNotIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_errata_type_technical(self):
        form = ErrataSearchForm(data={"errata_type": "technical"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_errata_type_editorial(self):
        form = ErrataSearchForm(data={"errata_type": "editorial"})
        result = search_errata(form)
        self.assertNotIn(self.erratum1, result)
        self.assertIn(self.erratum2, result)

    def test_search_by_submitter_name(self):
        form = ErrataSearchForm(data={"submitter_name": "Alice"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_date_year(self):
        form = ErrataSearchForm(data={"date": "2022"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_date_year_month(self):
        form = ErrataSearchForm(data={"date": "2022-03"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_date_year_month_day(self):
        form = ErrataSearchForm(data={"date": "2022-03-15"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_wg_acronym(self):
        form = ErrataSearchForm(data={"wg_acronym": "wgone"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_no_filters_returns_all(self):
        form = ErrataSearchForm(data={})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertIn(self.erratum2, result)

    def test_search_by_area_non_art(self):
        form = ErrataSearchForm(data={"area": "ops"})
        result = search_errata(form)
        self.assertIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)

    def test_search_by_area_art_expands_to_app_and_rai(self):
        art_rfc = RfcMetadataFactory(
            stream="ietf", area_acronym="art", area_assignment=""
        )
        art_erratum = ErratumFactory(
            rfc_metadata=art_rfc, rfc_number=art_rfc.rfc_number
        )
        app_rfc = RfcMetadataFactory(
            stream="ietf", area_acronym="app", area_assignment=""
        )
        app_erratum = ErratumFactory(
            rfc_metadata=app_rfc, rfc_number=app_rfc.rfc_number
        )
        rai_rfc = RfcMetadataFactory(
            stream="ietf", area_acronym="rai", area_assignment=""
        )
        rai_erratum = ErratumFactory(
            rfc_metadata=rai_rfc, rfc_number=rai_rfc.rfc_number
        )
        form = ErrataSearchForm(data={"area": "art"})
        result = search_errata(form)
        self.assertIn(art_erratum, result)
        self.assertIn(app_erratum, result)
        self.assertIn(rai_erratum, result)
        self.assertNotIn(self.erratum1, result)

    def test_search_by_stream_iab(self):
        form = ErrataSearchForm(data={"stream": "IAB"})
        result = search_errata(form)
        self.assertIn(self.erratum2, result)
        self.assertNotIn(self.erratum1, result)

    def test_search_by_stream_independent_maps_to_ise(self):
        ise_rfc = RfcMetadataFactory(stream="ise")
        ise_erratum = ErratumFactory(
            rfc_metadata=ise_rfc, rfc_number=ise_rfc.rfc_number
        )
        form = ErrataSearchForm(data={"stream": "INDEPENDENT"})
        result = search_errata(form)
        self.assertIn(ise_erratum, result)
        self.assertNotIn(self.erratum1, result)
        self.assertNotIn(self.erratum2, result)


class PublicViewTest(TestCase):
    def setUp(self):
        self.rfc = RfcMetadataFactory()
        self.erratum = ErratumFactory(
            rfc_metadata=self.rfc, rfc_number=self.rfc.rfc_number
        )
        self.staged = StagedErratumFactory(
            rfc_metadata=self.rfc,
            rfc_number=self.rfc.rfc_number,
            entry_status=StagedErratumStatus.INCOMPLETE,
        )

    def test_search_get_returns_200(self):
        response = self.client.get(reverse("errata_search"))
        self.assertEqual(response.status_code, 200)

    def test_search_get_with_rfc_number_returns_200(self):
        response = self.client.get(
            reverse("errata_search"), {"rfc_number": self.rfc.rfc_number}
        )
        self.assertEqual(response.status_code, 200)

    def test_detail_get_returns_200(self):
        response = self.client.get(
            reverse("errata_detail", kwargs={"pk": self.erratum.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_new_entry_instructions_get_returns_200(self):
        response = self.client.get(reverse("errata_new_entry_instructions"))
        self.assertEqual(response.status_code, 200)

    def test_new_entry_instructions_post_valid_rfc_redirects(self):
        response = self.client.post(
            reverse("errata_new_entry_instructions"),
            {"rfc_number": self.rfc.rfc_number},
        )
        self.assertRedirects(
            response,
            reverse(
                "errata_new_review_existing",
                kwargs={"rfc_number": self.rfc.rfc_number},
            ),
        )

    def test_new_entry_instructions_post_nonexistent_rfc_returns_invalid_form(self):
        response = self.client.post(
            reverse("errata_new_entry_instructions"),
            {"rfc_number": 999999},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())

    def test_new_review_existing_get_unknown_rfc_shows_error(self):
        response = self.client.get(
            reverse("errata_new_review_existing", kwargs={"rfc_number": 999999})
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("error_message", response.context)

    def test_new_review_existing_get_known_rfc_returns_200(self):
        response = self.client.get(
            reverse(
                "errata_new_review_existing",
                kwargs={"rfc_number": self.rfc.rfc_number},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_new_review_existing_post_confirm_creates_staged_erratum(self):
        count_before = StagedErratum.objects.count()
        response = self.client.post(
            reverse(
                "errata_new_review_existing",
                kwargs={"rfc_number": self.rfc.rfc_number},
            ),
            {"confirm": True},
        )
        self.assertEqual(StagedErratum.objects.count(), count_before + 1)
        new_staged = StagedErratum.objects.latest("created_at")
        self.assertRedirects(
            response,
            reverse("errata_new_edit", kwargs={"staged_erratum_id": new_staged.id}),
        )

    def test_new_edit_get_returns_200(self):
        response = self.client.get(
            reverse("errata_new_edit", kwargs={"staged_erratum_id": self.staged.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_new_edit_post_valid_redirects_to_preview(self):
        data = {
            "submitter_name": "Test Submitter",
            "submitter_email": "test@example.com",
            "section": "3",
            "orig_text": "Old text content",
            "corrected_text": "New text content",
            "notes": "Some notes",
        }
        if self.rfc.rfc_number >= 8650:
            data["formats"] = ["TXT"]
        response = self.client.post(
            reverse("errata_new_edit", kwargs={"staged_erratum_id": self.staged.id}),
            data,
        )
        self.assertRedirects(
            response,
            reverse("errata_new_preview", kwargs={"staged_erratum_id": self.staged.id}),
        )

    def test_new_edit_post_same_texts_returns_form_errors(self):
        data = {
            "submitter_name": "Test Submitter",
            "submitter_email": "test@example.com",
            "section": "3",
            "orig_text": "Same text",
            "corrected_text": "Same text",
            "notes": "Some notes",
        }
        response = self.client.post(
            reverse("errata_new_edit", kwargs={"staged_erratum_id": self.staged.id}),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("corrected_text", response.context["form"].errors)

    def test_new_preview_get_incomplete_returns_200(self):
        response = self.client.get(
            reverse("errata_new_preview", kwargs={"staged_erratum_id": self.staged.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_new_preview_get_submitted_shows_success_template(self):
        submitted = StagedErratumFactory(
            rfc_metadata=self.rfc,
            rfc_number=self.rfc.rfc_number,
            entry_status=StagedErratumStatus.SUBMITTED,
        )
        response = self.client.get(
            reverse("errata_new_preview", kwargs={"staged_erratum_id": submitted.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "errata/new_submission_success.html")

    def test_new_preview_post_return_to_edit_redirects(self):
        response = self.client.post(
            reverse("errata_new_preview", kwargs={"staged_erratum_id": self.staged.id}),
            {"return_to_edit": "1"},
        )
        self.assertRedirects(
            response,
            reverse("errata_new_edit", kwargs={"staged_erratum_id": self.staged.id}),
        )

    def test_new_preview_post_submit_for_screening_marks_submitted(self):
        response = self.client.post(
            reverse("errata_new_preview", kwargs={"staged_erratum_id": self.staged.id}),
            {"submit_for_screening": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "errata/new_submission_success.html")
        self.staged.refresh_from_db()
        self.assertEqual(self.staged.entry_status, StagedErratumStatus.SUBMITTED)
        self.assertIsNotNone(self.staged.submitted_at)


class RpcViewTest(TestCase):
    def setUp(self):
        self.rpc_user = RpcUserFactory()
        self.regular_user = UserFactory()
        self.rfc = RfcMetadataFactory()
        self.staged = StagedErratumFactory(
            rfc_metadata=self.rfc,
            rfc_number=self.rfc.rfc_number,
            entry_status=StagedErratumStatus.SUBMITTED,
        )
        self.erratum = ErratumFactory(
            rfc_metadata=self.rfc, rfc_number=self.rfc.rfc_number
        )

    def test_staged_list_unauthenticated_returns_403(self):
        response = self.client.get(reverse("errata_staged_list"))
        self.assertEqual(response.status_code, 403)

    def test_staged_list_regular_user_returns_403(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("errata_staged_list"))
        self.assertEqual(response.status_code, 403)

    def test_staged_list_rpc_user_returns_200(self):
        self.client.force_login(self.rpc_user)
        response = self.client.get(reverse("errata_staged_list"))
        self.assertEqual(response.status_code, 200)

    def test_staged_list_post_delete_redirects_to_confirm(self):
        self.client.force_login(self.rpc_user)
        response = self.client.post(
            reverse("errata_staged_list"),
            {"uuid": str(self.staged.id), "action": "delete"},
        )
        self.assertRedirects(
            response,
            reverse(
                "errata_staged_confirm_delete",
                kwargs={"staged_erratum_id": self.staged.id},
            ),
        )

    def test_staged_list_post_edit_redirects_to_edit(self):
        self.client.force_login(self.rpc_user)
        response = self.client.post(
            reverse("errata_staged_list"),
            {"uuid": str(self.staged.id), "action": "edit"},
        )
        self.assertRedirects(
            response,
            reverse(
                "errata_staged_rpc_edit",
                kwargs={"staged_erratum_id": self.staged.id},
            ),
        )

    def test_staged_list_post_post_technical_redirects_to_add_to_unverified(self):
        self.client.force_login(self.rpc_user)
        response = self.client.post(
            reverse("errata_staged_list"),
            {"uuid": str(self.staged.id), "action": "post_technical"},
        )
        self.assertRedirects(
            response,
            reverse(
                "errata_staged_rpc_add_to_unverified",
                kwargs={
                    "staged_erratum_id": self.staged.id,
                    "erratum_type": "technical",
                },
            ),
        )

    def test_staged_confirm_delete_get_returns_200(self):
        self.client.force_login(self.rpc_user)
        response = self.client.get(
            reverse(
                "errata_staged_confirm_delete",
                kwargs={"staged_erratum_id": self.staged.id},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_staged_confirm_delete_post_deletes_and_redirects(self):
        self.client.force_login(self.rpc_user)
        staged_id = self.staged.id
        with self.assertLogs("errata.views", level="INFO") as cm:
            response = self.client.post(
                reverse(
                    "errata_staged_confirm_delete",
                    kwargs={"staged_erratum_id": staged_id},
                ),
                {"action": "delete"},
            )
        self.assertRedirects(response, reverse("errata_staged_list"))
        self.assertFalse(StagedErratum.objects.filter(id=staged_id).exists())
        self.assertEqual(len(cm.output), 1)
        self.assertIn(f"Deleted staged erratum {staged_id}", cm.output[0])

    def test_staged_rpc_edit_get_returns_200(self):
        self.client.force_login(self.rpc_user)
        response = self.client.get(
            reverse(
                "errata_staged_rpc_edit",
                kwargs={"staged_erratum_id": self.staged.id},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_staged_rpc_edit_post_valid_redirects_to_staged_list(self):
        self.client.force_login(self.rpc_user)
        data = {
            "submitter_name": "Updated Name",
            "submitter_email": "updated@example.com",
            "section": "4",
            "orig_text": "Original text content",
            "corrected_text": "Corrected text content",
            "notes": "Some notes",
        }
        if self.rfc.rfc_number >= 8650:
            data["formats"] = ["TXT"]
        response = self.client.post(
            reverse(
                "errata_staged_rpc_edit",
                kwargs={"staged_erratum_id": self.staged.id},
            ),
            data,
        )
        self.assertRedirects(response, reverse("errata_staged_list"))

    def test_staged_rpc_add_to_unverified_get_returns_200(self):
        self.client.force_login(self.rpc_user)
        response = self.client.get(
            reverse(
                "errata_staged_rpc_add_to_unverified",
                kwargs={
                    "staged_erratum_id": self.staged.id,
                    "erratum_type": "technical",
                },
            )
        )
        self.assertEqual(response.status_code, 200)

    @patch("errata.views.send_new_erratum_notification")
    def test_staged_rpc_add_to_unverified_post_confirm_creates_erratum(
        self, mock_notify
    ):
        self.client.force_login(self.rpc_user)
        count_before = Erratum.objects.count()
        staged_id = self.staged.id
        with self.assertLogs("errata.views", level="INFO") as cm:
            response = self.client.post(
                reverse(
                    "errata_staged_rpc_add_to_unverified",
                    kwargs={
                        "staged_erratum_id": staged_id,
                        "erratum_type": "technical",
                    },
                ),
                {"action": "confirm"},
            )
        self.assertRedirects(response, reverse("errata_staged_list"))
        self.assertEqual(Erratum.objects.count(), count_before + 1)
        self.assertFalse(StagedErratum.objects.filter(id=staged_id).exists())
        mock_notify.assert_called_once()
        self.assertEqual(len(cm.output), 1)
        self.assertIn(f"Promoted staged erratum {staged_id}", cm.output[0])

    def test_reported_list_unauthenticated_returns_403(self):
        response = self.client.get(reverse("errata_reported_list"))
        self.assertEqual(response.status_code, 403)

    def test_reported_list_regular_user_returns_403(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("errata_reported_list"))
        self.assertEqual(response.status_code, 403)

    def test_reported_list_rpc_user_returns_200(self):
        self.client.force_login(self.rpc_user)
        response = self.client.get(reverse("errata_reported_list"))
        self.assertEqual(response.status_code, 200)

    def test_reported_classify_get_returns_200(self):
        self.client.force_login(self.rpc_user)
        response = self.client.get(
            reverse("errata_reported_classify", kwargs={"erratum_id": self.erratum.id})
        )
        self.assertEqual(response.status_code, 200)

    @patch("errata.views.send_erratum_classified_notification")
    def test_reported_classify_post_mark_verified(self, mock_notify):
        self.client.force_login(self.rpc_user)
        data = {
            "erratum_type": "technical",
            "section": "1",
            "orig_text": "Original text",
            "corrected_text": "Corrected text",
            "submitter_name": "Test Submitter",
            "submitter_email": "submitter@example.com",
            "notes": "",
            "action": "mark_verified",
        }
        if self.rfc.rfc_number >= 8650:
            data["formats"] = ["TXT"]
        response = self.client.post(
            reverse("errata_reported_classify", kwargs={"erratum_id": self.erratum.id}),
            data,
        )
        self.assertRedirects(response, reverse("errata_reported_list"))
        self.erratum.refresh_from_db()
        self.assertEqual(self.erratum.status_id, "verified")
        mock_notify.assert_called_once()

    @patch("errata.views.send_erratum_classified_notification")
    def test_reported_classify_post_save_stays_on_page(self, mock_notify):
        self.client.force_login(self.rpc_user)
        data = {
            "erratum_type": "technical",
            "section": "1",
            "orig_text": "Original text",
            "corrected_text": "Corrected text",
            "submitter_name": "Test Submitter",
            "submitter_email": "submitter@example.com",
            "notes": "",
            "action": "save",
        }
        if self.rfc.rfc_number >= 8650:
            data["formats"] = ["TXT"]
        response = self.client.post(
            reverse("errata_reported_classify", kwargs={"erratum_id": self.erratum.id}),
            data,
        )
        self.assertRedirects(
            response,
            reverse("errata_reported_classify", kwargs={"erratum_id": self.erratum.id}),
        )
        mock_notify.assert_not_called()

    @patch("errata.views.send_erratum_classified_notification")
    def test_reported_classify_post_mark_rejected(self, mock_notify):
        self.client.force_login(self.rpc_user)
        data = {
            "erratum_type": "technical",
            "section": "1",
            "orig_text": "Original text",
            "corrected_text": "Corrected text",
            "submitter_name": "Test Submitter",
            "submitter_email": "submitter@example.com",
            "notes": "",
            "action": "mark_rejected",
        }
        if self.rfc.rfc_number >= 8650:
            data["formats"] = ["TXT"]
        response = self.client.post(
            reverse("errata_reported_classify", kwargs={"erratum_id": self.erratum.id}),
            data,
        )
        self.assertRedirects(response, reverse("errata_reported_list"))
        self.erratum.refresh_from_db()
        self.assertEqual(self.erratum.status_id, "rejected")
        mock_notify.assert_called_once()

    @patch("errata.views.send_erratum_classified_notification")
    def test_reported_classify_post_mark_held_for_doc_update(self, mock_notify):
        self.client.force_login(self.rpc_user)
        data = {
            "erratum_type": "technical",
            "section": "1",
            "orig_text": "Original text",
            "corrected_text": "Corrected text",
            "submitter_name": "Test Submitter",
            "submitter_email": "submitter@example.com",
            "notes": "",
            "action": "mark_held_for_doc_update",
        }
        if self.rfc.rfc_number >= 8650:
            data["formats"] = ["TXT"]
        response = self.client.post(
            reverse("errata_reported_classify", kwargs={"erratum_id": self.erratum.id}),
            data,
        )
        self.assertRedirects(response, reverse("errata_reported_list"))
        self.erratum.refresh_from_db()
        self.assertEqual(self.erratum.status_id, "held_for_doc_update")
        mock_notify.assert_called_once()

    def test_rpc_force_metadata_update_get_returns_200(self):
        self.client.force_login(self.rpc_user)
        response = self.client.get(reverse("errata_rpc_force_metadata_update"))
        self.assertEqual(response.status_code, 200)

    @patch("errata.views.update_rfc_metadata_task")
    def test_rpc_force_metadata_update_post_valid_redirects(self, mock_task):
        self.client.force_login(self.rpc_user)
        response = self.client.post(
            reverse("errata_rpc_force_metadata_update"),
            {"rfc_numbers": "1234"},
        )
        self.assertRedirects(
            response, reverse("errata_rpc_force_metadata_update_accepted")
        )
        mock_task.delay.assert_called_once_with([1234])


@override_settings(
    APP_API_TOKENS={"errata.views.api_rfc_metadata_update": ["test-api-token"]}
)
class ApiViewTest(TestCase):
    VALID_TOKEN = "test-api-token"

    def setUp(self):
        self.url = reverse("errata_api_rfc_metadata_update")

    def test_no_token_returns_403(self):
        response = self.client.post(
            self.url,
            data='{"rfc_number_list": [1]}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_token_returns_403(self):
        response = self.client.post(
            self.url,
            data='{"rfc_number_list": [1]}',
            content_type="application/json",
            HTTP_X_API_KEY="wrong-token",
        )
        self.assertEqual(response.status_code, 403)

    def test_get_method_returns_405(self):
        response = self.client.get(self.url, HTTP_X_API_KEY=self.VALID_TOKEN)
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.url,
            data="not-json",
            content_type="application/json",
            HTTP_X_API_KEY=self.VALID_TOKEN,
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_rfc_number_list_returns_400(self):
        response = self.client.post(
            self.url,
            data="{}",
            content_type="application/json",
            HTTP_X_API_KEY=self.VALID_TOKEN,
        )
        self.assertEqual(response.status_code, 400)

    def test_rfc_number_list_not_a_list_returns_400(self):
        response = self.client.post(
            self.url,
            data='{"rfc_number_list": 123}',
            content_type="application/json",
            HTTP_X_API_KEY=self.VALID_TOKEN,
        )
        self.assertEqual(response.status_code, 400)

    def test_rfc_number_list_with_non_positive_returns_400(self):
        response = self.client.post(
            self.url,
            data='{"rfc_number_list": [0]}',
            content_type="application/json",
            HTTP_X_API_KEY=self.VALID_TOKEN,
        )
        self.assertEqual(response.status_code, 400)

    @patch("errata.views.update_rfc_metadata_task")
    def test_valid_request_queues_task_and_returns_200(self, mock_task):
        response = self.client.post(
            self.url,
            data='{"rfc_number_list": [1, 2, 3]}',
            content_type="application/json",
            HTTP_X_API_KEY=self.VALID_TOKEN,
        )
        self.assertEqual(response.status_code, 200)
        mock_task.delay.assert_called_once_with([1, 2, 3])


class UtilsTest(TestCase):
    def setUp(self):
        self.rpc_user = RpcUserFactory()
        self.regular_user = UserFactory()
        self.rfc = RfcMetadataFactory(stream="ietf", area_acronym="ops")
        self.erratum = ErratumFactory(
            rfc_metadata=self.rfc, rfc_number=self.rfc.rfc_number
        )

    def test_unverified_errata_includes_all_for_rpc_user(self):
        from errata.utils import unverified_errata

        result = unverified_errata(self.rpc_user)
        self.assertIn(self.erratum, result)

    def test_unverified_errata_excludes_for_non_verifier(self):
        from errata.utils import unverified_errata

        result = unverified_errata(self.regular_user)
        self.assertNotIn(self.erratum, result)

    def test_can_classify_true_for_rpc_user(self):
        from errata.utils import can_classify

        self.assertTrue(can_classify(self.rpc_user, self.erratum.id))

    def test_can_classify_false_for_regular_user(self):
        from errata.utils import can_classify

        self.assertFalse(can_classify(self.regular_user, self.erratum.id))

    def test_can_classify_false_for_nonexistent_erratum(self):
        from errata.utils import can_classify

        self.assertFalse(can_classify(self.rpc_user, 999999))
