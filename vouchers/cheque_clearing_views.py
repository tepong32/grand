from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .collections import require
from .collection_views import visible_sources
from .models import TreasuryCollectionSource as Source
from . import cheque_clearing


class ClearingForm(forms.Form):
    deposit = forms.ModelChoiceField(queryset=Source.objects.none(), label='Posted whole-cheque deposit')
    cleared_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Actual bank clearing date')
    bank_reference = forms.CharField(max_length=160, label='Bank clearing confirmation reference')
    evidence_reference = forms.CharField(widget=forms.Textarea, label='Bank evidence location / reference')

    def __init__(self, *args, receipt, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        candidates = Source.objects.filter(kind=Source.DEPOSIT, status=Source.POSTED,
            treasury_department_id=receipt.treasury_department_id, finance_department_id=receipt.finance_department_id,
            fund_code=receipt.fund_code)
        ids = [row.pk for row in candidates if any(share.get('receipt') == str(receipt.public_id)
            for share in row.proposal.get('allocations', []))]
        self.fields['deposit'].queryset = candidates.filter(pk__in=ids)
        self.fields['deposit'].label_from_instance = lambda row: f'{row.document_reference} · {row.source_date} · {row.amount}'


@login_required
@require_http_methods(['GET', 'POST'])
def create(request, public_id):
    receipt = get_object_or_404(visible_sources(request.user), public_id=public_id, kind=Source.RECEIPT)
    office = require(request.user, 'vouchers.prepare_collections')
    if office.pk != receipt.treasury_department_id:
        raise PermissionDenied
    form = ClearingForm(request.POST or None, receipt=receipt)
    if request.method == 'POST' and form.is_valid():
        try:
            cheque_clearing.propose(receipt=receipt, actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect('vouchers:collection_detail', public_id=receipt.public_id)
    return render(request, 'vouchers/collections/form.html', {'form':form, 'title':'Record bank cheque clearing', 'clearing_form':True})


@login_required
@require_POST
def review(request, public_id, clearance_id):
    receipt = get_object_or_404(visible_sources(request.user), public_id=public_id)
    row = get_object_or_404(receipt.cheque_clearances, public_id=clearance_id)
    form = forms.Form()
    try:
        action = request.POST.get('decision')
        if action == 'withdraw':
            cheque_clearing.withdraw(clearance=row, actor=request.user, reason=request.POST.get('reason'))
        elif action in ('approve', 'reject'):
            cheque_clearing.review(clearance=row, actor=request.user, approve=action == 'approve', reason=request.POST.get('reason'))
        else:
            raise ValidationError('Choose an explicit clearing decision.')
    except ValidationError as exc:
        form = forms.Form(request.POST)
        form.is_valid()
        form.add_error(None, exc)
        return render(request, 'vouchers/collections/form.html', {'form':form, 'title':'Cheque clearing decision', 'clearing_form':True}, status=400)
    return redirect('vouchers:collection_detail', public_id=receipt.public_id)
