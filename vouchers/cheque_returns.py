"""Actual incoming bank debits, retained beside their original whole-cheque deposit."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q

from accounting.models import JournalEntry
from departments.models import Department
from finance.models import FinancePostingRuleLine as Line
from .models import TreasuryCollectionSource as Source
from .collections import require, context, amount, account, financial_row, new_source
from .cheque_clearing import source_evidence
from .remittances import _digest


ACTIVE = (Source.PROPOSED, Source.APPROVED, Source.POSTED)


def protect(source):
    if Source.objects.filter(Q(return_receipt=source) | Q(return_deposit=source),
            kind=Source.CHEQUE_RETURN, status__in=ACTIVE).exists():
        raise ValidationError('Resolve the retained bank return before changing its receipt, deposit or clearing evidence.')


def rows(owner, snapshot, total, bank, collection_cash=(), collection_purposes=()):
    instructions = snapshot.get('lines', [])
    if (len(instructions) != 2 or {r['side'] for r in instructions} != {Line.DEBIT, Line.CREDIT}
            or any(r['amount_source'] != Line.EVENT_AMOUNT for r in instructions)):
        raise ValidationError('Use a reviewed whole-amount receivable debit and original-bank credit return recipe.')
    result = []
    for instruction in instructions:
        purpose = instruction.get('cash_flow_category', '')
        if instruction['side'] == Line.CREDIT:
            if (instruction['account_source'] != Line.BANK_MAPPING or instruction.get('mapping_code')
                    or not purpose or purpose == 'internal'):
                raise ValidationError('Credit the original deposit bank with an explicit external cash-flow purpose; do not override its mapping.')
            if set(collection_purposes) != {purpose}:
                raise ValidationError('Retain the original collection cash-flow purpose. Mixed-purpose returns need explicit component treatments.')
            ledger = account(owner, bank['ledger_account_code'])
            if ledger.pk != bank['ledger_account_id'] or ledger.account_type != 'asset':
                raise ValidationError('Retain the original deposit bank ledger account.')
        else:
            if instruction['account_source'] != Line.FIXED_ACCOUNT or purpose:
                raise ValidationError('Select the reviewed non-cash receivable account explicitly.')
            ledger = account(owner, instruction['ledger_account_code'])
            if ledger.account_type != 'asset' or ledger.pk in (*collection_cash, bank['ledger_account_id']):
                raise ValidationError('Select a separate reviewed receivable asset, not the bank itself.')
        result.append(financial_row(ledger, total, instruction['side'], purpose))
    return result


def original_evidence(receipt, deposit, day):
    evidence = source_evidence(receipt, deposit, day)
    if receipt.proposal.get('advance_refund'):
        raise ValidationError('Officer cheque refund returns require their dependent dated-capacity adapter.')
    evidence['charges'] = receipt.proposal.get('charges', [])
    evidence['collection_cash_accounts'] = sorted({row['account_id'] for row in receipt.proposal['financial_rows']
        if row.get('cash_flow_category')})
    evidence['collection_purposes'] = sorted({row['cash_flow_category'] for row in receipt.proposal['financial_rows']
        if row.get('cash_flow_category')})
    return evidence


def available(receipt, day, *, exclude=None):
    from .collection_corrections import corrected_sources
    prior = Source.objects.filter(return_receipt=receipt, kind=Source.CHEQUE_RETURN).exclude(pk=exclude)
    if prior.filter(status__in=ACTIVE).exists():
        raise ValidationError('Resolve the existing cheque bank return first.')
    retired = list(prior.filter(status=Source.CORRECTED))
    if retired:
        corrected = corrected_sources(receipt.treasury_department_id, day)
        if any(row.pk not in corrected for row in retired):
            raise ValidationError('A later correction cannot authorize an earlier replacement bank-return entry.')
    if receipt.cheque_clearances.filter(status='proposed').exists():
        raise ValidationError('Resolve the pending clearing proposal before recording a conflicting bank return.')
    if receipt.cheque_clearances.filter(status='approved', cleared_on__gt=day).exists():
        raise ValidationError('Reconcile clearing evidence dated after this bank debit before recording the return.')


@transaction.atomic
def capture(*, receipt, deposit, actor, variant, debited_on, debit_amount,
            bank_reference, reason, evidence_reference, applicability_reference):
    office = require(actor, 'vouchers.prepare_collections')
    if office.pk != receipt.treasury_department_id:
        raise PermissionDenied
    Department.objects.select_for_update().get(pk=office.pk)
    sources = {row.pk: row for row in Source.objects.select_for_update().filter(
        pk__in=(receipt.pk, deposit.pk)).order_by('pk')}
    receipt, deposit = sources[receipt.pk], sources[deposit.pk]
    protect(receipt)
    evidence = original_evidence(receipt, deposit, debited_on)
    available(receipt, debited_on)
    total = amount(debit_amount)
    if total != receipt.amount:
        raise ValidationError('Retain the whole cheque principal debit. Partial debits and fees need separate bank reconciliation.')
    variant, fund, rule, snapshot, checksum = context(variant, debited_on, receipt.fund_code, Source.CHEQUE_RETURN)
    if variant.department_id != receipt.finance_department_id or fund.pk != evidence['fund_id']:
        raise ValidationError('The return recipe must belong to the original Accounting office and fund.')
    values = {}
    for key, value in dict(bank_reference=bank_reference, reason=reason,
            evidence_reference=evidence_reference, applicability_reference=applicability_reference).items():
        value = str(value or '').strip()
        if not value or len(value) > (80 if key == 'bank_reference' else 4000):
            raise ValidationError('Retain the bank debit reference (up to 80 characters), reason, evidence and recipe applicability basis.')
        values[key] = value
    proposal = dict(schema_version=1, **values, original_cheque=evidence,
        receiving_bank=evidence['bank'], posting_rule=str(rule.public_id), posting_rule_snapshot=snapshot,
        posting_rule_checksum=checksum, fund_id=fund.pk,
        financial_rows=rows(variant.department_id, snapshot, total, evidence['bank'],
            evidence['collection_cash_accounts'], evidence['collection_purposes']))
    return new_source(actor=actor, treasury=office, variant=variant, fund=fund,
        kind=Source.CHEQUE_RETURN, book='', reference=values['bank_reference'], day=debited_on,
        total=total, proposal=proposal, return_receipt=receipt, return_deposit=deposit)


def validate(source, *, lock_finance=False):
    if source.kind != Source.CHEQUE_RETURN:
        return
    if not source.return_receipt_id or not source.return_deposit_id or _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('Retain the original receipt/deposit and unchanged return proposal.')
    evidence = original_evidence(source.return_receipt, source.return_deposit, source.source_date)
    if source.status in ACTIVE:
        available(source.return_receipt, source.source_date, exclude=source.pk)
    if lock_finance:
        list(JournalEntry.objects.select_for_update().filter(
            public_id__in=(evidence['receipt_entry'], evidence['deposit_entry'])).order_by('pk'))
        evidence = original_evidence(source.return_receipt, source.return_deposit, source.source_date)
    if (source.proposal.get('original_cheque') != evidence
            or source.proposal.get('receiving_bank') != evidence['bank']
            or source.amount != source.return_receipt.amount
            or source.finance_department_id != source.return_receipt.finance_department_id
            or source.treasury_department_id != source.return_receipt.treasury_department_id
            or source.proposal['fund_id'] != evidence['fund_id']
            or source.fund_code != source.return_receipt.fund_code
            or source.proposal['financial_rows'] != rows(source.finance_department_id,
                source.proposal['posting_rule_snapshot'], source.amount, evidence['bank'],
                evidence['collection_cash_accounts'], evidence['collection_purposes'])):
        raise ValidationError('The return must reproduce its original whole-cheque bank effect and approved counterpart.')


def validate_journal(entry):
    if entry.source_type != 'cheque_return':
        return
    source = Source.objects.get(public_id=entry.source_snapshot['collection_source'])
    validate(source)
    retained = entry.source_snapshot.get('collection_payload', {})
    if (entry.reversal_of_id or entry.fund_id != source.proposal['fund_id']
            or retained.get('proposal') != source.proposal
            or retained.get('proposal_checksum') != source.proposal_checksum):
        raise ValidationError('Bank dishonour is a new source event in the original fund, not a source-error reversal.')


def history(source):
    result = []
    for row in Source.objects.filter(Q(return_receipt=source) | Q(return_deposit=source)).order_by('pk'):
        if _digest(row.proposal) != row.proposal_checksum:
            raise ValidationError('The retained bank return evidence changed.')
        result.append({'source':str(row.public_id), 'date':row.source_date.isoformat(),
            'reference':row.document_reference, 'amount':str(row.amount), 'status':row.get_status_display(),
            'checksum':row.proposal_checksum})
    return result
