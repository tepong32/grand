"""Actual Treasury refunds applied to explicit original officer advances."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounting.models import JournalEntry, JournalSubsidiaryLine
from departments.models import Department
from finance.models import FinancePostingRuleLine as Line
from .models import TreasuryCollectionSource as Source, VoucherCase
from .advance_sources import original
from .remittances import _digest


def evidence(source):
    return source.proposal.get('advance_refund') or source.proposal.get('advance_refund_correction')


def visible_originals(actor):
    from .access import department_for_user
    from .models import VoucherPostingRequest
    office = department_for_user(actor)
    sources = VoucherPostingRequest.objects.filter(kind=VoucherPostingRequest.RECOGNITION,
        case__events__actor_department=office,
        case__events__action__in=('check_released', 'disbursement_completed')).values_list('public_id', flat=True)
    return JournalSubsidiaryLine.objects.filter(category=JournalSubsidiaryLine.ADVANCE, debit__gt=0,
        entry__status=JournalEntry.POSTED, source_reference__in=[str(value) for value in sources])


def lock_source_case(source):
    """Call before Treasury/source and Finance locks for every refund mutation."""
    source = Source.objects.get(pk=source.pk)
    data = evidence(source)
    if data:
        if _digest(source.proposal) != source.proposal_checksum:
            raise ValidationError('The retained officer refund evidence changed.')
        VoucherCase.objects.select_for_update().get(public_id=data['original_case'])


def movements(detail, *, exclude=None):
    """Signed dated holds; a posted correction releases its hold only on that date."""
    rows = []
    sources = Source.objects.filter(kind=Source.RECEIPT,
        proposal__advance_refund__original_detail=detail.pk).exclude(pk=exclude)
    for source in sources:
        if _digest(source.proposal) != source.proposal_checksum:
            raise ValidationError('The retained officer refund reservation changed.')
        data = source.proposal['advance_refund']
        if (source.finance_department_id != detail.entry.department_id
                or source.proposal['fund_id'] != detail.entry.fund_id
                or Decimal(data['amount']) != source.amount):
            raise ValidationError('Retain the original advance fund and refund amount.')
        if source.status in (Source.REJECTED, Source.WITHDRAWN):
            reviewer = source.reviewed_by_id if source.status == Source.REJECTED else source.withdrawn_by_id
            reason = source.review_reason if source.status == Source.REJECTED else source.withdrawal_reason
            if (not reviewer or reviewer == source.prepared_by_id or not reason
                    or source.posting_requests.exclude(status='cancelled').exists()):
                raise ValidationError('Retain independent rejection/withdrawal before releasing a refund reservation.')
            references = [str(value) for value in source.posting_requests.values_list('public_id', flat=True)]
            if JournalEntry.objects.filter(source_type='collection', source_reference__in=references).exclude(status=JournalEntry.VOIDED).exists():
                raise ValidationError('A refund with an active journal cannot release its reservation by withdrawal.')
            continue
        rows.append((source.source_date, source.amount))
        for correction in source.corrections.filter(status=Source.POSTED):
            from .collection_corrections import corrected_sources
            if source.pk not in corrected_sources(source.treasury_department_id, correction.source_date):
                raise ValidationError('Reconcile the exact refund correction before releasing its reservation.')
            rows.append((correction.source_date, -source.amount))
    return rows


@transaction.atomic
def record(*, actor, detail, variant, received_on, fund_code, receipt_book,
           receipt_number, payer_reference, received_amount, evidence_reference):
    from .collections import require, context, amount, account, financial_row, new_source
    from .advance_applications import capacity
    treasury = require(actor, 'vouchers.prepare_collections')
    detail, recognition, _ = original(detail)
    case = VoucherCase.objects.select_for_update().get(pk=recognition.case_id)
    release_event = case.events.filter(actor_department=treasury,
        action__in=('check_released', 'disbursement_completed')).order_by('pk').first()
    if release_event is None:
        raise PermissionDenied
    treasury = Department.objects.select_for_update().get(pk=treasury.pk)
    variant, fund, rule, snapshot, checksum = context(variant, received_on, fund_code, Source.RECEIPT)
    total = amount(received_amount)
    if fund.pk != detail.entry.fund_id or variant.department_id != detail.entry.department_id:
        raise ValidationError('The refund must retain the original advance Accounting office and fund.')
    if not str(evidence_reference or '').strip():
        raise ValidationError('Retain the actual returned-money receipt evidence.')
    instructions = snapshot['lines']
    cash = [row for row in instructions if row['side'] == Line.DEBIT
            and row['account_source'] == Line.FIXED_ACCOUNT and row['amount_source'] == Line.EVENT_AMOUNT]
    advance = [row for row in instructions if row['side'] == Line.CREDIT
               and row['account_source'] == Line.PRIOR_ADVANCE and row['amount_source'] == Line.EVENT_AMOUNT]
    if (len(instructions) != 2 or len(cash) != 1 or len(advance) != 1
            or not cash[0].get('cash_flow_category') or cash[0]['cash_flow_category'] == 'internal'
            or advance[0].get('cash_flow_category') or advance[0].get('mapping_code')
            or advance[0].get('ledger_account_code')):
        raise ValidationError('Use a reviewed received-cash debit and selected-original-advance credit for this refund.')
    cash_account = account(variant.department_id, cash[0]['ledger_account_code'])
    if cash_account.account_type != 'asset' or cash_account.pk == detail.journal_line.account_id:
        raise ValidationError('Select the actual cash-receipt asset, distinct from the original advance.')
    proof = capacity(detail, received_on, total)
    data = {'schema_version': 1, 'original_case': str(case.public_id), 'original_detail': detail.pk,
            'release_event': release_event.pk, 'treasury_department': treasury.pk,
            'original_entry': str(detail.entry.public_id), 'original_request': str(recognition.public_id),
            'original_jev_number': detail.entry.reference,
            'original_payload_checksum': recognition.payload_checksum, 'officer_key': detail.reference_key,
            'officer_name': detail.reference_label, 'amount': str(total),
            'disbursement': {key: str(value) if isinstance(value, Decimal) else value for key, value in proof.items()}}
    rows = [financial_row(cash_account, total, Line.DEBIT, cash[0]['cash_flow_category']),
            financial_row(detail.journal_line.account, total, Line.CREDIT)]
    proposal = {'schema_version': 1, 'advance_refund': data,
        'payer_reference': detail.reference_label, 'evidence_reference': str(evidence_reference).strip(),
        'posting_rule': str(rule.public_id), 'posting_rule_snapshot': snapshot,
        'posting_rule_checksum': checksum, 'fund_id': fund.pk, 'financial_rows': rows,
        'cash_account_id': cash_account.pk}
    return new_source(actor=actor, treasury=treasury, variant=variant, fund=fund, kind=Source.RECEIPT,
        book=receipt_book, reference=receipt_number, day=received_on, total=total, proposal=proposal)


def validate_source(source, *, check_capacity=True):
    from .advance_applications import capacity
    data = source.proposal.get('advance_refund')
    if not data:
        return
    if _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('The retained officer refund proposal changed.')
    detail, recognition, _ = original(JournalSubsidiaryLine.objects.get(pk=data['original_detail']))
    if (str(recognition.case.public_id) != data['original_case']
            or str(detail.entry.public_id) != data['original_entry'] or detail.entry.reference != data['original_jev_number']
            or str(recognition.public_id) != data['original_request']
            or recognition.payload_checksum != data['original_payload_checksum']
            or source.proposal['fund_id'] != detail.entry.fund_id
            or source.finance_department_id != detail.entry.department_id
            or source.treasury_department_id != data['treasury_department']
            or not recognition.case.events.filter(pk=data['release_event'],
                actor_department_id=source.treasury_department_id,
                action__in=('check_released', 'disbursement_completed')).exists()
            or source.amount != Decimal(data['amount'])
            or data['officer_key'] != detail.reference_key or data['officer_name'] != detail.reference_label):
        raise ValidationError('The refund must retain its exact original advance, officer, office and amount.')
    if check_capacity:
        capacity(detail, source.source_date, source.amount, exclude_refund=source.pk)


def attach(entry, source, request):
    data = source.proposal.get('advance_refund')
    if data:
        detail = JournalSubsidiaryLine.objects.get(pk=data['original_detail'])
        credit = entry.lines.get(credit=source.amount)
        row = JournalSubsidiaryLine(entry=entry, journal_line=credit, category=JournalSubsidiaryLine.ADVANCE,
            reference_key=detail.reference_key, reference_label=detail.reference_label,
            source_code=detail.source_code, source_reference=str(request.public_id), credit=source.amount,
            source_snapshot={'advance_refund': data, 'original_advance_detail': detail.pk,
                             'transaction_type': detail.source_code})
        row.full_clean(); row.save()
    elif source.proposal.get('advance_refund_correction'):
        original_entry = JournalEntry.objects.get(public_id=source.proposal['original_entry'])
        for detail in original_entry.subsidiary_lines.all():
            row = JournalSubsidiaryLine(entry=entry,
                journal_line=entry.lines.get(sequence=detail.journal_line.sequence), category=detail.category,
                reference_key=detail.reference_key, reference_label=detail.reference_label,
                source_code=detail.source_code, source_reference=str(request.public_id),
                debit=detail.credit, credit=detail.debit,
                source_snapshot={'advance_refund_correction': source.proposal['advance_refund_correction'],
                    'original_refund_detail': detail.pk, 'transaction_type': detail.source_code})
            row.full_clean(); row.save()


def validate_journal(entry):
    from .models import CollectionPostingRequest
    retained = entry.source_snapshot.get('collection_payload', {})
    proposal = retained.get('proposal', {})
    data = proposal.get('advance_refund') or proposal.get('advance_refund_correction')
    if not data:
        return
    request = CollectionPostingRequest.objects.select_related('source').get(public_id=entry.source_reference)
    from accounting.posted_evidence import verify_source_link
    verify_source_link(request, entry, source_type=entry.source_type)
    source = request.source
    if proposal != source.proposal or _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('The refund journal must retain its exact Treasury source.')
    subsidiary = list(entry.subsidiary_lines.all())
    if len(subsidiary) != 1:
        raise ValidationError('Retain one exact original-officer subsidiary on the refund.')
    row = subsidiary[0]
    detail = JournalSubsidiaryLine.objects.get(pk=data['original_detail'])
    correction = 'advance_refund_correction' in proposal
    if correction:
        original_entry = JournalEntry.objects.get(public_id=proposal['original_entry'])
        original_detail = original_entry.subsidiary_lines.get()
        if (entry.reversal_of_id != original_entry.pk
                or row.source_snapshot.get('original_refund_detail') != original_detail.pk
                or row.journal_line.sequence != original_detail.journal_line.sequence
                or row.debit != original_detail.credit or row.credit != original_detail.debit):
            raise ValidationError('The refund correction must mirror its exact original subsidiary.')
    elif row.source_snapshot.get('original_advance_detail') != detail.pk:
        raise ValidationError('Retain the exact original advance subsidiary identity.')
    if (row.category != JournalSubsidiaryLine.ADVANCE or row.reference_key != detail.reference_key
            or row.reference_label != detail.reference_label or row.source_code != detail.source_code
            or row.source_reference != str(request.public_id)
            or row.journal_line.account_id != detail.journal_line.account_id
            or row.debit != (source.amount if correction else 0)
            or row.credit != (0 if correction else source.amount)
            or row.source_snapshot.get('advance_refund_correction' if correction else 'advance_refund') != data):
        raise ValidationError('The refund subsidiary must retain its original officer, asset and exact amount.')
    if not correction:
        validate_source(source, check_capacity=entry.status not in (JournalEntry.POSTED, JournalEntry.VOIDED))
