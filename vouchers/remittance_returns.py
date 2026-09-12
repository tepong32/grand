"""Actual remittance receipts over explicit immutable original liability lines."""
from copy import copy, deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.models import JournalEntry, JournalLine, JournalSubsidiaryLine, AccountingPeriod
from accounting.posted_evidence import verify_source_link
from .models import RemittanceReturn, RemittancePostingRequest, TreasuryRemittanceBatch
from .remittances import _require, _require_treasury_scope, require_remittance_review_scope, _digest, _event, _consume_number


def original_payment(batch):
    requests = [r for r in batch.posting_requests.filter(status=RemittancePostingRequest.POSTED)
        if not r.payload.get('remittance_return')]
    if batch.status != batch.COMPLETED or len(requests) != 1:
        raise ValidationError('Reconcile the one original posted remittance before recording a return.')
    source = requests[0]
    entry = JournalEntry.objects.get(public_id=source.accounting_entry_public_id)
    verify_source_link(source, entry, source_type='remittance')
    if (entry.status != entry.POSTED or not entry.posted_by_id or not entry.posted_at
            or entry.created_by_id == entry.posted_by_id
            or not entry.audit_events.filter(action='posted', actor_id=entry.posted_by_id).exists()
            or entry.reversal_entries.exclude(status=entry.VOIDED).exists()):
        raise ValidationError('The original remittance must retain independent posting without a detached reversal.')
    details = list(entry.subsidiary_lines.select_related('journal_line__account').order_by('pk'))
    bank = list(entry.lines.exclude(pk__in=[d.journal_line_id for d in details]))
    if (not details or len(bank) != 1 or bank[0].debit or bank[0].credit != batch.total_amount
            or bank[0].account.account_type != 'asset'
            or any(d.category != d.WITHHOLDING or d.debit <= 0 or d.credit
                or d.journal_line.debit != d.debit or d.journal_line.credit for d in details)
            or sum((d.debit for d in details), Decimal('0')) != batch.total_amount):
        raise ValidationError('Retain the original bank credit and exact withholding debit allocations.')
    return source, entry, details, bank[0]


def remaining_allocations(batch, details, *, exclude=None, as_of=None):
    remaining = {str(d.pk): d.debit for d in details}
    for item in batch.returns.exclude(status__in=(RemittanceReturn.REJECTED, RemittanceReturn.WITHDRAWN)).exclude(pk=exclude):
        if _digest(item.proposal) != item.proposal_checksum:
            raise ValidationError('The retained return allocation checksum changed.')
        if item.status == item.CORRECTED:
            correction = item.corrections.filter(status='posted').get()
            if as_of is None or date.fromisoformat(correction.proposal['correction_date']) <= as_of:
                continue
        for row in item.proposal['allocations']:
            remaining[row['source_detail']] -= Decimal(row['amount'])
    return remaining


def filing_snapshot(batch):
    return list(batch.tax_filing_evidence.order_by('version').values(
        'public_id', 'version', 'status', 'evidence_checksum', 'state_version'))


def pending_receipt_holds(department_id, transaction_type, as_of_date):
    """Posted incoming money becomes usable after its default-store handoff."""
    holds = {}
    for item in RemittanceReturn.objects.filter(status=RemittanceReturn.APPROVED,
            batch__finance_department_id=department_id, batch__transaction_variant__code=transaction_type).select_related('posting_request'):
        request = item.posting_request
        if request is None:
            raise ValidationError('An approved return is missing its retained posting request.')
        entry = JournalEntry.objects.filter(source_type='remittance', source_reference=str(request.public_id),
            status=JournalEntry.POSTED, entry_date__lte=as_of_date).first()
        if entry is None:
            continue
        verify_source_link(request, entry, source_type='remittance')
        for row in item.proposal['allocations']:
            detail = JournalSubsidiaryLine.objects.select_related('entry__fund', 'journal_line__account').get(pk=row['source_detail'])
            key = (detail.entry.fund.code, detail.journal_line.account.code, detail.reference_key, detail.source_code)
            holds[key] = holds.get(key, Decimal('0')) + Decimal(row['amount'])
    return holds


@transaction.atomic
def propose_return(*, batch, actor, returned_on, receipt_reference, reason, filing_basis, allocations, expected_version, receiving_bank_id=None):
    _require(actor, 'vouchers.prepare_remittances')
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=batch.pk)
    _require_treasury_scope(actor, batch)
    if batch.state_version != expected_version:
        raise ValidationError('The remittance changed. Reload before recording the return.')
    source, entry, details, bank = original_payment(batch)
    if not isinstance(returned_on, date) or returned_on < entry.entry_date or returned_on > timezone.localdate():
        raise ValidationError('Use the actual receipt date, on or after the remittance and no later than today.')
    if not all(str(value or '').strip() for value in (receipt_reference, reason, filing_basis)):
        raise ValidationError('Record the actual bank/recipient receipt, return reason and tax-filing disposition basis.')
    remaining = remaining_allocations(batch, details, as_of=returned_on)
    rows = []
    seen = set()
    for supplied in allocations:
        key = str(supplied['source_detail'])
        try:
            amount = Decimal(str(supplied['amount']))
        except (InvalidOperation, ValueError):
            raise ValidationError('Enter a valid return allocation amount.')
        if (key in seen or key not in remaining or not amount.is_finite() or amount <= 0
                or amount > remaining[key] or amount != amount.quantize(Decimal('.01'))):
            raise ValidationError('Each explicit return share must fit its unreturned original liability line.')
        seen.add(key)
        rows.append({'source_detail': key, 'amount': str(amount)})
    if not rows:
        raise ValidationError('Allocate the actual received amount to original liability lines.')
    proposal = {'original_request': str(source.public_id), 'original_entry': str(entry.public_id),
        'original_payload_checksum': source.payload_checksum, 'original_rule_checksum': source.posting_rule_checksum,
        'bank_line': bank.pk, 'returned_on': returned_on.isoformat(), 'receipt_reference': receipt_reference.strip(),
        'reason': reason.strip(), 'filing_basis': filing_basis.strip(),
        'filing_evidence': [{**r, 'public_id': str(r['public_id'])} for r in filing_snapshot(batch)],
        'allocations': sorted(rows, key=lambda r: int(r['source_detail'])),
        'amount': str(sum((Decimal(r['amount']) for r in rows), Decimal('0')))}
    if receiving_bank_id:
        from .receipt_banks import bank_snapshot
        proposal['receiving_bank'] = bank_snapshot(batch, receiving_bank_id, returned_on)
    item = RemittanceReturn.objects.create(batch=batch,
        version=(batch.returns.aggregate(v=Max('version'))['v'] or 0) + 1,
        proposal=proposal, proposal_checksum=_digest(proposal), prepared_by=actor)
    batch.state_version += 1
    batch.save(update_fields=('state_version', 'updated_at'))
    _event(batch, actor, 'remittance_return_proposed', batch.status, reason,
        {'return': str(item.public_id), 'proposal_checksum': item.proposal_checksum})
    return item


@transaction.atomic
def materialize_return(request, actor):
    from accounting.access import can_prepare_journals, department_for_user
    if not can_prepare_journals(actor) or department_for_user(actor).pk != request.finance_department_id:
        raise PermissionDenied
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=request.batch_id)
    request = RemittancePostingRequest.objects.select_for_update().get(pk=request.pk)
    item = RemittanceReturn.objects.select_for_update().get(posting_request=request)
    retained = request.payload['remittance_return']
    if (request.status not in (request.PENDING, request.FAILED, request.MATERIALIZED)
            or item.status != item.APPROVED or _digest(request.payload) != request.payload_checksum
            or _digest(item.proposal) != item.proposal_checksum
            or retained['proposal_checksum'] != item.proposal_checksum
            or retained['reviewed_by'] != item.reviewed_by_id or item.reviewed_by_id == item.prepared_by_id
            or any(retained.get(k) != v for k, v in item.proposal.items())):
        raise ValidationError('Retain the approved return, exact allocations and independent review.')
    source, original, details, bank = original_payment(batch)
    if (str(source.public_id) != retained['original_request'] or str(original.public_id) != retained['original_entry']
            or source.payload_checksum != retained['original_payload_checksum']
            or source.posting_rule_checksum != retained['original_rule_checksum'] or bank.pk != retained['bank_line']):
        raise ValidationError('The return differs from its retained original payment.')
    with transaction.atomic(using='finance'):
        original = JournalEntry.objects.select_for_update().get(pk=original.pk)
        existing = JournalEntry.objects.filter(source_type='remittance', source_reference=str(request.public_id)).first()
        if existing:
            verify_source_link(request, existing, source_type='remittance')
            if existing.status == existing.VOIDED:
                raise ValidationError('The return draft was discarded; resolve its retained request before retrying.')
            entry, created = existing, False
        else:
            if original.reversal_entries.exclude(status=original.VOIDED).exists():
                raise ValidationError('Resolve the original payment reversal before recording a return.')
            period = AccountingPeriod.objects.get(department_id=request.finance_department_id,
                status=AccountingPeriod.OPEN, starts_on__lte=request.jev_date, ends_on__gte=request.jev_date)
            entry = JournalEntry(department_id=original.department_id, department_label=original.department_label,
                reference=request.jev_number, entry_date=request.jev_date, period=period, fund=original.fund,
                source_type='remittance', source_reference=str(request.public_id),
                source_snapshot={'remittance_batch': str(batch.public_id), 'payload_checksum': request.payload_checksum,
                    'posting_rule_checksum': request.posting_rule_checksum, 'remittance_return': retained},
                description=f'Return of {batch.reference_code}: {retained["reason"]}',
                created_by_id=actor.pk, created_by_label=actor.get_full_name() or actor.username)
            entry.full_clean(); entry.save()
            from .receipt_banks import receiving_account
            account = receiving_account(batch, retained.get('receiving_bank'), bank)
            cash = JournalLine(entry=entry, sequence=1, account=account, debit=Decimal(retained['amount']),
                credit=0, cash_flow_category=bank.cash_flow_category, memo=f'Return of remittance {batch.reference_code}')
            cash.full_clean(); cash.save()
            originals = {str(d.pk): d for d in details}
            for sequence, row in enumerate(retained['allocations'], start=2):
                detail = originals[row['source_detail']]
                line = JournalLine(entry=entry, sequence=sequence, account=detail.journal_line.account,
                    debit=0, credit=Decimal(row['amount']), memo=detail.reference_label)
                line.full_clean(); line.save()
                restored = JournalSubsidiaryLine(entry=entry, journal_line=line, category=detail.category,
                    reference_key=detail.reference_key, reference_label=detail.reference_label,
                    source_code=detail.source_code, source_reference=str(request.public_id), debit=0, credit=line.credit,
                    source_snapshot={**detail.source_snapshot, 'return_of_subsidiary_line': detail.pk,
                        'remittance_return': str(item.public_id)})
                restored.full_clean(); restored.save()
            from accounting.services import record_event
            record_event(entry, 'remittance_return_materialized', actor,
                snapshot={'original_entry': str(original.public_id), 'proposal_checksum': item.proposal_checksum})
            created = True
    request.status, request.accounting_entry_public_id = request.MATERIALIZED, entry.public_id
    request.materialized_at, request.failure_reason = timezone.now(), ''
    request.save()
    return entry, created


@transaction.atomic
def reconcile_return(entry, actor):
    from accounting.posted_evidence import require_persisted_posting
    entry = require_persisted_posting(entry, actor, source_type='remittance')
    source = RemittancePostingRequest.objects.get(public_id=entry.source_reference)
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=source.batch_id)
    source = RemittancePostingRequest.objects.select_for_update().get(pk=source.pk)
    item = RemittanceReturn.objects.select_for_update().get(posting_request=source)
    verify_source_link(source, entry, source_type='remittance')
    if source.status == source.POSTED and item.status in (item.POSTED, item.CORRECTED):
        return source
    if item.status != item.APPROVED or entry.source_snapshot.get('remittance_return') != source.payload['remittance_return']:
        raise ValidationError('The posted return differs from its approved incoming payment evidence.')
    source.status, source.posted_at = source.POSTED, entry.posted_at
    source.accounting_entry_public_id, source.failure_reason = entry.public_id, ''
    source.save()
    item.status = item.POSTED
    item.save(update_fields=('status',))
    _event(batch, actor, 'remittance_return_posted', batch.status,
        item.proposal['reason'], {'return': str(item.public_id), 'entry': str(entry.public_id),
            'amount': item.proposal['amount'], 'receipt_reference': item.proposal['receipt_reference']})
    return source


def export_returns(batch, actor):
    import csv
    import io
    from src.export_archive import archive_export
    _require(actor, 'vouchers.view_remittance_workbench')
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(('original_remittance', 'return_version', 'status', 'receipt_date', 'receipt_reference',
        'liability_account', 'reference', 'deduction_code', 'allocated_receipt', 'posted_receipt',
        'original_jev', 'return_jev', 'return_jev_status', 'filing_disposition_basis', 'review_reason',
        'withdrawal_reason', 'withdrawn_by', 'withdrawn_at', 'original_bank_ledger', 'receiving_bank', 'receiving_bank_ledger'))
    withdrawals = {event.metadata.get('return'): event for event in
        batch.events.filter(action='remittance_return_withdrawn').select_related('actor')}
    for item in batch.returns.select_related('posting_request').order_by('version'):
        if _digest(item.proposal) != item.proposal_checksum:
            raise ValidationError('The retained return proposal checksum changed.')
        original = JournalEntry.objects.get(public_id=item.proposal['original_entry'])
        request = item.posting_request
        withdrawal = withdrawals.get(str(item.public_id))
        original_bank = original.lines.select_related('account').get(pk=item.proposal['bank_line'])
        receiving_bank = item.proposal.get('receiving_bank') or {}
        for row in item.proposal['allocations']:
            detail = original.subsidiary_lines.select_related('journal_line__account').get(pk=row['source_detail'])
            writer.writerow((batch.reference_code, item.version, item.get_status_display(),
                item.proposal['returned_on'], item.proposal['receipt_reference'], detail.journal_line.account.code,
                detail.reference_key, detail.source_code, row['amount'], row['amount'] if item.status in (item.POSTED, item.CORRECTED) else '0.00',
                original.reference, request.jev_number if request else '', request.get_status_display() if request else '',
                item.proposal['filing_basis'], item.review_reason,
                withdrawal.reason if withdrawal else '', withdrawal.actor_id if withdrawal else '',
                withdrawal.created_at.isoformat() if withdrawal else '', original_bank.account.code,
                receiving_bank.get('bank_code', batch.bank_account_code),
                receiving_bank.get('ledger_account_code', original_bank.account.code)))
    content = output.getvalue().encode('utf-8-sig')
    return content, archive_export(content=content, department=batch.treasury_department, user=actor,
        category='finance-remittance-returns', filename=f'{batch.reference_code}-returns.csv',
        metadata={'remittance_public_id': str(batch.public_id)})


@transaction.atomic
def review_return(*, item, actor, approve, reason):
    _require(actor, 'vouchers.approve_remittances')
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=item.batch_id)
    item = RemittanceReturn.objects.select_for_update().get(pk=item.pk)
    require_remittance_review_scope(actor, batch)
    if item.status != item.PROPOSED or item.prepared_by_id == actor.pk or not reason.strip():
        raise ValidationError('An independent reviewer must decide the pending return with a retained basis.')
    if _digest(item.proposal) != item.proposal_checksum:
        raise ValidationError('The immutable return proposal no longer reproduces.')
    if approve:
        source, entry, details, bank = original_payment(batch)
        if item.proposal.get('receiving_bank'):
            from .receipt_banks import bank_snapshot
            retained_bank = item.proposal['receiving_bank']
            if bank_snapshot(batch, retained_bank['configuration_item'], date.fromisoformat(item.proposal['returned_on'])) != retained_bank:
                raise ValidationError('The receiving bank mapping changed. Return this proposal and prepare a current successor.')
        current = [{**r, 'public_id': str(r['public_id'])} for r in filing_snapshot(batch)]
        if current != item.proposal['filing_evidence']:
            raise ValidationError('Filing evidence changed. Return this proposal and prepare a current successor.')
        remaining = remaining_allocations(batch, details, exclude=item.pk, as_of=date.fromisoformat(item.proposal['returned_on']))
        if any(Decimal(r['amount']) > remaining[r['source_detail']] for r in item.proposal['allocations']):
            raise ValidationError('The proposed amount no longer fits the retained original allocations.')
        numbering = copy(batch)
        numbering.remittance_date = date.fromisoformat(item.proposal['returned_on'])
        number = _consume_number(numbering, actor, 'journal-entry', f'remittance-return-{item.version}')
        payload = deepcopy(source.payload)
        payload.update(event_amount=item.proposal['amount'], remittance_return={
            **item.proposal, 'return': str(item.public_id), 'proposal_checksum': item.proposal_checksum,
            'reviewed_by': actor.pk, 'review_reason': reason.strip()})
        request = RemittancePostingRequest(batch=batch,
            version=(batch.posting_requests.aggregate(v=Max('version'))['v'] or 0) + 1,
            jev_number=number, jev_date=numbering.remittance_date, finance_department_id=source.finance_department_id,
            finance_department_label=source.finance_department_label, posting_rule=source.posting_rule,
            posting_rule_snapshot=source.posting_rule_snapshot, posting_rule_checksum=source.posting_rule_checksum,
            payload=payload, payload_checksum=_digest(payload), requested_by=actor)
        request.full_clean(); request.save()
        item.posting_request = request
    item.status = item.APPROVED if approve else item.REJECTED
    item.reviewed_by, item.reviewed_at, item.review_reason = actor, timezone.now(), reason.strip()
    item.save()
    _event(batch, actor, 'remittance_return_approved' if approve else 'remittance_return_rejected', batch.status,
        reason, {'return': str(item.public_id), 'proposal_checksum': item.proposal_checksum})
    return item
