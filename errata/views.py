# Copyright The IETF Trust 2025, All Rights Reserved

from django.views.decorators.http import require_GET
from django.shortcuts import render


from .forms import ErrataSearchForm
from .models import Erratum
from .search import search_errata


def wobbleup(request):
    return render(request, "errata/wobbleup.html")


@require_GET
def search(request):
    form = ErrataSearchForm(request.GET)
    if form.is_bound and form.is_valid() and request.GET != {}:
        errata = search_errata(form)
        template = (
            "errata/list.html"
            if form.cleaned_data.get("presentation") == "table"
            else "errata/list_detail.html"
        )
        search_ran = True
    else:
        errata = Erratum.objects.none()
        template = "errata/list.html"
        search_ran = False
    return render(request, template, dict(errata=errata, form=form, search_ran=search_ran))


@require_GET
def detail(request, pk):
    erratum = Erratum.objects.prefetch_related("rfc_metadata", "status", "type").get(
        pk=pk
    )
    return render(request, "errata/detail.html", dict(erratum=erratum))
