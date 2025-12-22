# Copyright The IETF Trust 2025, All Rights Reserved

from django.contrib import admin

from .models import (
    AreaAssignment,
    Erratum,
    Log,
    Status,
    Type,
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


admin.site.register(Log, LogAdmin)


class AreaAssignmentAdmin(admin.ModelAdmin):
    search_fields = ["rfc_number", "area_acronym"]
    list_display = ["rfc_number", "area_acronym"]


admin.site.register(AreaAssignment, AreaAssignmentAdmin)
