"""Independent category/entity review; never statutory joint certification."""
from datetime import date, datetime
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from . import budget_native_actuals as actuals, budget_actuals_coverage as coverage
from .summary_actuals import text
from .access import department_for_user, has_explicit_permission
from .cash_classifications import checksum
from .models import NativeBudgetActualsPreparation as Record, Fund, AccountingAuditEvent


def permitted(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    return has_explicit_permission(actor, f'accounting.{action}_native_budget_actuals') and (
        action in ('view', 'export') or not is_finance_uat_viewer(actor))


def visible(actor, action='view'):
    if action not in ('view', 'export') or not permitted(actor, action):
        raise PermissionDenied
    owner=department_for_user(actor).pk
    return Record.objects.filter(Q(department_id=owner) | Q(budget_department_id=owner) | Q(treasury_department_id=owner))


def group(record):
    return Record.objects.filter(department_id=record.department_id, fund_id=record.fund_id,
        entity_key=record.entity_key, period_start=record.period_start, period_end=record.period_end)


def decision(record):
    return {key: getattr(record, key) for key in ('status', 'reviewed_by_id', 'reviewed_by_label',
        'review_authority', 'review_note', 'review_observation')} | {
        'preparation': str(record.public_id), 'payload_checksum': record.payload_checksum,
        'reviewed_at': record.reviewed_at.isoformat() if record.reviewed_at else None}


def verify(record):
    try:
        body = record.payload
        identity = {key: getattr(record, key) for key in ('department_id', 'fund_id',
            'budget_department_id', 'treasury_department_id', 'entity_key', 'entity_label', 'version',
            'prepared_by_id', 'prepared_by_label')}
        identity.update(public_id=str(record.public_id), period_start=record.period_start.isoformat(),
            period_end=record.period_end.isoformat(), prepared_at=record.prepared_at.isoformat())
        if (body['schema'] != 1 or body['kind'] != 'native_budget_actuals_preparation_record'
                or checksum(body) != record.payload_checksum or body['identity'] != identity):
            raise ValidationError('Native actuals preparation identity or immutable evidence changed.')
        proposal = coverage.verify(body['coverage'])
        scope = proposal['actuals']['payload']['scope']
        if (scope['fund']['id'] != record.fund_id or scope['fund']['department_id'] != record.department_id
            or scope['period_start'] != identity['period_start'] or scope['period_end'] != identity['period_end']
            or proposal['entity']['key'] != record.entity_key or proposal['entity']['label'] != record.entity_label):
            raise ValidationError('Native actuals preparation scope differs from its complete source coverage.')
        if record.status == 'submitted':
            if any((record.reviewed_by_id, record.reviewed_by_label, record.reviewed_at,
                    record.review_authority, record.review_note, record.review_observation, record.decision_checksum)):
                raise ValidationError('Pending preparation cannot invent independent review evidence.')
        elif record.status in ('approved', 'returned'):
            if (not record.reviewed_by_id or record.reviewed_by_id == record.prepared_by_id
                or not record.reviewed_at or record.reviewed_at < record.prepared_at
                or not record.review_authority.strip() or not record.review_note.strip()
                or record.decision_checksum != checksum(decision(record))):
                raise ValidationError('Retain the original independent actuals coverage decision.')
            if record.status == 'approved':
                actuals.verify(record.review_observation)
                if record.review_observation['source_checksum'] != proposal['actuals']['source_checksum']:
                    raise ValidationError('Review must observe this exact complete actuals source.')
                read_at = datetime.fromisoformat(record.review_observation['payload']['receipts']['captured_at'])
                if timezone.is_naive(read_at) or read_at > record.reviewed_at:
                    raise ValidationError('Source observation must precede its review decision.')
            elif record.review_observation is not None:
                raise ValidationError('Return must not invent a successful source observation.')
        else:
            raise ValidationError('Use an explicit retained preparation review state.')
        return body
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid retained native actuals preparation.') from error


@transaction.atomic(using='finance')
def prepare(*, actor, fund_id, budget_department_id, treasury_department_id, period_start, period_end,
            expected_latest, expected_source_checksum, entity, class_mappings, receipt_rows, expenditure_rows,
            reference, authority, reason):
    if not permitted(actor, 'prepare'):
        raise PermissionDenied
    from budget.models import BudgetCall
    from departments.models import Department
    owner = department_for_user(actor)
    if (type(period_start) is not date or type(period_end) is not date or
        period_start != date(period_end.year, 1, 1) or (period_end.month, period_end.day) not in ((6,30),(12,31))
        or period_end > timezone.localdate()):
        raise ValidationError('Prepare a completed calendar year or January–June actuals period.')
    if any(type(key) is not int or key <= 0 for key in (fund_id,budget_department_id,treasury_department_id)):
        raise ValidationError('Select explicit Fund and designated office identities.')
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=owner.pk).first()
    if (not fund or not BudgetCall.objects.filter(department_id=budget_department_id,
            fiscal_year__department_id=owner.pk).exists()
            or not Department.objects.filter(pk=treasury_department_id).exists()):
        raise ValidationError('Select this Accounting Fund, linked Budget office and designated Treasury office.')
    captured = actuals.capture(actor=actor, fund_id=fund.pk, period_start=period_start, period_end=period_end)
    if captured['source_checksum'] != expected_source_checksum:
        raise ValidationError('Actuals sources changed; reload complete category preparation.')
    proposal = coverage.propose(captured, entity=entity, class_mappings=class_mappings,
        receipt_rows=receipt_rows, expenditure_rows=expenditure_rows)
    entity = proposal['payload']['entity']
    versions = Record.objects.filter(department_id=owner.pk, fund=fund, entity_key=entity['key'],
        period_start=period_start, period_end=period_end)
    latest = versions.aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest) is not int or expected_latest != latest:
        raise ValidationError('A newer actuals preparation exists; reload its history.')
    if versions.exclude(budget_department_id=budget_department_id,
            treasury_department_id=treasury_department_id, entity_label=entity['label']).exists():
        raise ValidationError('Do not redirect the offices or entity of an existing preparation scope.')
    now = timezone.now(); label = (actor.get_full_name() or actor.username)[:160]
    record = Record(department_id=owner.pk, department_label=owner.name, fund=fund,
        budget_department_id=budget_department_id, treasury_department_id=treasury_department_id,
        entity_key=entity['key'], entity_label=entity['label'], period_start=period_start, period_end=period_end,
        version=latest+1, prepared_by_id=actor.pk, prepared_by_label=label, prepared_at=now)
    identity = {key: getattr(record,key) for key in ('department_id','fund_id','budget_department_id',
        'treasury_department_id','entity_key','entity_label','version','prepared_by_id','prepared_by_label')}
    identity.update(public_id=str(record.public_id), period_start=period_start.isoformat(),
        period_end=period_end.isoformat(), prepared_at=now.isoformat())
    record.payload = {'schema':1, 'kind':'native_budget_actuals_preparation_record', 'identity':identity,
        'coverage':proposal, 'reference':text(reference,'source reference',255),
        'authority':text(authority,'preparation authority'), 'reason':text(reason,'coverage explanation')}
    record.payload_checksum=checksum(record.payload); record.save(); verify(record)
    _audit(record,actor,'native_budget_actuals_prepared')
    return record


def _audit(record, actor, action):
    AccountingAuditEvent.objects.create(department_id=record.department_id, department_label=record.department_label,
        actor_id=actor.pk, actor_label=(actor.get_full_name() or actor.username)[:160], action=action,
        snapshot={'preparation':str(record.public_id),'version':record.version,
            'payload_checksum':record.payload_checksum,'decision_checksum':record.decision_checksum})


@transaction.atomic(using='finance')
def review(*, preparation_id, actor, approve, authority, note):
    if not permitted(actor,'review'):
        raise PermissionDenied
    if type(approve) is not bool:
        raise ValidationError('Choose explicit approval or return.')
    owner=department_for_user(actor)
    stored=Record.objects.filter(pk=preparation_id,department_id=owner.pk).first()
    if not stored: raise PermissionDenied
    fund=Fund.objects.select_for_update().get(pk=stored.fund_id)
    record=Record.objects.select_for_update().get(pk=stored.pk); verify(record)
    if record.status != 'submitted' or record.prepared_by_id == actor.pk:
        raise ValidationError('A different authorized reviewer must decide this pending preparation.')
    observation=None
    if approve:
        if fund.department_id != record.department_id or group(record).aggregate(n=Max('version'))['n'] != record.version:
            raise ValidationError('Source ownership or latest preparation changed; retain a return.')
        observation=actuals.capture(actor=actor,fund_id=record.fund_id,
            period_start=record.period_start,period_end=record.period_end)
        if observation['source_checksum'] != record.payload['coverage']['payload']['actuals']['source_checksum']:
            raise ValidationError('Actuals sources changed; prepare a successor.')
    record.status='approved' if approve else 'returned'; record.reviewed_by_id=actor.pk
    record.reviewed_by_label=(actor.get_full_name() or actor.username)[:160]; record.reviewed_at=timezone.now()
    record.review_authority=text(authority,'independent review authority'); record.review_note=text(note,'review explanation',4000)
    record.review_observation=observation; record.decision_checksum=checksum(decision(record))
    record._decision_write=True; record.save(); verify(record)
    _audit(record,actor,'native_budget_actuals_reviewed'); return record


def is_current(record, actor):
    if not visible(actor).filter(pk=record.pk).exists(): raise PermissionDenied
    if department_for_user(actor).pk != record.department_id: raise PermissionDenied
    verify(record)
    if (record.status != 'approved' or group(record).aggregate(n=Max('version'))['n'] != record.version
            or not Fund.objects.filter(pk=record.fund_id,department_id=record.department_id).exists()):
        return False
    return actuals.is_current(record.payload['coverage']['payload']['actuals'],actor)
