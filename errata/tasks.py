# Copyright The IETF Trust 2025-2026, All Rights Reserved

import datetime
import io

from celery import shared_task
from celery.utils.log import get_task_logger

from django.core.files.storage import storages
from django.db.models import F

from utils.task_utils import RetryTask

from .models import DirtyBits, MailMessage
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
def update_errata_json():
    """Periodically update errata.json based on `errata_json` DirtyBits

    N.B. This task MUST be set up to run periodically.
    An initial period of 5m is suggested."""
    dirty_work = DirtyBits.objects.get(slug="errata_json")
    if dirty_work.dirty_time is None:
        logger.error("DirtyWork `errata_json` object has unexpected dirty_time of None, skipping update")
    elif (
        dirty_work.processed_time is None
        or dirty_work.dirty_time > dirty_work.processed_time
    ):
        logger.info(
            f"Refreshing errata.json: dirty_time > processed_time: {dirty_work.dirty_time} > {dirty_work.processed_time}"
        )
        DirtyBits.objects.filter(slug="errata_json").update(
            processed_time=datetime.datetime.now().astimezone(datetime.UTC)
        )
        red_bucket = storages["red_bucket"]
        red_bucket.save("other/errata.json", io.StringIO(errata_json()))
    else:
        pass