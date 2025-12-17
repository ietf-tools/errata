# Copyright The IETF Trust 2025, All Rights Reserved
from django.urls import path


from . import views

urlpatterns = [
    path("", views.wobbleup, name="wobbleup"),
]
