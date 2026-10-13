"""Versioned native statements with a distinct independent certification decision."""
import uuid
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .access import department_for_user, has_explicit_permission
from . import budget_native_sources as sources
from . import budget_native_statements as statements
from .cash_classifications import checksum
from .models import Fund, NativeBudgetStatement as Statement


def permitted(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    return has_explicit_permission(actor, f'accounting.{action}_native_budget_statements') and (
        action in ('view', 'export') or not is_finance_uat_viewer(actor))


def _fund(actor, fund_id, action):
    if not permitted(actor, action):
        raise PermissionDenied
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=department_for_user(actor).pk).first()
    if fund is None:
        raise PermissionDenied
    return fund


def _versions(fund_id, start, end):
    return Statement.objects.filter(fund_id=fund_id, period_start=start, period_end=end)


def _text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError(f'Retain an explicit {label} of at most {limit} characters.')
    return value.strip()


def decision_payload(record):
    return {'public_id': str(record.public_id), 'payload_checksum': record.payload_checksum,
        'status': record.status, 'decided_by_id': record.decided_by_id,
        'decided_by_label': record.decided_by_label,
        'decided_at': record.decided_at.isoformat() if record.decided_at else None,
        'authority': record.authority, 'note': record.decision_note}


def verify(record):
    data = record.payload
    identity = {'public_id': str(record.public_id), 'department_id': record.department_id,
        'fund_id': record.fund_id, 'period_start': record.period_start.isoformat(),
        'period_end': record.period_end.isoformat(), 'version': record.version,
        'prepared_by_id': record.prepared_by_id, 'prepared_by_label': record.prepared_by_label,
        'prepared_at': record.prepared_at.isoformat()}
    if (checksum(data) != record.payload_checksum or data.get('identity') != identity
            or data.get('kind') != 'native_budget_statement' or data.get('schema') != 1):
        raise ValidationError('Native statement identity no longer reproduces its retained evidence.')
    captured = sources.verify(data['source'])
    scope = captured['scope']
    if (scope['fund']['id'] != record.fund_id or scope['fund']['department_id'] != record.department_id
            or scope['period_start'] != identity['period_start'] or scope['period_end'] != identity['period_end']
            or statements.project(data['source']) != data['statement']
            or not data['statement']['payload']['classification_complete']):
        raise ValidationError('Native statement coverage does not reproduce its source.')
    if record.status != Statement.SUBMITTED:
        if (record.status not in (Statement.CERTIFIED, Statement.RETURNED)
                or not record.decided_by_id or record.decided_by_id == record.prepared_by_id
                or not record.decided_at or not record.authority or not record.decision_note
                or record.decision_checksum != checksum(decision_payload(record))):
            raise ValidationError('Native statement decision does not reproduce independent authority.')
    return data


@transaction.atomic(using='finance')
def propose(*, actor, fund_id, period_start, period_end, expected_latest, expected_source_checksum,
            reason, coverage, evidence_reference):
    fund = _fund(actor, fund_id, 'prepare')
    if (type(period_start) is not date or type(period_end) is not date
            or period_start != date(period_end.year, 1, 1)
            or (period_end.month, period_end.day) not in ((6, 30), (12, 31))):
        raise ValidationError('Use a completed January–June or full calendar-year statement period.')
    latest = _versions(fund.pk, period_start, period_end).aggregate(number=Max('version'))['number'] or 0
    if type(expected_latest) is not int or expected_latest != latest:
        raise ValidationError('A newer statement exists; reload its complete history.')
    source = sources.capture(actor=actor, fund_id=fund.pk, period_start=period_start, period_end=period_end)
    if source['checksum'] != expected_source_checksum:
        raise ValidationError('Source or classification coverage changed; prepare from a fresh cohort.')
    statement = statements.project(source)
    if not statement['payload']['classification_complete']:
        raise ValidationError('Resolve every source classification before native certification preparation; empty evidence is not certified zero.')
    now, public_id = timezone.now(), uuid.uuid4()
    identity = {'public_id': str(public_id), 'department_id': fund.department_id, 'fund_id': fund.pk,
        'period_start': period_start.isoformat(), 'period_end': period_end.isoformat(), 'version': latest + 1,
        'prepared_by_id': actor.pk, 'prepared_by_label': actor.get_full_name() or actor.username,
        'prepared_at': now.isoformat()}
    payload = {'schema': 1, 'kind': 'native_budget_statement', 'identity': identity,
        'source': source, 'statement': statement,
        'reason': _text(reason, 2000, 'preparation explanation'),
        'coverage': _text(coverage, 2000, 'source completeness basis'),
        'evidence_reference': _text(evidence_reference, 255, 'supporting evidence reference')}
    return Statement.objects.create(public_id=public_id, department_id=fund.department_id,
        department_label=department_for_user(actor).name, fund=fund,
        period_start=period_start, period_end=period_end, version=latest + 1,
        payload=payload, payload_checksum=checksum(payload), prepared_by_id=actor.pk,
        prepared_by_label=identity['prepared_by_label'], prepared_at=now)


@transaction.atomic(using='finance')
def decide(*, statement_id, actor, certify, authority, note):
    if type(certify) is not bool:
        raise ValidationError('Choose an explicit certification or return decision.')
    # Read identity only; acquire shared Fund before any statement lock.
    stored = Statement.objects.get(pk=statement_id)
    _fund(actor, stored.fund_id, 'certify')
    record = Statement.objects.select_for_update().get(pk=stored.pk)
    verify(record)
    if record.status != Statement.SUBMITTED or record.prepared_by_id == actor.pk:
        raise ValidationError('A different authorized officer must decide a pending statement.')
    if certify:
        latest = _versions(record.fund_id, record.period_start, record.period_end).aggregate(number=Max('version'))['number']
        if record.version != latest:
            raise ValidationError('A newer statement exists; return this older preparation.')
        if not sources.is_current(record.payload['source'], actor):
            raise ValidationError('Source or classification changed; return this preparation and prepare a successor.')
    record.authority = _text(authority, 255, 'officer designation or certification authority')
    record.decision_note = _text(note, 2000, 'independent coverage review')
    record.status = Statement.CERTIFIED if certify else Statement.RETURNED
    record.decided_by_id = actor.pk
    record.decided_by_label = actor.get_full_name() or actor.username
    record.decided_at = timezone.now()
    record.decision_checksum = checksum(decision_payload(record))
    record._decision_write = True
    record.save(update_fields=('status', 'authority', 'decision_note', 'decided_by_id',
        'decided_by_label', 'decided_at', 'decision_checksum'))
    return record


def is_current(record, actor):
    if not any(permitted(actor, action) for action in ('view', 'prepare', 'certify', 'export')):
        raise PermissionDenied
    if record.department_id != department_for_user(actor).pk:
        raise PermissionDenied
    verify(record)
    latest = _versions(record.fund_id, record.period_start, record.period_end).filter(
        status=Statement.CERTIFIED).order_by('-version').values_list('pk', flat=True).first()
    return (record.status == Statement.CERTIFIED and record.pk == latest
            and sources.is_current(record.payload['source'], actor))
