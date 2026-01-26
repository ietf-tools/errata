# Copyright The IETF Trust 2025, All Rights Reserved
from django.urls import path


from . import views

urlpatterns = [
    path("", views.wobbleup, name="wobbleup"),
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
]
