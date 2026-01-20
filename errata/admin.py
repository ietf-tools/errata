# Copyright The IETF Trust 2025, All Rights Reserved

from django.contrib import admin

from .models import (
    Erratum,
    Log,
    Status,
    Type,
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
        "type",
        "submitter_email",
        "submitted_at",
    ]
    list_filter = ["status", "type"]


admin.site.register(Erratum, ErratumAdmin)


class TypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "used"]


admin.site.register(Type, TypeAdmin)


class StatusAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "used"]


admin.site.register(Status, StatusAdmin)


class LogAdmin(admin.ModelAdmin):
    list_display = [
        "erratum",
        "verifier_email",
        "status",
        "type",
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
