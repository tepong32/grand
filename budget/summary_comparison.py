"""Period-matched diagnostic comparison; no certification or coverage inference."""
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError

CLASSES = ('ps', 'mooe', 'fe', 'co', 'spa')


def compare_cohort(actual, forms, *, expected_offices, entity_key, coverage_reference):
    """Explicit cohort only; callers must authorize and verify every retained source."""
    if not isinstance(expected_offices, list) or not expected_offices or any(type(value) is not int or value <= 0 for value in expected_offices):
        raise ValidationError('Declare the complete expected office set.')
    if len(set(expected_offices)) != len(expected_offices):
        raise ValidationError('Do not declare an office twice.')
    if entity_key != actual['scope']['entity_key']:
        raise ValidationError('The cohort designation differs from the joint reporting entity.')
    if not isinstance(coverage_reference, str) or not coverage_reference.strip() or len(coverage_reference) > 2000:
        raise ValidationError('Record the complete office/entity coverage designation reference.')
    if not forms:
        raise ValidationError('Select one issued form for each expected office.')
    offices, proposal = set(), None
    combined = None
    for form in forms:
        schedule = form['schedule']
        office = schedule['office_id']
        if office in offices:
            raise ValidationError('Select exactly one issued version per office; do not sum version history.')
        offices.add(office)
        if proposal is not None and proposal != form['proposal']:
            raise ValidationError('Do not combine office forms from different proposals.')
        proposal = form['proposal']
        if form['department_id'] != actual['scope']['budget_department_id']:
            raise ValidationError('The office form belongs to another Budget owner.')
        # Compare every member individually to validate period/fund and leaf controls.
        compare(actual, schedule)
        if combined is None:
            from copy import deepcopy
            combined = deepcopy(schedule)
            combined['rows'] = []
            combined['totals'] = {key: '0.00' for key in schedule['totals']}
        if any(schedule[key] != combined[key] for key in ('fund_id', 'prior_year', 'current_year', 'budget_year')):
            raise ValidationError('Office form years or funds differ.')
        combined['rows'].extend(schedule['rows'])
        for key in combined['totals']:
            combined['totals'][key] = str(Decimal(combined['totals'][key]) + Decimal(schedule['totals'][key]))
    if offices != set(expected_offices):
        raise ValidationError('Selected forms must cover exactly the declared expected offices; reconcile missing or extra offices.')
    return compare(actual, combined) | {'expected_offices': sorted(offices),
        'entity_key': entity_key, 'coverage_reference': coverage_reference.strip(), 'proposal': proposal}


def compare(actual, schedule):
    scope = actual['scope']
    if scope['fund_id'] != schedule['fund_id']:
        raise ValidationError('The joint summary and office form have different funds.')
    start, end = date.fromisoformat(scope['period_start']), date.fromisoformat(scope['period_end'])
    if (start, end) == (date(schedule['prior_year'], 1, 1), date(schedule['prior_year'], 12, 31)):
        column, label = 'prior_amount', 'Past-year actual expenditures'
    elif (start, end) == (date(schedule['current_year'], 1, 1), date(schedule['current_year'], 6, 30)):
        column, label = 'half_amount', 'Current first-half actual expenditures'
    else:
        raise ValidationError('Select a joint summary for the exact past-year or current first-half comparison period.')
    joint = {key: Decimal('0.00') for key in CLASSES}
    office = {key: Decimal('0.00') for key in CLASSES}
    for row in actual['rows']:
        if row['kind'] == 'expenditure':
            joint[row['category']] += Decimal(row['amount'])
    for row in schedule['rows']:
        office[row['category']] += Decimal(row[column])
    if sum(joint.values()) != Decimal(actual['totals']['expenditure']) or sum(office.values()) != Decimal(schedule['totals'][column]):
        raise ValidationError('The comparison source controls do not reproduce their leaf rows.')
    return {'column': column, 'label': label,
        'rows': [{'category': key, 'joint': str(joint[key]), 'office': str(office[key]),
                  'difference': str(joint[key]-office[key])} for key in CLASSES],
        'joint_total': str(sum(joint.values())), 'office_total': str(sum(office.values())),
        'difference': str(sum(joint.values())-sum(office.values()))}
