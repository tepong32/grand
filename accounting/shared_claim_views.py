"""Ordinary entry and independent review of a complete historical schedule."""
import json

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .access import accounting_access_required, can_prepare_journals, can_post_journals, department_for_user
from .claim_views import AttributionForm, InvoiceAllocationForm
from . import claim_attributions as history
from .cash_classifications import checksum
from .models import JournalEntry, JournalLine, SharedPayableClaimProposal as Proposal
from .shared_claim_proposals import propose, review


def label(line):
    return f'{line.entry.reference} / line {line.sequence} · {line.entry.entry_date} · debit {line.debit:,.2f} / credit {line.credit:,.2f}'


class ScheduleForm(forms.Form):
    sources = forms.ModelMultipleChoiceField(queryset=JournalLine.objects.none(), label='Original liability credits',
        widget=forms.SelectMultiple(attrs={'size': 8}), help_text='Select at least two credits. Hold Ctrl or Command to select several entries.')
    applications = forms.ModelMultipleChoiceField(queryset=JournalLine.objects.none(), required=False,
        label='Earlier payments, deductions and their reversals', widget=forms.SelectMultiple(attrs={'size': 8}))
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    expected_approvals = forms.JSONField(widget=forms.HiddenInput)
    evidence_reference = forms.CharField(max_length=255, label='Supporting reconciliation schedule / documents')
    reason = forms.CharField(label='Basis and explanation', widget=forms.Textarea(attrs={'rows': 3}))
    complete_history = forms.BooleanField(label='I checked every selected credit and included all earlier applications and reversals.')

    def __init__(self, *args, source, preparing_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.source = source
        if preparing_only:
            for name in ('evidence_reference', 'reason', 'complete_history'):
                self.fields[name].required = False
        common = JournalLine.objects.filter(entry__department_id=source.entry.department_id,
            entry__fund_id=source.entry.fund_id, account_id=source.account_id, entry__status=JournalEntry.POSTED,
            payable_origin__isnull=True, payable_reservation__isnull=True, payable_allocation={},
            payable_party_key='', payable_claim_reference='').exclude(entry__source_type__in=('voucher', 'remittance'))
        self.fields['sources'].queryset = common.filter(credit__gt=0, debit=0, entry__reversal_of__isnull=True).select_related('entry').order_by('pk')
        self.fields['applications'].queryset = common.exclude(credit__gt=0, entry__reversal_of__isnull=True).select_related('entry').order_by('entry__entry_date', 'pk')
        for name, field in self.fields.items():
            if name != 'complete_history':
                field.widget.attrs['class'] = 'form-control'
            if name in ('sources', 'applications'):
                field.label_from_instance = label
                field.widget.attrs['size'] = min(8, max(3, field.queryset.count()))

    def clean_sources(self):
        sources = self.cleaned_data['sources']
        if not 2 <= len(sources) <= 100 or self.source.pk not in {line.pk for line in sources}:
            raise ValidationError('Include this original credit and at least one other credit, up to 100.')
        return sources


class SharedInvoiceForm(InvoiceAllocationForm):
    source = forms.ModelChoiceField(queryset=JournalLine.objects.none(), label='Original credit')

    def __init__(self, *args, sources, preparing_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source'].queryset = sources
        self.fields['source'].label_from_instance = label
        self.fields['source'].widget.attrs.update({'class': 'form-control', 'style': 'min-width: 22rem;'})
        self.order_fields(['source', 'key', 'party_key', 'claim_reference', 'recognized'])
        if preparing_only:
            for field in self.fields.values():
                field.required = False


@require_http_methods(['GET', 'POST'])
@accounting_access_required
def schedule_page(request, line_id):
    source = get_object_or_404(JournalLine.objects.select_related('entry__fund', 'account'), pk=line_id,
        entry__department_id=department_for_user(request.user).pk)
    can_prepare = can_prepare_journals(request.user) and source.entry.status == JournalEntry.POSTED
    if request.method == 'POST' and not can_prepare:
        raise PermissionDenied
    seed = next((record for record in Proposal.objects.filter(department_id=source.entry.department_id,
        fund_id=source.entry.fund_id).order_by('-pk') if source.pk in record.source_ids), None)
    posted = request.POST.copy() if request.method == 'POST' else None
    form = ScheduleForm(posted, source=source)
    ids = posted.getlist('sources') if posted is not None else (seed.source_ids if seed else [source.pk])
    ids = [int(pk) for pk in ids if str(pk).isdigit()]
    sources = form.fields['sources'].queryset.filter(pk__in=ids)
    source_ids = list(sources.values_list('pk', flat=True))
    applications = posted.getlist('applications') if posted is not None else (seed.application_ids if seed else [])
    applications = [int(pk) for pk in applications if str(pk).isdigit()]
    lines = list(form.fields['applications'].queryset.filter(pk__in=applications).exclude(pk__in=source_ids))
    cohort = checksum(source_ids)
    records = list(Proposal.objects.filter(department_id=source.entry.department_id, fund_id=source.entry.fund_id,
        source_set_checksum=cohort).order_by('-version'))
    latest = records[0] if records else None
    current_records = {line.pk: history.current(line) for line in sources}
    versions = {str(pk): record.version if record else 0 for pk, record in current_records.items()}
    initial = dict(sources=source_ids, applications=applications, expected_approvals=versions,
        expected_version=latest.version if latest else 0,
        evidence_reference=latest.evidence_reference if latest else '', reason=latest.reason if latest else '')
    parties = list(AttributionForm(source=source).fields['party_key'].choices)
    invoice_initial = []
    if latest:
        for member in latest.allocations:
            for row in member['invoices']:
                invoice_initial.append({'source': member['source_id'], **{name: row[name] for name in
                    ('key', 'party_key', 'claim_reference', 'recognized')},
                    **{f'share_{pk}': amount for pk, amount in row['applications'].items()}})
                if row['party_key'] not in dict(parties):
                    parties.append((row['party_key'], row['party_key']))
    if posted is not None and posted.get('action') == 'refresh':
        posted['expected_version'] = str(initial['expected_version'])
        posted['expected_approvals'] = json.dumps(versions)
    if posted is not None and posted.get('action') == 'add_invoice':
        try:
            posted['invoices-TOTAL_FORMS'] = str(min(100, max(0, int(posted.get('invoices-TOTAL_FORMS', '0'))) + 1))
        except ValueError:
            pass
    preparing_only = posted is not None and posted.get('action') in ('refresh', 'add_invoice')
    form = ScheduleForm(posted, source=source, initial=initial, preparing_only=preparing_only)
    factory = forms.formset_factory(SharedInvoiceForm, extra=max(0, 2-len(invoice_initial)), can_delete=True,
        max_num=100, validate_max=True, absolute_max=100)
    invoices = factory(posted, initial=invoice_initial, prefix='invoices',
        form_kwargs={'sources': sources, 'parties': parties, 'applications': lines, 'preparing_only': preparing_only})
    if posted is not None and posted.get('action', 'submit') == 'submit' and form.is_valid() and invoices.is_valid():
        data = dict(form.cleaned_data)
        data.pop('complete_history')
        selected_sources = list(data.pop('sources'))
        grouped = {line.pk: [] for line in selected_sources}
        for invoice in invoices:
            if invoice.cleaned_data and not invoice.cleaned_data.get('DELETE'):
                grouped[invoice.cleaned_data['source'].pk].append(invoice.allocation())
        try:
            propose(actor=request.user, source_ids=list(grouped),
                application_ids=[line.pk for line in data.pop('applications')],
                rows=[{'source_id': pk, 'invoices': rows} for pk, rows in grouped.items()], **data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Complete shared schedule submitted for independent review.')
            return redirect('accounting:shared_claim_schedule', line_id=source.pk)
    by_id = {line.pk: line for line in JournalLine.objects.filter(pk__in={pk for record in records
        for pk in [*record.source_ids, *record.application_ids]}).select_related('entry')}
    displayed = []
    for record in records:
        decision = record.attributions.order_by('source_id').first()
        rows = [{'source': by_id[member['source_id']], **row, 'payee_label': dict(parties).get(row['party_key'], row['party_key']),
            'shares': [{'line': by_id[int(pk)], 'amount': value} for pk, value in row['applications'].items()]}
            for member in record.allocations for row in member['invoices']]
        displayed.append({'record': record, 'decision': decision, 'rows': rows,
            'is_latest': record.pk == latest.pk,
            'is_current': all(current_records.get(pk) and current_records[pk].shared_proposal_id == record.pk for pk in record.source_ids),
            'can_review': decision is None and can_post_journals(request.user) and record.proposed_by_id != request.user.pk})
    return render(request, 'accounting/shared_claim_schedule.html', {'source': source, 'form': form,
        'invoices': invoices, 'can_prepare': can_prepare, 'records': displayed})


@require_POST
@accounting_access_required
def schedule_review(request, line_id, public_id, decision):
    record = get_object_or_404(Proposal, public_id=public_id, department_id=department_for_user(request.user).pk)
    if line_id not in record.source_ids or decision not in ('approve', 'return'):
        raise PermissionDenied
    try:
        review(record, request.user, approve=decision == 'approve', note=request.POST.get('note', ''))
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    else:
        messages.success(request, 'Shared schedule approved.' if decision == 'approve' else 'Shared schedule returned for correction.')
    return redirect('accounting:shared_claim_schedule', line_id=line_id)
