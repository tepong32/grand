"""Retained exact reversals of incorrectly posted remittance receipts."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.models import AccountingPeriod, JournalEntry, JournalLine, JournalSubsidiaryLine
from accounting.posted_evidence import verify_source_link, require_persisted_posting
from .models import RemittanceReturn, RemittanceReturnCorrection as Correction, RemittancePostingRequest, TreasuryRemittanceBatch
from .remittances import _require, _require_treasury_scope, require_remittance_review_scope, _digest, _event, _consume_number
from .remittance_returns import filing_snapshot
from .deduction_corrections import lock_withholding_scope


def financial_rows(entry, *, reverse=False):
    rows = []
    for line in entry.lines.order_by('sequence', 'pk'):
        details = list(JournalSubsidiaryLine.objects.filter(journal_line=line).order_by('pk'))
        rows.append({'sequence': line.sequence, 'account': line.account_id,
            'center': line.responsibility_center_id, 'cash': line.cash_flow_category,
            'debit': str(line.credit if reverse else line.debit), 'credit': str(line.debit if reverse else line.credit),
            'details': [{'category': d.category, 'key': d.reference_key, 'code': d.source_code,
                'debit': str(d.credit if reverse else d.debit), 'credit': str(d.debit if reverse else d.credit),
                'transaction_type': d.source_snapshot.get('transaction_type', '')} for d in details]})
    return rows


def receipt_source(receipt):
    source = receipt.posting_request
    if receipt.status != receipt.POSTED or source is None or source.status != source.POSTED:
        raise ValidationError('Reconcile the original posted receipt before requesting its correction.')
    entry = JournalEntry.objects.get(public_id=source.accounting_entry_public_id)
    verify_source_link(source, entry, source_type='remittance')
    if (entry.status != entry.POSTED or not entry.posted_by_id or not entry.posted_at
            or entry.posted_by_id == entry.created_by_id
            or not entry.audit_events.filter(action='posted', actor_id=entry.posted_by_id).exists()
            or _digest(receipt.proposal) != receipt.proposal_checksum):
        raise ValidationError('Retain the independently posted receipt and its immutable proposal.')
    return source, entry


def pending_holds(department_id, transaction_type):
    holds = {}
    for item in Correction.objects.filter(status__in=(Correction.PROPOSED, Correction.APPROVED),
            receipt__batch__finance_department_id=department_id,
            receipt__batch__transaction_variant__code=transaction_type):
        if _digest(item.proposal) != item.proposal_checksum:
            raise ValidationError('The retained receipt correction checksum changed.')
        for row in item.proposal['withholding']:
            key = tuple(row[k] for k in ('fund_code', 'account_code', 'reference_key', 'deduction_code'))
            holds[key] = holds.get(key, Decimal('0')) + Decimal(row['amount'])
    return holds


def require_capacity(batch, proposal, *, retained_hold=False):
    from .withholding_capacity import correction_balances
    balances = correction_balances(department_id=batch.finance_department_id,
        transaction_type=batch.transaction_variant.code, as_of_date=date.fromisoformat(proposal['correction_date']))
    required = {}
    for row in proposal['withholding']:
        key = tuple(row[k] for k in ('fund_code', 'account_code', 'reference_key', 'deduction_code'))
        required[key] = required.get(key, Decimal('0')) + Decimal(row['amount'])
    for key, amount in required.items():
        if balances.get(key, Decimal('0')) + (amount if retained_hold else 0) < amount:
            raise ValidationError('Restored withholding was already used, reserved or corrected. Resolve the downstream transactions first.')


@transaction.atomic
def propose_correction(*, receipt, actor, correction_date, reason, evidence_reference, filing_basis, expected_version):
    _require(actor, 'vouchers.prepare_remittances')
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=receipt.batch_id)
    receipt = RemittanceReturn.objects.select_for_update().get(pk=receipt.pk)
    _require_treasury_scope(actor, batch)
    if batch.state_version != expected_version:
        raise ValidationError('The remittance changed. Reload before proposing a receipt correction.')
    lock_withholding_scope(batch.finance_department_id)
    source, entry = receipt_source(receipt)
    if receipt.corrections.exclude(status__in=(Correction.REJECTED, Correction.WITHDRAWN)).exists():
        raise ValidationError('Resolve the existing receipt correction before preparing another.')
    if not isinstance(correction_date, date) or not entry.entry_date <= correction_date <= timezone.localdate():
        raise ValidationError('Use the actual correction date, on or after the receipt and no later than today.')
    if not all(str(v or '').strip() for v in (reason, evidence_reference, filing_basis)):
        raise ValidationError('Record the posting error, supporting evidence and filing disposition basis.')
    if not AccountingPeriod.objects.filter(department_id=batch.finance_department_id, status=AccountingPeriod.OPEN,
            starts_on__lte=correction_date, ends_on__gte=correction_date).exists():
        raise ValidationError('Use an open Accounting period for the correction.')
    with transaction.atomic(using='finance'):
        entry = JournalEntry.objects.select_for_update().get(pk=entry.pk)
        if entry.reversal_entries.exclude(status=entry.VOIDED).exists():
            raise ValidationError('Resolve the existing reversal of this receipt.')
        withheld = []
        for d in entry.subsidiary_lines.select_related('journal_line__account'):
            if d.category != d.WITHHOLDING or d.credit <= 0 or d.debit:
                raise ValidationError('Retain the original receipt withholding credits.')
            withheld.append({'fund_code': entry.fund.code, 'account_code': d.journal_line.account.code,
                'reference_key': d.reference_key, 'deduction_code': d.source_code, 'amount': str(d.credit)})
        if sum((Decimal(r['amount']) for r in withheld), Decimal('0')) != Decimal(receipt.proposal['amount']):
            raise ValidationError('The receipt withholding does not reproduce its approved amount.')
        proposal = {'receipt': str(receipt.public_id), 'original_request': str(source.public_id),
            'original_entry': str(entry.public_id), 'original_payload_checksum': source.payload_checksum,
            'original_rows_checksum': _digest(financial_rows(entry)), 'correction_date': correction_date.isoformat(),
            'amount': receipt.proposal['amount'], 'withholding': withheld, 'reason': reason.strip(),
            'evidence_reference': evidence_reference.strip(), 'filing_basis': filing_basis.strip(),
            'filing_evidence': [{**r, 'public_id': str(r['public_id'])} for r in filing_snapshot(batch)]}
        require_capacity(batch, proposal)
        item = Correction.objects.create(receipt=receipt,
            version=(receipt.corrections.aggregate(v=Max('version'))['v'] or 0) + 1,
            proposal=proposal, proposal_checksum=_digest(proposal), prepared_by=actor)
        batch.state_version += 1; batch.save(update_fields=('state_version', 'updated_at'))
        _event(batch, actor, 'receipt_correction_proposed', batch.status, reason,
            {'correction': str(item.public_id), 'proposal_checksum': item.proposal_checksum})
    return item


@transaction.atomic
def review_correction(*, item, actor, approve, reason):
    _require(actor, 'vouchers.approve_remittances')
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=item.receipt.batch_id)
    item = Correction.objects.select_for_update().get(pk=item.pk)
    require_remittance_review_scope(actor, batch)
    if item.status != item.PROPOSED or actor.pk == item.prepared_by_id or not reason.strip():
        raise ValidationError('An independent reviewer must decide this pending receipt correction.')
    lock_withholding_scope(batch.finance_department_id)
    if _digest(item.proposal) != item.proposal_checksum:
        raise ValidationError('The immutable receipt correction proposal changed.')
    if approve:
        source, original = receipt_source(item.receipt)
        if (_digest(financial_rows(original)) != item.proposal['original_rows_checksum'] or
                source.payload_checksum != item.proposal['original_payload_checksum'] or
                [{**r, 'public_id': str(r['public_id'])} for r in filing_snapshot(batch)] != item.proposal['filing_evidence']):
            raise ValidationError('Receipt or filing evidence changed. Reject this proposal and prepare a current successor.')
        require_capacity(batch, item.proposal, retained_hold=True)
        day = date.fromisoformat(item.proposal['correction_date'])
        number = _consume_number(batch, actor, 'journal-entry', f'receipt-correction-{item.public_id}', as_of=day)
        payload = deepcopy(source.payload)
        payload['remittance_return_correction'] = {**item.proposal, 'correction': str(item.public_id),
            'proposal_checksum': item.proposal_checksum, 'reviewed_by': actor.pk, 'review_reason': reason.strip()}
        request = RemittancePostingRequest(batch=batch,
            version=(batch.posting_requests.aggregate(v=Max('version'))['v'] or 0) + 1,
            jev_number=number, jev_date=day, finance_department_id=source.finance_department_id,
            finance_department_label=source.finance_department_label, posting_rule=source.posting_rule,
            posting_rule_snapshot=source.posting_rule_snapshot, posting_rule_checksum=source.posting_rule_checksum,
            payload=payload, payload_checksum=_digest(payload), requested_by=actor)
        request.full_clean(); request.save(); item.posting_request = request
    item.status = item.APPROVED if approve else item.REJECTED
    item.reviewed_by, item.reviewed_at, item.review_reason = actor, timezone.now(), reason.strip()
    item.save()
    batch.state_version += 1; batch.save(update_fields=('state_version', 'updated_at'))
    _event(batch, actor, 'receipt_correction_reviewed', batch.status, reason,
        {'correction': str(item.public_id), 'approved': approve})
    return item


def validate_mirror(entry):
    retained = entry.source_snapshot.get('remittance_return_correction')
    if not retained:
        return
    if not entry.reversal_of_id:
        raise ValidationError('A receipt correction must retain its original receipt reversal link.')
    original = entry.reversal_of
    if (str(original.public_id) != retained['original_entry'] or original.status != original.POSTED
            or _digest(financial_rows(original)) != retained['original_rows_checksum']
            or financial_rows(entry) != financial_rows(original, reverse=True)):
        raise ValidationError('The receipt correction must exactly reverse its retained financial lines.')


@transaction.atomic
def materialize_correction(request, actor):
    from accounting.access import can_prepare_journals, department_for_user
    if not can_prepare_journals(actor) or getattr(department_for_user(actor), 'pk', None) != request.finance_department_id:
        raise PermissionDenied
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=request.batch_id)
    request = RemittancePostingRequest.objects.select_for_update().get(pk=request.pk)
    item = Correction.objects.select_for_update().get(posting_request=request)
    retained = request.payload['remittance_return_correction']
    if (item.status != item.APPROVED or request.status not in (request.PENDING, request.FAILED, request.MATERIALIZED)
            or _digest(request.payload) != request.payload_checksum or _digest(item.proposal) != item.proposal_checksum
            or retained['proposal_checksum'] != item.proposal_checksum or retained['reviewed_by'] != item.reviewed_by_id
            or item.reviewed_by_id == item.prepared_by_id or any(retained.get(k) != v for k, v in item.proposal.items())):
        raise ValidationError('Retain the independent correction approval and exact source evidence.')
    lock_withholding_scope(batch.finance_department_id)
    source, original = receipt_source(item.receipt)
    with transaction.atomic(using='finance'):
        original = JournalEntry.objects.select_for_update().get(pk=original.pk)
        existing = JournalEntry.objects.filter(source_type='remittance', source_reference=str(request.public_id)).first()
        if existing:
            verify_source_link(request, existing, source_type='remittance'); validate_mirror(existing)
            if existing.status == existing.VOIDED:
                raise ValidationError('Retain the discarded correction in a posting successor.')
            entry, created = existing, False
        else:
            require_capacity(batch, item.proposal, retained_hold=True)
            if original.reversal_entries.exclude(status=original.VOIDED).exists():
                raise ValidationError('A correction reversal already exists for this receipt.')
            period = AccountingPeriod.objects.get(department_id=batch.finance_department_id,
                status=AccountingPeriod.OPEN, starts_on__lte=request.jev_date, ends_on__gte=request.jev_date)
            entry = JournalEntry(department_id=original.department_id, department_label=original.department_label,
                reference=request.jev_number, entry_date=request.jev_date, period=period, fund=original.fund,
                source_type='remittance', source_reference=str(request.public_id), reversal_of=original,
                reversal_reason=retained['reason'], description=f'Receipt correction: {retained["reason"]}',
                source_snapshot={'remittance_batch': str(batch.public_id), 'payload_checksum': request.payload_checksum,
                    'posting_rule_checksum': request.posting_rule_checksum, 'remittance_return': request.payload['remittance_return'],
                    'remittance_return_correction': retained},
                created_by_id=actor.pk, created_by_label=actor.get_full_name() or actor.username)
            entry.full_clean(); entry.save()
            for line in original.lines.order_by('sequence', 'pk'):
                reversed_line = JournalLine(entry=entry, sequence=line.sequence, account=line.account,
                    responsibility_center=line.responsibility_center, debit=line.credit, credit=line.debit,
                    cash_flow_category=line.cash_flow_category, memo=f'Receipt correction: {line.memo}'[:255])
                reversed_line.full_clean(); reversed_line.save()
                for detail in JournalSubsidiaryLine.objects.filter(journal_line=line):
                    reversed_detail = JournalSubsidiaryLine(entry=entry, journal_line=reversed_line, category=detail.category,
                        reference_key=detail.reference_key, reference_label=detail.reference_label, source_code=detail.source_code,
                        source_reference=str(request.public_id), debit=detail.credit, credit=detail.debit,
                        source_snapshot={**detail.source_snapshot, 'reversal_of_subsidiary_line': detail.pk,
                            'receipt_correction': str(item.public_id)})
                    reversed_detail.full_clean(); reversed_detail.save()
            validate_mirror(entry)
            from accounting.services import record_event
            record_event(entry, 'receipt_correction_materialized', actor, snapshot={'proposal_checksum': item.proposal_checksum})
            created = True
    request.status, request.accounting_entry_public_id = request.MATERIALIZED, entry.public_id
    request.materialized_at, request.failure_reason = timezone.now(), ''
    request.save()
    return entry, created


@transaction.atomic
def reconcile_correction(entry, actor):
    entry = require_persisted_posting(entry, actor, source_type='remittance')
    request = RemittancePostingRequest.objects.get(public_id=entry.source_reference)
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=request.batch_id)
    request = RemittancePostingRequest.objects.select_for_update().get(pk=request.pk)
    item = Correction.objects.select_for_update().get(posting_request=request)
    receipt = RemittanceReturn.objects.select_for_update().get(pk=item.receipt_id)
    lock_withholding_scope(batch.finance_department_id)
    verify_source_link(request, entry, source_type='remittance'); validate_mirror(entry)
    retained = request.payload['remittance_return_correction']
    if (_digest(item.proposal) != item.proposal_checksum or retained['proposal_checksum'] != item.proposal_checksum
            or any(retained.get(k) != v for k, v in item.proposal.items())):
        raise ValidationError('The correction no longer reproduces its retained proposal.')
    if item.status == item.POSTED and receipt.status == receipt.CORRECTED and request.status == request.POSTED:
        return request
    if item.status != item.APPROVED or receipt.status != receipt.POSTED:
        raise ValidationError('The posted correction no longer matches the operational receipt state.')
    request.status, request.posted_at, request.accounting_entry_public_id = request.POSTED, entry.posted_at, entry.public_id
    request.failure_reason = ''; request.save()
    item.status = item.POSTED; item.save(update_fields=('status',))
    receipt.status = receipt.CORRECTED; receipt.save(update_fields=('status',))
    batch.state_version += 1; batch.save(update_fields=('state_version', 'updated_at'))
    _event(batch, actor, 'receipt_correction_posted', batch.status, item.proposal['reason'],
        {'correction': str(item.public_id), 'original_receipt': str(receipt.public_id), 'entry': str(entry.public_id)})
    return request


def export_corrections(batch, actor):
    import csv
    import io
    from src.export_archive import archive_export
    _require(actor, 'vouchers.view_remittance_workbench')
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(('remittance', 'receipt_version', 'correction_version', 'status', 'correction_date',
        'amount', 'original_receipt_jev', 'correction_jev', 'reason', 'evidence_reference', 'filing_basis',
        'prepared_by', 'reviewed_by', 'review_reason', 'proposal_checksum', 'withdrawal_reason', 'withdrawn_by', 'withdrawn_at'))
    withdrawals = {event.metadata.get('correction'): event for event in batch.events.filter(action='receipt_correction_withdrawn')}
    for item in Correction.objects.filter(receipt__batch=batch).select_related('receipt__posting_request', 'posting_request').order_by('receipt__version', 'version'):
        if _digest(item.proposal) != item.proposal_checksum:
            raise ValidationError('The retained receipt correction checksum changed.')
        withdrawal = withdrawals.get(str(item.public_id))
        writer.writerow((batch.reference_code, item.receipt.version, item.version, item.get_status_display(),
            item.proposal['correction_date'], item.proposal['amount'], item.receipt.posting_request.jev_number,
            item.posting_request.jev_number if item.posting_request else '', item.proposal['reason'],
            item.proposal['evidence_reference'], item.proposal['filing_basis'], item.prepared_by_id,
            item.reviewed_by_id or '', item.review_reason, item.proposal_checksum,
            withdrawal.reason if withdrawal else '', withdrawal.actor_id if withdrawal else '',
            withdrawal.created_at.isoformat() if withdrawal else ''))
    content = output.getvalue().encode('utf-8-sig')
    return content, archive_export(content=content, department=batch.treasury_department, user=actor,
        category='finance-receipt-corrections', filename=f'{batch.reference_code}-receipt-corrections.csv',
        metadata={'remittance_public_id': str(batch.public_id)})


@transaction.atomic
def withdraw_correction(*, item, actor, reason):
    _require(actor, 'vouchers.approve_remittances')
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=item.receipt.batch_id)
    item = Correction.objects.select_for_update().get(pk=item.pk)
    require_remittance_review_scope(actor, batch)
    if actor.pk == item.prepared_by_id or not str(reason or '').strip():
        raise ValidationError('An independent reviewer must record why the unposted correction is withdrawn.')
    if item.status == item.WITHDRAWN:
        return item
    if item.status != item.APPROVED or not item.posting_request_id:
        raise ValidationError('Only an approved, unposted correction can be withdrawn.')
    lock_withholding_scope(batch.finance_department_id)
    receipt_source(item.receipt)
    if _digest(item.proposal) != item.proposal_checksum:
        raise ValidationError('The retained correction proposal changed.')
    sources = list(batch.posting_requests.select_for_update().filter(
        payload__remittance_return_correction__correction=str(item.public_id)).order_by('pk'))
    if (not sources or item.posting_request_id not in {r.pk for r in sources}
            or any(r.status == r.POSTED or _digest(r.payload) != r.payload_checksum for r in sources)):
        raise ValidationError('Retain the complete unposted correction source chain.')
    by_reference = {str(r.public_id): r for r in sources}
    with transaction.atomic(using='finance'):
        JournalEntry.objects.select_for_update().get(public_id=item.proposal['original_entry'])
        entries = list(JournalEntry.objects.select_for_update().filter(source_type='remittance',
            source_reference__in=by_reference).order_by('pk'))
        for entry in entries:
            verify_source_link(by_reference[entry.source_reference], entry, source_type='remittance')
            if entry.status != entry.VOIDED:
                raise ValidationError('Discard the unposted correction JEV first; posted corrections cannot be withdrawn.')
        if any(r.accounting_entry_public_id and r.accounting_entry_public_id not in {e.public_id for e in entries} for r in sources):
            raise ValidationError('Investigate the missing correction JEV before releasing its hold.')
        source = next(r for r in sources if r.pk == item.posting_request_id)
        source.status, source.failure_reason = source.CANCELLED, f'Correction withdrawn: {reason.strip()}'
        source.save(update_fields=('status', 'failure_reason'))
        item.status = item.WITHDRAWN; item.save(update_fields=('status',))
        batch.state_version += 1; batch.save(update_fields=('state_version', 'updated_at'))
        _event(batch, actor, 'receipt_correction_withdrawn', batch.status, reason.strip(),
            {'correction': str(item.public_id), 'posting_requests': list(by_reference),
                'proposal_checksum': item.proposal_checksum, 'discarded_entries': [str(e.public_id) for e in entries]})
    return item
