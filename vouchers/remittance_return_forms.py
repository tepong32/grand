from django import forms
from django.utils import timezone

from .remittance_returns import original_payment, remaining_allocations


class RemittanceReturnWithdrawalForm(forms.Form):
    reason = forms.CharField(label='Why must this approved receipt be replaced?',
        widget=forms.Textarea(attrs={'rows': 2}),
        help_text='Discard any unposted JEV first. A posted receipt needs a separate Accounting correction.')


class ReceiptCorrectionForm(forms.Form):
    correction_date = forms.DateField(label='Correction posting date', initial=timezone.localdate,
        widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(label='What was recorded incorrectly?', widget=forms.Textarea(attrs={'rows': 2}))
    evidence_reference = forms.CharField(label='Evidence of the receipt error', max_length=200)
    filing_basis = forms.CharField(label='Tax-filing review / disposition basis', widget=forms.Textarea(attrs={'rows': 2}),
        help_text='The existing filing remains retained. Any filing amendment requires its own review.')
    expected_version = forms.IntegerField(widget=forms.HiddenInput)


class RemittanceReturnForm(forms.Form):
    returned_on = forms.DateField(label='Actual receipt date', initial=timezone.localdate,
        widget=forms.DateInput(attrs={'type': 'date'}))
    receipt_reference = forms.CharField(label='Bank or recipient receipt reference', max_length=200)
    receiving_bank_id = forms.ChoiceField(label='Account that actually received the money', required=False)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label='Why was this amount returned?')
    filing_basis = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}),
        label='Tax-filing review / agency disposition evidence',
        help_text='Retain any existing filing. Explain the documented filing implications; receipt alone does not amend a return.')
    expected_version = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, batch, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['expected_version'] = batch.state_version
        self.fields['receipt_reference'].help_text = 'Match the actual bank credit. Deducted bank fees require separate Accounting treatment.'
        _, _, details, bank = original_payment(batch)
        from .receipt_banks import available_banks
        day = timezone.localdate()
        if self.is_bound:
            try:
                day = self.fields['returned_on'].clean(self.data.get('returned_on'))
            except forms.ValidationError:
                pass
        self.fields['receiving_bank_id'].choices = [('', f'Original account: {batch.bank_account_code} · {bank.account.code}')]
        self.fields['receiving_bank_id'].choices += [(str(item.public_id), f'{item.label} · {item.code} · v{item.version}')
            for item in available_banks(batch, day)]
        remaining = remaining_allocations(batch, details)
        self.source_keys = []
        for detail in details:
            key = str(detail.pk)
            if remaining[key] <= 0:
                continue
            name = f'amount_{key}'
            self.source_keys.append((name, key))
            self.fields[name] = forms.DecimalField(required=False, min_value=0,
                max_value=remaining[key], max_digits=18, decimal_places=2,
                label=f'{detail.reference_label} / {detail.source_code} — amount received',
                help_text=f'Unreturned and unreserved: {remaining[key]:,.2f}. Leave blank for no return against this line.')

    def clean(self):
        cleaned = super().clean()
        cleaned['allocations'] = [{'source_detail': key, 'amount': cleaned[name]}
            for name, key in self.source_keys if cleaned.get(name)]
        if not cleaned['allocations']:
            raise forms.ValidationError('Allocate the actual receipt to at least one original liability line.')
        return cleaned

    def cleaned_data_without_amounts(self):
        return {key: value for key, value in self.cleaned_data.items() if not key.startswith('amount_')}
