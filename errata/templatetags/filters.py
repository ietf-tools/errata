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
