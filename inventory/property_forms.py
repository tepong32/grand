from django import forms
from .models import PropertyDetermination
from .property_determinations import CONTENT_FIELDS


class PropertyForm(forms.ModelForm):
    source_token = forms.CharField(widget=forms.HiddenInput)
    upload = forms.FileField(label="Supplied determination (PDF or image)")

    class Meta:
        model = PropertyDetermination
        fields = CONTENT_FIELDS
        widgets = {name: forms.DateInput(attrs={"type": "date"}) for name in ("source_date", "life_start", "expires_on", "acquisition_date")}
        labels = {"treatment": "Treatment stated in the supplied document", "source_authority": "Authority stated in the source",
            "property_class": "Property class as supplied (leave blank if unknown)",
            "fund_label": "Fund name shown in the source (optional)",
            "acquisition_date": "Acquisition date stated in the retained packet (optional)",
            "acquisition_reference": "Acquisition source reference in the retained packet (optional)",
            "receipt_item_number": "Receipt-item number assigned by the property unit (as supplied, optional)",
            "useful_life": "Documented useful-life duration (leave blank if unknown)",
            "life_basis": "Documented useful-life start basis", "life_start": "Supplied start date (optional)",
            "expires_on": "Supplied expiry date (optional)",
            "reason": "Reason for this entry or successor correction"}
        help_texts = {"acquisition_reference": "Identify the acquisition document included in this private packet. Leave unknown facts blank.",
            "receipt_item_number": "Copy the assigned source number. This does not allocate a new series or replace the asset's property tag.",
            "acquisition_date": "Copy the documented acquisition date; delivery, inspection and entry dates are separate facts."}


class PropertyDecisionForm(forms.Form):
    note = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 3}), label="Document check and decision basis")


class PropertyVersionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
