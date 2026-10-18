from django import forms
from .maintenance_forms import MaintenanceWorkForm


class CorrectionValuesForm(MaintenanceWorkForm):
    finished_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    closure_note = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}),
                                   label='Documented outcome or cancellation explanation')


class CorrectionProposalForm(CorrectionValuesForm):
    source_token = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}),
                             label='Why does the recorded information need correction?')
    source_reference = forms.CharField(max_length=240, label='Basis for this correction (document / office reference)')
    upload = forms.FileField(label='Correction evidence (PDF or image; up to 15 MB)')


class CorrectionDecisionForm(forms.Form):
    expected_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action = forms.ChoiceField(choices=(('', 'Choose a decision'), ('approved', 'Approve documentary correction'), ('rejected', 'Reject proposal')))
    note = forms.CharField(max_length=4000, widget=forms.Textarea(attrs={'rows': 3}), label='Independent review findings')
