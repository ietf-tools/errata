# Copyright The IETF Trust 2026, All Rights Reserved

import re
from django import forms

STATUS_CHOICES = [
    ("any", "All/Any"),
    ("verified_reported", "Verified+Reported"),
    ("verified", "Verified"),
    ("reported", "Reported"),
    ("held", "Held for Document Update"),
    ("rejected", "Rejected"),
]

AREA_CHOICES = [
    ("any", "All/Any"),
    ("app", "app"),
    ("art", "art"),
    ("gen", "gen"),
    ("int", "int"),
    ("ops", "ops"),
    ("rai", "rai"),
    ("rtg", "rtg"),
    ("sec", "sec"),
    ("tsv", "tsv"),
    ("wit", "wit"),
]

TYPE_CHOICES = [
    ("any", "All/Any"),
    ("editorial", "Editorial"),
    ("technical", "Technical"),
]

# These left tuple element reflects query strings long in the wild.
STREAM_CHOICES = [
    ("any", "All/Any"),
    ("IAB", "IAB"),
    ("INDEPENDENT", "INDEPENDENT"),
    ("IRTF", "IRTF"),
    ("Legacy", "Legacy"),
    ("Editorial", "Editorial"),
]

PRESENTATION_CHOICES = [
    ("table", "Table"),
    ("records", "Full Records"),
]


class ErrataSearchForm(forms.Form):
    rfc_number = forms.IntegerField(required=False, label="RFC Number")
    errata_id = forms.IntegerField(required=False, label="Errata ID")
    status = forms.ChoiceField(
        choices=STATUS_CHOICES, required=False, label="Status", initial="any"
    )
    area = forms.ChoiceField(
        choices=AREA_CHOICES, required=False, label="Area Acronym", initial="any"
    )
    errata_type = forms.ChoiceField(
        choices=TYPE_CHOICES, required=False, label="Type", initial="any"
    )
    wg_acronym = forms.CharField(max_length=40, required=False, label="WG Acronym")
    submitter_name = forms.CharField(
        max_length=80, required=False, label="Submitter Name"
    )
    stream = forms.ChoiceField(
        choices=STREAM_CHOICES, required=False, label="Stream", initial="any"
    )  # Labeled "Other" in previous errata app
    date = forms.CharField(
        required=False,
        label="Date Submitted",
        widget=forms.TextInput(attrs={"placeholder": "YYYY-MM-DD"}),
    )
    presentation = forms.ChoiceField(
        choices=PRESENTATION_CHOICES,
        required=False,
        label="Presentation",
        initial="table",
    )

    def clean_date(self):
        pattern = r"^\d{4}(?:-\d{1,2}(?:-\d{1,2})?)?$"
        date_str = self.cleaned_data.get("date", "")
        if date_str != "" and not re.match(pattern, date_str):
            raise forms.ValidationError("Date format must be a valid prefix YYYY-MM-DD")
        return date_str