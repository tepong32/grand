"""Explicit bank credits retained through collection review and posting."""
from decimal import Decimal
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from finance.models import FinancePostingRuleLine as Line
from .receipt_banks import bank_snapshot, receiving_account


def capture(owner_id, day, bank_id, reference):
    reference = str(reference or '').strip()
    if not bank_id:
        if reference:
            raise ValidationError('Choose the receiving bank for this bank transaction reference.')
        return {}
    if not reference or len(reference) > 160:
        raise ValidationError('Retain the actual bank credit reference, up to 160 characters.')
    return {'receiving_bank': bank_snapshot(SimpleNamespace(finance_department_id=owner_id), bank_id, day),
            'bank_transaction_reference': reference}


def debit_account(owner_id, instruction, bank=None):
    from .collections import account
    if bank:
        if (instruction['account_source'] != Line.BANK_MAPPING
                or instruction.get('ledger_account_code') or instruction.get('mapping_code')):
            raise ValidationError('A bank-transfer receipt requires the reviewed receiving-bank debit recipe.')
        return receiving_account(SimpleNamespace(finance_department_id=owner_id), bank, None)
    if instruction['account_source'] != Line.FIXED_ACCOUNT:
        raise ValidationError('Choose the actual receiving bank for this bank-mapped receipt recipe.')
    return account(owner_id, instruction['ledger_account_code'])


def validate(source, *, review=False):
    from .models import TreasuryCollectionSource as Source
    if source.kind != Source.RECEIPT:
        return
    bank = source.proposal.get('receiving_bank')
    reference = source.proposal.get('bank_transaction_reference')
    if not bank and not reference:
        return
    if not bank or not str(reference or '').strip() or len(reference) > 160:
        raise ValidationError('Retain both the receiving bank and actual bank credit reference.')
    if review and bank_snapshot(source, bank['configuration_item'], source.source_date) != bank:
        raise ValidationError('The receiving bank mapping changed before independent receipt review.')
    instructions = source.proposal['posting_rule_snapshot']['lines']
    debits = [row for row in instructions if row['side'] == Line.DEBIT]
    if len(debits) != 1 or debits[0]['amount_source'] != Line.EVENT_AMOUNT:
        raise ValidationError('Retain one reviewed bank debit for the actual receipt amount.')
    ledger = debit_account(source.finance_department_id, debits[0], bank)
    rows = [row for row in source.proposal['financial_rows'] if Decimal(row['debit']) > 0]
    if (source.proposal['cash_account_id'] != ledger.pk or not rows
            or sum((Decimal(row['debit']) for row in rows), Decimal('0')) != source.amount
            or any(row['account_id'] != ledger.pk or row['account_code'] != ledger.code
                   or Decimal(row['credit']) or not row['cash_flow_category']
                   or row['cash_flow_category'] == 'internal' for row in rows)):
        raise ValidationError('The receipt must retain its actual external bank credit exactly.')
