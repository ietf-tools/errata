# Copyright The IETF Trust 2025, All Rights Reserved
from django.urls import path


from . import views

urlpatterns = [
    path("", views.wobbleup, name="wobbleup"),
    path("search/", views.search, name="errata_search"),
    path("eid<int:pk>/", views.detail, name="errata_detail"),
]
