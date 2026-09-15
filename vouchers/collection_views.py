"""Ordinary collection entry and office-scoped receipt/deposit register."""
import csv
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from finance.models import FinanceConfigurationItem, FinanceTransactionVariant, FinancePostingRule
from .access import department_for_user, has_explicit_permission
from .models import TreasuryCollectionSource as Source
from .collections import record_receipt, record_deposit, remaining_receipts, require
from .roles import is_finance_uat_viewer
from accounting.models import JournalSubsidiaryLine


def visible_sources(user):
    office = department_for_user(user)
    if not office or not has_explicit_permission(user, 'vouchers.view_collection_register'):
        raise PermissionDenied
    return Source.objects.filter(Q(treasury_department_id=office.pk) | Q(finance_department_id=office.pk))


class ReceiptForm(forms.Form):
    cheque_bank = forms.CharField(max_length=160, required=False, label='Cheque drawee bank (cheque only)')
    cheque_drawer_account = forms.CharField(max_length=160, required=False, label='Cheque drawer account reference')
    cheque_number = forms.CharField(max_length=160, required=False, label='Cheque number')
    cheque_drawer = forms.CharField(max_length=160, required=False, label='Cheque drawer')
    cheque_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}), label='Cheque date')
    receiving_bank_id = forms.ModelChoiceField(queryset=FinanceConfigurationItem.objects.none(),
        to_field_name='public_id', required=False, label='Receiving bank (bank transfer only)',
        help_text='Choose only after the incoming bank credit is confirmed. Leave blank for cash.')
    bank_transaction_reference = forms.CharField(max_length=160, required=False,
        label='Bank credit reference (bank transfer only)')
    advance_detail = forms.ModelChoiceField(queryset=JournalSubsidiaryLine.objects.none(), required=False,
        label='Original officer advance (returned advance money only)',
        help_text='Choose the original advance and a reviewed refund collection type. The officer identity is retained automatically. The cheque amount is reserved against this advance. Receipt posting alone is not bank clearing; clearing needs independent bank evidence.')
    variant = forms.ModelChoiceField(queryset=FinanceTransactionVariant.objects.none(), label='Collection type')
    received_on = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}), label='Date received')
    fund_code = forms.ChoiceField(label='Fund')
    receipt_book = forms.CharField(max_length=80, label='Receipt book')
    receipt_number = forms.CharField(max_length=80)
    payer_reference = forms.CharField(label='Payer / reference', required=False)
    received_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal('.01'), label='Amount received')
    evidence_reference = forms.CharField(widget=forms.Textarea(attrs={'rows':3}), label='Collection evidence / remarks')

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['receiving_bank_id'].queryset = FinanceConfigurationItem.objects.filter(
            category='bank_account',status='active',release__status='active').select_related('release')
        if user:
            from .advance_refunds import visible_originals
            self.fields['advance_detail'].queryset = visible_originals(user).select_related('entry', 'entry__fund')
            self.fields['advance_detail'].label_from_instance = lambda row: f'{row.reference_label} · {row.entry.reference} · {row.entry.fund.code} · original {row.debit}'
        self.fields['variant'].queryset = FinanceTransactionVariant.objects.filter(
            status='active', release__status='active', posting_rules__event_kind=FinancePostingRule.COLLECTION
        ).exclude(posting_rules__lines__account_source='return_receivable').distinct()
        self.fields['fund_code'].choices = [('', 'Choose a fund'), *FinanceConfigurationItem.objects.filter(
            category='fund',status='active',release__status='active').order_by('code','label').values_list('code','label').distinct()]
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class CollectionChargeForm(forms.Form):
    variant = forms.ModelChoiceField(queryset=FinanceTransactionVariant.objects.none(), to_field_name='public_id', label='Charge type')
    amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal('.01'), label='Charge amount')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['variant'].queryset = ReceiptForm().fields['variant'].queryset
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


CollectionCharges = forms.formset_factory(CollectionChargeForm, extra=2)


class DepositForm(forms.Form):
    variant = forms.ModelChoiceField(queryset=FinanceTransactionVariant.objects.none(), label='Deposit type')
    deposited_on = forms.DateField(widget=forms.DateInput(attrs={'type':'date'}), label='Deposit date')
    fund_code = forms.ChoiceField(label='Fund')
    deposit_reference = forms.CharField(max_length=80, label='Deposit slip / reference')
    receiving_bank_id = forms.ModelChoiceField(queryset=FinanceConfigurationItem.objects.none(),
        to_field_name='public_id', label='Receiving bank account')
    evidence_reference = forms.CharField(widget=forms.Textarea(attrs={'rows':3}), label='Deposit evidence / remarks')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['variant'].queryset = FinanceTransactionVariant.objects.filter(
            status='active',release__status='active',posting_rules__event_kind=FinancePostingRule.DEPOSIT).distinct()
        self.fields['fund_code'].choices = ReceiptForm().fields['fund_code'].choices
        self.fields['receiving_bank_id'].queryset = FinanceConfigurationItem.objects.filter(
            category='bank_account',status='active',release__status='active').select_related('release')
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class ReceiptChoice(forms.ModelChoiceField):
    def label_from_instance(self, source):
        return f'{source.book_reference} / {source.document_reference} · {source.source_date} · {source.fund_code} · collected {source.amount}'


class DepositShareForm(forms.Form):
    receipt = ReceiptChoice(queryset=Source.objects.none())
    amount = forms.DecimalField(max_digits=18,decimal_places=2,min_value=Decimal('.01'),label='Amount in this deposit')

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['receipt'].queryset = visible_sources(user).filter(
            treasury_department=department_for_user(user),kind=Source.RECEIPT,status=Source.POSTED).exclude(proposal__has_key="receiving_bank")
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


DepositShares = forms.formset_factory(DepositShareForm,extra=5,min_num=1,validate_min=True)


@login_required
@require_http_methods(['GET','POST'])
def deposit_create(request):
    require(request.user,'vouchers.prepare_collection_deposits')
    visible_sources(request.user)
    data = request.POST if request.method == 'POST' else None
    form = DepositForm(data)
    shares = DepositShares(data,prefix='shares',form_kwargs={'user':request.user})
    if request.method == 'POST' and form.is_valid() and shares.is_valid():
        values = dict(form.cleaned_data)
        values['receiving_bank_id'] = values['receiving_bank_id'].public_id
        values['allocations'] = [{'receipt':str(row.cleaned_data['receipt'].public_id),
            'amount':row.cleaned_data['amount']} for row in shares if row.cleaned_data]
        try:
            source = record_deposit(actor=request.user,**values)
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect('vouchers:collection_detail',public_id=source.public_id)
    return render(request,'vouchers/collections/form.html',{'form':form,'shares':shares,'title':'Record bank deposit'})


@login_required
@require_http_methods(['GET', 'POST'])
def receipt_create(request):
    require(request.user, 'vouchers.prepare_collections')
    visible_sources(request.user)
    initial = {}
    charge_initial = []
    if request.method == 'GET' and request.GET.get('supersedes'):
        prior = get_object_or_404(visible_sources(request.user).filter(
            Q(status__in=(Source.REJECTED,Source.WITHDRAWN)) | Q(corrections__status=Source.POSTED)).distinct(),
            public_id=request.GET['supersedes'],kind=Source.RECEIPT,treasury_department=department_for_user(request.user))
        initial = {'variant':prior.transaction_variant_id,'received_on':prior.source_date,'fund_code':prior.fund_code,
            'receipt_book':prior.book_reference,'receipt_number':prior.document_reference,'received_amount':prior.amount,
            'payer_reference':prior.proposal['payer_reference'],'evidence_reference':prior.proposal['evidence_reference']}
        initial['receiving_bank_id'] = prior.proposal.get('receiving_bank', {}).get('configuration_item')
        initial['bank_transaction_reference'] = prior.proposal.get('bank_transaction_reference', '')
        for key, value in prior.proposal.get('cheque', {}).items():
            if key != 'identity':
                initial['cheque_' + key] = value
        initial['advance_detail'] = prior.proposal.get('advance_refund', {}).get('original_detail')
        charge_initial = [{'variant':row['variant'],'amount':row['amount']} for row in prior.proposal.get('charges',[])]
    form = ReceiptForm(request.POST or None,initial=initial,user=request.user)
    charge_data = request.POST if request.method == 'POST' and any(key.startswith('charges-') for key in request.POST) else None
    charges = CollectionCharges(charge_data, prefix='charges', initial=charge_initial)
    if request.method == 'POST' and form.is_valid() and (not charges.is_bound or charges.is_valid()):
        values = dict(form.cleaned_data)
        if values.get('receiving_bank_id'):
            values['receiving_bank_id'] = values['receiving_bank_id'].public_id
        cheque = {key: values.pop('cheque_' + key) for key in ('bank','drawer_account','number','drawer','date')}
        if any(cheque.values()):
            values['cheque'] = cheque
        if charges.is_bound:
            values['charges'] = [{'variant':str(row.cleaned_data['variant'].public_id),'amount':row.cleaned_data['amount']}
                for row in charges if row.cleaned_data]
        try:
            source = record_receipt(actor=request.user, **values)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect('vouchers:collection_detail', public_id=source.public_id)
    return render(request, 'vouchers/collections/form.html', {'form':form, 'charges':charges, 'has_charges':bool(charge_initial), 'title':'Record collection receipt'})


def register_rows(user):
    sources = list(visible_sources(user).select_related('prepared_by', 'reviewed_by').prefetch_related('posting_requests'))
    balances = {}
    for treasury_id in {source.treasury_department_id for source in sources}:
        balances.update(remaining_receipts(treasury_id))
    return [{'source':source, 'available':balances.get(str(source.public_id)),
        'journals':list(source.posting_requests.all())} for source in sources]


@login_required
@require_GET
def register(request):
    return render(request, 'vouchers/collections/register.html', {'rows':register_rows(request.user),
        'can_export':has_explicit_permission(request.user,'finance.export_finance_work'),
        'can_deposit':not is_finance_uat_viewer(request.user) and has_explicit_permission(request.user,'vouchers.prepare_collection_deposits'),
        'can_prepare':not is_finance_uat_viewer(request.user) and has_explicit_permission(request.user,'vouchers.prepare_collections')})


@login_required
@require_GET
def detail(request, public_id):
    from accounting.access import can_prepare_journals, can_post_journals
    from finance.cash_flows import CASH_FLOW_CHOICES
    source = get_object_or_404(visible_sources(request.user), public_id=public_id)
    from .cheque_redemptions import settlement, OR_DISPOSITIONS
    from .advance_cheques import settlement as advance_cheque_settlement
    from .cheque_custody import evidence as custody_evidence
    from tracepoint.access import can_resolve_exceptions, packet_is_visible
    custody = None
    custody_links = []
    if source.kind == Source.CHEQUE_RETURN:
        try:
            custody = custody_evidence(source,request.user)
        except PermissionDenied:
            custody = {'restricted':True}
        custody_links = [link for link in source.custody_links.select_related('item__current_packet','linked_by')
            if packet_is_visible(request.user,link.item.current_packet)]
    link_permission = (not is_finance_uat_viewer(request.user)
        and source.treasury_department_id == department_for_user(request.user).pk
        and has_explicit_permission(request.user,'vouchers.link_collection_custody'))
    return render(request, 'vouchers/collections/detail.html', {'source':source,
        'custody':custody, 'custody_links':custody_links,
        'can_link_custody':link_permission and source.kind == Source.CHEQUE_RETURN
            and source.status in (Source.PROPOSED,Source.APPROVED,Source.POSTED),
        'can_withdraw_custody':link_permission and can_resolve_exceptions(request.user,source.treasury_department),
        'old_receipt_label':OR_DISPOSITIONS.get(source.proposal.get('old_receipt_disposition'),''),
        'redemption_receipts':[{'source':row, 'settlement':settlement(row)} for row in source.redemption_receipts.all()],
        'redemption_settlement':settlement(source) if source.redemption_return_id else None,
        'advance_cheque_settlement':advance_cheque_settlement(source),
        'can_redeem':source.kind == Source.CHEQUE_RETURN and source.status == Source.POSTED
            and not is_finance_uat_viewer(request.user) and source.treasury_department_id == department_for_user(request.user).pk
            and has_explicit_permission(request.user,'vouchers.prepare_collections'),
        'return_financial_rows':[{**row, 'purpose_label':dict(CASH_FLOW_CHOICES).get(row.get('cash_flow_category',''), '')}
            for row in source.proposal.get('financial_rows', [])] if source.kind == Source.CHEQUE_RETURN or source.redemption_return_id else [],
        'clearances':source.cheque_clearances.all(),
        'cheque_returns':source.cheque_returns.all(),
        'can_clear_cheque':source.status == Source.POSTED and bool(source.proposal.get('cheque'))
            and not is_finance_uat_viewer(request.user)
            and source.treasury_department_id == department_for_user(request.user).pk
            and has_explicit_permission(request.user,'vouchers.prepare_collections'),
        'can_review_clearing':not is_finance_uat_viewer(request.user)
            and source.finance_department_id == department_for_user(request.user).pk
            and has_explicit_permission(request.user,'vouchers.review_collections'),
        'journals':source.posting_requests.all(),
        'outputs':source.issued_outputs.all(),
        'can_output':has_explicit_permission(request.user,'finance.export_finance_work'),
        'can_materialize':source.status == Source.APPROVED and can_prepare_journals(request.user)
            and department_for_user(request.user).pk == source.finance_department_id,
        'can_reconcile':source.status == Source.APPROVED and can_post_journals(request.user)
            and department_for_user(request.user).pk == source.finance_department_id,
        'can_withdraw':source.status == Source.APPROVED and not is_finance_uat_viewer(request.user)
            and department_for_user(request.user).pk == source.finance_department_id
            and source.prepared_by_id != request.user.pk
            and has_explicit_permission(request.user,'vouchers.review_collections'),
        'can_correct':source.status == Source.POSTED and source.kind in (Source.RECEIPT,Source.DEPOSIT,Source.CHEQUE_RETURN)
            and not source.corrections.filter(status__in=(Source.PROPOSED,Source.APPROVED,Source.POSTED)).exists()
            and not is_finance_uat_viewer(request.user) and source.treasury_department_id == department_for_user(request.user).pk
            and has_explicit_permission(request.user,'vouchers.prepare_collections' if source.kind == Source.RECEIPT else 'vouchers.prepare_collection_deposits'),
        'can_replace':source.kind in (Source.RECEIPT,Source.DEPOSIT) and not source.redemption_return_id
            and (source.status in (Source.REJECTED,Source.WITHDRAWN) or source.corrections.filter(status=Source.POSTED).exists())
            and not is_finance_uat_viewer(request.user)
            and source.treasury_department_id == department_for_user(request.user).pk
            and has_explicit_permission(request.user,'vouchers.prepare_collections' if source.kind == Source.RECEIPT else 'vouchers.prepare_collection_deposits'),
        'can_review':not is_finance_uat_viewer(request.user) and source.status == Source.PROPOSED
            and source.prepared_by_id != request.user.pk
            and department_for_user(request.user).pk == source.finance_department_id
            and has_explicit_permission(request.user,'vouchers.review_collections')})


@login_required
@require_POST
def review(request, public_id):
    from .collection_posting import review_source, withdraw_unposted
    source = get_object_or_404(visible_sources(request.user), public_id=public_id)
    form = forms.Form(request.POST)
    form.fields['decision'] = forms.ChoiceField(choices=(('approve','Approve'),('reject','Return for correction'),('withdraw','Withdraw unposted approval')))
    form.fields['reason'] = forms.CharField(widget=forms.Textarea)
    if form.is_valid():
        try:
            if form.cleaned_data['decision'] == 'withdraw':
                withdraw_unposted(source=source,actor=request.user,reason=form.cleaned_data['reason'])
            else:
                review_source(source=source, actor=request.user, approve=form.cleaned_data['decision']=='approve',
                    reason=form.cleaned_data['reason'])
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect('vouchers:collection_detail',public_id=source.public_id)
    return render(request,'vouchers/collections/form.html',{'form':form,'title':'Review collection / deposit'})


@login_required
@require_http_methods(['GET','POST'])
def correction_create(request, public_id):
    from .collection_corrections import propose
    original=get_object_or_404(visible_sources(request.user),public_id=public_id,kind__in=(Source.RECEIPT,Source.DEPOSIT,Source.CHEQUE_RETURN))
    office=require(request.user,'vouchers.prepare_collections' if original.kind == Source.RECEIPT else 'vouchers.prepare_collection_deposits')
    if office.pk != original.treasury_department_id:
        raise PermissionDenied
    form=forms.Form(request.POST if request.method == 'POST' else None)
    form.fields['corrected_on']=forms.DateField(label='Correction date',widget=forms.DateInput(attrs={'type':'date','class':'form-control'}))
    form.fields['reason']=forms.CharField(label='Posted error and correction basis',widget=forms.Textarea(attrs={'class':'form-control'}))
    if request.method == 'POST' and form.is_valid():
        try:
            source=propose(original=original,actor=request.user,**form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect('vouchers:collection_detail',public_id=source.public_id)
    return render(request,'vouchers/collections/form.html',{'form':form,'title':f'Correct posted {original.document_reference}'})


@login_required
@require_POST
def accounting_action(request, public_id, action):
    from accounting.models import JournalEntry
    from .collection_posting import materialize, reconcile
    source = get_object_or_404(visible_sources(request.user),public_id=public_id)
    posting = get_object_or_404(source.posting_requests.exclude(status='cancelled').order_by('-version'))
    try:
        if action == 'materialize':
            entry,_ = materialize(posting,request.user)
            return redirect('accounting:entry_detail',public_id=entry.public_id)
        if action != 'reconcile':
            raise PermissionDenied
        entry = get_object_or_404(JournalEntry,public_id=posting.accounting_entry_public_id)
        reconcile(entry,request.user)
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages))
    return redirect('vouchers:collection_detail',public_id=source.public_id)


@login_required
@require_GET
def export(request):
    # Download authority is separate from read access, including for UAT viewers.
    if not has_explicit_permission(request.user, 'finance.export_finance_work'):
        raise PermissionDenied
    from .views import _safe_writerow
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="collection-deposit-register.csv"'
    writer = csv.writer(response)
    _safe_writerow(writer, ['Kind','Date','Book','Reference','Version','Fund','Amount','Status',
        'Available for deposit (after pending allocations)','Prepared by','Reviewed by','JEVs',
        'Withdrawal reason','Withdrawn by','Withdrawn at','Original advance JEV','Officer advance identity',
        'Receiving bank','Bank credit reference','Cheque bank','Cheque number','Cheque date','Cheque drawer',
        'Cheque clearing history','Original returned receipt','Original returned deposit','Return applicability','Bank return history'])
    for row in register_rows(request.user):
        source = row['source']
        from .cheque_clearing import output_evidence
        clearing_history = output_evidence(source) if source.proposal.get('cheque') else []
        from .cheque_returns import history
        return_history = history(source)
        from .advance_refunds import evidence as officer_evidence
        refund = officer_evidence(source) or {}
        _safe_writerow(writer, [source.get_kind_display(),source.source_date,source.book_reference,
            source.document_reference,source.version,source.fund_code,source.amount,source.get_status_display(),
            row['available'],source.prepared_by.get_username(),
            source.reviewed_by.get_username() if source.reviewed_by else '',
            '; '.join(r.jev_number for r in row['journals']),source.withdrawal_reason,
            source.withdrawn_by.get_username() if source.withdrawn_by else '',source.withdrawn_at,
            refund.get('original_jev_number',''),refund.get('officer_key',''),
            source.proposal.get('receiving_bank',{}).get('bank_label',''),
            source.proposal.get('bank_transaction_reference',''),
            source.proposal.get('cheque',{}).get('bank',''),source.proposal.get('cheque',{}).get('number',''),
            source.proposal.get('cheque',{}).get('date',''),source.proposal.get('cheque',{}).get('drawer',''),
            '; '.join(f"v{item['version']} {item['status']} {item['date']} {item['bank_reference']} [{item['checksum']}]"
                for item in clearing_history),
            source.proposal.get('original_cheque',{}).get('receipt',''),
            source.proposal.get('original_cheque',{}).get('deposit',''),
            source.proposal.get('applicability_reference',''),
            '; '.join(f"{item['reference']} {item['date']} {item['amount']} {item['status']} [{item['checksum']}]" for item in return_history)])
    return response


@login_required
@require_POST
def output_generate(request, public_id):
    from .collection_outputs import generate
    source=get_object_or_404(visible_sources(request.user),public_id=public_id)
    try:
        output=generate(source=source,actor=request.user,include_custody=request.POST.get('include_custody') == 'on')
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages))
        return redirect('vouchers:collection_detail',public_id=source.public_id)
    return redirect('vouchers:collection_output_download',public_id=source.public_id,output_id=output.public_id)


@login_required
@require_GET
def output_download(request, public_id, output_id):
    from .collection_outputs import content
    source=get_object_or_404(visible_sources(request.user),public_id=public_id)
    output=get_object_or_404(source.issued_outputs,public_id=output_id)
    try:
        response=HttpResponse(content(output,request.user),content_type='text/html; charset=utf-8')
    except ValidationError as exc:
        return HttpResponse(' '.join(exc.messages),status=409,content_type='text/plain; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="collection-{source.public_id}-v{output.version}.html"'
    response['Content-Security-Policy']="sandbox; default-src 'none'; style-src 'unsafe-inline'"
    return response
