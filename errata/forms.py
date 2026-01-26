# Copyright The IETF Trust 2026, All Rights Reserved

import re
from django import forms

from .models import RfcMetadata

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


class ChooseRfcForm(forms.Form):
    rfc_number = forms.IntegerField(required=True, label="RFC Number")

    def clean_rfc_number(self):
        rfc_number = self.cleaned_data.get("rfc_number")
        if rfc_number <= 0:
            raise forms.ValidationError("RFC Number must be a positive integer.")
        if not RfcMetadata.objects.filter(rfc_number=rfc_number).exists():
            raise forms.ValidationError(
                f"RFC {rfc_number} has not been published. (Very recently published RFCs may not yet be provisioned in the errata system.)"
            )
        return rfc_number


# Confirm form to ensure user has read existing errata before proceeding
class ConfirmExistingErrataReadForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label="I have read the existing errata for this RFC and what I wish to report has not been reported before.",
    )


class EditStagedErratumForm(forms.Form):
    submitter_name = forms.CharField(max_length=80, required=True, label="Your Name")
    submitter_email = forms.EmailField(
        max_length=120, required=True, label="Your Email"
    )
    formats = forms.MultipleChoiceField(
        choices=[("HTML", "HTML"), ("PDF", "PDF"), ("TXT", "TXT")],
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Publication Formats",
    )
    section = forms.CharField(
        widget=forms.TextInput(attrs={"placeholder": "Enter number or GLOBAL"}),
        required=True,
        label="Section",
    )
    orig_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}), required=True, label="Original Text"
    )
    corrected_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}), required=True, label="Corrected Text"
    )
    notes = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Enter any explanatory notes or rationale for the suggested correction.",
            }
        ),
        required=True,
        label="Notes",
    )

    def __init__(self, rfc_number, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if rfc_number < 8650:  # Start of the v3 RFCs
            self.fields.pop("formats")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("orig_text") == cleaned_data.get("corrected_text"):
            self.add_error(
                "corrected_text", "Corrected Text must be different from Original Text."
            )
