from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from finance.models import FinanceTransactionVariant, FinancePostingRuleLine as Line
from .collection_views import visible_sources
from .collections import require
from .models import TreasuryCollectionSource as Source
from . import cheque_redemptions


class RedemptionForm(forms.Form):
    variant = forms.ModelChoiceField(queryset=FinanceTransactionVariant.objects.none(), label='Reviewed principal-receipt treatment')
    received_on = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}), label='Actual date received')
    received_amount = forms.DecimalField(max_digits=18,decimal_places=2,label='Principal received')
    receipt_book = forms.CharField(max_length=80,label='New receipt book')
    receipt_number = forms.CharField(max_length=80,label='New receipt number')
    evidence_reference = forms.CharField(max_length=4000,widget=forms.Textarea,label='Actual receipt evidence')
    old_receipt_disposition = forms.ChoiceField(choices=(('','Choose actual evidence'),
        ('surrendered','Original receipt surrendered'),('loss_affidavit','Loss affidavit retained')),label='Original receipt evidence')
    old_receipt_evidence = forms.CharField(max_length=4000,widget=forms.Textarea,label='Surrender / affidavit reference')
    method = forms.ChoiceField(choices=(('cash','Cash'),('manager','Manager’s cheque'),('cashier','Cashier’s cheque')),
        label='Payment received')
    cheque_bank = forms.CharField(max_length=160,required=False,label='Cheque bank (cheque only)')
    cheque_drawer_account = forms.CharField(max_length=160,required=False,label='Cheque drawer account reference')
    cheque_number = forms.CharField(max_length=160,required=False,label='Cheque number')
    cheque_drawer = forms.CharField(max_length=160,required=False,label='Cheque drawer')
    cheque_date = forms.DateField(required=False,widget=forms.DateInput(attrs={'type':'date'}),label='Cheque date')

    def __init__(self,*args,original_return,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['variant'].queryset = FinanceTransactionVariant.objects.filter(
            department_id=original_return.finance_department_id,status='active',release__status='active',
            posting_rules__lines__account_source=Line.RETURN_RECEIVABLE).distinct()
        for field in self.fields.values(): field.widget.attrs['class'] = 'form-control'

    def clean(self):
        values = super().clean()
        supplied = {key:values.pop('cheque_'+key,None) for key in ('bank','drawer_account','number','drawer','date')}
        method = values.pop('method',None)
        if method == 'cash':
            if any(supplied.values()): raise ValidationError('Choose the actual cheque method when instrument details are supplied.')
        elif method in ('manager','cashier'):
            supplied['kind'] = method
            values['cheque'] = supplied
        return values


@login_required
@require_http_methods(['GET','POST'])
def create(request,public_id):
    source = get_object_or_404(visible_sources(request.user),public_id=public_id,kind=Source.CHEQUE_RETURN)
    if require(request.user,'vouchers.prepare_collections').pk != source.treasury_department_id:
        raise PermissionDenied
    form = RedemptionForm(request.POST or None,original_return=source,initial={'received_amount':source.amount})
    if request.method == 'POST' and form.is_valid():
        try:
            receipt = cheque_redemptions.capture(original_return=source,actor=request.user,**form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect('vouchers:collection_detail',public_id=receipt.public_id)
    return render(request,'vouchers/collections/form.html',{'form':form,'title':'Receive returned-cheque principal',
        'redemption_form':True})
