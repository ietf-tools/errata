# Copyright The IETF Trust 2026, All Rights Reserved

import logging

from email.policy import EmailPolicy

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from .models import MailMessage, RfcMetadata
from .tasks import send_mail_task

logger = logging.getLogger(__name__)


def get_ad_emails(erratum):
    """Return the emails of the proper ads to notify when sending email about an erratum.

    The base case is the ads of the area an RFCs WG was in. However, there are both
    implicit and explicit overrides of the base case. Explicitly, the RPC can make an
    area_assignment. To date (early 2026), they've only done this for Legacy RFCs that
    should have been treated as IETF RFCs. Implicitly, when an area has taken over for
    a closed area, such as the merger of rai and app in to art, notifications should go
    to the _current_ area ads. Further, erratum for IETF stream individual submissions
    need to notify the gen area ad.

    This implementation defers creatign a new API to ask about ADs for areas separately from
    what is being returned by the red_doc_list api. It assumes that some RFC in the
    series will have the ADs for any given active area already attached to it. This
    assumption has little risk for IETF stream RFCs, but if a very old RFC is assigned
    to a newly minted area that has not yet produced any RFCs, it will fail. A future
    improvement will be to separately sync area information into a new class.
    """
    metadata = erratum.rfc_metadata
    target_acronym = None
    if metadata.area_assignment != "":
        target_acronym = metadata.area_assignment
    elif metadata.area_acronym in ["rai", "app"]:
        target_acronym = "art"
    elif metadata.group_acronym == "none":
        target_acronym = "gen"
    else:
        # datatracker group information reflects the current area,
        # so, e.g., the wit reorg is handled.
        pass
    if target_acronym is not None:
        proxy_meta = RfcMetadata.objects.filter(area_acronym=target_acronym).first()
        if proxy_meta is None:
            logger.warning(f"Can not find AD addresses for area {target_acronym}")
            return []
        return proxy_meta.area_ad_emails
    else:
        return metadata.area_ad_emails


def strip_garbage(addr_list, erratum):
    policy = EmailPolicy(utf8=True)
    cleaned_list = []
    for addr in addr_list:
        if addr is not None and addr.strip() != "":
            header = policy.header_factory("To", addr)
            if len(header.defects) == 0:
                cleaned_list.append(addr)
    unclean = set(addr_list) - set(cleaned_list)
    if len(unclean) > 0:
        logger.warning(
            f"Sending mail for erratum id: {erratum.id} - discarding addresses: {unclean}"
        )
    return cleaned_list


def send_new_erratum_notification(erratum, user):
    subject = f"[{erratum.erratum_type} Errata Reported] RFC{erratum.rfc_metadata.rfc_number} ({erratum.id})"
    body = render_to_string(
        "errata/email/new_erratum_general.txt",
        {"erratum": erratum, "base_url": settings.BASE_URL},
    )
    to = []
    cc = []
    metadata = erratum.rfc_metadata
    stream = erratum.rfc_metadata.stream
    if erratum.erratum_type.slug == "technical":
        if stream == "legacy":
            to.append("iesg@ietf.org")
            cc.append(erratum.submitter_email)
        elif stream == "ietf":
            if metadata.group_acronym == "none":
                to.append("iesg@ietf.org")
            to.extend(metadata.author_emails)
            if metadata.doc_ad_email:
                to.append(metadata.doc_ad_email)
            to.extend(get_ad_emails(erratum))
            if metadata.shepherd_email:
                to.append(metadata.shepherd_email)
            cc.append(erratum.submitter_email)
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            # Future possible improvement - cc the _group_ ad
            # to handle groups with out-of-area ads.
        elif stream == "iab":
            to.extend(metadata.author_emails)
            to.append("iab@iab.org")
            cc.append(erratum.submitter_email)
        elif stream == "irtf":
            to.extend(metadata.author_emails)
            to.append("irsg@irtf.org")
            cc.append(erratum.submitter_email)
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
        elif stream == "independent":
            to.extend(metadata.author_emails)
            to.append("rfc-ise@rfc-editor.org")
            cc.append(erratum.submitter_email)
        elif stream == "editorial":
            to.extend(metadata.author_emails)
            to.append("rsab@rfc-editor.org")
            cc.append(erratum.submitter_email)
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
    else:
        to.append("rfc-editor@rfc-editor.org")
        cc.append(erratum.submitter_email)
        if stream == "ietf":
            cc.extend(metadata.author_emails)
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
        elif stream == "iab":
            cc.extend(metadata.author_emails)
            cc.append("iab@iab.org")
        elif stream == "irtf":
            cc.extend(metadata.author_emails)
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
        elif stream == "independent":
            cc.append("rfc-ise@rfc-editor.org")
            cc.extend(metadata.author_emails)
        elif stream == "editorial":
            cc.extend(metadata.author_emails)
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
    # Always CC the RFC Editor
    cc.append("rfc-editor@rfc-editor.org")

    to_set = set(to)
    to_set.discard(None)
    to_set.discard("")
    to = strip_garbage(list(to_set), erratum)

    cc_set = set(cc)
    cc_set.discard(None)
    cc_set.discard("")
    cc = strip_garbage(list(cc_set), erratum)

    mail_message = None
    try:
        mail_message = MailMessage.objects.create(
            subject=subject,
            body=body,
            sender=user,
            to=to,
            cc=cc,
        )
    except ValidationError:
        logger.error(
            f"Unable to construct message to send for erratum {erratum.pk} with subject {subject} - to: {to}, cc: {cc}"
        )
    if mail_message is not None:
        send_mail_task.delay(mail_message.pk)


def send_erratum_classified_notification(erratum, user):
    subject = f"[Errata {erratum.status.name}] RFC{erratum.rfc_metadata.rfc_number} ({erratum.id})"
    body = render_to_string(
        "errata/email/erratum_classified.txt",
        {"erratum": erratum, "base_url": settings.BASE_URL},
    )
    to = []
    cc = []
    metadata = erratum.rfc_metadata
    stream = erratum.rfc_metadata.stream
    if erratum.erratum_type.slug == "technical":
        if stream == "legacy":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("iesg@ietf.org")
        elif stream == "ietf":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("iesg@ietf.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
        elif stream == "iab":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("iab@iab.org")
            cc.append("chair@iab.org")
        elif stream == "irtf":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("irsg@irtf.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
        elif stream == "independent":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("rfc-ise@rfc-editor.org")
            cc.append(metadata.shepherd_email)
            cc.append("iana@iana.org")
        elif stream == "editorial":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("rsab@rfc-editor.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
    else:
        if stream == "legacy":
            to.append(erratum.submitter_email)
            cc.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("iesg@ietf.org")
            cc.append("iana@iana.org")
        elif stream == "ietf":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("iesg@ietf.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
        elif stream == "iab":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("iab@iab.org")
            cc.append("chair@iab.org")
        elif stream == "irtf":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("irsg@irtf.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
        elif stream == "independent":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("rfc-ise@rfc-editor.org")
            cc.append("iana@iana.org")
        elif stream == "editorial":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(erratum.verifier_email)
            cc.append("rsab@rfc-editor.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
    # Always CC the RFC Editor
    cc.append("rfc-editor@rfc-editor.org")

    to_set = set(to)
    to_set.discard(None)
    to_set.discard("")
    to = strip_garbage(list(to_set), erratum)

    cc_set = set(cc)
    cc_set.discard(None)
    cc_set.discard("")
    cc = strip_garbage(list(cc_set), erratum)

    mail_message = None
    try:
        mail_message = MailMessage.objects.create(
            subject=subject,
            body=body,
            sender=user,
            to=to,
            cc=cc,
        )
    except ValidationError:
        logger.error(
            f"Unable to construct message to send for erratum {erratum.pk} with subject {subject} - to: {to}, cc: {cc}"
        )
    if mail_message is not None:
        send_mail_task.delay(mail_message.pk)
