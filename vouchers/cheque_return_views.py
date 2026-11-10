from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from finance.models import FinanceTransactionVariant, FinancePostingRule, FinancePostingRuleLine
from .cheque_clearing_views import ClearingForm
from .collection_views import visible_sources
from .collections import require
from .models import TreasuryCollectionSource as Source
from . import cheque_returns


class ReturnForm(forms.Form):
    deposit = forms.ModelChoiceField(queryset=Source.objects.none(), label='Original posted deposit')
    variant = forms.ModelChoiceField(queryset=FinanceTransactionVariant.objects.none(), label='Reviewed bank-return treatment')
    debited_on = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}), label='Actual bank debit date')
    debit_amount = forms.DecimalField(max_digits=18, decimal_places=2, label='Whole cheque amount debited')
    bank_reference = forms.CharField(max_length=80, label='Bank debit memo / reference')
    reason = forms.CharField(max_length=4000, label='Bank return reason')
    evidence_reference = forms.CharField(max_length=4000, widget=forms.Textarea, label='Bank debit evidence')
    applicability_reference = forms.CharField(max_length=4000, widget=forms.Textarea,
        label='Basis for applying this treatment to the original collection',
        help_text='Identify the reviewed collection category and authority. Include every component of a multi-charge receipt.')

    def __init__(self, *args, receipt, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['deposit'].queryset = ClearingForm(receipt=receipt).fields['deposit'].queryset
        self.fields['deposit'].label_from_instance = lambda row: f'{row.document_reference} · {row.source_date} · {row.amount}'
        self.fields['variant'].queryset = FinanceTransactionVariant.objects.filter(
            department_id=receipt.finance_department_id, status='active', release__status='active',
            posting_rules__event_kind=FinancePostingRule.CHEQUE_RETURN).distinct()
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class ReturnComponentForm(forms.Form):
    purpose = forms.ChoiceField(disabled=True,label='Original non-officer cash purpose / amount')
    variant = forms.ModelChoiceField(queryset=FinanceTransactionVariant.objects.none(),to_field_name='public_id',
        label='Reviewed charge-receivable return treatment')

    def __init__(self,*args,receipt,parts,**kwargs):
        super().__init__(*args,**kwargs)
        from finance.cash_flows import CASH_FLOW_CHOICES
        labels = dict(CASH_FLOW_CHOICES)
        self.fields['purpose'].choices = [(key,f'{labels[key]} · {value:,.2f}') for key,value in sorted(parts.items())]
        self.fields['variant'].queryset = FinanceTransactionVariant.objects.filter(
            department_id=receipt.finance_department_id,status='active',release__status='active',
            posting_rules__event_kind=FinancePostingRule.CHEQUE_RETURN,
            posting_rules__lines__side=FinancePostingRuleLine.DEBIT,
            posting_rules__lines__account_source=FinancePostingRuleLine.FIXED_ACCOUNT).distinct()
        for field in self.fields.values():field.widget.attrs['class'] = 'form-control'


ReturnComponents = forms.formset_factory(ReturnComponentForm,extra=0,min_num=1,validate_min=True)


@login_required
@require_http_methods(['GET','POST'])
def create(request, public_id):
    receipt = get_object_or_404(visible_sources(request.user), public_id=public_id, kind=Source.RECEIPT)
    if require(request.user, 'vouchers.prepare_collections').pk != receipt.treasury_department_id:
        raise PermissionDenied
    form = ReturnForm(request.POST or None, receipt=receipt, initial={'debit_amount':receipt.amount})
    components, source_error = None, None
    if receipt.proposal.get('officer_components'):
        from .officer_receipt_components import receipt_parts
        try:
            _, parts = receipt_parts(receipt)
        except ValidationError as exc:
            source_error = ' '.join(exc.messages)
        else:
            components = ReturnComponents(request.POST if request.method == 'POST' else None,prefix='components',
                initial=[{'purpose':key} for key in sorted(parts)],form_kwargs={'receipt':receipt,'parts':parts})
    if request.method == 'POST' and not source_error and form.is_valid() and (components is None or components.is_valid()):
        try:
            choices = [{'purpose':row.cleaned_data['purpose'],'variant':str(row.cleaned_data['variant'].public_id)}
                for row in components] if components is not None else None
            source = cheque_returns.capture(receipt=receipt,actor=request.user,charge_treatments=choices,**form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect('vouchers:collection_detail', public_id=source.public_id)
    return render(request,'vouchers/collections/form.html',{'form':form,'title':'Record incoming cheque bank return',
        'return_components':components,'source_error':source_error})
