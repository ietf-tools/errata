# Copyright The IETF Trust 2025-2026, All Rights Reserved

import logging

from simple_history.admin import SimpleHistoryAdmin

from django import forms
from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from .mail import (
    send_erratum_classified_notification,
    send_new_erratum_notification,
)
from .models import (
    Erratum,
    StagedErratum,
    Status,
    ErratumType,
    RfcMetadata,
    DirtyBits,
)

logger = logging.getLogger(__name__)

# Statuses that represent a classified erratum. Matches the transitions
# offered by errata.views.reported_classify and errata.views.rpc_reclassify.
CLASSIFIED_STATUS_SLUGS = {"verified", "rejected", "held_for_doc_update"}


class ErratumAdminForm(forms.ModelForm):
    """Require an erratum type, which the model leaves optional.

    Every notification branches on erratum_type, so an untyped erratum cannot
    be announced. Historical rows are allowed to have none, but nothing the
    admin saves should add to them.
    """

    class Meta:
        model = Erratum
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["erratum_type"].required = True


class ErratumAdmin(SimpleHistoryAdmin):
    form = ErratumAdminForm
    search_fields = ["rfc_number", "verifier_name", "verifier_email", "submitter_email"]
    list_display = [
        "pk",
        "rfc_number",
        "verifier_name",
        "verifier_email",
        "status",
        "erratum_type",
        "submitter_email",
        "submitted_at",
    ]
    list_filter = ["status", "erratum_type"]

    def save_model(self, request, obj, form, change):
        """Trigger the same notifications the public workflow sends.

        Editing errata through the admin bypasses the views in errata.views,
        so we mirror their notification side effects here:

        * Creating an erratum in the "reported" state notifies stakeholders
          the same way promoting a staged erratum does
          (see staged_rpc_add_to_unverified).
        * Moving an erratum into a classified state notifies the same way
          reported_classify and rpc_reclassify do.
        """
        notify = None

        if not change:
            if obj.status_id == "reported":
                notify = send_new_erratum_notification
        else:
            previous_status = (
                Erratum.objects.filter(pk=obj.pk)
                .values_list("status_id", flat=True)
                .first()
            )
            if (
                previous_status != obj.status_id
                and obj.status_id in CLASSIFIED_STATUS_SLUGS
            ):
                notify = send_erratum_classified_notification
                # Record the acting user as the verifier unless this save
                # supplied one, which lets an admin attribute a classification
                # to someone else. Keying on what the form changed rather than
                # on what the record already holds matters for reclassification:
                # an erratum being reclassified still carries the previous
                # verifier, which would otherwise suppress the fallback.
                if not self._verifier_supplied(form):
                    obj.verifier_name = request.user.name
                    obj.verifier_email = request.user.email
                obj.verified_at = timezone.now()

        super().save_model(request, obj, form, change)

        if notify is None:
            return
        if obj.erratum_type_id is None:
            # Only reachable for a save that bypasses ErratumAdminForm. Log
            # rather than raise: the admin runs save_model inside a
            # transaction, so an exception here would roll back the edit that
            # just succeeded.
            logger.warning(
                "Erratum %s has no erratum_type; skipping notification", obj.pk
            )
            return
        # Defer until the admin's transaction commits. send_mail_task is queued
        # by the notification, and a worker picking it up before the commit
        # would not find the MailMessage it names.
        transaction.on_commit(lambda: notify(obj, request.user))

    @staticmethod
    def _verifier_supplied(form):
        """Did this save explicitly set the verifier, rather than inherit one?"""
        if form is None:
            return False
        return bool({"verifier_name", "verifier_email"}.intersection(form.changed_data))


admin.site.register(Erratum, ErratumAdmin)


class ErratumTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "used"]


admin.site.register(ErratumType, ErratumTypeAdmin)


class StatusAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "used"]


admin.site.register(Status, StatusAdmin)


class RfcMetadataAdmin(admin.ModelAdmin):
    search_fields = ["rfc_number", "title"]
    list_display = [
        "rfc_number",
        "title",
        "publication_year",
        "publication_month",
        "group_acronym",
        "area_acronym",
        "stream",
        "area_assignment",
    ]
    list_filter = ["area_acronym", "stream", "area_assignment"]


admin.site.register(RfcMetadata, RfcMetadataAdmin)


class StagedErratumAdmin(admin.ModelAdmin):
    search_fields = ["rfc_number", "submitter_email"]
    list_display = [
        "id",
        "rfc_number",
        "submitter_name",
        "submitter_email",
        "entry_status",
        "created_at",
    ]
    list_filter = ["entry_status"]


admin.site.register(StagedErratum, StagedErratumAdmin)


@admin.register(DirtyBits)
class DirtyBitsAdmin(admin.ModelAdmin):
    list_display = ["slug", "dirty_time", "processed_time"]
