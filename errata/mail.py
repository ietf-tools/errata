# Copyright The IETF Trust 2026, All Rights Reserved

from .models import MailMessage
from .tasks import send_mail_task

from django.conf import settings
from django.template.loader import render_to_string


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
        elif (
            stream == "ietf" and erratum.rfc_metadata.group_acronym != "none"
        ):  # TODO verify "none" is what the metadata sync captures, and that area is populated as gen when it is
            to.extend(metadata.author_emails)
            if metadata.doc_ad_email:
                to.append(metadata.doc_ad_email)
            to.extend(metadata.area_ad_emails)
            if metadata.shepherd_email:
                to.append(metadata.shepherd_email)
            cc.append(erratum.submitter_email)
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
        elif stream == "ietf":
            to.append("iesg@ietf.org")
            to.extend(metadata.author_emails)
            cc.append(erratum.submitter_email)
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
    to = list(to_set)

    cc_set = set(cc)
    cc_set.discard(None)
    cc_set.discard("")
    cc = list(cc_set)

    mail_message = MailMessage.objects.create(
        subject=subject,
        body=body,
        sender=user,
        to=to,
        cc=cc,
    )
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
    to = list(to_set)

    cc_set = set(cc)
    cc_set.discard(None)
    cc_set.discard("")
    cc = list(cc_set)

    mail_message = MailMessage.objects.create(
        subject=subject,
        body=body,
        sender=user,
        to=to,
        cc=cc,
    )
    send_mail_task.delay(mail_message.pk)
