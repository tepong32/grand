"""Retained Budget preparation and scoped independent Accounting account review."""
from copy import deepcopy
from hashlib import sha256
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from accounting.cash_classifications import checksum
from accounting import summary_actuals
from accounting.models import Fund
from .access import department_for_user, has_budget_permission
from .models import Form1AccountReview as Record, BudgetVersion, BudgetReceiptForecast
from .services import record_event
from . import form1_account_proposals as drafts, form1_components, form1_flows
from . import receipt_forecast_reviews as forecasts, receipt_forecasts, office_forms, summary_sources


def _access(proposal, fund, actor, action):
    from vouchers.roles import is_finance_uat_viewer
    owner = department_for_user(actor)
    allowed = {'prepare': (proposal.department_id,), 'review': (fund.department_id,),
        'view': (proposal.department_id, fund.department_id), 'export': (proposal.department_id, fund.department_id)}
    if (action not in allowed or not owner or owner.pk not in allowed[action]
        or fund.department_id != proposal.fiscal_year.department_id
        or not has_budget_permission(actor, action+'_form1_account_reviews')
        or (action in ('prepare', 'review') and is_finance_uat_viewer(actor))):
        raise PermissionDenied('This package requires its explicit Budget/Accounting role and original office scope.')


def _sources(record, actor, action='view'):
    body = drafts.verify(record.payload['draft'])['inventory']['payload']['flows']['payload']
    for parent in body['sources']['reconciliations']:
        payload = parent['payload']
        summary_sources.require_visible(payload, actor, action)
        for source in payload['actuals'].values():
            if source.get('route', 'historical') == 'historical':
                if not summary_actuals.permitted(actor, action):
                    raise PermissionDenied('This package also requires the original historical source read/export permission.')
                if not summary_actuals.visible(actor).filter(public_id=source['id'], status='approved',
                    scope__budget_department_id=record.department_id, scope__department_id=record.fund.department_id).exists():
                    raise PermissionDenied('The original adopted actuals source is no longer accessible.')


def decision(record):
    return dict(payload_checksum=record.payload_checksum, status=record.status,
        reviewed_by=record.reviewed_by_id, reviewed_at=record.reviewed_at.isoformat() if record.reviewed_at else None,
        note=record.review_note, authority=record.review_authority)


def verify(record):
    try:
        payload = record.payload
        draft = drafts.verify(payload['draft'])
        original = draft['inventory']['payload']['flows']['payload']['sources']['forecast']
        identity = dict(public_id=str(record.public_id), proposal=str(record.proposal.public_id),
            department_id=record.department_id, accounting_department_id=record.fund.department_id,
            fund_id=record.fund_id, forecast=str(record.forecast.public_id), version=record.version,
            prepared_by=record.prepared_by_id, prepared_at=record.prepared_at.isoformat())
        if (set(payload) != {'schema', 'identity', 'draft', 'code_reference', 'evidence'}
            or payload['schema'] != 1 or payload['identity'] != identity
            or record.department_id != record.proposal.department_id
            or record.fund.department_id != record.proposal.fiscal_year.department_id
            or record.forecast.proposal_id != record.proposal_id or record.forecast.fund_id != record.fund_id
            or original['payload']['identity']['public_id'] != identity['forecast']
            or original['payload'] != record.forecast.payload
            or original['payload_checksum'] != record.forecast.payload_checksum
            or original['decision'] != forecasts.decision(record.forecast)
            or original['decision_checksum'] != record.forecast.decision_checksum
            or record.payload_checksum != checksum(payload)
            or payload['evidence']['sha256'] != sha256(bytes(record.evidence)).hexdigest()):
            raise ValidationError('Retain the original reporting-account package identity and code evidence.')
        summary_actuals.text(payload['code_reference'], 'code authority reference')
        summary_actuals.text(payload['evidence']['name'], 'code evidence name', 180)
        if record.status == 'prepared':
            if any((record.reviewed_by_id, record.reviewed_at, record.review_note, record.review_authority, record.decision_checksum)):
                raise ValidationError('Pending selections cannot contain an independent decision.')
        elif (record.status not in ('approved', 'returned') or not record.reviewed_by_id
            or record.reviewed_by_id == record.prepared_by_id or not record.reviewed_at
            or not record.review_note or not record.review_authority
            or record.decision_checksum != checksum(decision(record))
            or (record.status == 'approved' and not draft['selection_complete'])):
            raise ValidationError('Retain an independent Accounting decision over complete selections.')
        return payload
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid retained reporting-account review evidence.') from error


def _current(record, actor):
    forecast = record.forecast
    group = forecasts.verify(forecast)['group']
    original_flows = drafts.verify(record.payload['draft'])['inventory']['payload']['flows']['payload']
    if (forecast.status != 'approved'
        or BudgetReceiptForecast.objects.filter(proposal_id=record.proposal_id, fund_id=record.fund_id).aggregate(n=Max('version'))['n'] != forecast.version
        or forecasts._snapshot(forecast) != original_flows['sources']['forecast']):
        raise ValidationError('The original approved forecast changed or has a successor.')
    parents = {row.entity_key: row for row in forecasts.inventory(record.proposal, record.fund)}
    if set(parents) != {member['entity_key'] for member in group['members']}:
        raise ValidationError('The complete reconciliation entity inventory changed.')
    context = office_forms._retained_context(record.proposal)
    for member in group['members']:
        parent = parents[member['entity_key']]
        current = receipt_forecasts._capture_sources(record.proposal, parent, actor, context)
        original = member['forecast']['payload']['capture']
        if current['payload'] != original['payload'] or current['checksum'] != original['checksum']:
            raise ValidationError('Original reporting sources changed; prepare a successor.')
        forecasts._current_reconciliation(parent, actor)


@transaction.atomic(using='finance')
def prepare(*, forecast, actor, allocations, coverage_reference, code_reference, evidence, expected_latest):
    proposal = BudgetVersion.objects.select_for_update().get(pk=forecast.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=forecast.fund_id)
    _access(proposal, fund, actor, 'prepare')
    forecast = BudgetReceiptForecast.objects.get(pk=forecast.pk, proposal=proposal, fund=fund)
    flows = form1_flows.capture(forecast=forecast, actor=actor)
    draft = drafts.propose(form1_components.inventory(flows), allocations, coverage_reference=coverage_reference)
    data, metadata = summary_actuals.document(evidence, 'reporting code authority')
    reference = summary_actuals.text(code_reference, 'government-code applicability authority')
    latest = Record.objects.filter(proposal=proposal, fund=fund).aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest) is not int or latest != expected_latest:
        raise ValidationError('A newer account package exists; reload its history.')
    now = timezone.now(); public_id = uuid.uuid4()
    identity = dict(public_id=str(public_id), proposal=str(proposal.public_id), department_id=proposal.department_id,
        accounting_department_id=fund.department_id, fund_id=fund.pk, forecast=str(forecast.public_id),
        version=latest+1, prepared_by=actor.pk, prepared_at=now.isoformat())
    payload = dict(schema=1, identity=identity, draft=draft, code_reference=reference, evidence=metadata)
    record = Record(public_id=public_id, proposal=proposal, fund=fund, forecast=forecast, version=latest+1,
        department_id=proposal.department_id, department_label=proposal.department_label, prepared_by_id=actor.pk,
        prepared_at=now, payload=payload, payload_checksum=checksum(payload), evidence=data)
    verify(record); _sources(record, actor)
    record.save()
    record_event(record, 'form1_accounts_prepared', actor, reference, dict(payload_checksum=record.payload_checksum))
    return record


@transaction.atomic(using='finance')
def review(record, actor, *, approve, note, authority, codes_verified=False):
    proposal = BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=record.fund_id)
    _access(proposal, fund, actor, 'review')
    record = Record.objects.select_for_update().get(pk=record.pk, proposal=proposal, fund=fund)
    verify(record); _sources(record, actor)
    if type(approve) is not bool or record.status != 'prepared' or record.prepared_by_id == actor.pk:
        raise ValidationError('A different designated Accountant must decide a pending package once.')
    note = summary_actuals.text(note, 'independent account review note')
    authority = summary_actuals.text(authority, 'Accounting designation authority')
    if approve:
        latest = Record.objects.filter(proposal=proposal, fund=fund).aggregate(n=Max('version'))['n']
        if latest != record.version or not drafts.verify(record.payload['draft'])['selection_complete'] or codes_verified is not True:
            raise ValidationError('Review the latest complete selections and explicitly verify their code authority/applicability.')
        _current(record, actor)
    record.status = 'approved' if approve else 'returned'
    record.reviewed_by_id = actor.pk; record.reviewed_at = timezone.now()
    record.review_note = note; record.review_authority = authority
    record.decision_checksum = checksum(decision(record)); record._decision_write = True
    record.save()
    record_event(record, 'form1_accounts_'+record.status, actor, note, decision(record))
    return record


def snapshot(record, actor, *, export=False):
    record = Record.objects.select_related('proposal__fiscal_year', 'fund', 'forecast').get(pk=record.pk)
    _access(record.proposal, record.fund, actor, 'export' if export else 'view')
    payload = verify(record); _sources(record, actor, 'export' if export else 'view')
    return dict(payload=deepcopy(payload), payload_checksum=record.payload_checksum, decision=decision(record),
        decision_checksum=record.decision_checksum, independently_reviewed=record.status=='approved',
        code_authority_approved=record.status=='approved', form_issued=False)


def evidence_bytes(record, actor):
    record = Record.objects.select_related('proposal__fiscal_year', 'fund', 'forecast').get(pk=record.pk)
    _access(record.proposal, record.fund, actor, 'export'); verify(record); _sources(record, actor, 'export')
    return bytes(record.evidence)


@transaction.atomic(using='finance')
def is_current(record, actor):
    proposal = BudgetVersion.objects.select_for_update().get(pk=record.proposal_id)
    fund = Fund.objects.select_for_update().get(pk=record.fund_id)
    record = Record.objects.get(pk=record.pk, proposal=proposal, fund=fund)
    _access(proposal, fund, actor, 'view'); verify(record); _sources(record, actor)
    if record.status != 'approved' or Record.objects.filter(proposal=proposal, fund=fund).aggregate(n=Max('version'))['n'] != record.version:
        return False
    try:
        _current(record, actor)
        return True
    except ValidationError:
        return False
