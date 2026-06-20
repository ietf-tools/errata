# Copyright The IETF Trust 2026, All Rights Reserved

import re
from django import forms

from .models import RfcMetadata, Erratum

STATUS_CHOICES = [
    ("any", "All/Any"),
    ("verified_reported", "Verified+Reported"),
    ("verified", "Verified"),
    ("reported", "Reported"),
    ("held_for_doc_update", "Held for Document Update"),
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
        widget=forms.TextInput(attrs={"placeholder": "YYYY-MM-DD, YYYY-MM, or YYYY"}),
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


class StagedErrataFilterForm(forms.Form):
    rfc_number = forms.IntegerField(required=False, label="RFC Number")
    submitter = forms.CharField(
        max_length=120,
        required=False,
        label="Submitter",
        widget=forms.TextInput(attrs={"placeholder": "Name or email"}),
    )
    date_from = forms.DateField(
        required=False,
        label="Submitted On or After",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        label="Submitted On or Before",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error(
                "date_to", "End date must not be earlier than the start date."
            )
        return cleaned_data


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


class EditErratumForm(forms.ModelForm):
    formats = forms.MultipleChoiceField(
        choices=[("HTML", "HTML"), ("PDF", "PDF"), ("TXT", "TXT")],
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta:
        model = Erratum
        fields = (
            "erratum_type",
            "section",
            "orig_text",
            "corrected_text",
            "submitter_name",
            "submitter_email",
            "notes",
            "formats",
        )
        widgets = {
            "section": forms.TextInput(attrs={"placeholder": "Enter number or GLOBAL"}),
        }
        help_texts = {
            "formats": "",
        }
        labels = {"orig_text": "Original text"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.rfc_number < 8650:
            self.fields.pop("formats")
        else:
            self.fields["formats"].required = True
        self.fields["erratum_type"].required = True
        self.fields["section"].required = True
        self.fields["orig_text"].required = True
        self.fields["corrected_text"].required = True
        self.fields["submitter_name"].required = True
        self.fields["submitter_email"].required = True

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("orig_text") == cleaned_data.get("corrected_text"):
            self.add_error(
                "corrected_text", "Corrected Text must be different from Original Text."
            )
        return cleaned_data


class ReclassifyErratumForm(EditErratumForm):
    """EditErratumForm plus a record of who the reclassification is on behalf of.

    The RPC can reclassify on behalf of themselves or name another verifying
    party. The verifier name/email are only consulted when a status-changing
    action is taken; a plain "save" leaves the existing verifier untouched.
    """

    ON_BEHALF_OF_MYSELF = "myself"
    ON_BEHALF_OF_OTHER = "other"
    ON_BEHALF_OF_CHOICES = [
        (ON_BEHALF_OF_MYSELF, "Myself (RFC Production Center)"),
        (ON_BEHALF_OF_OTHER, "Someone else"),
    ]

    on_behalf_of = forms.ChoiceField(
        choices=ON_BEHALF_OF_CHOICES,
        widget=forms.RadioSelect,
        initial=ON_BEHALF_OF_MYSELF,
        label="Reclassifying on behalf of",
    )
    verifier_name = forms.CharField(
        max_length=80,
        required=False,
        label="Verifying party name",
    )
    verifier_email = forms.EmailField(
        max_length=120,
        required=False,
        label="Verifying party email",
    )

    def __init__(self, *args, action="", **kwargs):
        # The submitted action determines whether the status is changing, which
        # in turn determines whether the verifying party is actually used.
        self.action = action
        super().__init__(*args, **kwargs)
        # Prefill the "someone else" fields with the current verifying party so
        # the RPC can keep or edit it.
        self.fields["verifier_name"].initial = self.instance.verifier_name
        self.fields["verifier_email"].initial = self.instance.verifier_email

    def clean(self):
        cleaned_data = super().clean()
        # The verifying party is only recorded when the status changes. A plain
        # "save" leaves the existing verifier untouched, so don't make the RPC
        # name someone just to save edits.
        changing_status = self.action.startswith("mark_")
        if (
            changing_status
            and cleaned_data.get("on_behalf_of") == self.ON_BEHALF_OF_OTHER
        ):
            if not cleaned_data.get("verifier_name"):
                self.add_error(
                    "verifier_name",
                    "Provide a name when reclassifying on behalf of someone else.",
                )
            if not cleaned_data.get("verifier_email"):
                self.add_error(
                    "verifier_email",
                    "Provide an email when reclassifying on behalf of someone else.",
                )
        return cleaned_data


class RfcNumberListForm(forms.Form):
    rfc_numbers = forms.CharField(
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. 1234, 5678-5680  Leave blank for all RFCs"}
        ),
        required=False,
        label="RFC Numbers",
    )

    def clean_rfc_numbers(self):
        rfc_numbers_str = self.cleaned_data["rfc_numbers"]
        if rfc_numbers_str.strip() == "":
            return []
        rfc_numbers = set()
        for part in rfc_numbers_str.split(","):
            part = part.strip()
            if "-" in part:
                start_str, end_str = part.split("-", 1)
                try:
                    start = int(start_str)
                    end = int(end_str)
                    if start > end:
                        raise forms.ValidationError(f"Invalid range: {part}")
                    rfc_numbers.update(range(start, end + 1))
                except ValueError:
                    raise forms.ValidationError(f"Invalid RFC number in range: {part}")
            else:
                try:
                    rfc_number = int(part)
                    rfc_numbers.add(rfc_number)
                except ValueError:
                    raise forms.ValidationError(f"Invalid RFC number: {part}")
        return sorted(rfc_numbers)
