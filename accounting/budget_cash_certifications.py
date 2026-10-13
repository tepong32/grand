"""Joint fixed-cohort cash decisions; never cash capacity or a period posting lock."""
from datetime import datetime
import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import budget_cash, budget_cash_preparations as preparations, budget_native_cash
from .access import department_for_user, has_explicit_permission
from .cash_classifications import checksum
from .models import NativeBudgetCashDecision as Decision, NativeBudgetCashPreparation as Preparation
from .models import Fund, BudgetCashEvidence, AccountingAuditEvent

ROLES = ('accountant', 'treasurer')


def permitted(actor, role):
    from vouchers.roles import is_finance_uat_viewer
    return bool(role in ROLES and actor.is_active and department_for_user(actor)
        and not is_finance_uat_viewer(actor)
        and has_explicit_permission(actor, f'accounting.certify_{role}_native_budget_cash'))


def _visible(record, actor):
    if not preparations.visible(actor).filter(pk=record.pk).exists():
        raise PermissionDenied


def _group(record):
    return Preparation.objects.filter(department_id=record.department_id, fund_id=record.fund_id,
        entity_key=record.entity_key, balance_date=record.balance_date, boundary=record.boundary)


def _observe(record):
    """Only called after exact record visibility/role authorization, never client scope."""
    from departments.models import Department
    payload = preparations.verify(record)
    owner = Department.objects.get(pk=record.department_id)
    native = payload['native']; scope = native['payload']['scope']
    observed = budget_native_cash._capture_for_owner(owner=owner, fund_id=record.fund_id,
        opening_batch_id=native['payload']['opening']['id'], entity_key=record.entity_key,
        coverage_authority=scope['coverage_authority'], balance_date=record.balance_date,
        boundary=record.boundary)
    if observed['source_checksum'] != native['source_checksum']:
        raise ValidationError('Native cash sources changed; prepare and reconcile a successor.')
    if record.restriction_source_id:
        source = BudgetCashEvidence.objects.get(pk=record.restriction_source_id)
        budget_cash.verify(source)
        latest = BudgetCashEvidence.objects.filter(department_id=record.department_id,
            fund_id=record.fund_id, entity_key=record.entity_key, balance_date=record.balance_date,
            boundary=record.boundary).aggregate(n=Max('version'))['n']
        retained = payload['restriction_source']
        if (source.status != 'adopted' or source.version != latest
            or source.payload_checksum != retained['payload_checksum']
            or source.decision_checksum != retained['decision_checksum']):
            raise ValidationError('Restriction source changed; reconcile a successor preparation.')
    return observed


def verify_decision(record, decision):
    original = preparations.verify(record)
    payload = decision.payload
    try:
        identity = {'public_id': str(decision.public_id), 'preparation': str(record.public_id),
            'preparation_checksum': record.payload_checksum, 'department_id': record.department_id,
            'role': decision.role, 'outcome': decision.outcome, 'actor_id': decision.actor_id,
            'actor_label': decision.actor_label, 'actor_department_id': decision.actor_department_id,
            'decided_at': decision.decided_at.isoformat()}
        office = record.department_id if decision.role == 'accountant' else record.treasury_department_id
        if (checksum(payload) != decision.payload_checksum or payload['schema'] != 1
            or payload['kind'] != 'native_budget_cash_role_decision' or payload['identity'] != identity
            or decision.preparation_id != record.pk or decision.department_id != record.department_id
            or decision.role not in ROLES or decision.outcome not in ('certified', 'returned')
            or decision.actor_department_id != office or not decision.actor_id
            or decision.actor_id == record.prepared_by_id
            or not payload['authority'].strip() or not payload['note'].strip()):
            raise ValidationError('Native cash decision identity or independent authority changed.')
        observation = payload['observation']
        if decision.outcome == 'certified':
            if original['restricted'] is None or original['net'] is None:
                raise ValidationError('Missing restriction evidence cannot be jointly certified.')
            budget_native_cash.verify(observation)
            if observation['source_checksum'] != original['native']['source_checksum']:
                raise ValidationError('Native cash decision did not observe its exact source cohort.')
            # Retain the source read time separately from decision time. Neither
            # time asserts that ordinary posting was locked out until commit.
            read_at = datetime.fromisoformat(observation['captured_at'])
            if timezone.is_naive(read_at) or read_at > decision.decided_at:
                raise ValidationError('Native cash observation must precede its decision.')
        elif observation is not None:
            raise ValidationError('A return must not invent a successful source observation.')
        return payload
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Invalid retained native cash decision structure.') from error


def _decisions(record):
    decisions = list(record.joint_decisions.order_by('decided_at', 'pk'))
    for decision in decisions:
        verify_decision(record, decision)
    if (len({item.role for item in decisions}) != len(decisions)
        or len({item.actor_id for item in decisions}) != len(decisions)
        or any(item.outcome == 'returned' for item in decisions[:-1])):
        raise ValidationError('Native cash joint decisions do not reproduce independent closure.')
    return decisions


@transaction.atomic(using='finance')
def decide(*, preparation_id, actor, role, certify, authority, note):
    if not permitted(actor, role):
        raise PermissionDenied
    if type(certify) is not bool:
        raise ValidationError('Choose an explicit certification or return.')
    stored = Preparation.objects.get(pk=preparation_id)
    _visible(stored, actor)
    office = stored.department_id if role == 'accountant' else stored.treasury_department_id
    if department_for_user(actor).pk != office:
        raise PermissionDenied
    fund = Fund.objects.select_for_update().get(pk=stored.fund_id)
    record = Preparation.objects.select_for_update().get(pk=stored.pk)
    preparations.verify(record)
    decisions = _decisions(record)
    if (actor.pk == record.prepared_by_id or any(item.actor_id == actor.pk for item in decisions)
        or any(item.role == role or item.outcome == 'returned' for item in decisions)):
        raise ValidationError('A different authorized officer must decide each still-pending role.')
    authority = budget_cash.shared.text(authority, 'certification authority', 2000)
    note = budget_cash.shared.text(note, 'decision explanation', 4000)
    observation = None
    if certify:
        if fund.department_id != record.department_id:
            raise ValidationError('The Fund no longer belongs to this Accounting owner.')
        if record.version != _group(record).aggregate(n=Max('version'))['n']:
            raise ValidationError('A newer preparation exists; return the obsolete preparation.')
        if record.payload['restricted'] is None or record.payload['net'] is None:
            raise ValidationError('Reconcile explicit restrictions or evidenced zero before certification.')
        observation = _observe(record)
    now, public_id = timezone.now(), uuid.uuid4()
    identity = {'public_id': str(public_id), 'preparation': str(record.public_id),
        'preparation_checksum': record.payload_checksum, 'department_id': record.department_id,
        'role': role, 'outcome': 'certified' if certify else 'returned', 'actor_id': actor.pk,
        'actor_label': (actor.get_full_name() or actor.username)[:160],
        'actor_department_id': office, 'decided_at': now.isoformat()}
    payload = {'schema': 1, 'kind': 'native_budget_cash_role_decision', 'identity': identity,
        'authority': authority, 'note': note, 'observation': observation}
    decision = Decision.objects.create(public_id=public_id, preparation=record,
        department_id=record.department_id, department_label=record.department_label,
        role=role, outcome=identity['outcome'], actor_id=actor.pk, actor_label=identity['actor_label'],
        actor_department_id=office, decided_at=now, payload=payload, payload_checksum=checksum(payload))
    verify_decision(record, decision)
    AccountingAuditEvent.objects.create(department_id=record.department_id,
        department_label=record.department_label, actor_id=actor.pk, actor_label=identity['actor_label'],
        action='native_budget_cash_decided', snapshot={'preparation': str(record.public_id),
            'decision': str(public_id), 'role': role, 'outcome': identity['outcome'],
            'preparation_checksum': record.payload_checksum, 'decision_checksum': decision.payload_checksum})
    return decision


def snapshot(record, actor):
    _visible(record, actor)
    original = preparations.verify(record)
    decisions = _decisions(record)
    status = ('returned' if any(item.outcome == 'returned' for item in decisions) else
        'jointly_certified' if len(decisions) == 2 else 'awaiting_joint_certification')
    payload = {'schema': 1, 'kind': 'native_budget_joint_cash_snapshot',
        'preparation': str(record.public_id), 'preparation_checksum': record.payload_checksum,
        'original_preparation': original, 'status': status,
        'decisions': [{'payload': item.payload, 'checksum': item.payload_checksum} for item in decisions]}
    return {'payload': payload, 'checksum': checksum(payload)}


def is_current(record, actor):
    retained = snapshot(record, actor)
    if (retained['payload']['status'] != 'jointly_certified'
        or Fund.objects.get(pk=record.fund_id).department_id != record.department_id
        or record.version != _group(record).aggregate(n=Max('version'))['n']):
        return False
    try:
        _observe(record)
    except ValidationError:
        return False
    return True
