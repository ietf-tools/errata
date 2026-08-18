# Copyright The IETF Trust 2026, All Rights Reserved

import datetime
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from errata.factories import (
    ErratumFactory,
    RfcMetadataFactory,
    RpcUserFactory,
    UserFactory,
)
from errata.mail import (
    build_monthly_report,
    get_ad_emails,
    send_erratum_classified_notification,
    send_new_erratum_notification,
    strip_garbage,
)
from errata.models import Erratum, ErratumType, MailMessage, Status


def _fetch(erratum):
    """Re-fetch from the DB so AddressListField values are lists, not strings."""
    return Erratum.objects.select_related("rfc_metadata", "status", "erratum_type").get(
        pk=erratum.pk
    )


class GetAdEmailsTest(TestCase):
    def test_area_assignment_redirects_to_target_area(self):
        RfcMetadataFactory(area_acronym="ops", area_ad_emails="ops-ad@example.com")
        rfc = RfcMetadataFactory(
            area_acronym="art",
            area_assignment="ops",
            area_ad_emails="wrong@example.com",
        )
        erratum = _fetch(ErratumFactory(rfc_metadata=rfc, rfc_number=rfc.rfc_number))
        self.assertEqual(get_ad_emails(erratum), ["ops-ad@example.com"])

    def test_rai_maps_to_art(self):
        RfcMetadataFactory(area_acronym="art", area_ad_emails="art-ad@example.com")
        rfc = RfcMetadataFactory(area_acronym="rai", area_assignment="")
        erratum = _fetch(ErratumFactory(rfc_metadata=rfc, rfc_number=rfc.rfc_number))
        self.assertEqual(get_ad_emails(erratum), ["art-ad@example.com"])

    def test_app_maps_to_art(self):
        RfcMetadataFactory(area_acronym="art", area_ad_emails="art-ad@example.com")
        rfc = RfcMetadataFactory(area_acronym="app", area_assignment="")
        erratum = _fetch(ErratumFactory(rfc_metadata=rfc, rfc_number=rfc.rfc_number))
        self.assertEqual(get_ad_emails(erratum), ["art-ad@example.com"])

    def test_none_group_maps_to_gen(self):
        RfcMetadataFactory(area_acronym="gen", area_ad_emails="gen-ad@example.com")
        rfc = RfcMetadataFactory(
            group_acronym="none", area_acronym="ops", area_assignment=""
        )
        erratum = _fetch(ErratumFactory(rfc_metadata=rfc, rfc_number=rfc.rfc_number))
        self.assertEqual(get_ad_emails(erratum), ["gen-ad@example.com"])

    def test_no_redirect_returns_own_area_ad_emails(self):
        rfc = RfcMetadataFactory(
            group_acronym="httpbis",
            area_acronym="art",
            area_assignment="",
            area_ad_emails="own-ad@example.com",
        )
        erratum = _fetch(ErratumFactory(rfc_metadata=rfc, rfc_number=rfc.rfc_number))
        self.assertEqual(get_ad_emails(erratum), ["own-ad@example.com"])

    def test_proxy_not_found_logs_warning_and_returns_empty(self):
        rfc = RfcMetadataFactory(area_assignment="zz-nonexistent")
        erratum = _fetch(ErratumFactory(rfc_metadata=rfc, rfc_number=rfc.rfc_number))
        with self.assertLogs("errata.mail", level="WARNING") as cm:
            result = get_ad_emails(erratum)
        self.assertEqual(result, [])
        self.assertIn("Can not find AD addresses for area zz-nonexistent", cm.output[0])


class StripGarbageTest(TestCase):
    def setUp(self):
        self.erratum = _fetch(ErratumFactory())

    def test_valid_addresses_pass_through_without_warning(self):
        addr_list = ["a@example.com", "b@example.com"]
        with self.assertNoLogs("errata.mail", level="WARNING"):
            result = strip_garbage(addr_list, self.erratum)
        self.assertEqual(result, ["a@example.com", "b@example.com"])

    def test_empty_list_returns_empty_without_warning(self):
        with self.assertNoLogs("errata.mail", level="WARNING"):
            result = strip_garbage([], self.erratum)
        self.assertEqual(result, [])

    def test_none_value_removed_and_warning_logged(self):
        addr_list = ["good@example.com", None]
        with self.assertLogs("errata.mail", level="WARNING") as cm:
            result = strip_garbage(addr_list, self.erratum)
        self.assertEqual(result, ["good@example.com"])
        self.assertIn(str(self.erratum.id), cm.output[0])

    def test_empty_string_removed_and_warning_logged(self):
        addr_list = ["good@example.com", ""]
        with self.assertLogs("errata.mail", level="WARNING") as cm:
            result = strip_garbage(addr_list, self.erratum)
        self.assertEqual(result, ["good@example.com"])
        self.assertIn(str(self.erratum.id), cm.output[0])


class SendNewErratumNotificationTest(TestCase):
    def setUp(self):
        self.user = UserFactory()

    def _make_erratum(self, stream, erratum_type_slug="technical", **rfc_kwargs):
        rfc_defaults = dict(
            stream=stream,
            area_assignment="",
            area_ad_emails="",
            author_emails="",
        )
        rfc_defaults.update(rfc_kwargs)
        rfc = RfcMetadataFactory(**rfc_defaults)
        erratum = ErratumFactory(
            rfc_metadata=rfc,
            rfc_number=rfc.rfc_number,
            erratum_type=ErratumType.objects.get(slug=erratum_type_slug),
            submitter_email="submitter@example.com",
        )
        return _fetch(erratum)

    @patch("errata.mail.send_mail_task")
    def test_technical_ietf_wg_recipients(self, mock_task):
        erratum = self._make_erratum(
            stream="ietf",
            group_acronym="httpbis",
            author_emails="author@example.com",
            doc_ad_email="dad@example.com",
            shepherd_email="shepherd@example.com",
            group_list_email="wg@ietf.org",
        )
        send_new_erratum_notification(erratum, self.user)
        mock_task.delay.assert_called_once()
        msg = MailMessage.objects.latest("id")
        self.assertIn("author@example.com", msg.to)
        self.assertIn("dad@example.com", msg.to)
        self.assertIn("shepherd@example.com", msg.to)
        self.assertIn("submitter@example.com", msg.cc)
        self.assertIn("wg@ietf.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_ietf_no_wg_adds_iesg(self, mock_task):
        erratum = self._make_erratum(
            stream="ietf",
            group_acronym="none",
            author_emails="author@example.com",
        )
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("iesg@ietf.org", msg.to)
        self.assertIn("author@example.com", msg.to)

    @patch("errata.mail.send_mail_task")
    def test_technical_legacy_notifies_iesg(self, mock_task):
        erratum = self._make_erratum(stream="legacy")
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("iesg@ietf.org", msg.to)
        self.assertIn("submitter@example.com", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_iab_notifies_iab(self, mock_task):
        erratum = self._make_erratum(stream="iab", author_emails="author@example.com")
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("iab@iab.org", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("submitter@example.com", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_irtf_notifies_irsg(self, mock_task):
        erratum = self._make_erratum(
            stream="irtf",
            author_emails="author@example.com",
            group_list_email="rg@irtf.org",
        )
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("irsg@irtf.org", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("rg@irtf.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_ise_stream_notifies_ise(self, mock_task):
        erratum = self._make_erratum(stream="ise", author_emails="author@example.com")
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("rfc-ise@rfc-editor.org", msg.to)
        self.assertIn("submitter@example.com", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_editorial_stream_notifies_rsab(self, mock_task):
        erratum = self._make_erratum(
            stream="editorial",
            author_emails="author@example.com",
            group_list_email="rsab-list@rfc-editor.org",
        )
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("rsab@rfc-editor.org", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("rsab-list@rfc-editor.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_goes_to_rfc_editor(self, mock_task):
        erratum = self._make_erratum(
            stream="ietf",
            erratum_type_slug="editorial",
            group_acronym="httpbis",
            author_emails="author@example.com",
            group_list_email="wg@ietf.org",
        )
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("rfc-editor@rfc-editor.org", msg.to)
        self.assertIn("submitter@example.com", msg.cc)
        self.assertIn("author@example.com", msg.cc)
        self.assertIn("wg@ietf.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_iab_ccs_iab(self, mock_task):
        erratum = self._make_erratum(
            stream="iab",
            erratum_type_slug="editorial",
            author_emails="author@example.com",
        )
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("rfc-editor@rfc-editor.org", msg.to)
        self.assertIn("author@example.com", msg.cc)
        self.assertIn("iab@iab.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_irtf_ccs_group_list(self, mock_task):
        erratum = self._make_erratum(
            stream="irtf",
            erratum_type_slug="editorial",
            author_emails="author@example.com",
            group_list_email="rg@irtf.org",
        )
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("rfc-editor@rfc-editor.org", msg.to)
        self.assertIn("author@example.com", msg.cc)
        self.assertIn("rg@irtf.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_ise_ccs_rfc_ise(self, mock_task):
        erratum = self._make_erratum(
            stream="ise",
            erratum_type_slug="editorial",
            author_emails="author@example.com",
        )
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("rfc-editor@rfc-editor.org", msg.to)
        self.assertIn("rfc-ise@rfc-editor.org", msg.cc)
        self.assertIn("author@example.com", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_editorial_stream_ccs_rsab_and_group_list(self, mock_task):
        erratum = self._make_erratum(
            stream="editorial",
            erratum_type_slug="editorial",
            author_emails="author@example.com",
            group_list_email="rsab-list@rfc-editor.org",
        )
        send_new_erratum_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("rfc-editor@rfc-editor.org", msg.to)
        self.assertIn("author@example.com", msg.cc)
        self.assertIn("rsab-list@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_always_ccs_rfc_editor(self, mock_task):
        for stream in ["ietf", "iab", "irtf", "legacy"]:
            with self.subTest(stream=stream):
                erratum = self._make_erratum(stream=stream)
                send_new_erratum_notification(erratum, self.user)
                msg = MailMessage.objects.latest("id")
                self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_validation_error_logs_error_and_skips_task(self, mock_task):
        erratum = self._make_erratum(stream="legacy")
        with (
            patch(
                "errata.mail.MailMessage.objects.create",
                side_effect=ValidationError("bad address"),
            ),
            self.assertLogs("errata.mail", level="ERROR") as cm,
        ):
            send_new_erratum_notification(erratum, self.user)
        mock_task.delay.assert_not_called()
        self.assertIn("Unable to construct message", cm.output[0])


class SendErratumClassifiedNotificationTest(TestCase):
    def setUp(self):
        self.user = UserFactory(email="verifier@example.com")

    def _make_erratum(
        self,
        stream,
        erratum_type_slug="technical",
        author_emails="author@example.com",
        group_acronym="testgroup",
        group_list_email="",
        shepherd_email="",
        verifier_email="verifier@example.com",
    ):
        rfc = RfcMetadataFactory(
            stream=stream,
            area_assignment="",
            area_ad_emails="",
            author_emails=author_emails,
            group_acronym=group_acronym,
            group_list_email=group_list_email,
            shepherd_email=shepherd_email,
        )
        erratum = ErratumFactory(
            rfc_metadata=rfc,
            rfc_number=rfc.rfc_number,
            erratum_type=ErratumType.objects.get(slug=erratum_type_slug),
            status=Status.objects.get(slug="verified"),
            submitter_email="submitter@example.com",
            verifier_email=verifier_email,
        )
        return _fetch(erratum)

    @patch("errata.mail.send_mail_task")
    def test_technical_ietf_notifies_submitter_authors_and_iesg(self, mock_task):
        erratum = self._make_erratum(stream="ietf", group_list_email="wg@ietf.org")
        send_erratum_classified_notification(erratum, self.user)
        mock_task.delay.assert_called_once()
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("verifier@example.com", msg.cc)
        self.assertIn("iesg@ietf.org", msg.cc)
        self.assertIn("wg@ietf.org", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_iab_notifies_iab_and_chair(self, mock_task):
        erratum = self._make_erratum(stream="iab")
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("iab@iab.org", msg.cc)
        self.assertIn("chair@iab.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_irtf_notifies_irsg(self, mock_task):
        erratum = self._make_erratum(stream="irtf", group_list_email="rg@irtf.org")
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("irsg@irtf.org", msg.cc)
        self.assertIn("rg@irtf.org", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_legacy_notifies_iesg(self, mock_task):
        erratum = self._make_erratum(stream="legacy")
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("iesg@ietf.org", msg.cc)
        self.assertNotIn("iana@iana.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_ise_notifies_rfc_ise_and_shepherd(self, mock_task):
        erratum = self._make_erratum(
            stream="ise", shepherd_email="shepherd@example.com"
        )
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("rfc-ise@rfc-editor.org", msg.cc)
        self.assertIn("shepherd@example.com", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_technical_editorial_stream_notifies_rsab(self, mock_task):
        erratum = self._make_erratum(
            stream="editorial", group_list_email="rsab-list@rfc-editor.org"
        )
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("rsab@rfc-editor.org", msg.cc)
        self.assertIn("rsab-list@rfc-editor.org", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_ietf_notifies_submitter_and_authors_in_to(self, mock_task):
        erratum = self._make_erratum(stream="ietf", erratum_type_slug="editorial")
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_ietf_includes_group_list_email(self, mock_task):
        erratum = self._make_erratum(
            stream="ietf",
            erratum_type_slug="editorial",
            group_list_email="wg@ietf.org",
        )
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("wg@ietf.org", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_legacy_ccs_iesg_and_iana(self, mock_task):
        erratum = self._make_erratum(stream="legacy", erratum_type_slug="editorial")
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.cc)
        self.assertIn("iesg@ietf.org", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_iab_notifies_iab_and_chair(self, mock_task):
        erratum = self._make_erratum(stream="iab", erratum_type_slug="editorial")
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("iab@iab.org", msg.cc)
        self.assertIn("chair@iab.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_irtf_notifies_irsg(self, mock_task):
        erratum = self._make_erratum(
            stream="irtf",
            erratum_type_slug="editorial",
            group_list_email="rg@irtf.org",
        )
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("irsg@irtf.org", msg.cc)
        self.assertIn("rg@irtf.org", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_ise_notifies_rfc_ise(self, mock_task):
        erratum = self._make_erratum(stream="ise", erratum_type_slug="editorial")
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("rfc-ise@rfc-editor.org", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_editorial_type_editorial_stream_notifies_rsab(self, mock_task):
        erratum = self._make_erratum(
            stream="editorial",
            erratum_type_slug="editorial",
            group_list_email="rsab-list@rfc-editor.org",
        )
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("submitter@example.com", msg.to)
        self.assertIn("author@example.com", msg.to)
        self.assertIn("rsab@rfc-editor.org", msg.cc)
        self.assertIn("rsab-list@rfc-editor.org", msg.cc)
        self.assertIn("iana@iana.org", msg.cc)
        self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_rpc_classifying_editorial_errata_omits_verifier_email_and_uses_rfc_production_center(
        self, mock_task
    ):
        stream_expected_ccs = {
            "legacy": ["iesg@ietf.org", "iana@iana.org"],
            "ietf": ["iesg@ietf.org", "iana@iana.org", "list@example.com"],
            "iab": ["iab@iab.org", "chair@iab.org"],
            "irtf": ["irsg@irtf.org", "iana@iana.org", "list@example.com"],
            "ise": ["rfc-ise@rfc-editor.org", "iana@iana.org"],
            "editorial": ["rsab@rfc-editor.org", "iana@iana.org", "list@example.com"],
        }
        rpc_user = RpcUserFactory(email="verifier@example.com")
        for stream in ["ietf", "iab", "irtf", "ise", "editorial", "legacy"]:
            with self.subTest(stream=stream):
                erratum = self._make_erratum(
                    stream=stream,
                    erratum_type_slug="editorial",
                    group_list_email="list@example.com",
                    shepherd_email="shepherd@example.com",
                )
                self.assertEqual(rpc_user.email, erratum.verifier_email)
                send_erratum_classified_notification(erratum, rpc_user)
                msg = MailMessage.objects.latest("id")
                self.assertNotIn(rpc_user.email, msg.cc)
                self.assertIn("rfc-editor@rfc-editor.org", msg.cc)
                self.assertIn("RFC Production Center", msg.body)
                for addr in stream_expected_ccs[stream]:
                    self.assertIn(addr, msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_ccs_acting_user_when_they_are_the_recorded_verifier(self, mock_task):
        # The common case: the user classifying is also the recorded verifier.
        erratum = self._make_erratum(stream="ietf")
        send_erratum_classified_notification(erratum, self.user)
        msg = MailMessage.objects.latest("id")
        self.assertIn(self.user.email, msg.cc)
        mock_task.delay.assert_called_once_with(msg.pk)

    @patch("errata.mail.send_mail_task")
    def test_ccs_recorded_verifier_not_acting_user_when_they_differ(self, mock_task):
        # When the RPC reclassifies on behalf of someone else, the recorded
        # verifier differs from the acting user. The CC must go to the recorded
        # party, and building the message must not assume they are the same.
        rpc_user = RpcUserFactory(email="rpc@example.com")
        erratum = self._make_erratum(stream="ietf", verifier_email="ad@example.com")
        send_erratum_classified_notification(erratum, rpc_user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("ad@example.com", msg.cc)
        self.assertNotIn("rpc@example.com", msg.cc)
        mock_task.delay.assert_called_once_with(msg.pk)

    @patch("errata.mail.send_mail_task")
    def test_rpc_reclassifying_editorial_on_behalf_of_other_ccs_named_party(
        self, mock_task
    ):
        # Editorial errata are normally the RPC's own authority (no individual
        # verifier CC'd, body credits "RFC Production Center"). But when the RPC
        # reclassifies on behalf of a named party, that party is the verifier,
        # so they must be CC'd and credited instead.
        rpc_user = RpcUserFactory(email="rpc@example.com")
        erratum = self._make_erratum(
            stream="editorial",
            erratum_type_slug="editorial",
            verifier_email="ad@example.com",
        )
        send_erratum_classified_notification(erratum, rpc_user)
        msg = MailMessage.objects.latest("id")
        self.assertIn("ad@example.com", msg.cc)
        self.assertNotIn("rpc@example.com", msg.cc)
        self.assertNotIn("RFC Production Center", msg.body)

    @patch("errata.mail.send_mail_task")
    def test_always_ccs_rfc_editor(self, mock_task):
        for stream in ["ietf", "iab", "irtf", "legacy"]:
            with self.subTest(stream=stream):
                erratum = self._make_erratum(stream=stream)
                send_erratum_classified_notification(erratum, self.user)
                msg = MailMessage.objects.latest("id")
                self.assertIn("rfc-editor@rfc-editor.org", msg.cc)

    @patch("errata.mail.send_mail_task")
    def test_validation_error_logs_error_and_skips_task(self, mock_task):
        erratum = self._make_erratum(stream="ietf")
        with (
            patch(
                "errata.mail.MailMessage.objects.create",
                side_effect=ValidationError("bad address"),
            ),
            self.assertLogs("errata.mail", level="ERROR") as cm,
        ):
            send_erratum_classified_notification(erratum, self.user)
        mock_task.delay.assert_not_called()
        self.assertIn("Unable to construct message", cm.output[0])


class BuildMonthlyReportTest(TestCase):
    def setUp(self):
        UserFactory(username="(System)")

    def test_subject_contains_month_and_year(self):
        moment = datetime.datetime(2025, 3, 1, tzinfo=datetime.UTC)
        msg = build_monthly_report(moment)
        self.assertEqual(msg.subject, "Reported Errata Summary for March, 2025")

    def test_sends_to_all_stream_managers(self):
        moment = datetime.datetime(2025, 3, 1, tzinfo=datetime.UTC)
        msg = build_monthly_report(moment)
        msg = MailMessage.objects.get(pk=msg.pk)
        for addr in [
            "iesg@ietf.org",
            "rfc-editor@rfc-editor.org",
            "iab@iab.org",
            "irsg@irtf.org",
            "rfc-ise@rfc-editor.org",
            "rsab@rfc-editor.org",
        ]:
            with self.subTest(addr=addr):
                self.assertIn(addr, msg.to)

    def test_uses_current_utc_time_when_moment_is_none(self):
        msg = build_monthly_report(None)
        now = datetime.datetime.now(datetime.UTC)
        self.assertIn(now.strftime("%B, %Y"), msg.subject)
