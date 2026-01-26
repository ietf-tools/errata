# Copyright The IETF Trust 2025, All Rights Reserved

import datetime
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, redirect, render


from .forms import (
    EditStagedErratumForm,
    ErrataSearchForm,
    ChooseRfcForm,
    ConfirmExistingErrataReadForm,
)
from .models import Erratum, RfcMetadata, StagedErratum, StagedErratumStatus
from .search import search_errata


def wobbleup(request):
    return render(request, "errata/wobbleup.html")


@require_GET
def search(request):
    form = ErrataSearchForm(request.GET)
    if form.is_bound and form.is_valid() and request.GET != {}:
        errata = search_errata(form)
        template = (
            "errata/list.html"
            if form.cleaned_data.get("presentation") == "table"
            else "errata/list_detail.html"
        )
        search_ran = True
    else:
        errata = Erratum.objects.none()
        template = "errata/list.html"
        search_ran = False
    return render(
        request, template, dict(errata=errata, form=form, search_ran=search_ran)
    )


@require_GET
def detail(request, pk):
    erratum = Erratum.objects.prefetch_related(
        "rfc_metadata", "status", "erratum_type"
    ).get(pk=pk)
    return render(request, "errata/detail.html", dict(erratum=erratum))


def new_entry_instructions(request):
    if request.method == "POST":
        form = ChooseRfcForm(request.POST)
        if form.is_valid():
            rfc_number = form.cleaned_data["rfc_number"]
            return redirect("errata_new_review_existing", rfc_number=rfc_number)
    else:
        form = ChooseRfcForm()
    return render(request, "errata/entry_instructions.html", dict(form=form))


def new_review_existing(request, rfc_number: int):
    if not RfcMetadata.objects.filter(rfc_number=rfc_number).exists():
        return render(
            request,
            "errata/review_existing.html",
            dict(
                error_message=f"RFC{rfc_number} has not been published. (Recently published RFCs may not yet be provisioned in the errata system.)",
            ),
        )
    search_form = ErrataSearchForm(dict(rfc_number=rfc_number))
    errata = search_errata(search_form)
    if request.method == "POST":
        confirm_form = ConfirmExistingErrataReadForm(request.POST)
        if confirm_form.is_valid():
            staged_erratum = StagedErratum.objects.create(
                rfc_number=rfc_number, rfc_metadata_id=rfc_number
            )
            return redirect("errata_new_edit", staged_erratum_id=staged_erratum.id)
    else:
        confirm_form = ConfirmExistingErrataReadForm()
    return render(
        request,
        "errata/review_existing.html",
        dict(errata=errata, rfc_number=rfc_number, form=confirm_form, search_ran=True),
    )


def new_edit(request, staged_erratum_id):
    staged_erratum = get_object_or_404(
        StagedErratum, id=staged_erratum_id, entry_status=StagedErratumStatus.INCOMPLETE
    )

    if request.method == "POST":
        form = EditStagedErratumForm(
            rfc_number=staged_erratum.rfc_number, data=request.POST
        )
        if form.is_valid():
            staged_erratum.submitter_name = form.cleaned_data["submitter_name"]
            staged_erratum.submitter_email = form.cleaned_data["submitter_email"]
            if staged_erratum.rfc_number >= 8650:  # Start of the v3 RFCs
                staged_erratum.formats = form.cleaned_data["formats"]
            else:
                staged_erratum.formats = [
                    "TXT",
                ]
            staged_erratum.section = form.cleaned_data["section"]
            staged_erratum.orig_text = form.cleaned_data["orig_text"]
            staged_erratum.corrected_text = form.cleaned_data["corrected_text"]
            staged_erratum.notes = form.cleaned_data["notes"]
            staged_erratum.save()
            return redirect("errata_new_preview", staged_erratum_id=staged_erratum.id)
    else:
        form = EditStagedErratumForm(
            rfc_number=staged_erratum.rfc_number,
            initial=dict(
                submitter_name=staged_erratum.submitter_name,
                submitter_email=staged_erratum.submitter_email,
                formats=staged_erratum.formats,
                section=staged_erratum.section,
                orig_text=staged_erratum.orig_text,
                corrected_text=staged_erratum.corrected_text,
                notes=staged_erratum.notes,
            ),
        )
    return render(
        request,
        "errata/new_edit.html",
        dict(staged_erratum=staged_erratum, form=form),
    )


def new_preview(request, staged_erratum_id):
    staged_erratum = get_object_or_404(StagedErratum, id=staged_erratum_id)
    if staged_erratum.entry_status == StagedErratumStatus.SUBMITTED:
        return render(
            request,
            "errata/new_submission_success.html",
            dict(
                rfc_number=staged_erratum.rfc_number,
                staged_erratum_id=staged_erratum.id,
            ),
        )
    today = datetime.date.today()
    if request.method == "POST":
        if "return_to_edit" in request.POST:
            return redirect("errata_new_edit", staged_erratum_id=staged_erratum.id)
        elif "submit_for_screening" in request.POST:
            staged_erratum.entry_status = StagedErratumStatus.SUBMITTED
            staged_erratum.submitted_at = datetime.datetime.now()
            staged_erratum.save()
            return render(
                request,
                "errata/new_submission_success.html",
                dict(
                    rfc_number=staged_erratum.rfc_number,
                    staged_erratum_id=staged_erratum.id,
                ),
            )
    return render(
        request,
        "errata/new_preview.html",
        dict(erratum=staged_erratum, today=today),
    )
