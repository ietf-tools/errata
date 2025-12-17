# Copyright The IETF Trust 2025, All Rights Reserved
from django.shortcuts import render

def wobbleup(request):
    return render(request, "errata/wobbleup.html")
