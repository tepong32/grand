"""One receipt total allocated to existing reviewed collection types."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from finance.models import FinanceTransactionVariant
from .models import TreasuryCollectionSource as Source
from .collections import amount, context, receipt_rows
from .remittances import _digest


def merge_cash(groups, row):
    key = row['cash_flow_category']
    if key not in groups:
        groups[key] = dict(row)
    else:
        groups[key]['debit'] = str(Decimal(groups[key]['debit']) + Decimal(row['debit']))


def build(variant, day, fund_code, total, charges, bank=None):
    primary, fund, _, recipe, _ = context(variant, day, fund_code, Source.RECEIPT)
    primary_rows = receipt_rows(primary.department_id, recipe, total, bank)
    cash = next(row for row in primary_rows if Decimal(row['debit']) > 0)
    retained, credits, seen, cash_groups = [], [], set(), {}
    for supplied in charges:
        try:
            component = FinanceTransactionVariant.objects.get(public_id=supplied['variant'])
        except (FinanceTransactionVariant.DoesNotExist, ValueError, TypeError, KeyError, ValidationError):
            raise ValidationError('Choose a reviewed collection type for each charge.')
        if component.pk in seen or component.department_id != primary.department_id or component.release_id != primary.release_id:
            raise ValidationError('Use each charge type once from the same approved Accounting setup.')
        seen.add(component.pk)
        value = amount(supplied.get('amount'))
        component, component_fund, rule, snapshot, checksum = context(component, day, fund_code, Source.RECEIPT)
        rows = receipt_rows(primary.department_id, snapshot, value, bank)
        debit = next(row for row in rows if Decimal(row['debit']) > 0)
        if component_fund.pk != fund.pk or any(debit[k] != cash[k] for k in ('account_id','account_code')):
            raise ValidationError('Combined charges must use the same collection cash account and fund.')
        merge_cash(cash_groups, debit)
        credits.append(next(row for row in rows if Decimal(row['credit']) > 0))
        retained.append({'variant':str(component.public_id),'code':component.code,'label':component.label,
            'amount':str(value),'posting_rule':str(rule.public_id),'posting_rule_snapshot':snapshot,
            'posting_rule_checksum':checksum})
    if not retained or sum((Decimal(row['amount']) for row in retained),Decimal('0')) != total:
        raise ValidationError('The charge amounts must equal the one actual receipt total.')
    return [*cash_groups.values(),*credits], retained


def validate(source, *, review=False):
    charges = source.proposal.get('charges')
    if not charges or source.kind != Source.RECEIPT:
        return
    if source.proposal.get('advance_refund'):
        raise ValidationError('Keep the original officer advance refund separate from ordinary collection charges.')
    if review:
        rows, current = build(source.transaction_variant, source.source_date, source.fund_code, source.amount, charges, source.proposal.get('receiving_bank'))
        if current != charges or rows != source.proposal['financial_rows']:
            raise ValidationError('A charge recipe changed. Reject this receipt and prepare a current successor.')
        return
    # After approval, use the pinned recipes rather than a later setup version.
    primary_rows = receipt_rows(source.finance_department_id,source.proposal['posting_rule_snapshot'],source.amount,source.proposal.get('receiving_bank'))
    cash = next(row for row in primary_rows if Decimal(row['debit']) > 0)
    credits, seen, total, cash_groups = [], set(), Decimal('0'), {}
    for charge in charges:
        if charge['variant'] in seen or _digest(charge['posting_rule_snapshot']) != charge['posting_rule_checksum']:
            raise ValidationError('Retain each distinct approved charge recipe and checksum.')
        seen.add(charge['variant'])
        value=amount(charge['amount']); total+=value
        rows=receipt_rows(source.finance_department_id,charge['posting_rule_snapshot'],value,source.proposal.get('receiving_bank'))
        debit=next(row for row in rows if Decimal(row['debit']) > 0)
        if any(debit[k]!=cash[k] for k in ('account_id','account_code')):
            raise ValidationError('Retain the approved common collection cash account.')
        merge_cash(cash_groups, debit)
        credits.append(next(row for row in rows if Decimal(row['credit']) > 0))
    if total!=source.amount or [*cash_groups.values(),*credits]!=source.proposal['financial_rows']:
        raise ValidationError('The retained charge breakdown must reproduce the receipt total and financial rows.')
