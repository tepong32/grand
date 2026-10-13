"""Explicit complete category/entity proposals; no independent certification."""
from copy import deepcopy
from decimal import Decimal
import re

from django.core.exceptions import ValidationError

from . import budget_native_actuals as actuals
from .summary_actuals import RECEIPTS, EXPENDITURES, text
from .budget_actuals import money
from .cash_classifications import checksum


def _rows(supplied, totals, active):
    if not isinstance(supplied, list) or len(supplied) != len(totals):
        raise ValidationError('Declare every required leaf category exactly once.')
    result, seen = [], set()
    for row in supplied:
        if not isinstance(row, dict) or set(row) != {'category', 'amount', 'coverage', 'basis'}:
            raise ValidationError('Retain explicit category, amount, activity coverage and evidence basis.')
        key = row['category']
        if not isinstance(key, str) or key not in totals or key in seen:
            raise ValidationError('Use each required category exactly once; omit no leaf and add no subtotal.')
        seen.add(key)
        amount = money(row['amount'])
        expected = 'activity' if key in active else 'no_activity'
        if amount != totals[key] or row['coverage'] != expected:
            raise ValidationError('Category declarations must reproduce activity, including net-zero movements.')
        result.append(dict(category=key, amount=str(amount), coverage=expected,
            basis=text(row['basis'], 'the explicit category coverage basis', 1000)))
    return sorted(result, key=lambda row: row['category'])


def propose(captured, *, entity, class_mappings, receipt_rows, expenditure_rows):
    body = actuals.verify(captured)
    if not body['classification_complete']:
        raise ValidationError('Complete both financial source classifications before declaring category coverage.')
    if (not isinstance(entity, dict) or set(entity) != {'key', 'label', 'full_fund', 'basis'}
            or entity['full_fund'] is not True):
        raise ValidationError('Explicitly declare the named reporting entity and complete Fund coverage.')
    key = text(entity['key'], 'General Fund or actual enterprise identity', 80).lower()
    if key != 'general' and not re.fullmatch(r'enterprise:[a-z0-9][a-z0-9_-]{0,60}', key):
        raise ValidationError('Select General Fund or an explicitly named actual LGU enterprise.')
    retained_entity = dict(key=key, label=text(entity['label'], 'the reporting entity designation', 255),
        full_fund=True, basis=text(entity['basis'], 'the full Fund/entity coverage basis', 1000))
    statement = body['expenditures']['payload']
    classes = {row['expense_class'] for row in statement['rows']}
    if not isinstance(class_mappings, list) or len(class_mappings) != len(classes):
        raise ValidationError('Explicitly map every retained expenditure class exactly once.')
    mappings = {}
    for row in class_mappings:
        if not isinstance(row, dict) or set(row) != {'expense_class', 'category', 'basis'}:
            raise ValidationError('Retain the exact expenditure class, required category and mapping basis.')
        label, category = row['expense_class'], row['category']
        if (not isinstance(label, str) or label not in classes or label in mappings
                or not isinstance(category, str) or category not in EXPENDITURES):
            raise ValidationError('Map each exact retained expenditure class to one required leaf category.')
        mappings[label] = dict(expense_class=label, category=category,
            basis=text(row['basis'], 'the explicit expenditure mapping basis', 1000))
    expense_totals = {key: Decimal('0.00') for key in EXPENDITURES}
    expense_active = set()
    for row in statement['rows']:
        category = mappings[row['expense_class']]['category']
        expense_totals[category] += money(row['amount'])
        if row['components']:
            expense_active.add(category)
    receipts = body['receipts']['payload']
    receipt_active = {row['allocation']['category'] for row in receipts['bridge']
        if row['allocation']['disposition'] == 'include'}
    payload = {'schema': 1, 'kind': 'native_budget_actuals_coverage_proposal',
        'actuals': deepcopy(captured), 'entity': retained_entity,
        'class_mappings': [mappings[key] for key in sorted(mappings)],
        'receipt_rows': _rows(receipt_rows,
            {key: money(receipts['category_totals'][key]) for key in RECEIPTS}, receipt_active),
        'expenditure_rows': _rows(expenditure_rows, expense_totals, expense_active),
        'review_status': 'not_reviewed', 'certification_status': 'not_certified',
        'receipt_total': None, 'expenditure_total': None}
    return {'payload': payload, 'checksum': checksum(payload)}


def verify(proposal):
    try:
        body = proposal['payload']
        reproduced = propose(body['actuals'], entity=body['entity'], class_mappings=body['class_mappings'],
            receipt_rows=body['receipt_rows'], expenditure_rows=body['expenditure_rows'])
        if proposal != reproduced:
            raise ValidationError('Coverage proposal does not reproduce its retained source and declarations.')
        return body
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Invalid retained actuals coverage proposal.') from error
