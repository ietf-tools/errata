# Copyright The IETF Trust 2025-2026, All Rights Reserved

import operator

from functools import reduce

from django.db.models import Q

from errata_auth.utils import is_rpc, is_verifier

from .models import Erratum


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
