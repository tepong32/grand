"""Principal receipts applied once to a specific posted incoming-cheque return."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from accounting.models import JournalEntry
from departments.models import Department
from finance.models import FinancePostingRuleLine as Line
from .models import TreasuryCollectionSource as Source
from .collections import require, context, amount, account, financial_row, new_source
from .remittances import _digest

OR_DISPOSITIONS = {'surrendered':'Original receipt surrendered', 'loss_affidavit':'Loss affidavit retained'}


def original(source, day):
    from .collection_corrections import original_journal
    if (source.kind != Source.CHEQUE_RETURN or source.status != Source.POSTED
            or not isinstance(day, date) or not source.source_date <= day <= timezone.localdate()):
        raise ValidationError('Select a posted bank return and an actual subsequent principal receipt date.')
    if source.corrections.filter(status__in=(Source.PROPOSED,Source.APPROVED,Source.POSTED)).exists():
        raise ValidationError('Resolve the bank-return correction before receiving its redemption.')
    entry, request = original_journal(source)
    debits = list(entry.lines.filter(debit__gt=0).select_related('account'))
    if len(debits) != 1 or debits[0].debit != source.amount or entry.reversal_entries.exclude(status=entry.VOIDED).exists():
        raise ValidationError('Retain one exact original return receivable and resolve any reversal first.')
    return entry, {'return_source':str(source.public_id), 'return_checksum':source.proposal_checksum,
        'return_entry':str(entry.public_id), 'return_request':str(request.public_id),
        'return_request_checksum':request.payload_checksum, 'receivable_line':debits[0].pk,
        'receivable_account':debits[0].account_id, 'receivable_code':debits[0].account.code,
        'principal':str(source.amount), 'fund_id':entry.fund_id,
        'original_receipt':str(source.return_receipt.public_id),
        'original_receipt_checksum':source.return_receipt.proposal_checksum,
        'cash_flow_purpose':source.proposal['original_cheque']['collection_purposes'][0]}


def available(source, day, *, exclude=None):
    from .collection_corrections import corrected_sources
    corrected = None
    for receipt in source.redemption_receipts.exclude(pk=exclude).order_by('pk'):
        if _digest(receipt.proposal) != receipt.proposal_checksum:
            raise ValidationError('The retained redemption receipt changed.')
        if receipt.status in (Source.REJECTED,Source.WITHDRAWN):
            reviewer = receipt.reviewed_by_id if receipt.status == Source.REJECTED else receipt.withdrawn_by_id
            reason = receipt.review_reason if receipt.status == Source.REJECTED else receipt.withdrawal_reason
            if (not reviewer or reviewer == receipt.prepared_by_id or not reason
                    or receipt.posting_requests.exclude(status='cancelled').exists()):
                raise ValidationError('Retain independent withdrawal and resolved posting drafts before releasing the principal hold.')
            references = [str(value) for value in receipt.posting_requests.values_list('public_id',flat=True)]
            if JournalEntry.objects.filter(source_type='collection',source_reference__in=references).exclude(status='voided').exists():
                raise ValidationError('Resolve the original redemption journal before releasing its principal hold.')
            continue
        if receipt.redemption_active:
            raise ValidationError('This returned-cheque principal already has a redemption receipt or pending reservation.')
        if corrected is None:
            corrected = corrected_sources(source.treasury_department_id,day)
        if receipt.pk not in corrected:
            raise ValidationError('Only a reconciled exact correction can release principal, from its actual correction date.')


def protect(source, day):
    if source.kind == Source.CHEQUE_RETURN:
        available(source, day)


def rows(owner, snapshot, total, proof):
    instructions = snapshot.get('lines', [])
    cash = [row for row in instructions if row['side'] == Line.DEBIT and row['account_source'] == Line.FIXED_ACCOUNT
        and row['amount_source'] == Line.EVENT_AMOUNT]
    credits = [row for row in instructions if row['side'] == Line.CREDIT and row['account_source'] == Line.RETURN_RECEIVABLE
        and row['amount_source'] == Line.EVENT_AMOUNT]
    if (len(instructions) != 2 or len(cash) != 1 or len(credits) != 1
            or cash[0].get('cash_flow_category') != proof['cash_flow_purpose']
            or credits[0].get('cash_flow_category') or credits[0].get('mapping_code')
            or credits[0].get('ledger_account_code')):
        raise ValidationError('Use a reviewed actual-cash debit and selected-return-receivable credit, preserving the original cash-flow purpose.')
    cash_account = account(owner,cash[0]['ledger_account_code'])
    debtor = account(owner,proof['receivable_code'])
    if cash_account.account_type != 'asset' or debtor.pk != proof['receivable_account'] or cash_account.pk == debtor.pk:
        raise ValidationError('Retain the original receivable and a separate actual collection asset.')
    return [financial_row(cash_account,total,Line.DEBIT,proof['cash_flow_purpose']),
        financial_row(debtor,total,Line.CREDIT)]


@transaction.atomic
def capture(*, original_return, actor, variant, received_on, received_amount, receipt_book,
            receipt_number, evidence_reference, old_receipt_disposition, old_receipt_evidence, cheque=None):
    office = require(actor,'vouchers.prepare_collections')
    if office.pk != original_return.treasury_department_id:
        raise PermissionDenied
    Department.objects.select_for_update().get(pk=office.pk)
    source = Source.objects.select_for_update().get(pk=original_return.pk)
    _, proof = original(source,received_on)
    available(source,received_on)
    variant,fund,rule,snapshot,checksum = context(variant,received_on,source.fund_code,Source.RECEIPT)
    total = amount(received_amount)
    if total != source.amount or fund.pk != proof['fund_id'] or variant.department_id != source.finance_department_id:
        raise ValidationError('Redeem the whole original principal in its original fund and Accounting office.')
    if (old_receipt_disposition not in OR_DISPOSITIONS
            or not str(old_receipt_evidence or '').strip() or not str(evidence_reference or '').strip()):
        raise ValidationError('Retain the actual receipt evidence and original OR surrender or loss-affidavit evidence.')
    if cheque and cheque.get('kind') not in ('manager','cashier'):
        raise ValidationError('Cheque redemption requires an explicitly identified manager’s or cashier’s cheque.')
    from .collection_cheques import capture as capture_cheque
    instrument = capture_cheque(office,received_on,cheque)
    financial = rows(source.finance_department_id,snapshot,total,proof)
    proposal = {'schema_version':1, 'payer_reference':source.return_receipt.proposal['payer_reference'],
        'evidence_reference':str(evidence_reference).strip(), 'redemption':proof,
        'old_receipt_disposition':old_receipt_disposition,'old_receipt_evidence':str(old_receipt_evidence).strip(),
        'posting_rule':str(rule.public_id),'posting_rule_snapshot':snapshot,'posting_rule_checksum':checksum,
        'fund_id':fund.pk,'financial_rows':financial,'cash_account_id':financial[0]['account_id']}
    if instrument:
        proposal['cheque'] = instrument
    return new_source(actor=actor,treasury=office,variant=variant,fund=fund,kind=Source.RECEIPT,
        book=receipt_book,reference=receipt_number,day=received_on,total=total,proposal=proposal,redemption_return=source)


def validate(source, *, lock_finance=False):
    proof = source.proposal.get('redemption')
    if not proof and not source.redemption_return_id:
        return
    if (not proof or not source.redemption_return_id or source.kind != Source.RECEIPT
            or _digest(source.proposal) != source.proposal_checksum):
        raise ValidationError('Retain the exact redemption source and its original returned-cheque identity.')
    entry, current = original(source.redemption_return, source.source_date)
    if lock_finance:
        JournalEntry.objects.select_for_update().get(pk=entry.pk)
        _, current = original(source.redemption_return,source.source_date)
    expected = rows(source.finance_department_id,source.proposal['posting_rule_snapshot'],source.amount,proof)
    if (proof != current or source.amount != Decimal(proof['principal']) or source.proposal['fund_id'] != entry.fund_id
            or source.finance_department_id != entry.department_id
            or source.treasury_department_id != source.redemption_return.treasury_department_id
            or source.fund_code != source.redemption_return.fund_code
            or source.proposal.get('cash_account_id') != expected[0]['account_id']
            or source.proposal.get('payer_reference') != source.redemption_return.return_receipt.proposal['payer_reference']
            or source.proposal['financial_rows'] != expected
            or source.proposal.get('old_receipt_disposition') not in OR_DISPOSITIONS
            or not source.proposal.get('old_receipt_evidence','').strip()
            or (source.proposal.get('cheque') and source.proposal['cheque'].get('kind') not in ('manager','cashier'))):
        raise ValidationError('Retain the original whole principal, fund, receivable and approved redemption recipe.')
    if source.status in (Source.PROPOSED,Source.APPROVED):
        if not source.redemption_active:
            raise ValidationError('Retain the active principal reservation before posting.')
        available(source.redemption_return,source.source_date,exclude=source.pk)


def validate_journal(entry):
    proposal = entry.source_snapshot.get('collection_payload',{}).get('proposal',{})
    if not proposal.get('redemption'):
        return
    source = Source.objects.get(public_id=entry.source_snapshot['collection_source'])
    validate(source)
    if proposal != source.proposal or entry.reversal_of_id:
        raise ValidationError('The redemption journal must retain the exact independently reviewed principal receipt.')


def settlement(receipt):
    if not receipt.redemption_active and receipt.status == Source.POSTED:
        return {'status':'Receipt corrected; original principal reservation retired','date':''}
    if receipt.status != Source.POSTED or not receipt.redemption_active:
        return {'status':'Awaiting posted principal receipt','date':''}
    if receipt.corrections.filter(status__in=(Source.PROPOSED,Source.APPROVED,Source.POSTED)).exists():
        return {'status':'Receipt correction in progress','date':''}
    from .collections import posted_receipt
    posted_receipt(receipt)
    if receipt.cheque_returns.filter(status__in=(Source.PROPOSED,Source.APPROVED,Source.POSTED)).exists():
        return {'status':'Replacement cheque return; follow the linked bank-return source','date':''}
    if not receipt.proposal.get('cheque'):
        return {'status':'Principal received in cash','date':receipt.source_date.isoformat()}
    from .cheque_clearing import verify
    clearance = receipt.cheque_clearances.filter(status='approved').first()
    if not clearance:
        return {'status':'Replacement cheque received; bank clearing pending','date':''}
    verify(clearance)
    return {'status':'Replacement cheque clearing confirmed','date':clearance.cleared_on.isoformat()}


def history(source):
    result = []
    for row in source.redemption_receipts.order_by('pk'):
        if _digest(row.proposal) != row.proposal_checksum:
            raise ValidationError('The retained principal receipt changed.')
        result.append({'source':str(row.public_id),'book':row.book_reference,'reference':row.document_reference,
            'amount':str(row.amount),'date':row.source_date.isoformat(),'checksum':row.proposal_checksum,
            'settlement':settlement(row)})
    return result
