# Copyright The IETF Trust 2026, All Rights Reserved

from django.db.models import Q

from .forms import ErrataSearchForm
from .models import Erratum


def search_errata(form: ErrataSearchForm):
    if not (form.is_bound and form.is_valid()):
        return Erratum.objects.none()
    errata = Erratum.objects.order_by(
        "status__order", "rfc_number", "erratum_type__order", "pk"
    ).prefetch_related("rfc_metadata", "status", "erratum_type")
    if form.cleaned_data.get("rfc_number") is not None:
        errata = errata.filter(rfc_number=form.cleaned_data["rfc_number"])
    if form.cleaned_data.get("errata_id") is not None:
        errata = errata.filter(pk=form.cleaned_data["errata_id"])
    if form.cleaned_data.get("status") and form.cleaned_data["status"] != "any":
        status = form.cleaned_data["status"]
        if status == "verified_reported":
            errata = errata.filter(status__slug__in=["verified", "reported"])
        else:
            errata = errata.filter(status__slug=status)
    if form.cleaned_data.get("area") and form.cleaned_data["area"] != "any":
        search_areas = [form.cleaned_data["area"]]
        if form.cleaned_data.get("area") == "art":
            search_areas = ["art", "app", "rai"]
        errata = errata.filter(
            Q(rfc_metadata__area_assignment__in=search_areas)
            | Q(rfc_metadata__area_acronym__in=search_areas)
        )
    if (
        form.cleaned_data.get("errata_type")
        and form.cleaned_data["errata_type"] != "any"
    ):
        errata = errata.filter(erratum_type__slug=form.cleaned_data["errata_type"])
    if form.cleaned_data.get("wg_acronym"):
        errata = errata.filter(
            rfc_metadata__group_acronym=form.cleaned_data["wg_acronym"]
        )
    if form.cleaned_data.get("submitter_name"):
        errata = errata.filter(
            submitter_name__icontains=form.cleaned_data["submitter_name"]
        )
    if form.cleaned_data.get("stream") and form.cleaned_data["stream"] != "any":
        stream = form.cleaned_data["stream"].lower()
        if stream == "independent":
            stream = "ise"
        errata = errata.filter(rfc_metadata__stream=stream)
    if form.cleaned_data.get("date") != "":
        date_str = form.cleaned_data.get("date")
        if len(date_str) == 4:
            errata = errata.filter(submitted_at__year=date_str)
        elif len(date_str) in [6, 7]:
            year, month = map(int, date_str.split("-"))
            errata = errata.filter(submitted_at__year=year, submitted_at__month=month)
        else:
            year, month, day = map(int, date_str.split("-"))
            errata = errata.filter(
                submitted_at__year=year,
                submitted_at__month=month,
                submitted_at__day=day,
            )
    return errata
