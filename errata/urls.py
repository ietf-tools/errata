# Copyright The IETF Trust 2025-2026, All Rights Reserved
from django.http import HttpResponse
from django.urls import path, register_converter
from django.views.generic import RedirectView


from . import views


class ErratumTypeConverter:
    regex = "editorial|technical"

    def to_python(self, value):
        return str(value)

    def to_url(self, value):
        return str(value)


register_converter(ErratumTypeConverter, "erratumtype")

urlpatterns = [
    path("", RedirectView.as_view(url="/search/", permanent=True)),
    path("health/", lambda _: HttpResponse(status=204)),  # no content
    path("user-info/", views.user_info, name="errata_user_info"),
    path("search/", views.search, name="errata_search"),
    path("eid<int:pk>/", views.detail, name="errata_detail"),
    path(
        "new/entry-instructions/",
        views.new_entry_instructions,
        name="errata_new_entry_instructions",
    ),
    path(
        "new/review-existing/<int:rfc_number>/",
        views.new_review_existing,
        name="errata_new_review_existing",
    ),
    path("new/edit/<uuid:staged_erratum_id>/", views.new_edit, name="errata_new_edit"),
    path(
        "new/preview/<uuid:staged_erratum_id>/",
        views.new_preview,
        name="errata_new_preview",
    ),
    path(
        "staged/list/",
        views.staged_list,
        name="errata_staged_list",
    ),
    path(
        "staged/confirm-delete/<uuid:staged_erratum_id>",
        views.staged_confirm_delete,
        name="errata_staged_confirm_delete",
    ),
    path(
        "staged/edit/<uuid:staged_erratum_id>",
        views.staged_rpc_edit,
        name="errata_staged_rpc_edit",
    ),
    path(
        "staged/add-unverified/<uuid:staged_erratum_id>/<erratumtype:erratum_type>",
        views.staged_rpc_add_to_unverified,
        name="errata_staged_rpc_add_to_unverified",
    ),
    path(
        "reported/list",
        views.reported_list,
        name="errata_reported_list",
    ),
    path(
        "reported/classify/<int:erratum_id>",
        views.reported_classify,
        name="errata_reported_classify",
    ),
]
