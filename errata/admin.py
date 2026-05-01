# Copyright The IETF Trust 2025-2026, All Rights Reserved

from simple_history.admin import SimpleHistoryAdmin

from django.contrib import admin

from .models import (
    Erratum,
    StagedErratum,
    Status,
    ErratumType,
    RfcMetadata,
    DirtyBits,
)


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
