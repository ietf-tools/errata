# Copyright The IETF Trust 2025, All Rights Reserved

import calendar
from django import template

from errata.utils import can_classify

register = template.Library()


@register.filter
def suppress_strings_starting_with_99(value):
    """
    Returns "-" if string starts with "99", otherwise returns the input string.
    """
    if isinstance(value, str) and value.startswith("99"):
        return "-"
    return value


@register.filter
def month_name(month_number):
    return calendar.month_name[month_number]


@register.filter
def has_role(user, role_names):
    from errata_auth.utils import has_role

    if not user:
        return False
    return has_role(user, role_names.split(","))


@register.filter
def is_classifiable_by(erratum, user):
    return can_classify(user, erratum.id)


@register.filter
def txt_errata_section(erratum):
    if erratum.section.upper() == "GLOBAL":
        return "Throughout the document, when it says:"
    elif suppress_strings_starting_with_99(erratum.section) != "-":
        return f"Section {erratum.section} says:"
    else:
        # Covers the html branch for strings of len < 2
        # with a return of "" instead of &nbsp;
        return erratum.section[2:]


@register.filter
def txt_errata_verifying_party(erratum):
    rfc_meta = erratum.rfc_metadata
    if rfc_meta.area_assignment != "" or rfc_meta.stream == "ietf":
        return "IESG"
    elif rfc_meta.stream == "irtf":
        return "IRSG"
    elif rfc_meta.stream == "iab":
        return "IAB"
    elif rfc_meta.stream == "independent":
        return "ISE & Editorial Board"
    elif rfc_meta.stream == "editorial":
        return "RSAB"
    else:
        return "RFC-Editor"
