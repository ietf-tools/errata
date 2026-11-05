# Copyright The IETF Trust 2026, All Rights Reserved

import datetime
import logging
from email.policy import EmailPolicy

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from errata.utils import counts_per_authority
from errata_auth.models import User
from errata_auth.utils import current_area, is_rpc

from .models import MailMessage, RfcMetadata
from .tasks import send_mail_task
from .templatetags.filters import txt_errata_verifying_party

logger = logging.getLogger(__name__)


def get_ad_emails(erratum):
    """Return the email addresses of the ADs to notify about an erratum.

    Usually these are the ADs of the area the RFC's group was in, except that:

    * An area_assignment, set in the admin at the RPC's request, takes
      precedence. To date (early 2026) it has only been used for Legacy RFCs
      that should have been treated as IETF RFCs.
    * A closed area is replaced by the current area that took it over (app and
      rai by art; tsv, for its concluded groups, by wit). This also applies to
      an area_assignment naming a closed area.
    * IETF stream individual submissions go to the gen ADs.

    The addresses are borrowed from another RFC in the target area rather than
    from a separate API for areas. That is safe for IETF stream RFCs, but finds
    no ADs for an area that has not yet published an RFC. A future improvement
    is to sync area information separately.
    """
    metadata = erratum.rfc_metadata
    target_acronym = None
    if metadata.area_assignment != "":
        target_acronym = current_area(metadata.area_assignment)
    elif current_area(metadata.area_acronym) != metadata.area_acronym:
        target_acronym = current_area(metadata.area_acronym)
    elif metadata.group_acronym == "none":
        target_acronym = "gen"
    else:
        # datatracker group information reflects the current area,
        # so, e.g., the wit reorg is handled.
        pass
    if target_acronym is not None:
        proxy_meta = RfcMetadata.objects.filter(area_acronym=target_acronym).first()
        if proxy_meta is None:
            logger.warning(f"Cannot find AD addresses for area {target_acronym}")
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
            f"Sending mail for erratum id: {erratum.id} - "
            f"discarding addresses: {unclean}"
        )
    return cleaned_list


def send_new_erratum_notification(erratum, user):
    subject = (
        f"[{erratum.erratum_type} Errata Reported] "
        f"RFC{erratum.rfc_metadata.rfc_number} ({erratum.id})"
    )
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
        elif stream == "ise":
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
        elif stream == "ise":
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
            f"Unable to construct message to send for erratum {erratum.pk} "
            f"with subject {subject} - to: {to}, cc: {cc}"
        )
    if mail_message is not None:
        send_mail_task.delay(mail_message.pk)


def send_erratum_classified_notification(erratum, user):
    subject = (
        f"[Errata {erratum.status.name}] "
        f"RFC{erratum.rfc_metadata.rfc_number} ({erratum.id})"
    )
    metadata = erratum.rfc_metadata
    stream = metadata.stream
    # The RFC Production Center is the verifying authority for editorial errata
    # it classifies itself. But when the RPC reclassifies on behalf of a named
    # other party (recorded as a verifier_email that isn't the acting user's),
    # that party is the verifier, so fall back to the normal handling that CCs
    # them and names the stream's verifying party.
    rpc_classifying_editorial = (
        is_rpc(user)
        and erratum.erratum_type.slug == "editorial"
        and erratum.verifier_email == user.email
    )
    verifying_party = txt_errata_verifying_party(erratum, rpc_classifying_editorial)
    body = render_to_string(
        "errata/email/erratum_classified.txt",
        {
            "erratum": erratum,
            "base_url": settings.BASE_URL,
            "verifying_party": verifying_party,
        },
    )
    to = []
    cc = []
    # CC the verifying party recorded on the erratum. This is usually the
    # classifying user, but when the RPC reclassifies on behalf of someone
    # else it is that other party, so trust the erratum rather than the user.
    verifier_email = erratum.verifier_email
    if erratum.erratum_type.slug == "technical":
        if stream == "legacy":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(verifier_email)
            cc.append("iesg@ietf.org")
        elif stream == "ietf":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(verifier_email)
            cc.append("iesg@ietf.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
        elif stream == "iab":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(verifier_email)
            cc.append("iab@iab.org")
            cc.append("chair@iab.org")
        elif stream == "irtf":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(verifier_email)
            cc.append("irsg@irtf.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
        elif stream == "ise":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(verifier_email)
            cc.append("rfc-ise@rfc-editor.org")
            cc.append(metadata.shepherd_email)
            cc.append("iana@iana.org")
        elif stream == "editorial":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append(verifier_email)
            cc.append("rsab@rfc-editor.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
    else:
        if not rpc_classifying_editorial:
            cc.append(verifier_email)
        if stream == "legacy":
            to.append(erratum.submitter_email)
            cc.extend(metadata.author_emails)
            cc.append("iesg@ietf.org")
            cc.append("iana@iana.org")
        elif stream == "ietf":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append("iesg@ietf.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
        elif stream == "iab":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append("iab@iab.org")
            cc.append("chair@iab.org")
        elif stream == "irtf":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append("irsg@irtf.org")
            if metadata.group_list_email:
                cc.append(metadata.group_list_email)
            cc.append("iana@iana.org")
        elif stream == "ise":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
            cc.append("rfc-ise@rfc-editor.org")
            cc.append("iana@iana.org")
        elif stream == "editorial":
            to.append(erratum.submitter_email)
            to.extend(metadata.author_emails)
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
            f"Unable to construct message to send for erratum {erratum.pk} "
            f"with subject {subject} - to: {to}, cc: {cc}"
        )
    if mail_message is not None:
        send_mail_task.delay(mail_message.pk)


def build_monthly_report(moment: datetime.datetime = None):
    if moment is None:
        moment = datetime.datetime.now(datetime.UTC)
    ordered_authorities = [
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
    ]
    search_links = {}
    for authority in ["art", "gen", "int", "ops", "rtg", "sec", "wit"]:
        search_links[authority] = (
            f"{settings.BASE_URL}/search/?status=reported&errata_type=technical&area={authority}&presentation=records"
        )
    for authority in ["iab", "ise", "irtf", "legacy", "editorial"]:
        search_links[authority] = (
            f"{settings.BASE_URL}/search/?status=reported&errata_type=technical&stream={authority}&presentation=records"
        )
    authority_counts = counts_per_authority()
    authority_data = []
    for authority in ordered_authorities:
        authority_data.append(
            {
                "authority": authority,
                "count": authority_counts[authority],
                "search_link": search_links[authority],
            }
        )
    # HTML ONLY BODY IS HORRIBLE.
    body = render_to_string(
        "errata/email/monthly_report.html",
        context=dict(
            authority_data=authority_data,
            base_url=settings.BASE_URL,
        ),
    )
    message = MailMessage.objects.create(
        subject=f"Reported Errata Summary for {moment.strftime('%B, %Y')}",
        body=body,
        sender=User.objects.get(username="(System)"),
        to=[
            "iesg@ietf.org",
            "rfc-editor@rfc-editor.org",
            "iab@iab.org",
            "irsg@irtf.org",
            "rfc-ise@rfc-editor.org",
            "rsab@rfc-editor.org",
        ],
    )
    return message
