"""Exact original cash-purpose amounts for mixed-purpose cheque returns and redemption."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from finance.cash_flows import CASH_FLOW_CHOICES


COMPONENT_AMOUNT = 'original_cash_component'


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0 or result != result.quantize(Decimal('0.01')):
            raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Retain positive exact-cent original cash component amounts.')


def amounts(components, total):
    """Verify a complete immutable cash-purpose allocation, with no residual inference."""
    allowed = set(dict(CASH_FLOW_CHOICES)) - {'', 'internal'}
    result = {}
    for component in components:
        purpose = component.get('purpose')
        if purpose not in allowed or purpose in result:
            raise ValidationError('Retain each original external cash-flow purpose exactly once.')
        result[purpose] = money(component.get('amount'))
    if not result or sum(result.values(), Decimal('0')) != money(total):
        raise ValidationError('Original cash components must reproduce the whole cheque principal.')
    return result


def capture(receipt):
    """Caller first verifies the unchanged posted receipt and original source link."""
    values = {}
    for row in receipt.proposal['financial_rows']:
        purpose = row.get('cash_flow_category')
        if not purpose:
            continue
        if Decimal(row['credit']) != 0:
            raise ValidationError('Retain actual original collection cash debits as component evidence.')
        values[purpose] = values.get(purpose, Decimal('0')) + money(row['debit'])
    components = [{'purpose':purpose,'amount':str(value)} for purpose,value in sorted(values.items())]
    amounts(components,receipt.amount)
    return components


def return_rows(owner, snapshot, total, bank, collection_cash, components):
    from finance.models import FinancePostingRuleLine as Line
    from vouchers.collections import account, financial_row
    values = amounts(components,total)
    instructions = snapshot.get('lines',[])
    debits = [row for row in instructions if row['side'] == Line.DEBIT]
    credits = [row for row in instructions if row['side'] == Line.CREDIT]
    if (len(debits) != 1 or len(credits) != len(values) or len(instructions) != len(values)+1
            or debits[0]['account_source'] != Line.FIXED_ACCOUNT
            or debits[0]['amount_source'] != Line.EVENT_AMOUNT or debits[0].get('cash_flow_category')
            or {row.get('cash_flow_category') for row in credits} != set(values)
            or any(row['account_source'] != Line.BANK_MAPPING or row['amount_source'] != COMPONENT_AMOUNT
                or row.get('mapping_code') or row.get('ledger_account_code') for row in credits)):
        raise ValidationError('Review one whole-principal receivable debit and one original-bank credit for each original cash purpose.')
    debtor = account(owner,debits[0]['ledger_account_code'])
    bank_account = account(owner,bank['ledger_account_code'])
    if (debtor.account_type != 'asset' or debtor.pk in (*collection_cash,bank['ledger_account_id'])
            or bank_account.pk != bank['ledger_account_id'] or bank_account.account_type != 'asset'):
        raise ValidationError('Retain the original bank and a separate reviewed receivable.')
    return [financial_row(debtor,total,Line.DEBIT) if row['side'] == Line.DEBIT else
        financial_row(bank_account,values[row['cash_flow_category']],Line.CREDIT,row['cash_flow_category'])
        for row in instructions]


def redemption_rows(owner,snapshot,total,proof):
    from finance.models import FinancePostingRuleLine as Line
    from vouchers.collections import account, financial_row
    values = amounts(proof['cash_flow_components'],total)
    instructions = snapshot.get('lines',[])
    debits = [row for row in instructions if row['side'] == Line.DEBIT]
    credits = [row for row in instructions if row['side'] == Line.CREDIT]
    if (len(credits) != 1 or len(debits) != len(values) or len(instructions) != len(values)+1
            or credits[0]['account_source'] != Line.RETURN_RECEIVABLE
            or credits[0]['amount_source'] != Line.EVENT_AMOUNT or credits[0].get('cash_flow_category')
            or credits[0].get('mapping_code') or credits[0].get('ledger_account_code')
            or {row.get('cash_flow_category') for row in debits} != set(values)
            or any(row['account_source'] != Line.FIXED_ACCOUNT or row['amount_source'] != COMPONENT_AMOUNT
                or row.get('mapping_code') for row in debits)):
        raise ValidationError('Review one actual collection asset debit per original cash purpose and one selected principal-receivable credit.')
    debtor = account(owner,proof['receivable_code'])
    cash_accounts = [account(owner,row['ledger_account_code']) for row in debits]
    if (len({row.pk for row in cash_accounts}) != 1 or cash_accounts[0].account_type != 'asset'
            or debtor.pk != proof['receivable_account'] or debtor.pk == cash_accounts[0].pk):
        raise ValidationError('Retain one actual receipt asset, separate from the original principal receivable.')
    return [financial_row(cash_accounts[0],values[row['cash_flow_category']],Line.DEBIT,row['cash_flow_category'])
        for row in debits] + [financial_row(debtor,total,Line.CREDIT)]
