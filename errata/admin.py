# Copyright The IETF Trust 2025-2026, All Rights Reserved

from simple_history.admin import SimpleHistoryAdmin

from django.contrib import admin
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

# Statuses that represent a classification of a previously "reported" erratum.
# Matches the transitions handled by errata.views.reported_classify.
CLASSIFIED_STATUS_SLUGS = {"verified", "rejected", "held_for_doc_update"}


class ErratumAdmin(SimpleHistoryAdmin):
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
        * Moving a "reported" erratum to a classified state notifies the same
          way reported_classify does. The acting user is recorded as the
          verifier only when the form leaves the verifier fields blank, so an
          admin can attribute the classification to someone else.
        """
        notify_new = False
        notify_classified = False

        if not change:
            notify_new = obj.status_id == "reported"
        else:
            previous_status = (
                Erratum.objects.filter(pk=obj.pk)
                .values_list("status_id", flat=True)
                .first()
            )
            if (
                previous_status == "reported"
                and obj.status_id in CLASSIFIED_STATUS_SLUGS
            ):
                notify_classified = True
                # Preserve verifier details entered in the admin form; only
                # fall back to the acting user when they were left blank. This
                # lets an admin record a classification performed by someone
                # else while still defaulting to themselves in the common case.
                if not obj.verifier_email:
                    obj.verifier_name = request.user.name
                    obj.verifier_email = request.user.email
                if obj.verified_at is None:
                    obj.verified_at = timezone.now()

        super().save_model(request, obj, form, change)

        if notify_new:
            send_new_erratum_notification(obj, request.user)
        elif notify_classified:
            send_erratum_classified_notification(obj, request.user)


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
