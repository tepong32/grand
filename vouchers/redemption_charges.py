"""Explicit assessed charges alongside an unchanged returned-cheque principal."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from finance.models import FinanceTransactionVariant
from .collections import amount, context, receipt_rows
from .collection_charges import merge_cash
from .models import TreasuryCollectionSource as Source
from .remittances import _digest


def build(*, owner, release_id, fund_id, day, fund_code, principal_rows, charges, current=False):
    """Resolve current recipes before approval; reproduce only pinned recipes afterward."""
    cash, credits, retained, seen = {}, [], [], set()
    for row in principal_rows:
        if Decimal(row['debit']) > 0:
            merge_cash(cash, row)
        else:
            credits.append(row)
    receipt_cash = next(iter(cash.values()))
    if not isinstance(charges, (list, tuple)):
        raise ValidationError('Enter each assessed charge as a separate collection component.')
    for supplied in charges:
        if not isinstance(supplied, dict):
            raise ValidationError('Retain the assessed charge and its supporting references.')
        references = {}
        for key in ('authority_reference', 'assessment_reference'):
            value = supplied.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 4000:
                raise ValidationError('Each additional charge needs its applicable authority and actual assessment reference.')
            references[key] = value.strip()
        value = amount(supplied.get('amount'))
        if current:
            try:
                variant = FinanceTransactionVariant.objects.get(public_id=supplied.get('variant'))
            except (FinanceTransactionVariant.DoesNotExist, ValueError, TypeError, ValidationError):
                raise ValidationError('Choose a reviewed collection type for each assessed charge.')
            if variant.department_id != owner or variant.release_id != release_id:
                raise ValidationError('Additional charges must use the same approved Accounting setup as the principal.')
            variant, fund, rule, snapshot, checksum = context(variant, day, fund_code, Source.RECEIPT)
            if fund.pk != fund_id:
                raise ValidationError('Additional charges must retain the original principal fund.')
            component = {'variant': str(variant.public_id), 'code': variant.code, 'label': variant.label,
                'amount': str(value), 'posting_rule': str(rule.public_id), 'posting_rule_snapshot': snapshot,
                'posting_rule_checksum': checksum, **references}
        else:
            component = supplied
        snapshot = component.get('posting_rule_snapshot')
        if (not isinstance(snapshot, dict) or _digest(snapshot) != component.get('posting_rule_checksum')
                or snapshot.get('variant_public_id') != component.get('variant')
                or snapshot.get('rule_public_id') != component.get('posting_rule')
                or snapshot.get('release_id') != release_id or not snapshot.get('authority_reference', '').strip()
                or component.get('variant') in seen):
            raise ValidationError('Retain each distinct reviewed charge recipe, authority and checksum.')
        seen.add(component['variant'])
        financial = receipt_rows(owner, snapshot, value)
        debit = next(row for row in financial if Decimal(row['debit']) > 0)
        if any(debit[key] != receipt_cash[key] for key in ('account_id', 'account_code')):
            raise ValidationError('Principal and additional charges must use the same actual collection asset.')
        merge_cash(cash, debit)
        credits.append(next(row for row in financial if Decimal(row['credit']) > 0))
        retained.append(component)
    return [*cash.values(), *credits], retained
