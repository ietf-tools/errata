# Copyright The IETF Trust 2026, All Rights Reserved

import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from errata.factories import ErratumFactory, MailMessageFactory, RfcMetadataFactory
from errata.models import DirtyBits, MailMessage
from errata.tasks import (
    SendEmailError,
    mail_monthly_report_task,
    send_mail_task,
    trigger_red_precompute_multiple_task,
    update_errata_json_task,
    update_rfc_metadata_task,
)


class SendMailTaskTest(TestCase):
    def test_success_sends_email_and_deletes_message(self):
        msg = MailMessageFactory()
        mock_email = MagicMock()
        with self.assertNoLogs("errata.tasks", level="DEBUG"):
            with patch.object(MailMessage, "as_emailmessage", return_value=mock_email):
                send_mail_task(msg.pk)
        mock_email.send.assert_called_once()
        self.assertFalse(MailMessage.objects.filter(pk=msg.pk).exists())

    def test_failure_raises_send_email_error_and_keeps_message(self):
        msg = MailMessageFactory()
        mock_email = MagicMock()
        mock_email.send.side_effect = Exception("SMTP connection refused")
        with self.assertLogs("errata.tasks", level="ERROR") as cm:
            with patch.object(MailMessage, "as_emailmessage", return_value=mock_email):
                with self.assertRaises(SendEmailError):
                    send_mail_task(msg.pk)
        self.assertTrue(MailMessage.objects.filter(pk=msg.pk).exists())
        self.assertEqual(len(cm.output), 1)
        self.assertIn("Sending with subject", cm.output[0])
        self.assertIn("SMTP connection refused", cm.output[0])

    def test_failure_increments_attempts(self):
        msg = MailMessageFactory()
        mock_email = MagicMock()
        mock_email.send.side_effect = Exception("SMTP error")
        with self.assertLogs("errata.tasks", level="ERROR") as cm:
            with patch.object(MailMessage, "as_emailmessage", return_value=mock_email):
                with self.assertRaises(SendEmailError):
                    send_mail_task(msg.pk)
        msg.refresh_from_db()
        self.assertEqual(msg.attempts, 1)
        self.assertEqual(len(cm.output), 1)
        self.assertIn("Sending with subject", cm.output[0])
        self.assertIn("SMTP error", cm.output[0])

    def test_success_increments_attempts(self):
        msg = MailMessageFactory()
        mock_email = MagicMock()
        with self.assertNoLogs("errata.tasks", level="DEBUG"):
            with patch.object(MailMessage, "as_emailmessage", return_value=mock_email):
                send_mail_task(msg.pk)
        self.assertFalse(MailMessage.objects.filter(pk=msg.pk).exists())


class UpdateRfcMetadataTaskTest(TestCase):
    @patch("errata.tasks.update_rfc_metadata")
    def test_passes_rfc_numbers_to_update_rfc_metadata(self, mock_update):
        with self.assertLogs("errata.tasks", level="INFO") as cm:
            update_rfc_metadata_task([1234, 5678])
        mock_update.assert_called_once_with([1234, 5678])
        self.assertEqual(len(cm.output), 1)
        self.assertIn("[1234, 5678]", cm.output[0])

    @patch("errata.tasks.update_rfc_metadata")
    def test_default_empty_tuple(self, mock_update):
        with self.assertLogs("errata.tasks", level="INFO") as cm:
            update_rfc_metadata_task()
        mock_update.assert_called_once_with(())
        self.assertEqual(len(cm.output), 1)
        self.assertIn("all RFCs", cm.output[0])


class UpdateErrataJsonTaskTest(TestCase):
    def _dirty_bits(self):
        return DirtyBits.objects.get(slug=DirtyBits.Slugs.ERRATA_JSON)

    def test_null_dirty_time_skips_update(self):
        with self.assertLogs("errata.tasks", level="ERROR") as cm:
            update_errata_json_task()
        self.assertIsNone(self._dirty_bits().processed_time)
        self.assertEqual(len(cm.output), 1)
        self.assertIn("unexpected dirty_time of None", cm.output[0])

    @patch("errata.tasks.trigger_red_precompute_multiple_task")
    @patch("errata.tasks.storages")
    def test_updates_when_dirty_time_exceeds_processed_time(
        self, mock_storages, mock_trigger
    ):
        dirty = self._dirty_bits()
        dirty.dirty_time = datetime.datetime(2020, 1, 2, tzinfo=datetime.UTC)
        dirty.processed_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
        dirty.save()
        mock_bucket = MagicMock()
        mock_storages.__getitem__.return_value = mock_bucket

        with self.assertLogs("errata.tasks", level="INFO") as cm:
            update_errata_json_task()

        mock_bucket.save.assert_called_once()
        self.assertEqual(mock_bucket.save.call_args[0][0], "other/errata.json")
        mock_trigger.assert_called_once()
        dirty.refresh_from_db()
        self.assertIsNotNone(dirty.processed_time)
        self.assertEqual(len(cm.output), 1)
        self.assertIn("Refreshing errata.json", cm.output[0])

    @patch("errata.tasks.trigger_red_precompute_multiple_task")
    @patch("errata.tasks.storages")
    def test_updates_when_processed_time_is_none(self, mock_storages, mock_trigger):
        dirty = self._dirty_bits()
        dirty.dirty_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
        dirty.processed_time = None
        dirty.save()
        mock_bucket = MagicMock()
        mock_storages.__getitem__.return_value = mock_bucket

        with self.assertLogs("errata.tasks", level="INFO") as cm:
            update_errata_json_task()

        mock_bucket.save.assert_called_once()
        dirty.refresh_from_db()
        self.assertIsNotNone(dirty.processed_time)
        self.assertEqual(len(cm.output), 1)
        self.assertIn("Refreshing errata.json", cm.output[0])

    @patch("errata.tasks.trigger_red_precompute_multiple_task")
    @patch("errata.tasks.storages")
    def test_skips_when_already_processed(self, mock_storages, mock_trigger):
        dirty = self._dirty_bits()
        dirty.dirty_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
        dirty.processed_time = datetime.datetime(2020, 1, 2, tzinfo=datetime.UTC)
        dirty.save()

        with self.assertNoLogs("errata.tasks", level="DEBUG"):
            update_errata_json_task()

        mock_storages.__getitem__.assert_not_called()
        mock_trigger.assert_not_called()

    @patch("errata.tasks.trigger_red_precompute_multiple_task")
    @patch("errata.tasks.storages")
    def test_storage_error_does_not_update_processed_time(
        self, mock_storages, mock_trigger
    ):
        dirty = self._dirty_bits()
        dirty.dirty_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
        dirty.processed_time = None
        dirty.save()
        mock_bucket = MagicMock()
        mock_bucket.save.side_effect = Exception("S3 unavailable")
        mock_storages.__getitem__.return_value = mock_bucket

        with self.assertLogs("errata.tasks", level="INFO") as cm:
            update_errata_json_task()

        dirty.refresh_from_db()
        self.assertIsNone(dirty.processed_time)
        self.assertEqual(len(cm.output), 2)
        self.assertIn("Refreshing errata.json", cm.output[0])
        self.assertIn("Attempt to push to red_bucket failed", cm.output[1])
        self.assertIn("S3 unavailable", cm.output[1])

    @patch("errata.tasks.trigger_red_precompute_multiple_task")
    @patch("errata.tasks.storages")
    def test_passes_dirty_rfc_numbers_to_precompute(self, mock_storages, mock_trigger):
        rfc = RfcMetadataFactory()
        erratum = ErratumFactory(rfc_metadata=rfc, rfc_number=rfc.rfc_number)

        dirty = self._dirty_bits()
        dirty.dirty_time = datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC)
        dirty.processed_time = None
        dirty.save()
        mock_bucket = MagicMock()
        mock_storages.__getitem__.return_value = mock_bucket

        with self.assertLogs("errata.tasks", level="INFO") as cm:
            update_errata_json_task()

        mock_trigger.assert_called_once()
        called_numbers = mock_trigger.call_args[1]["rfc_number_list"]
        self.assertIn(erratum.rfc_number, called_numbers)
        self.assertEqual(len(cm.output), 1)
        self.assertIn("Refreshing errata.json", cm.output[0])


class MailMonthlyReportTaskTest(TestCase):
    @patch("errata.tasks.send_mail_task")
    @patch("errata.mail.build_monthly_report")
    def test_calls_build_and_sends_result(self, mock_build, mock_send_mail):
        mock_message = MagicMock()
        mock_message.id = 42
        mock_build.return_value = mock_message

        mail_monthly_report_task()

        mock_build.assert_called_once()
        build_arg = mock_build.call_args[0][0]
        self.assertIsInstance(build_arg, datetime.datetime)
        self.assertIsNotNone(build_arg.tzinfo)
        mock_send_mail.assert_called_once_with(42)


class TriggerRedPrecomputeMultipleTaskTest(TestCase):
    def test_no_url_configured_does_not_raise(self):
        with self.assertLogs("errata.tasks", level="ERROR") as cm:
            trigger_red_precompute_multiple_task(rfc_number_list=[1234])
        self.assertEqual(len(cm.output), 1)
        self.assertIn("No URL configured", cm.output[0])

    @override_settings(
        TRIGGER_RED_PRECOMPUTE_MULTIPLE_URL="http://red.example.com/precompute",
        DEFAULT_REQUESTS_TIMEOUT=5,
    )
    @patch("errata.tasks.requests.post")
    def test_posts_to_configured_url(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        with self.assertLogs("errata.tasks", level="INFO") as cm:
            trigger_red_precompute_multiple_task(rfc_number_list=[1234, 5678])
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[0][0], "http://red.example.com/precompute")
        self.assertEqual(len(cm.output), 1)
        self.assertIn("Triggering red precompute multiple", cm.output[0])

    @override_settings(
        TRIGGER_RED_PRECOMPUTE_MULTIPLE_URL="http://red.example.com/precompute",
        DEFAULT_REQUESTS_TIMEOUT=5,
    )
    @patch("errata.tasks.requests.post")
    def test_payload_contains_comma_separated_rfc_numbers(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        with self.assertLogs("errata.tasks", level="INFO") as cm:
            trigger_red_precompute_multiple_task(rfc_number_list=[10, 20, 30])
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["rfcs"], "10,20,30")
        self.assertEqual(len(cm.output), 1)
        self.assertIn("Triggering red precompute multiple", cm.output[0])

    @override_settings(
        TRIGGER_RED_PRECOMPUTE_MULTIPLE_URL="http://red.example.com/precompute",
        DEFAULT_REQUESTS_TIMEOUT=5,
    )
    @patch("errata.tasks.requests.post")
    def test_non_200_response_does_not_raise(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500, text="Server Error")
        with self.assertLogs("errata.tasks", level="INFO") as cm:
            trigger_red_precompute_multiple_task(rfc_number_list=[1234])
        self.assertEqual(len(cm.output), 2)
        self.assertIn("Triggering red precompute multiple", cm.output[0])
        self.assertIn("POST request failed", cm.output[1])
        self.assertIn("500", cm.output[1])

    @override_settings(
        TRIGGER_RED_PRECOMPUTE_MULTIPLE_URL="http://red.example.com/precompute",
        DEFAULT_REQUESTS_TIMEOUT=5,
    )
    @patch("errata.tasks.requests.post")
    def test_timeout_does_not_raise(self, mock_post):
        import requests as req_lib

        mock_post.side_effect = req_lib.Timeout()
        with self.assertLogs("errata.tasks", level="INFO") as cm:
            trigger_red_precompute_multiple_task(rfc_number_list=[1234])
        self.assertEqual(len(cm.output), 2)
        self.assertIn("Triggering red precompute multiple", cm.output[0])
        self.assertIn("POST request timed out", cm.output[1])
