"""Retained whole Fund/entity forecasts and independent Budget Officer review."""
from copy import deepcopy
from decimal import Decimal
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.cash_classifications import checksum
from accounting.models import Fund
from accounting.summary_actuals import text
from .access import department_for_user, has_budget_permission
from .models import BudgetReceiptForecast as Record, BudgetVersion, BudgetSummaryReconciliation, BudgetOfficeForm
from .services import _require_action, record_event
from . import receipt_forecasts as forecasts, summary_reconciliations, summary_sources, office_forms


def decision(record):
    return dict(payload_checksum=record.payload_checksum, status=record.status,
        reviewed_by=record.reviewed_by_id, reviewed_at=record.reviewed_at.isoformat() if record.reviewed_at else None,
        note=record.review_note, authority=record.review_authority)


def inventory(proposal, fund):
    """Latest reconciliation versions include pending/returned heads, never hide them."""
    query = BudgetSummaryReconciliation.objects.filter(proposal=proposal, fund=fund)
    heads = query.values('entity_key').annotate(latest=Max('version'))
    return [query.get(entity_key=row['entity_key'], version=row['latest']) for row in heads.order_by('entity_key')]


def combine(proposals, *, entity_inventory, coverage_reference):
    """Pure cross-entity reproduction; independent approval remains a separate step."""
    if not isinstance(proposals, list) or not proposals:
        raise ValidationError('Retain at least one complete entity forecast proposal.')
    coverage_reference = text(coverage_reference, 'complete reporting-entity forecast coverage')
    members = []
    for proposal in proposals:
        body = forecasts.verify(proposal)
        scope = body['capture']['payload']['scope']
        members.append(dict(entity_key=scope['entity_key'], entity_label=scope['entity_label'], forecast=deepcopy(proposal)))
    members.sort(key=lambda row: row['entity_key'])
    entities = [dict(key=row['entity_key'], label=row['entity_label']) for row in members]
    if len({row['key'] for row in entities}) != len(entities) or entity_inventory != entities:
        raise ValidationError('Retain every declared entity once with its exact original label.')
    first = members[0]['forecast']['payload']['capture']['payload']
    baseline_half = sorted(members[0]['forecast']['payload']['columns']['half_estimate']['sources'], key=lambda row: row['id'])
    for member in members:
        body = member['forecast']['payload']; capture = body['capture']['payload']
        if (any(capture['scope'][key] != first['scope'][key] for key in
            ('budget_department_id', 'accounting_department_id', 'treasury_department_id', 'fund_id', 'fund_code', 'budget_year'))
            or any(capture[key] != first[key] for key in ('proposal', 'resources', 'resource_nodes', 'resource_roots', 'accounts'))
            or sorted(body['columns']['half_estimate']['sources'], key=lambda row: row['id']) != baseline_half):
            raise ValidationError('All entities must retain one common Fund, proposal and complete forecast source cohort.')
    controls = {}
    for column in ('half_estimate', 'proposed'):
        roots = {}; included_keys = set()
        for member in members:
            body = member['forecast']['payload']['columns'][column]
            sources = {row['id']: row for row in body['sources']}
            for source in sources.values():
                root = source['root_key']; value = forecasts.amount(source['root_amount'])
                if root in roots and roots[root]['source_amount'] != str(value):
                    raise ValidationError('Shared original source caps must reproduce exactly across entities.')
                roots.setdefault(root, dict(root=root, source_amount=str(value), included=Decimal('0.00')))
            for component in body['components']:
                if component['disposition'] != 'include':
                    continue
                if component['coverage_key'] in included_keys:
                    raise ValidationError('Two entities cannot include the same funding coverage identity.')
                included_keys.add(component['coverage_key'])
                roots[sources[component['source_id']]['root_key']]['included'] += forecasts.amount(component['amount'])
        rows = []
        for root in sorted(roots):
            row = roots[root]; remaining = forecasts.amount(row['source_amount']) - row['included']
            if remaining < 0:
                raise ValidationError('Combined entities exceed an original forecast source amount.')
            rows.append(dict(root=root, source_amount=row['source_amount'], included=str(row['included']),
                unallocated=str(remaining)))
        controls[column] = dict(roots=rows, diagnostic_total=str(sum((row['included'] for row in roots.values()), Decimal('0.00'))))
    return dict(schema=1, kind='budget_receipt_forecast_group', members=members,
        entity_inventory=deepcopy(entities), coverage_reference=coverage_reference,
        controls=controls, classification_complete=all(row['forecast']['payload']['classification_complete'] for row in members),
        actual_receipts=False, cash_available=False, form_issued=False)


def verify(record):
    try:
        payload = record.payload
        identity = dict(public_id=str(record.public_id), proposal=str(record.proposal.public_id),
            department_id=record.department_id, fund_id=record.fund_id, version=record.version,
            prepared_by=record.prepared_by_id, prepared_at=record.prepared_at.isoformat())
        group = payload['group']
        reproduced = combine([member['forecast'] for member in group['members']],
            entity_inventory=group['entity_inventory'], coverage_reference=group['coverage_reference'])
        if (payload != dict(schema=1, identity=identity, group=reproduced)
            or record.payload_checksum != checksum(payload)):
            raise ValidationError('Retained forecast package does not reproduce its original identity and controls.')
        for member in group['members']:
            captured = member['forecast']['payload']['capture']['payload']
            if (captured['proposal']['public_id'] != identity['proposal']
                or captured['scope']['budget_department_id'] != record.department_id
                or captured['scope']['fund_id'] != record.fund_id):
                raise ValidationError('Forecast members differ from their retained package scope.')
        if record.status == 'prepared':
            if record.reviewed_by_id or record.reviewed_at or record.decision_checksum or record.review_note or record.review_authority:
                raise ValidationError('A pending forecast cannot contain an independent decision.')
        elif (record.status not in ('approved', 'returned') or not record.reviewed_by_id
            or record.reviewed_by_id == record.prepared_by_id or not record.reviewed_at
            or not record.review_note or not record.review_authority or checksum(decision(record)) != record.decision_checksum
            or (record.status == 'approved' and not group['classification_complete'])):
            raise ValidationError('Retain a complete independent Budget Officer decision.')
        return payload
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid retained Budget receipt forecast evidence.') from error


def _current_reconciliation(record, actor):
    parent = summary_reconciliations.verify(record)
    if parent['schema'] < 2:
        raise ValidationError('Prepare a successor reconciliation with complete original decisions.')
    for source in parent['actuals'].values():
        routed = deepcopy(source)
        routed.setdefault('route', 'historical')
        summary_sources.require_current(routed, actor=actor, budget_department_id=record.department_id)
    for source in parent['forms']:
        member = BudgetOfficeForm.objects.filter(public_id=source['id'], proposal_id=record.proposal_id,
            department_id=record.department_id, status=BudgetOfficeForm.ISSUED).first()
        if (not member or office_forms.verify(member) != source['payload']
            or office_forms.decision_payload(member) != source['decision']):
            raise ValidationError('The original issued office evidence changed; retain a successor reconciliation.')
        summary_reconciliations.require_current_office(member)


def _check_sources(group, proposal, fund, actor, *, preparing):
    records = inventory(proposal, fund)
    by_entity = {record.entity_key: record for record in records}
    if set(by_entity) != {member['entity_key'] for member in group['members']}:
        raise ValidationError('The complete entity reconciliation inventory changed; prepare a successor forecast package.')
    for member in group['members']:
        record = by_entity[member['entity_key']]
        original = member['forecast']['payload']['capture']
        current = forecasts.capture(reconciliation=record, actor=actor)
        if (current['payload'] != original['payload'] or current['checksum'] != original['checksum']
            or (preparing and current['observed_on'] != original['observed_on'])):
            raise ValidationError('Forecast source evidence changed; recapture sources and prepare a successor.')
        _current_reconciliation(record, actor)


@transaction.atomic(using='finance')
def prepare(*, proposal, actor, fund_id, proposals, entity_inventory, coverage_reference,
            coverage_confirmed, expected_latest):
    proposal = BudgetVersion.objects.select_for_update().get(pk=proposal.pk)
    _require_action(actor, proposal, 'prepare_budget_receipt_forecasts')
    fund = Fund.objects.select_for_update().get(pk=fund_id)
    if fund.department_id != proposal.fiscal_year.department_id:
        raise ValidationError('Select the proposal’s original Accounting Fund.')
    if coverage_confirmed is not True:
        raise ValidationError('Confirm complete reporting-entity and forecast source coverage.')
    group = combine(proposals, entity_inventory=entity_inventory, coverage_reference=coverage_reference)
    _check_sources(group, proposal, fund, actor, preparing=True)
    latest = Record.objects.filter(proposal=proposal, fund=fund).aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest) is not int or latest != expected_latest:
        raise ValidationError('A newer forecast package exists; reload its history.')
    now = timezone.now(); public_id = uuid.uuid4()
    identity = dict(public_id=str(public_id), proposal=str(proposal.public_id), department_id=proposal.department_id,
        fund_id=fund.pk, version=latest+1, prepared_by=actor.pk, prepared_at=now.isoformat())
    payload = dict(schema=1, identity=identity, group=group)
    record = Record.objects.create(public_id=public_id, proposal=proposal, fund=fund, version=latest+1,
        department_id=proposal.department_id, department_label=proposal.department_label,
        prepared_by_id=actor.pk, prepared_at=now, payload=payload, payload_checksum=checksum(payload))
    record_event(record, 'receipt_forecast_prepared', actor, coverage_reference, dict(payload_checksum=record.payload_checksum))
    return record


@transaction.atomic(using='finance')
def review(record, actor, *, approve, note, authority):
    proposal = BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    _require_action(actor, proposal, 'review_budget_receipt_forecasts')
    fund = Fund.objects.select_for_update().get(pk=record.fund_id)
    record = Record.objects.select_for_update().get(pk=record.pk, proposal=proposal)
    payload = verify(record)
    require_visible(record, actor)
    if type(approve) is not bool or record.status != 'prepared' or record.prepared_by_id == actor.pk:
        raise ValidationError('A different designated Budget Officer must decide a pending forecast once.')
    note = text(note, 'independent forecast review note')
    authority = text(authority, 'Budget Officer designation authority')
    latest = Record.objects.filter(proposal=proposal, fund=fund).aggregate(n=Max('version'))['n']
    if approve:
        if latest != record.version or not payload['group']['classification_complete']:
            raise ValidationError('Review the latest package with every forecast classification resolved.')
        _check_sources(payload['group'], proposal, fund, actor, preparing=False)
    record.status = 'approved' if approve else 'returned'
    record.reviewed_by_id = actor.pk; record.reviewed_at = timezone.now()
    record.review_note = note; record.review_authority = authority
    record.decision_checksum = checksum(decision(record)); record._decision_write = True
    record.save()
    record_event(record, 'receipt_forecast_'+record.status, actor, note, decision(record))
    return record


def require_visible(record, actor, action='view'):
    owner = department_for_user(actor)
    if (action not in ('view', 'export') or not owner or owner.pk != record.department_id
        or not has_budget_permission(actor, action+'_budget_receipt_forecasts')):
        raise PermissionDenied
    for member in verify(record)['group']['members']:
        original = member['forecast']['payload']['capture']['payload']['reconciliation']
        parent = BudgetSummaryReconciliation.objects.filter(public_id=original['public_id'],
            proposal_id=record.proposal_id, department_id=record.department_id).first()
        if not parent:
            raise ValidationError('Retain the original reconciliation source identity.')
        summary_sources.require_visible(summary_reconciliations.verify(parent), actor, action)


def snapshot(record, actor, *, export=False):
    require_visible(record, actor, 'export' if export else 'view')
    return _snapshot(record)


def _snapshot(record):
    """Internal retained projection; public callers separately enforce access."""
    payload = verify(record)
    return dict(payload=deepcopy(payload), payload_checksum=record.payload_checksum,
        decision=decision(record), decision_checksum=record.decision_checksum,
        status=record.status, actual_receipts=False, cash_available=False, form_issued=False,
        reviewed_totals={member['entity_key']: {column: member['forecast']['payload']['columns'][column]['diagnostic_total']
            for column in ('half_estimate', 'proposed')} for member in payload['group']['members']}
            if record.status == 'approved' else None)


@transaction.atomic(using='finance')
def is_current(record, actor):
    """Currentness is a separate observation; do not rewrite old approvals."""
    proposal = BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=record.fund_id)
    record = Record.objects.get(pk=record.pk, proposal=proposal)
    require_visible(record, actor)
    latest = Record.objects.filter(proposal=proposal, fund=fund).aggregate(n=Max('version'))['n']
    if record.status != 'approved' or latest != record.version:
        return False
    try:
        _check_sources(verify(record)['group'], proposal, fund, actor, preparing=False)
        return True
    except ValidationError:
        return False
