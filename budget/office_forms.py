"""Office/fund Form 2 coverage, independent issuance and retained evidence."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from hashlib import sha256

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.cash_classifications import checksum
from accounting.models import ResponsibilityCenter
from .models import BudgetAuditEvent, BudgetOfficeForm as Form, BudgetVersion
from .planning_context import build_context, can_read_context
from .services import _require_action, record_event

CLASSES = {'ps': 'Personal Services', 'mooe': 'Maintenance and Other Operating Expenses',
    'fe': 'Financial Expenses', 'co': 'Capital Outlays', 'spa': 'Special Purpose Appropriations'}
AMOUNTS = ('prior_amount', 'half_amount', 'estimate', 'current_total', 'proposed')
ROLES = {'department_head': 'Department Head', 'budget_officer': 'Local Budget Officer',
         'chief_executive': 'Local Chief Executive'}


def frozen_context(version, actor):
    if not can_read_context(actor, version):
        raise PermissionDenied
    return _retained_context(version)


def _retained_context(version):
    """Internal integrity check; callers must authorize access before using it."""
    if version.status not in (BudgetVersion.APPROVED, BudgetVersion.AUTHORIZED):
        raise ValidationError('Independently approve the proposal before preparing an office form.')
    context = version.planning_context_snapshot
    event = BudgetAuditEvent.objects.filter(target_id=str(version.public_id), action='submit').order_by('-pk').first()
    if not context or not event or event.snapshot.get('planning_context') != context:
        raise ValidationError('The proposal no longer reproduces its submitted planning evidence.')
    if context.get('schema', 0) < 7:
        raise ValidationError('This historical snapshot has no captured office identities. Prepare a new proposal version; do not backfill it.')
    return context


def project(context, office_id, fund_id):
    """All selected office rows, without substituting zero for missing evidence."""
    issues, rows = [], []
    if not context.get('prior_period_complete') or not context.get('half_period_complete'):
        issues.append('Both actual comparison periods must be complete.')
    if context.get('forecast_issues'):
        issues.extend(context['forecast_issues'])
    for row in context.get('certified_schedule', []):
        if row['fund_id'] != fund_id:
            continue
        if not row.get('office_id') or not row.get('office_label'):
            issues.append(f"{row['center_code']} / {row['account_code']}: office identity is missing; reconcile it before choosing an office subset.")
            continue
        if row['office_id'] != office_id:
            continue
        label = f"{row['center_code']} / {row['account_code']} / {row['expense_class']}"
        if row['expense_class'].strip().casefold() not in CLASSES:
            issues.append(f'{label}: use a reviewed PS, MOOE, FE, CO or SPA object classification.')
        for key in AMOUNTS:
            if row.get(key) is None:
                issues.append(f'{label}: {key.replace("_", " ")} is missing; it is not zero.')
        for prefix in ('prior', 'half'):
            if not row[prefix + '_rows']:
                issues.append(f'{label}: {prefix} certification evidence is missing.')
            for evidence in row[prefix + '_rows']:
                scope = evidence['scope']
                if (scope['office_id'] != office_id or scope['fund_id'] != fund_id
                        or scope['center_id'] != row['center_id']):
                    issues.append(f'{label}: certification scope differs from this office row.')
                if not all(evidence.get(key) for key in ('certificate', 'accountant_name', 'certification_authority')):
                    issues.append(f'{label}: Accountant certification authority is missing.')
        forecasts = row['proposal_lines'] if row['has_proposal'] else [row.get('historical_forecast') or {}]
        for forecast in forecasts:
            dated = forecast.get('estimate_as_of') if row['has_proposal'] else forecast.get('as_of')
            basis = forecast.get('estimate_basis') if row['has_proposal'] else forecast.get('basis')
            if not dated or not basis or date.fromisoformat(dated).year != context['current_year']:
                issues.append(f'{label}: a dated current-year forecast basis is required.')
        if all(row.get(key) is not None for key in AMOUNTS):
            if Decimal(row['current_total']) != Decimal(row['half_amount']) + Decimal(row['estimate']):
                issues.append(f'{label}: current-year total does not reproduce its components.')
        rows.append(deepcopy(row))
    if not rows:
        issues.append('No captured rows cover this office and fund.')
    if issues:
        raise ValidationError(list(dict.fromkeys(issues)))
    names = {row['office_label'] for row in rows}
    funds = {row['fund_code'] for row in rows}
    if len(names) != 1 or len(funds) != 1:
        raise ValidationError('Captured office/fund labels conflict; reconcile the proposal evidence.')
    # Account/object totals span all captured centers, retaining each contributing row.
    grouped = {}
    for row in rows:
        key = (row['expense_class'].strip().casefold(), row['account_id'])
        item = grouped.setdefault(key, {'category': key[0], 'account_id': row['account_id'],
            'account_code': row['account_code'], 'account_title': row['account_title'],
            **{name: Decimal('0.00') for name in AMOUNTS}, 'sources': []})
        if (item['account_code'], item['account_title']) != (row['account_code'], row['account_title']):
            raise ValidationError('Captured account labels conflict across office centers.')
        for name in AMOUNTS:
            item[name] += Decimal(row[name])
        item['sources'].append(row)
    output = []
    for key in sorted(grouped, key=lambda key: (list(CLASSES).index(key[0]), grouped[key]['account_code'], key[1])):
        item = grouped[key]
        output.append({**item, **{name: str(item[name]) for name in AMOUNTS}})
    return {'office_id': office_id, 'office_label': names.pop(), 'fund_id': fund_id, 'fund_code': funds.pop(),
        'budget_year': context['budget_year'], 'prior_year': context['prior_year'], 'current_year': context['current_year'],
        'rows': output, 'totals': {name: str(sum((Decimal(row[name]) for row in output), Decimal('0.00'))) for name in AMOUNTS}}


def current_context(version, actor, office_id, fund_id):
    context = frozen_context(version, actor)
    fresh = build_context(version, actor)  # Existing Version -> sorted Fund lock order.
    for name in ('selected_actual_scopes', 'certified_schedule', 'historical_forecasts'):
        if fresh.get(name) != context.get(name):
            raise ValidationError('Planning sources or office setup changed after submission. Prepare an approved successor before issuing a new form.')
    from .actuals_scopes import available_scopes
    found, errors = available_scopes(version, actor)
    if errors:
        raise ValidationError(errors)
    centers = set(ResponsibilityCenter.objects.filter(department_id=version.fiscal_year.department_id,
        office_id=office_id).values_list('pk', flat=True))
    missing = [scope['label'] for key, scope in found.items() if scope['fund_id'] == fund_id
        and scope['center_id'] in centers and key not in context['selected_actual_scopes']]
    if missing:
        raise ValidationError('Additional known office history has no source choice: ' + '; '.join(missing))
    return context


def latest(version, office_id, fund_id):
    return Form.objects.filter(proposal=version, office_id=office_id, fund_id=fund_id).aggregate(value=Max('version'))['value'] or 0


def required(value, label, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f'Record {label} (up to {maximum} characters).')
    return value.strip()


@transaction.atomic(using='finance')
def prepare(*, version, actor, office_id, fund_id, expected_latest, expected_context_checksum,
            lgu, fund_scope, coverage, coverage_confirmed, signatories):
    version = BudgetVersion.objects.select_for_update().get(pk=version.pk)
    _require_action(actor, version, 'prepare_budget_proposals')
    if type(office_id) is not int or type(fund_id) is not int or office_id <= 0 or fund_id <= 0:
        raise ValidationError('Select explicit office and fund identities.')
    context = frozen_context(version, actor)
    schedule = project(context, office_id, fund_id)
    current_context(version, actor, office_id, fund_id)
    if checksum(context) != expected_context_checksum or type(expected_latest) is not int or latest(version, office_id, fund_id) != expected_latest:
        raise ValidationError('The preparation preview changed; reload it before saving.')
    if coverage_confirmed is not True:
        raise ValidationError('Explicitly confirm full office/fund coverage against the supporting records.')
    if (not isinstance(signatories, dict) or set(signatories) != set(ROLES)
            or any(not isinstance(value, dict) for value in signatories.values())):
        raise ValidationError('Record all three designated officers and their authority evidence.')
    people = {role: {'name': required(signatories[role].get('name'), ROLES[role] + ' name', 160),
        'authority': required(signatories[role].get('authority'), ROLES[role] + ' designation evidence')}
        for role in ROLES}
    payload = {'schema': 1, 'proposal': str(version.public_id), 'proposal_title': version.title,
        'proposal_version': version.version, 'department_id': version.department_id,
        'form_version': expected_latest + 1, 'context': deepcopy(context), 'context_checksum': checksum(context),
        'schedule': schedule, 'lgu': required(lgu, 'LGU name', 200), 'fund_scope': required(fund_scope, 'fund scope and authority'),
        'coverage': required(coverage, 'full office/fund/period coverage basis and evidence reference'),
        'coverage_confirmed': True, 'signatories': people, 'unsigned': True,
        'prepared_by_id': actor.pk, 'prepared_by_label': actor.get_full_name() or actor.username}
    item = Form.objects.create(department_id=version.department_id, department_label=version.department_label,
        proposal=version, office_id=office_id, fund_id=fund_id, version=expected_latest + 1,
        payload=payload, payload_checksum=checksum(payload), prepared_by_id=actor.pk,
        prepared_by_label=payload['prepared_by_label'])
    record_event(item, 'office_form_prepared', actor, payload['coverage'], {'payload_checksum': item.payload_checksum})
    return item


def decision_payload(item):
    return {'payload_checksum': item.payload_checksum, 'status': item.status, 'actor': item.decided_by_id,
        'label': item.decided_by_label, 'at': item.decided_at.isoformat() if item.decided_at else None,
        'note': item.decision_note, 'document_checksum': item.document_checksum}


def verify(item):
    data = item.payload
    if (checksum(data) != item.payload_checksum or data['proposal'] != str(item.proposal.public_id)
            or data['department_id'] != item.department_id or data['form_version'] != item.version
            or data['prepared_by_id'] != item.prepared_by_id or data['prepared_by_label'] != item.prepared_by_label
            or checksum(data['context']) != data['context_checksum']
            or project(data['context'], item.office_id, item.fund_id) != data['schedule'] or data['unsigned'] is not True):
        raise ValidationError('Retained Form 2 evidence failed integrity verification.')
    if item.status != Form.PREPARED:
        if (item.status not in (Form.ISSUED, Form.RETURNED) or not item.decided_at
                or not item.decided_by_id or item.decided_by_id == item.prepared_by_id or not item.decision_note
                or checksum(decision_payload(item)) != item.decision_checksum):
            raise ValidationError('Retained office-form decision failed independent verification.')
    if item.status == Form.ISSUED and (not item.document or sha256(bytes(item.document)).hexdigest() != item.document_checksum):
        raise ValidationError('Retained Form 2 document failed integrity verification.')
    return data


@transaction.atomic(using='finance')
def decide(*, item, actor, issue, note):
    if type(issue) is not bool:
        raise ValidationError('Choose an explicit issue or return decision.')
    # Never lock a joined proposal implicitly after locking the child.
    version = BudgetVersion.objects.select_for_update().get(pk=item.proposal_id)
    _require_action(actor, version, 'review_budget_proposals')
    item = Form.objects.select_for_update().get(pk=item.pk, proposal=version)
    data = verify(item)
    if item.status != Form.PREPARED or item.prepared_by_id == actor.pk:
        raise ValidationError('A different reviewer must decide a pending preparation exactly once.')
    note = required(note, 'independent coverage and designation review note')
    if issue:
        if latest(version, item.office_id, item.fund_id) != item.version:
            raise ValidationError('A newer preparation exists; review that version instead.')
        current_context(version, actor, item.office_id, item.fund_id)
        from .office_form_pdf import render_document
        item.document = render_document(data)
        item.document_checksum = sha256(item.document).hexdigest()
    item.status = Form.ISSUED if issue else Form.RETURNED
    item.decided_by_id, item.decided_by_label = actor.pk, actor.get_full_name() or actor.username
    item.decided_at, item.decision_note = timezone.now(), note
    item.decision_checksum = checksum(decision_payload(item))
    item._decision_write = True
    item.save(update_fields=('status', 'decided_by_id', 'decided_by_label', 'decided_at', 'decision_note',
        'decision_checksum', 'document', 'document_checksum'))
    record_event(item, 'office_form_issued' if issue else 'office_form_returned', actor, note, decision_payload(item))
    return item
