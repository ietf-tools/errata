# Copyright The IETF Trust 2025-2026, All Rights Reserved

import datetime

from django.http import Http404
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, redirect, render

from errata_auth.utils import role_required

from .forms import (
    EditErratumForm,
    EditStagedErratumForm,
    ErrataSearchForm,
    ChooseRfcForm,
    ConfirmExistingErrataReadForm,
)
from .models import (
    Erratum,
    ErratumType,
    RfcMetadata,
    StagedErratum,
    StagedErratumStatus,
    Status,
)
from .search import search_errata
from .utils import can_classify, unverified_errata


def user_info(request):
    return render(request, "errata/user_info.html")


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


@role_required("rpc")
def staged_list(request):
    if request.method == "POST":
        uuid = request.POST.get("uuid")
        action = request.POST.get("action")
        staged_erratum = get_object_or_404(StagedErratum, id=uuid)
        print(action)
        if action == "delete":
            return redirect(
                "errata_staged_confirm_delete", staged_erratum_id=staged_erratum.id
            )
        elif action == "edit":
            return redirect(
                "errata_staged_rpc_edit", staged_erratum_id=staged_erratum.id
            )
        elif action in ("post_editorial", "post_technical"):
            return redirect(
                "errata_staged_rpc_add_to_unverified",
                staged_erratum_id=staged_erratum.id,
                erratum_type=action[5:],
            )
        else:
            pass
    staged_errata = StagedErratum.objects.filter(
        entry_status=StagedErratumStatus.SUBMITTED
    ).order_by("submitted_at")
    return render(
        request,
        "errata/staged_list.html",
        dict(staged_errata=staged_errata),
    )


@role_required("rpd")
def staged_confirm_delete(request, staged_erratum_id):
    staged_erratum = get_object_or_404(StagedErratum, id=staged_erratum_id)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "delete":
            # TODO: log that we deleted the object
            staged_erratum.delete()
            return redirect("errata_staged_list)")
        else:
            pass
    return render(
        request,
        "errata/staged_erratum_confirm_delete.html",
        dict(erratum=staged_erratum),
    )


@role_required("rpc")
def staged_rpc_edit(request, staged_erratum_id):
    staged_erratum = get_object_or_404(StagedErratum, id=staged_erratum_id)
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
            return redirect("errata_staged_list")
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
        "errata/staged_erratum_rpc_edit.html",
        dict(erratum=staged_erratum, form=form),
    )


@role_required("rpc")
def staged_rpc_add_to_unverified(request, staged_erratum_id, erratum_type):
    staged_erratum = get_object_or_404(StagedErratum, id=staged_erratum_id)
    erratum_type = get_object_or_404(ErratumType, slug=erratum_type)
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "confirm":
            reported = Status.objects.get(slug="reported")
            # Will need `erratum=` on this create for logging
            # and email.
            Erratum.objects.create(
                rfc_number=staged_erratum.rfc_number,
                rfc_metadata_id=staged_erratum.rfc_number,
                status=reported,
                erratum_type=erratum_type,
                section=staged_erratum.section,
                orig_text=staged_erratum.orig_text,
                corrected_text=staged_erratum.corrected_text,
                submitter_name=staged_erratum.submitter_name,
                submitter_email=staged_erratum.submitter_email,
                notes=staged_erratum.notes,
                submitted_at=staged_erratum.submitted_at,
                # created at gets default of now
                # updated_at is an AutoDateTimeField
                format=staged_erratum.formats,
            )
            staged_erratum.delete()
            # TODO: log what happened
            # TODO: Send mail about it
            return redirect("errata_staged_list")
        else:
            pass
    return render(
        request,
        "errata/staged_add_to_unverified.html",
        dict(erratum=staged_erratum, erratum_type=erratum_type),
    )


@role_required("rpc", "verifier")
def reported_list(request):
    reported = unverified_errata(request.user)
    return render(request, "errata/reported_list.html", dict(errata=reported))


@role_required("rpc", "verifier")
def reported_classify(request, erratum_id: int):
    # TODO: Consider not filtering to "reported" and showing
    # a simple "this erratum has already been classified" instead
    # of a 400 if the status isn't reported.
    erratum = get_object_or_404(Erratum, id=erratum_id, status_id="reported")
    # Make sure this user can manipulate this erratum
    if not can_classify(request.user, erratum_id):
        raise Http404
    if request.method == "POST":
        form = EditErratumForm(data=request.POST, instance=erratum)
        if form.is_valid():
            action = request.POST.get("action", "")
            if action == "save":
                form.save()
                return redirect("errata_reported_classify", erratum_id=erratum.id)
            elif action.startswith("mark_") and action[5:] in (
                "verified",
                "rejected",
                "held_for_doc_update",
            ):
                erratum = form.save(commit=False)
                erratum.status_id = action[5:]
                erratum.verifier_name = request.user.name
                erratum.verifier_email = request.user.email
                erratum.verified_at = datetime.datetime.now()
                erratum.save()
                return redirect("errata_reported_list")
            else:
                pass
    else:
        form = EditErratumForm(instance=erratum)
    return render(request, "errata/reported_classify.html", dict(form=form))
