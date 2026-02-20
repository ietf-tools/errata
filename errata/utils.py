# Copyright The IETF Trust 2025-2026, All Rights Reserved

import json
import operator
# from zoneinfo import ZoneInfo # used to test emitting errata.json in pacifc time

from functools import reduce

import rpcapi_client
from email.policy import EmailPolicy

from django.db.models import Q

from errata_auth.utils import is_rpc, is_verifier

from .models import Erratum, RfcMetadata
from .rpcapi import with_rpcapi


def unverified_errata(user):
    unverified = Erratum.objects.filter(status_id="reported")
    if is_rpc(user):
        return unverified
    if not is_verifier(user):
        return unverified.none()

    # This leakes knowledge of role details out of errata_auth
    # consider pushing that back to that module through utility
    # access.
    user_roles = getattr(user, "roles", [])
    queries_to_union = [
        Q()
    ]  # if no other queries are added, this empty Q makes reduce happpy
    # IETF Stream
    if ["ad", "iesg"] in user_roles:
        for area in ["gen", "wit", "art", "ops", "rtg", "int", "sec"]:
            if ["ad", area] in user_roles:
                queries_to_union.append(Q(rfc_metadata__area_acronym=area))
                queries_to_union.append(Q(rfc_metadata__area_assignment=area))
                if area == "art":
                    for oldarea in ["app", "rai"]:
                        queries_to_union.append(Q(rfc_metadata__area_acronym=area))
                        queries_to_union.append(Q(rfc_metadata__area_assignment=area))
    # IAB
    for role in [
        ["chair", "iab"],
        ["delegate_stream_manager", "iab"],
    ]:
        if role in user_roles:
            queries_to_union.append(Q(rfc_metadata__stream="iab"))
    # IRTF Stream
    for role in [
        ["chair", "irtf"],
        ["delegate_stream_manager", "irtf"],
    ]:
        if role in user_roles:
            queries_to_union.append(Q(rfc_metadata__stream="irtf"))
    # Editorial Stream
    for role in [
        ["chair", "rsab"],
        ["delegate_stream_manager", "rsab"],
    ]:
        if role in user_roles:
            queries_to_union.append(Q(rfc_metadata__stream="editorial"))
    # Independent Stream
    if ["chair", "ise"] in user_roles:
        queries_to_union.append(Q(rfc_metadata__stream="irtf"))
    combined_queries = reduce(operator.or_, queries_to_union)
    return unverified.filter(combined_queries)


def can_classify(user, erratum_id):
    return unverified_errata(user).filter(id=erratum_id).exists()


@with_rpcapi
def test_datatracker_api(*, rpcapi: rpcapi_client.RedApi):
    """Demo of datatracker API usage

    todo remove this
    """
    # Example: retrieve all sip / sipcore RFCs using default pagination
    results = []
    page = rpcapi.red_doc_list(group=["sip", "sipcore"])
    results.extend([r.number, r.title, r.group.acronym] for r in page.results)
    offset = len(page.results)
    while offset < page.count:
        page = rpcapi.red_doc_list(group=["sip", "sipcore"], offset=offset)
        results.extend([r.number, r.title, r.group.acronym] for r in page.results)
        offset += len(page.results)
    return results


@with_rpcapi
def update_rfc_metadata(rfc_numbers=[], *, rpcapi: rpcapi_client.RedApi) -> None:
    """Update the rfc_metadata table for a given list of rfc numbers.

    If no list is provided, update metadata for all RFCs.
    """
    if rfc_numbers != []:
        # TODO limit the search to these numbers once the API supports it
        raise NotImplementedError()
    policy = EmailPolicy(utf8=True)
    page = rpcapi.red_doc_list(sort=["published"], limit=500)
    offset = 0
    while offset < page.count:
        for r in page.results:
            authors = []
            for a in r.authors:
                name = a.titlepage_name
                if a.is_editor:
                    name += ", Ed."
                authors.append(name)
            author_emails = []
            for a in r.authors:
                if a.email is not None:
                    header = policy.header_factory("To", a.email)
                    if len(header.defects) == 0:
                        author_emails.append(a.email)
            area_ad_emails = []
            if r.area and r.area.ads:
                for ad in r.area.ads:
                    if ad.email is not None:
                        header = policy.header_factory("To", ad.email)
                        if len(header.defects) == 0:
                            area_ad_emails.append(ad.email)
            RfcMetadata.objects.filter(rfc_number=r.number).update_or_create(
                rfc_number=r.number,
                defaults=dict(
                    title=r.title,
                    draft_name=r.draft.name if r.draft else "",
                    author_names=", ".join(authors),
                    author_emails=", ".join(author_emails),
                    sheperd_email=r.draft.shepherd.email
                    if r.draft and r.draft.shepherd and r.draft.shepherd.email
                    else "",
                    doc_ad_email=r.ad.email if r.ad and r.ad.email else "",
                    area_ad_emails=", ".join(area_ad_emails),
                    std_level=r.status.name.title(),
                    publication_year=r.published.year,
                    publication_month=r.published.month,
                    group_acronym=r.group.acronym,
                    group_name=r.group.name,
                    group_list_email=r.group_list_email,
                    area_acronym=r.area.acronym if r.area else "",
                    stream=r.stream.slug,
                    obsoleted_by=", ".join([f"RFC{o.number}" for o in r.obsoleted_by]),
                    updated_by=", ".join([f"RFC{u.number}" for u in r.updated_by]),
                ),
            )
        offset += len(page.results)
        page = rpcapi.red_doc_list(sort=["published"], limit=500, offset=offset)
    return


def errata_json():
    """Return a JSON object of all errata with their metadata."""
    # pacific_tz = ZoneInfo("America/Los_Angeles")

    rows = [
        {
            "errata_id": f"{e.id}",
            "doc-id": f"RFC{e.rfc_metadata.rfc_number}",  # Note the hyphen in the key
            "errata_status_code": f"{e.status.name}",
            "errata_type_code": f"{e.erratum_type.name}",
            "section": e.section if not e.section.startswith("99") else e.section[2:],
            "orig_text": e.orig_text,
            "correct_text": e.corrected_text,
            "notes": e.notes,
            "submit_date": e.submitted_at.date().isoformat(),
            "submitter_name": e.submitter_name,
            "verifier_id": "",  # deprecating verifier_id
            "verifier_name": e.verifier_name,
            "update_date": e.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            # "update_date": e.updated_at.astimezone(pacific_tz).strftime("%Y-%m-%d %H:%M:%S"),
        }
        for e in Erratum.objects.select_related("rfc_metadata").all()
    ]
    return json.dumps(rows)
