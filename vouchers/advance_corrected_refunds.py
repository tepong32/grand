"""Exact corrected receipt/deposit histories retained by original advance correction."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from accounting.models import JournalEntry
from accounting.posted_evidence import verify_source_link
from accounting.claim_attributions import _exact_reversal
from .models import TreasuryCollectionSource as Source
from .remittances import _digest
from .advance_corrected_applications import journal_evidence


def withdrawn(source):
    if _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('Retain the unchanged refund/deposit source proposal.')
    if source.status not in (Source.REJECTED, Source.WITHDRAWN):
        return False
    actor = source.reviewed_by_id if source.status == Source.REJECTED else source.withdrawn_by_id
    reason = source.review_reason if source.status == Source.REJECTED else source.withdrawal_reason
    if not actor or actor == source.prepared_by_id or not reason or source.posting_requests.exclude(status='cancelled').exists():
        raise ValidationError('Retain independent refund/deposit withdrawal or rejection.')
    references = [str(value) for value in source.posting_requests.values_list('public_id', flat=True)]
    if JournalEntry.objects.filter(source_reference__in=references,
            source_type__in=('collection', 'deposit', 'collection_fix')).exclude(status=JournalEntry.VOIDED).exists():
        raise ValidationError('A refund/deposit with an active journal cannot be treated as withdrawn.')
    return True


def posted(source, *, capture, reversal=None):
    from .collection_posting import validate_collection_journal
    requests = list(source.posting_requests.exclude(status='cancelled'))
    if (source.status != Source.POSTED or len(requests) != 1 or requests[0].status != 'posted'
            or not source.reviewed_at or not source.reviewed_by_id or source.reviewed_by_id == source.prepared_by_id
            or not source.review_reason or _digest(source.proposal) != source.proposal_checksum):
        raise ValidationError('Reconcile the independently reviewed refund/deposit posting first.')
    request = requests[0]
    entry = JournalEntry.objects.get(public_id=request.accounting_entry_public_id)
    kind = {Source.RECEIPT: 'collection', Source.DEPOSIT: 'deposit', Source.CORRECTION: 'collection_fix'}[source.kind]
    verify_source_link(request, entry, source_type=kind)
    if capture:
        validate_collection_journal(entry)
    event = entry.audit_events.filter(action='posted').first()
    debit, credit = entry.totals
    try:
        totals = (Decimal(event.snapshot['debit']), Decimal(event.snapshot['credit'])) if event else None
    except (KeyError, TypeError, ValueError, InvalidOperation):
        totals = None
    if (entry.status != entry.POSTED or not entry.posted_at or not entry.posted_by_id
            or entry.posted_by_id in (entry.created_by_id, entry.submitted_by_id, source.prepared_by_id)
            or not event or event.actor_id != entry.posted_by_id or event.department_id != entry.department_id
            or debit <= 0 or debit != credit or totals != (debit, credit)
            or request.payload.get('proposal') != source.proposal
            or request.payload.get('proposal_checksum') != source.proposal_checksum
            or request.payload.get('prepared_by') != source.prepared_by_id
            or request.payload.get('reviewed_by') != source.reviewed_by_id
            or request.payload.get('review_reason') != source.review_reason
            or request.payload.get('source_date') != source.source_date.isoformat()
            or request.payload.get('amount') != str(source.amount)):
        raise ValidationError('Retain the exact independently posted refund/deposit source and totals.')
    if entry.fund_id != source.proposal.get('fund_id'):
        raise ValidationError('Retain the approved refund/deposit fund in its posted journal.')
    children = entry.reversal_entries.exclude(status=JournalEntry.VOIDED)
    if reversal:
        children = children.exclude(source_type='collection_fix', source_reference=str(reversal.public_id))
    if children.exists():
        raise ValidationError('Resolve every additional refund/deposit reversal.')
    proof = {'source': str(source.public_id), 'kind': source.kind, 'date': source.source_date.isoformat(),
        'amount': str(source.amount), 'proposal_checksum': source.proposal_checksum,
        'treasury': source.treasury_department_id, 'finance': source.finance_department_id,
        'prepared_by': source.prepared_by_id, 'reviewed_by': source.reviewed_by_id,
        'reviewed_at': source.reviewed_at.isoformat(), 'review_reason': source.review_reason,
        'journal': journal_evidence(request, entry)}
    return entry, proof


def corrected_pair(source, day, *, capture):
    from .collection_corrections import validate_correction
    fixes = [row for row in source.corrections.all() if not withdrawn(row)]
    if source.status != Source.POSTED or len(fixes) != 1 or fixes[0].status != Source.POSTED or fixes[0].source_date > day:
        raise ValidationError('Resolve and retain linked advance liquidation/refund corrections before original recognition correction.')
    fix = fixes[0]
    requests = list(fix.posting_requests.filter(status='posted'))
    if len(requests) != 1:
        raise ValidationError('Reconcile one exact refund/deposit correction posting.')
    original, original_proof = posted(source, capture=capture, reversal=requests[0])
    reversal, reversal_proof = posted(fix, capture=capture)
    if capture:
        validate_correction(fix)
    if not _exact_reversal(reversal, original) or reversal.entry_date > day:
        raise ValidationError('Retain the exact dated refund/deposit correction.')
    return {'original': original_proof, 'correction': reversal_proof}, fix


def evidence(detail, day, *, retained=None):
    from .advance_refunds import validate_source
    result = []
    for refund in Source.objects.filter(kind=Source.RECEIPT, proposal__advance_refund__original_detail=detail.pk):
        if withdrawn(refund):
            continue
        if retained is None:
            validate_source(refund, check_capacity=False)
        pair, fix = corrected_pair(refund, day, capture=retained is None)
        deposits = []
        for deposit in Source.objects.filter(kind=Source.DEPOSIT, treasury_department_id=refund.treasury_department_id):
            if not any(row.get('receipt') == str(refund.public_id) for row in deposit.proposal.get('allocations', [])):
                continue
            if withdrawn(deposit):
                continue
            proof, _ = corrected_pair(deposit, fix.source_date, capture=retained is None)
            deposits.append(proof)
        deposits.sort(key=lambda row: row['original']['source'])
        result.append({'receipt': pair, 'deposits': deposits})
    result.sort(key=lambda row: row['receipt']['original']['source'])
    if retained is not None and result != retained:
        raise ValidationError('The retained corrected refund/deposit history changed after original advance correction preparation.')
    return result
