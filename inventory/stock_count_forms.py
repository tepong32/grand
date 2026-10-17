from django import forms
from django.utils import timezone


class StockCountForm(forms.Form):
    source_token = forms.CharField(widget=forms.HiddenInput)
    counted_on = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    quantity = forms.DecimalField(min_value=0, max_digits=12, decimal_places=3, label="Quantity physically counted")
    reference = forms.CharField(max_length=120, label="Count-sheet reference")
    note = forms.CharField(max_length=240, label="Count and variance facts", widget=forms.Textarea(attrs={"rows": 3}))


class StockCountEvidenceForm(forms.Form):
    upload = forms.FileField(label="Count evidence (PDF or image)")
    note = forms.CharField(max_length=240, label="What the document establishes")


class StockCountDecisionForm(forms.Form):
    note = forms.CharField(max_length=240, label="Decision basis", widget=forms.Textarea(attrs={"rows": 3}))


class StockCountVersionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
