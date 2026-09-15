"""Bank-evidenced cheque clearing under the existing Treasury source lock."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from departments.models import Department
from .collections import require, posted_receipt
from .collection_corrections import original_journal
from .models import TreasuryCollectionSource as Source, CollectionChequeClearance as Clearance
from .remittances import _digest


def source_evidence(receipt, deposit, day):
    if (not isinstance(day, date) or not receipt.source_date <= deposit.source_date <= day <= timezone.localdate()
            or not receipt.proposal.get('cheque') or deposit.kind != Source.DEPOSIT
            or deposit.treasury_department_id != receipt.treasury_department_id
            or deposit.finance_department_id != receipt.finance_department_id or deposit.fund_code != receipt.fund_code):
        raise ValidationError('Choose the original cheque and its whole posted deposit, with an actual subsequent clearing date.')
    receipt_entry = posted_receipt(receipt)
    deposit_entry, _ = original_journal(deposit)
    if (deposit_entry.reversal_entries.exclude(status='voided').exists()
            or Source.objects.filter(correction_of_id__in=(receipt.pk, deposit.pk),
                status__in=(Source.PROPOSED, Source.APPROVED, Source.POSTED)).exists()):
        raise ValidationError('Resolve receipt/deposit corrections before confirming cheque clearing.')
    shares = [row for row in deposit.proposal.get('allocations', []) if row.get('receipt') == str(receipt.public_id)]
    if (len(shares) != 1 or Decimal(shares[0]['amount']) != receipt.amount
            or shares[0]['proposal_checksum'] != receipt.proposal_checksum
            or shares[0]['entry'] != str(receipt_entry.public_id)
            or deposit_entry.fund_id != receipt_entry.fund_id):
        raise ValidationError('Clearing must retain the exact whole-cheque deposit allocation and original journal.')
    return {'receipt': str(receipt.public_id), 'receipt_checksum': receipt.proposal_checksum,
        'receipt_entry': str(receipt_entry.public_id), 'deposit': str(deposit.public_id),
        'deposit_checksum': deposit.proposal_checksum, 'deposit_entry': str(deposit_entry.public_id),
        'bank': deposit.proposal['receiving_bank'], 'cheque': receipt.proposal['cheque'],
        'amount': str(receipt.amount), 'fund_id': receipt_entry.fund_id}


@transaction.atomic
def propose(*, receipt, deposit, actor, cleared_on, bank_reference, evidence_reference):
    office = require(actor, 'vouchers.prepare_collections')
    if office.pk != receipt.treasury_department_id:
        raise PermissionDenied
    Department.objects.select_for_update().get(pk=office.pk)
    receipt = Source.objects.select_for_update().get(pk=receipt.pk)
    deposit = Source.objects.get(pk=deposit.pk)
    if receipt.cheque_clearances.filter(status__in=('proposed', 'approved')).exists():
        raise ValidationError('Resolve the existing cheque clearing proposal or decision first.')
    from .cheque_returns import protect
    protect(receipt)
    snapshot = source_evidence(receipt, deposit, cleared_on)
    bank_reference, evidence_reference = str(bank_reference or '').strip(), str(evidence_reference or '').strip()
    if not bank_reference or len(bank_reference) > 160 or not evidence_reference:
        raise ValidationError('Retain the actual bank clearing reference (up to 160 characters) and evidence location.')
    snapshot.update(bank_reference=bank_reference, evidence_reference=evidence_reference, cleared_on=cleared_on.isoformat())
    return Clearance.objects.create(receipt=receipt, deposit=deposit, cleared_on=cleared_on,
        version=(receipt.cheque_clearances.aggregate(v=Max('version'))['v'] or 0) + 1,
        snapshot=snapshot, checksum=_digest(snapshot), prepared_by=actor)


def verify(row):
    if _digest(row.snapshot) != row.checksum or row.snapshot.get('cleared_on') != row.cleared_on.isoformat():
        raise ValidationError('The retained cheque clearing evidence changed.')
    evidence = source_evidence(row.receipt, row.deposit, row.cleared_on)
    if any(row.snapshot.get(key) != value for key, value in evidence.items()):
        raise ValidationError('The original cheque/deposit evidence no longer reproduces the clearing proposal.')


@transaction.atomic
def review(*, clearance, actor, approve, reason):
    office = require(actor, 'vouchers.review_collections')
    Department.objects.select_for_update().get(pk=clearance.receipt.treasury_department_id)
    row = Clearance.objects.select_for_update().select_related('receipt', 'deposit').get(pk=clearance.pk)
    if office.pk != row.receipt.finance_department_id:
        raise PermissionDenied
    if row.status != 'proposed' or actor.pk == row.prepared_by_id or not str(reason or '').strip():
        raise ValidationError('An independent reviewer must decide the proposed clearing evidence with a retained basis.')
    verify(row)
    if approve:
        from .cheque_returns import protect
        protect(row.receipt)
    if approve and row.receipt.cheque_clearances.exclude(pk=row.pk).filter(status='approved').exists():
        raise ValidationError('This cheque already retains approved clearing evidence.')
    row.status = 'approved' if approve else 'rejected'
    row.reviewed_by, row.reviewed_at, row.review_reason = actor, timezone.now(), reason.strip()
    row.save()
    return row


@transaction.atomic
def withdraw(*, clearance, actor, reason):
    office = require(actor, 'vouchers.review_collections')
    Department.objects.select_for_update().get(pk=clearance.receipt.treasury_department_id)
    row = Clearance.objects.select_for_update().select_related('receipt', 'deposit').get(pk=clearance.pk)
    if office.pk != row.receipt.finance_department_id:
        raise PermissionDenied
    if row.status != 'approved' or actor.pk == row.prepared_by_id or not str(reason or '').strip():
        raise ValidationError('An independent reviewer must withdraw approved clearing evidence with a reason.')
    verify(row)
    from .cheque_returns import protect
    protect(row.receipt)
    # Officer cheque refunds remain blocked until dependent dated capacity is implemented.
    if row.receipt.proposal.get('advance_refund'):
        raise ValidationError('Resolve the dependent officer refund before withdrawing its clearing evidence.')
    row.status = 'withdrawn'
    row.withdrawn_by, row.withdrawn_at, row.withdrawal_reason = actor, timezone.now(), reason.strip()
    row.save()
    return row


def protect_correction(source):
    if Clearance.objects.filter(Q(receipt=source) | Q(deposit=source), status__in=('proposed', 'approved')).exists():
        raise ValidationError('Return or independently withdraw the retained cheque clearing evidence before correcting this source.')


def output_evidence(receipt):
    result = []
    for row in receipt.cheque_clearances.select_related('receipt', 'deposit').order_by('version'):
        if _digest(row.snapshot) != row.checksum:
            raise ValidationError('The retained cheque clearing evidence changed.')
        if row.status == 'approved':
            verify(row)
        result.append({'version': row.version, 'status': row.get_status_display(), 'date': row.cleared_on.isoformat(),
            'bank_reference': row.snapshot['bank_reference'], 'evidence_reference': row.snapshot['evidence_reference'],
            'checksum': row.checksum, 'prepared_by': row.prepared_by_id,
            'reviewed_by': row.reviewed_by_id, 'review_reason': row.review_reason,
            'withdrawn_by': row.withdrawn_by_id, 'withdrawal_reason': row.withdrawal_reason})
    return result
