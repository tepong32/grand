from django import forms
from django.utils import timezone


class ReturnStartForm(forms.Form):
    source_token = forms.CharField(widget=forms.HiddenInput)
    transfer_date = forms.DateField(label="Physical return date", initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}))
    destination_custodian = forms.CharField(max_length=160, label="Receiving GSO location / storeroom")
    reference = forms.CharField(max_length=120, label="Witnessed return document reference")
    return_condition = forms.ChoiceField(label="Observed condition", initial="unknown", choices=(
        ("serviceable", "Serviceable"), ("damaged", "Damaged / needs attention"), ("unknown", "Not assessed")))
    reason = forms.CharField(max_length=240, label="Witnessed receipt facts",
        widget=forms.Textarea(attrs={"rows": 3}))


class ReturnEvidenceForm(forms.Form):
    upload = forms.FileField(label="Return evidence (PDF or image)")
    note = forms.CharField(max_length=240, label="What this document establishes")


class ReturnDecisionForm(forms.Form):
    note = forms.CharField(max_length=240, widget=forms.Textarea(attrs={"rows": 3}), label="Decision basis")


class ReturnVersionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
