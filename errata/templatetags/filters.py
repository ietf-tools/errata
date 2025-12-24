# Copyright The IETF Trust 2025, All Rights Reserved

import calendar
from django import template

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
