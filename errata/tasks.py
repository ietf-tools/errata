# Copyright The IETF Trust 2025-2026, All Rights Reserved

import datetime
import io
import requests

from celery import shared_task
from celery.utils.log import get_task_logger

from django.conf import settings
from django.core.files.storage import storages
from django.db.models import F

from utils.task_utils import RetryTask

from .models import DirtyBits, Erratum, MailMessage
from .utils import errata_json, update_rfc_metadata

logger = get_task_logger(__name__)


class EmailTask(RetryTask):
    max_retries = 4 * 24 * 3  # every 15 minutes for 3 days
    # When retries run out, the admins will be emailed. There's a good chance that
    # sending that mail will fail also, but it's what we have for now.


class SendEmailError(Exception):
    pass


@shared_task(base=EmailTask, autoretry_for=(SendEmailError,))
def send_mail_task(message_id):
    message = MailMessage.objects.get(pk=message_id)
    email = message.as_emailmessage()
    try:
        email.send()
    except Exception as err:
        logger.error(
            "Sending with subject '%s' failed: %s",
            message.subject,
            str(err),
        )
        raise SendEmailError from err
    else:
        # Flag that the message was sent in case the task fails before deleting it
        MailMessage.objects.filter(pk=message_id).update(sent=True)
    finally:
        # Always increment this
        MailMessage.objects.filter(pk=message_id).update(attempts=F("attempts") + 1)
    message.delete()


@shared_task
def update_rfc_metadata_task(rfc_numbers=()):
    logger.info(
        f"Starting update_rfc_metadata_task for RFCs: {rfc_numbers if rfc_numbers else 'all RFCs'}"
    )
    update_rfc_metadata(rfc_numbers)


@shared_task
def update_errata_json_task():
    """Periodically update errata.json based on `errata_json` DirtyBits

    N.B. This task MUST be set up to run periodically.
    An initial period of 5m is suggested."""
    dirty_work = DirtyBits.objects.get(slug="errata_json")
    old_processed_time = dirty_work.processed_time
    if dirty_work.dirty_time is None:
        logger.error(
            "DirtyWork `errata_json` object has unexpected dirty_time of None, skipping update"
        )
    elif (
        dirty_work.processed_time is None
        or dirty_work.dirty_time >= dirty_work.processed_time
    ):
        logger.info(
            f"Refreshing errata.json: dirty_time >= processed_time: {dirty_work.dirty_time} >= {dirty_work.processed_time}"
        )
        new_processed_time_start = datetime.datetime.now(datetime.UTC)
        dirty_rfc_numbers = list(
            Erratum.history.filter(history_date__gt=dirty_work.processed_time)
            .values_list("rfc_number", flat=True)
            .distinct()
            .order_by("rfc_number")
        )
        try:
            red_bucket = storages["red_bucket"]
            red_bucket.save("other/errata.json", io.StringIO(errata_json()))
            # Intentionally not using .delay()
            trigger_red_precompute_multiple_task(rfc_number_list=dirty_rfc_numbers)
            DirtyBits.objects.filter(slug="errata_json").update(
                processed_time=new_processed_time_start
            )
        except Exception as e:
            # Log the error and swallow it.
            logger.error(f"Attempt to push to red_bucket failed: {e}")
    else:
        pass


@shared_task
def mail_monthly_report_task():
    """Send a monthly report to the stream managere.

    This must be scheduled for the 1st of each month.
    Suggested time is 12:00 UTC."""

    # Avoid a circular import
    from errata.mail import build_monthly_report

    moment = datetime.datetime.now(datetime.UTC)
    message = build_monthly_report(moment)
    # We're already in a task.
    send_mail_task(message.id)


# Providing this as a shared task even though its only currently used directly from
# the update_errata_json_task, to allow it to be run from the admin if needed.
@shared_task
def trigger_red_precompute_multiple_task(rfc_number_list=()):
    url = getattr(settings, "TRIGGER_RED_PRECOMPUTE_MULTIPLE_URL", None)
    if url is not None:
        payload = {
            "rfcs": ",".join([str(n) for n in rfc_number_list]),
        }
        try:
            logger.info(
                f"Triggering red precompute multiple for RFCs {rfc_number_list}"
            )
            response = requests.post(
                url,
                json=payload,
                timeout=settings.DEFAULT_REQUESTS_TIMEOUT,
            )
        except requests.Timeout as e:
            logger.error(f"POST request timed out for {url} ]: {e}")
            return
        if response.status_code != 200:
            logger.error(
                f"POST request failed for {url} ]: {response.status_code} {response.text}"
            )
    else:
        logger.error(
            "No URL configured for triggering red precompute multiple, skipping"
        )
