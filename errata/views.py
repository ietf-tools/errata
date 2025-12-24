# Copyright The IETF Trust 2025, All Rights Reserved
from django.shortcuts import render
from .models import Erratum


def wobbleup(request):
    return render(request, "errata/wobbleup.html")


def list(request):
    errata = Erratum.objects.order_by(
        "status__order", "rfc_number", "type__order", "pk"
    ).prefetch_related("rfc_metadata", "status", "type")
    return render(request, "errata/list.html", dict(errata=errata))


def detail(request, pk):
    erratum = Erratum.objects.prefetch_related("rfc_metadata", "status", "type").get(
        pk=pk
    )
    return render(request, "errata/detail.html", dict(erratum=erratum))
