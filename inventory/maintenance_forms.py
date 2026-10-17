from django import forms
from django.utils import timezone

from .models import Asset


class MaintenanceOpenForm(forms.Form):
    reported_date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    problem = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={"rows": 3}))
    provider = forms.CharField(max_length=240, required=False, label="Service provider / workshop")


class MaintenanceWorkForm(MaintenanceOpenForm):
    work_performed = forms.CharField(max_length=4000, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    documented_cost = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0, required=False,
        help_text="Leave blank if unknown. This record does not establish payment or accounting treatment.")
    cost_reference = forms.CharField(max_length=240, required=False)


class MaintenanceEvidenceForm(forms.Form):
    upload = forms.FileField(label="Supporting document (PDF, JPG, PNG or WebP; up to 15 MB)")
    note = forms.CharField(max_length=240, label="What does this document establish or correct?")


class MaintenanceCloseForm(forms.Form):
    action = forms.ChoiceField(choices=(("completed", "Complete work"), ("cancelled", "Cancel case")))
    finished_date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    outcome = forms.ChoiceField(required=False, choices=(("", "Select when completing"),
        (Asset.ACTIVE, "Returned to service"), (Asset.MAINTENANCE, "Still unserviceable / further work needed")))
    note = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={"rows": 3}), label="Outcome or cancellation reason")


class MaintenanceVersionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput(attrs={"id": ""}))
