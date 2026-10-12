"""Explicit forecasts for selected historical objects without proposal lines."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.budget_actuals import money
from accounting.cash_classifications import checksum
from .models import BudgetVersion
from .services import _require_action, record_event

IDENTITY = ('fund_id', 'center_id', 'account_id', 'expense_class')
LABELS = ('fund_code', 'center_code', 'account_code', 'account_title', 'office_id', 'office_label')


def row_key(row):
    return checksum({**{name: row[name] for name in IDENTITY},
                     'expense_class': row['expense_class'].strip().casefold()})


def source_digest(row):
    return checksum({name: row[name] for name in ('prior_rows', 'half_rows')})


def overlay(schedule, forecasts):
    rows = {row_key(row): row for row in schedule}
    issues = []
    for key, forecast in forecasts.items():
        if row_key(forecast['row']) != key:
            raise ValidationError('Retained forecast identity does not reproduce its object.')
        row = rows.setdefault(key, {**deepcopy(forecast['row']), 'proposal_lines': [],
            'prior_rows': [], 'half_rows': [], 'prior_amount': None, 'half_amount': None,
            'has_proposal': False, 'proposed': '0.00', 'estimate': None, 'current_total': None})
        problem = ''
        if row['has_proposal']:
            problem = 'Proposal lines now cover this object. Reconcile their estimates and clear the historical forecast.'
        elif not (row['prior_rows'] or row['half_rows']):
            problem = 'Select the historical actual evidence again or clear this forecast.'
        elif source_digest(row) != forecast['source_digest']:
            problem = 'Selected actual evidence changed. Review and save the forecast again.'
        row['historical_forecast'] = deepcopy(forecast)
        row['forecast_problem'] = problem
        row['estimate'] = None if problem else forecast['amount']
        row['current_total'] = str(Decimal(row['half_amount']) + Decimal(row['estimate'])) if (
            row['half_amount'] is not None and row['estimate'] is not None) else None
        if problem:
            issues.append(f"{row['fund_code']} / {row['center_code']} / {row['account_code']} / {row['expense_class']}: {problem}")
    for key, row in rows.items():
        row['forecast_key'] = key
        row['forecast_source_digest'] = source_digest(row)
    return sorted(rows.values(), key=lambda row: tuple(str(row[name]) for name in IDENTITY)), issues


@transaction.atomic(using='finance')
def save_forecast(*, version, actor, key, expected_state_version, expected_source_digest,
                  amount=None, as_of=None, basis='', reason='', clear=False):
    version = BudgetVersion.objects.select_for_update().get(pk=version.pk)
    _require_action(actor, version, 'prepare_budget_proposals')
    if version.status not in (BudgetVersion.DRAFT, BudgetVersion.RETURNED):
        raise ValidationError('Return the proposal before changing forecasts.')
    if type(expected_state_version) is not int or version.state_version != expected_state_version:
        raise ValidationError('The proposal changed; reload the forecast.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Record a reason for this forecast change.')
    before = version.historical_forecasts.get(key)
    after = None
    if clear:
        if before is None:
            raise ValidationError('There is no historical forecast to clear.')
    else:
        from .planning_context import build_context
        context = build_context(version, actor)
        row = next((item for item in context.get('certified_schedule', []) if row_key(item) == key), None)
        if not row or row['has_proposal'] or not (row['prior_rows'] or row['half_rows']):
            raise ValidationError('Choose a selected historical object without proposal lines; use line estimates for proposed objects.')
        if source_digest(row) != expected_source_digest:
            raise ValidationError('Displayed actual evidence changed; inspect a fresh forecast preview.')
        amount = money(amount)
        if amount < 0 or type(as_of) is not date or as_of.year != version.fiscal_year.year - 1 or as_of > timezone.localdate():
            raise ValidationError('Use a nonnegative forecast dated within the current planning year, not in the future.')
        if not isinstance(basis, str) or not basis.strip() or len(basis) > 2000:
            raise ValidationError('Record the dated planning basis and evidence reference.')
        after = {'row': {name: row[name] for name in (*IDENTITY, *LABELS)}, 'amount': str(amount),
            'as_of': as_of.isoformat(), 'basis': basis.strip(), 'source_digest': source_digest(row),
            'source_rows': {name: deepcopy(row[name]) for name in ('prior_rows', 'half_rows')},
            'prepared_by_id': actor.pk, 'prepared_by_label': actor.get_full_name() or actor.username,
            'prepared_at': timezone.now().isoformat(), 'reason': reason.strip()}
        if before and before.get('origin'):
            after['origin'] = deepcopy(before['origin'])
    version.historical_forecasts = {name: value for name, value in version.historical_forecasts.items() if name != key}
    if after is not None:
        version.historical_forecasts[key] = after
    version.state_version += 1
    version.save(update_fields=('historical_forecasts', 'state_version'))
    record_event(version, 'historical_forecast_cleared' if clear else 'historical_forecast_saved', actor, reason.strip(),
        {'key': key, 'before': before, 'after': after, 'state_version': version.state_version})
    return version


def consolidate_forecasts(sources):
    """Copy only submitted/approved forecast evidence, retaining its origin."""
    result = {}
    for source in sources:
        frozen = source.planning_context_snapshot.get('historical_forecasts', {})
        if frozen != source.historical_forecasts:
            raise ValidationError('A source forecast differs from its submitted evidence.')
        for key, forecast in frozen.items():
            if key in result:
                raise ValidationError('Source proposals contain overlapping historical forecasts. Reconcile the office/object scope before consolidation.')
            result[key] = {**deepcopy(forecast), 'origin': {'proposal': str(source.public_id),
                'title': source.title, 'version': source.version, 'forecast_checksum': checksum(forecast)}}
    return result
