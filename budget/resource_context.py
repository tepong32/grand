"""Frozen proposed financing estimates; never certified receipts or cash."""
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import BudgetAuditEvent, BudgetResourceEstimate, BudgetVersion


def row_payload(item):
    source = item.funding_source
    version = item.version
    if (item.department_id != version.department_id or source.department_id != version.fiscal_year.department_id
            or source.fiscal_year_id != version.fiscal_year_id
            or (source.fund_id and source.fund.department_id != source.department_id)):
        raise ValidationError('A resource estimate no longer matches its Budget owner, Finance ledger and fiscal year.')
    if item.amount < 0 or not item.basis.strip():
        raise ValidationError('Each resource estimate requires a nonnegative amount and its planning basis.')
    return {'id': item.pk, 'description': item.description, 'amount': str(item.amount), 'basis': item.basis,
        'funding_source': {'id': source.pk, 'code': source.code, 'name': source.name, 'kind': source.kind,
            'authority_reference': source.authority_reference, 'fiscal_year_id': source.fiscal_year_id,
            'fund_id': source.fund_id, 'fund_code': source.fund.code if source.fund_id else None,
            'effective_from': source.effective_from.isoformat(),
            'effective_to': source.effective_to.isoformat() if source.effective_to else None,
            'is_active': source.is_active}}


def capture(version):
    rows = [row_payload(item) for item in BudgetResourceEstimate.objects.filter(version=version).select_related(
        'version__fiscal_year', 'funding_source__fund').order_by('pk')]
    origin = BudgetAuditEvent.objects.filter(target_id=str(version.public_id), action='consolidated').order_by('pk').first()
    return {'schema': 1, 'budget_year': version.fiscal_year.year, 'rows': rows,
        'origins': deepcopy(origin.snapshot.get('resource_origins', [])) if origin else [],
        'certified_receipts': False, 'cash_available': False,
        'aggregation': 'No total: reconcile overlapping financing sources before using these estimates in a summary.'}


def require_retained(version):
    retained = (version.planning_context_snapshot or {}).get('resources')
    actual = capture(version)
    if retained is None:
        if actual['rows']:
            raise ValidationError('Resource estimates have no submitted snapshot. Return/resubmit or prepare a successor; never backfill approval evidence.')
    elif actual != retained:
        raise ValidationError('Resource estimates or funding-source evidence changed after submission. Return/resubmit or prepare a successor.')
    return retained or actual


@transaction.atomic(using='finance')
def save_estimate(*, version, actor, funding_source, description, amount, basis, expected_state_version,
                  item_id=None, reason=''):
    from .services import _require_action, record_event
    version = BudgetVersion.objects.select_for_update().get(pk=version.pk)
    _require_action(actor, version, 'prepare_budget_proposals')
    if version.status not in (BudgetVersion.DRAFT, BudgetVersion.RETURNED):
        raise ValidationError('Return the proposal before changing its resource estimates.')
    if type(expected_state_version) is not int or expected_state_version != version.state_version:
        raise ValidationError('The proposal changed; reload the resource estimate.')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Record the reason for this resource estimate change.')
    # Resolve the selected source afresh; do not retain a caller-cached setup row.
    from accounting.models import FundingSource
    source = FundingSource.objects.select_related('fund').filter(pk=funding_source.pk,
        department_id=version.fiscal_year.department_id, fiscal_year_id=version.fiscal_year_id, is_active=True).first()
    if not source:
        raise ValidationError('Select an active funding source in this Finance ledger and fiscal year.')
    if item_id is None:
        item = BudgetResourceEstimate(version=version, department_id=version.department_id,
            department_label=version.department_label)
        before = None
    else:
        item = BudgetResourceEstimate.objects.select_for_update().filter(pk=item_id, version=version).first()
        if not item:
            raise ValidationError('Select a resource estimate belonging to this proposal.')
        before = row_payload(item)
    item.funding_source, item.description, item.amount, item.basis = source, description, amount, basis
    item.save()
    version.state_version += 1
    version.save(update_fields=('state_version',))
    record_event(version, 'resource_estimate_changed' if before else 'resource_estimate_added', actor, reason.strip(),
        {'before': before, 'after': row_payload(item), 'state_version': version.state_version})
    return item


def copy_resources(sources, target):
    """Caller locks approved source versions; retain each estimate, never deduplicate by label."""
    origins = []
    for source in sources:
        retained = require_retained(source)
        for row in retained['rows']:
            item = BudgetResourceEstimate.objects.create(version=target, department_id=target.department_id,
                department_label=target.department_label, funding_source_id=row['funding_source']['id'],
                description=row['description'], amount=row['amount'], basis=row['basis'])
            origins.append({'target_resource_id': item.pk, 'source_proposal': str(source.public_id),
                'source_title': source.title, 'source_version': source.version,
                'requesting_office_id': source.requesting_department_id,
                'requesting_office_label': source.requesting_department_label, 'source_resource': deepcopy(row)})
    return origins
