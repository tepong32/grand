"""Explicit office checks for the existing immutable whole-package review service."""
from django import forms
from .form1_package_reviews import CHECKS

LABELS = {
    'entity_inventory': 'Complete entity inventory',
    'estimates': 'Approved receipt and expenditure estimates',
    'stock_calendar': 'Opening stock dates and annual boundary',
    'planning_cash_reconciliation': 'Planning resources and cash timing reconciliation',
    'philhealth_policy': 'Applicable PhilHealth policy evidence',
    'actuals': 'Original actuals and source controls',
    'accounts_and_spa': 'Reporting accounts and SPA subdivisions',
    'philhealth_sources': 'Original PhilHealth source evidence',
    'overlap_treatment': 'Evidenced overlap and funding treatment',
    'cash_sources': 'Original cash, deposit and collection sources',
    'restriction_lineage': 'Restriction identities and history',
    'timing_worksheet': 'Cash timing worksheet evidence',
}


class PackageDecision(forms.Form):
    authority = forms.CharField(label='Your designation authority', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))
    note = forms.CharField(label='Independent review or return reason', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))

    def __init__(self, role, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role
        for key in CHECKS[role]:
            self.fields[key+'_verified'] = forms.TypedChoiceField(label=LABELS[key],
                choices=(('', 'Choose a finding'), ('true', 'Verified'), ('false', 'Not verified')),
                coerce=lambda value: value == 'true',
                widget=forms.Select(attrs={'class': 'form-select'}))
            self.fields[key+'_basis'] = forms.CharField(label=LABELS[key]+' — evidence and basis',
                max_length=2000, widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))

    def checks(self):
        return {key: dict(verified=self.cleaned_data[key+'_verified'],
            basis=self.cleaned_data[key+'_basis']) for key in CHECKS[self.role]}
