"""Discover certified history for the offices represented by a proposal."""
from django.core.exceptions import PermissionDenied, ValidationError

from accounting import budget_native_certifications as native
from accounting.models import BudgetActualScope, Fund, NativeBudgetStatement, ResponsibilityCenter


def office_ids(version):
    ledger = version.fiscal_year.department_id
    offices = set(version.lines.filter(responsibility_center__department_id=ledger).exclude(
        responsibility_center__office_id=None).values_list('responsibility_center__office_id', flat=True))
    if version.requesting_department_id:
        offices.add(version.requesting_department_id)
    offices.update(version.source_links.filter(department_id=version.department_id,
        source_version__department_id=version.department_id, source_version__budget_call_id=version.budget_call_id,
        source_version__fiscal_year_id=version.fiscal_year_id).exclude(
        source_version__requesting_department_id=None).values_list('source_version__requesting_department_id', flat=True))
    return offices


def available_scopes(version, actor):
    """Discovery is advisory; selection revalidates exact sources under Fund locks."""
    from .planning_context import can_read_context
    from .actuals_selection import periods
    if not can_read_context(actor, version):
        raise PermissionDenied
    ledger = version.fiscal_year.department_id
    centers = {item.pk: item for item in ResponsibilityCenter.objects.filter(
        department_id=ledger, office_id__in=office_ids(version))}
    funds = {item.pk: item for item in Fund.objects.filter(department_id=ledger)}
    spans = periods(version)
    pairs = {(start, end): prefix for prefix, (start, end) in spans.items()}
    found = {(fund_id, center_id, prefix) for fund_id, center_id in
        version.lines.values_list('fund_id', 'responsibility_center_id') for prefix in spans}
    external = BudgetActualScope.objects.filter(department_id=ledger, budget_department_id=version.department_id,
        fund_id__in=funds, responsibility_center_id__in=centers, current_version__status='approved',
        period_start__in={start for start, end in pairs}).values_list(
            'fund_id', 'responsibility_center_id', 'period_start', 'period_end')
    for fund_id, center_id, start, end in external:
        if (start, end) in pairs:
            found.add((fund_id, center_id, pairs[(start, end)]))
    records = NativeBudgetStatement.objects.filter(department_id=ledger, fund_id__in=funds,
        status=NativeBudgetStatement.CERTIFIED, period_start__in={start for start, end in pairs}).order_by(
            'fund_id', 'period_start', 'period_end', '-version')
    seen, errors = set(), []
    for record in records:
        identity = (record.fund_id, record.period_start, record.period_end)
        prefix = pairs.get((record.period_start, record.period_end))
        if identity in seen or prefix is None:
            continue
        seen.add(identity)
        try:
            payload = native.verify(record)
        except ValidationError:
            errors.append(f'Native certification for {funds[record.fund_id].code} / {prefix} needs integrity review by Accounting.')
            continue
        for row in payload['statement']['payload']['rows']:
            center = centers.get(row['center']['id'])
            if center and row['office_id'] == center.office_id:
                found.add((record.fund_id, center.pk, prefix))
    result = {}
    for fund_id, center_id, prefix in sorted(found):
        if fund_id not in funds or center_id not in centers:
            continue
        start, end = spans[prefix]
        result[f'{fund_id}:{center_id}:{prefix}'] = {'fund_id': fund_id, 'center_id': center_id,
            'prefix': prefix, 'label': f'{funds[fund_id].code} / {centers[center_id].code} / {start} – {end}'}
    return result, errors
