"""Detached statement preparation from one trusted cohort; never certification."""
from copy import deepcopy
from decimal import Decimal

from django.core.exceptions import ValidationError

from . import budget_attributions as attribution
from . import budget_native_sources as sources
from .budget_actuals import money
from .cash_classifications import checksum


def project(captured):
    """Reproduce all offices and coverage without reading newer heads or setup.

    This internal function accepts trusted server-captured/retained evidence only.
    Checksums prove integrity, not client authority. No subset of offices can hide
    incomplete fund coverage, and an empty cohort does not establish certified zero.
    """
    payload = sources.verify(captured)
    if payload['schema'] != 7:
        raise ValidationError('Prepare native statements from current source evidence; retain older captures unchanged.')
    reviewed = {row['entry_id']: row for row in attribution.reviewed_allocations(captured)}
    bridge, offices, issues = [], {}, []
    controls = {key: {'debit': Decimal('0.00'), 'credit': Decimal('0.00')}
                for key in ('include', 'exclude', 'unresolved', 'unreviewed')}
    for entry in payload['journals']:
        decision = reviewed[entry['id']]
        allocations = decision['allocations']
        if decision['status'] == 'unreviewed':
            issues.append({'entry_id': entry['id'], 'kind': 'unreviewed'})
        for line in entry['lines']:
            debit, credit = money(line['debit']), money(line['credit'])
            if (debit > 0) == (credit > 0) or debit < 0 or credit < 0:
                raise ValidationError('Statement sources require valid one-sided financial lines.')
            parts = [deepcopy(row) for row in allocations if row['line_id'] == line['id']]
            if decision['status'] == 'unreviewed':
                parts = [{'line_id': line['id'], 'amount': str(debit + credit),
                    'signed_amount': str(debit - credit), 'disposition': 'unreviewed'}]
            if sum((money(part['amount']) for part in parts), Decimal('0.00')) != debit + credit:
                raise ValidationError('Statement allocation coverage does not reproduce every source line.')
            for part in parts:
                amount, signed = money(part['amount']), money(part['signed_amount'])
                disposition = part['disposition']
                if amount <= 0 or signed != (amount if debit else -amount) or disposition not in controls:
                    raise ValidationError('Statement allocation signs or dispositions do not reproduce the source.')
                controls[disposition]['debit' if debit else 'credit'] += amount
                if disposition == 'unresolved':
                    issues.append({'entry_id': entry['id'], 'line_id': line['id'], 'kind': 'unresolved'})
                if disposition == 'include':
                    center = part['center']
                    office_id = center['office_id']
                    key = (office_id, center['id'], line['account_id'], part['expense_class'])
                    if key not in offices:
                        offices[key] = {'office_id': office_id, 'center': deepcopy(center),
                            'account': deepcopy(line['account']), 'expense_class': part['expense_class'],
                            'debit': Decimal('0.00'), 'credit': Decimal('0.00'), 'components': []}
                    group = offices[key]
                    if group['center'] != center or group['account'] != line['account']:
                        raise ValidationError('Reconcile inconsistent retained office/account metadata before statement preparation.')
                    group['debit' if debit else 'credit'] += amount
                    group['components'].append({'entry_id': entry['id'], 'line_id': line['id'],
                        'attribution_id': decision['version'], 'allocation': deepcopy(part)})
            bridge.append({'entry_id': entry['id'], 'reference': entry['reference'],
                'entry_date': entry['entry_date'], 'line_id': line['id'], 'sequence': line['sequence'],
                'account': deepcopy(line['account']), 'debit': str(debit), 'credit': str(credit),
                'attribution_id': decision.get('version'), 'allocations': parts})
    for side in ('debit', 'credit'):
        if sum((group[side] for group in controls.values()), Decimal('0.00')) != money(payload['controls'][side]):
            raise ValidationError('Statement bridge does not reconcile to captured ledger controls.')
    if not payload['journals']:
        issues.append({'kind': 'empty_cohort_requires_evidence'})
    rows = [dict(offices[key], amount=offices[key]['debit'] - offices[key]['credit']) for key in sorted(offices)]
    result = attribution.json_value({'schema': 1, 'kind': 'native_budget_statement_preparation',
        'certificate': False, 'source_checksum': captured['checksum'],
        'scope': deepcopy(payload['scope']), 'source_controls': deepcopy(payload['controls']),
        'classification_complete': not issues, 'issues': issues, 'coverage': controls,
        'rows': rows, 'total': sum((row['amount'] for row in rows), Decimal('0.00')), 'bridge': bridge})
    return {'payload': result, 'checksum': checksum(result)}


def prepare(*, actor, fund_id, period_start, period_end):
    """Authorized read-only calculation retaining the exact cohort used."""
    captured = sources.capture(actor=actor, fund_id=fund_id,
        period_start=period_start, period_end=period_end)
    return {'source': captured, 'statement': project(captured)}
