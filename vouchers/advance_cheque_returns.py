"""Dated return adjustments to the exact original officer advance."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from accounting.models import JournalEntry, JournalSubsidiaryLine
from finance.models import FinancePostingRuleLine as Line
from .models import TreasuryCollectionSource as Source
from .remittances import _digest

RETURN = 'advance_cheque_return'
CORRECTION = 'advance_cheque_return_correction'


def evidence(source):
    return source.proposal.get(RETURN) or source.proposal.get(CORRECTION)


def return_rows(owner, snapshot, total, bank, purposes, data):
    from .advance_sources import original
    from .collections import account, financial_row
    detail, _, _ = original(JournalSubsidiaryLine.objects.get(pk=data['original_detail']))
    lines = snapshot.get('lines', [])
    debits = [row for row in lines if row['side'] == Line.DEBIT]
    credits = [row for row in lines if row['side'] == Line.CREDIT]
    if (len(lines) != 2 or len(debits) != 1 or len(credits) != 1
            or debits[0]['account_source'] != Line.PRIOR_ADVANCE
            or credits[0]['account_source'] != Line.BANK_MAPPING
            or any(row['amount_source'] != Line.EVENT_AMOUNT or row.get('mapping_code')
                or row.get('ledger_account_code') for row in lines)
            or debits[0].get('cash_flow_category')
            or not credits[0].get('cash_flow_category')
            or credits[0]['cash_flow_category'] == 'internal'
            or set(purposes) != {credits[0]['cash_flow_category']}):
        raise ValidationError('Review one selected-original-advance debit and one original-bank credit with the original refund cash purpose.')
    bank_account = account(owner, bank['ledger_account_code'])
    if (bank_account.pk != bank['ledger_account_id'] or bank_account.account_type != 'asset'
            or bank_account.pk == detail.journal_line.account_id or detail.entry.department_id != owner):
        raise ValidationError('Retain the original officer advance and its separate original deposit bank.')
    return [financial_row(detail.journal_line.account,total,Line.DEBIT),
        financial_row(bank_account,total,Line.CREDIT,credits[0]['cash_flow_category'])]


def validate_source(source, *, check_capacity=True):
    data = evidence(source)
    if not data:
        return
    from .advance_refunds import validate_source as validate_refund
    returning = source if source.kind == Source.CHEQUE_RETURN else source.correction_of
    if returning is None or returning.kind != Source.CHEQUE_RETURN or not returning.return_receipt_id:
        raise ValidationError('Retain the original officer cheque bank-return source.')
    receipt = returning.return_receipt
    validate_refund(receipt, check_capacity=False)
    if (not receipt.proposal.get('advance_refund') or data != receipt.proposal['advance_refund']
            or _digest(source.proposal) != source.proposal_checksum
            or source.finance_department_id != receipt.finance_department_id
            or source.treasury_department_id != receipt.treasury_department_id
            or source.proposal['fund_id'] != receipt.proposal['fund_id']
            or source.amount != receipt.amount
            or (source.kind == Source.CORRECTION and source.proposal.get(CORRECTION) != returning.proposal.get(RETURN))):
        raise ValidationError('Retain the exact original refund, officer, amount and fund through the return adjustment.')
    if source.kind == Source.CORRECTION and check_capacity:
        from .advance_applications import capacity
        detail = JournalSubsidiaryLine.objects.get(pk=data['original_detail'])
        # The proposed correction already holds its full debit-reversing amount.
        capacity(detail,source.source_date,Decimal('0'))


def prepare_correction(original, day):
    data = original.proposal.get(RETURN)
    if not data:
        return None
    validate_source(original,check_capacity=False)
    from .advance_applications import capacity
    capacity(JournalSubsidiaryLine.objects.get(pk=data['original_detail']),day,original.amount)
    return data


def active_hold(source):
    if source.status not in (Source.REJECTED,Source.WITHDRAWN):
        return True
    reviewer = source.reviewed_by_id if source.status == Source.REJECTED else source.withdrawn_by_id
    reason = source.review_reason if source.status == Source.REJECTED else source.withdrawal_reason
    references = [str(value) for value in source.posting_requests.values_list('public_id',flat=True)]
    if (not reviewer or reviewer == source.prepared_by_id or not reason
            or source.posting_requests.exclude(status='cancelled').exists()
            or JournalEntry.objects.filter(source_type='collection_fix',source_reference__in=references)
                .exclude(status=JournalEntry.VOIDED).exists()):
        raise ValidationError('Retain independent withdrawal and discarded journals before releasing the return-correction reservation.')
    return False


def movements(detail):
    from .collection_corrections import original_journal, corrected_sources
    result = []
    returns = Source.objects.filter(kind=Source.CHEQUE_RETURN,
        proposal__advance_cheque_return__original_detail=detail.pk,
        status__in=(Source.POSTED,Source.CORRECTED))
    for source in returns:
        validate_source(source,check_capacity=False)
        original_journal(source)
        result.append((source.source_date,-source.amount))
    corrections = Source.objects.filter(kind=Source.CORRECTION,
        proposal__advance_cheque_return_correction__original_detail=detail.pk)
    for source in corrections:
        validate_source(source,check_capacity=False)
        if not active_hold(source):
            continue
        if source.status == Source.POSTED and source.correction_of_id not in corrected_sources(
                source.treasury_department_id,source.source_date):
            raise ValidationError('Reconcile the exact officer return correction before treating it as posted.')
        result.append((source.source_date,source.amount))
    return result


def attach(entry, source, request):
    data = evidence(source)
    if not data:
        return
    detail = JournalSubsidiaryLine.objects.get(pk=data['original_detail'])
    correction = source.kind == Source.CORRECTION
    line = entry.lines.get(account_id=detail.journal_line.account_id)
    row = JournalSubsidiaryLine(entry=entry,journal_line=line,category=JournalSubsidiaryLine.ADVANCE,
        reference_key=detail.reference_key,reference_label=detail.reference_label,source_code=detail.source_code,
        source_reference=str(request.public_id),debit=0 if correction else source.amount,
        credit=source.amount if correction else 0,
        source_snapshot={CORRECTION if correction else RETURN:data,
            'original_advance_detail':detail.pk,'transaction_type':detail.source_code})
    row.full_clean(); row.save()


def validate_journal(entry):
    proposal = entry.source_snapshot.get('collection_payload',{}).get('proposal',{})
    data = proposal.get(RETURN) or proposal.get(CORRECTION)
    if not data:
        return
    from .models import CollectionPostingRequest
    from accounting.posted_evidence import verify_source_link
    request = CollectionPostingRequest.objects.select_related('source').get(public_id=entry.source_reference)
    verify_source_link(request,entry,source_type=entry.source_type)
    source = request.source
    validate_source(source,check_capacity=entry.status not in (JournalEntry.POSTED,JournalEntry.VOIDED))
    detail = JournalSubsidiaryLine.objects.get(pk=data['original_detail'])
    rows = list(entry.subsidiary_lines.all())
    correction = source.kind == Source.CORRECTION
    if len(rows) != 1:
        raise ValidationError('Retain one exact original-officer subsidiary on the return adjustment.')
    row = rows[0]
    if (proposal != source.proposal or row.category != JournalSubsidiaryLine.ADVANCE
            or row.reference_key != detail.reference_key or row.reference_label != detail.reference_label
            or row.source_code != detail.source_code or row.source_reference != str(request.public_id)
            or row.journal_line.account_id != detail.journal_line.account_id
            or row.source_snapshot != {CORRECTION if correction else RETURN:data,
                'original_advance_detail':detail.pk,'transaction_type':detail.source_code}
            or row.debit != (0 if correction else source.amount)
            or row.credit != (source.amount if correction else 0)):
        raise ValidationError('Retain the original officer, asset and exact subsidiary amount through the return adjustment.')
    if correction:
        original_entry = JournalEntry.objects.get(public_id=source.proposal['original_entry'])
        original_detail = original_entry.subsidiary_lines.get()
        if (entry.reversal_of_id != original_entry.pk or row.debit != original_detail.credit
                or row.credit != original_detail.debit or row.journal_line.sequence != original_detail.journal_line.sequence):
            raise ValidationError('The return correction must mirror its exact original officer subsidiary.')
