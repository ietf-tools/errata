# Copyright The IETF Trust 2025-2026, All Rights Reserved

from django.contrib import admin

from .models import (
    Erratum,
    Log,
    StagedErratum,
    Status,
    ErratumType,
    RfcMetadata,
)


class ErratumAdmin(admin.ModelAdmin):
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


class LogAdmin(admin.ModelAdmin):
    list_display = [
        "erratum",
        "verifier_email",
        "status",
        "erratum_type",
        "editor_email",
        "created_at",
    ]
    raw_id_fields = ["erratum"]
    list_filter = ["erratum"]


admin.site.register(Log, LogAdmin)


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
