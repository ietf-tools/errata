# Copyright The IETF Trust 2026, All Rights Reserved

from unittest.mock import patch

from django.test import TestCase, override_settings

from errata_project.mail import send_mail


class SendMailTest(TestCase):
    @patch("errata_project.mail._send_mail")
    def test_uses_default_from_email_when_frm_not_given(self, mock_send):
        with override_settings(DEFAULT_FROM_EMAIL="default@example.com"):
            send_mail(to="r@example.com", subject="Hello", msg="Body")
        self.assertEqual(mock_send.call_args.args[2], "default@example.com")

    @patch("errata_project.mail._send_mail")
    def test_explicit_frm_is_used_when_provided(self, mock_send):
        send_mail(to="r@example.com", subject="s", msg="m", frm="sender@example.com")
        self.assertEqual(mock_send.call_args.args[2], "sender@example.com")

    @patch("errata_project.mail._send_mail")
    def test_string_to_is_wrapped_in_list(self, mock_send):
        send_mail(to="r@example.com", subject="s", msg="m", frm="f@example.com")
        self.assertEqual(mock_send.call_args.args[3], ["r@example.com"])

    @patch("errata_project.mail._send_mail")
    def test_list_to_is_passed_through_unchanged(self, mock_send):
        send_mail(
            to=["a@example.com", "b@example.com"],
            subject="s",
            msg="m",
            frm="f@example.com",
        )
        self.assertEqual(
            mock_send.call_args.args[3], ["a@example.com", "b@example.com"]
        )

    @patch("errata_project.mail._send_mail")
    def test_fail_silently_passed_through(self, mock_send):
        send_mail(
            to="r@example.com",
            subject="s",
            msg="m",
            frm="f@example.com",
            fail_silently=False,
        )
        self.assertFalse(mock_send.call_args.kwargs["fail_silently"])
