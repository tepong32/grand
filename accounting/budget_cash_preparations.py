"""Retained native cash sources with explicit historical restriction reconciliation."""
from copy import deepcopy
from datetime import date
from hashlib import sha256
import re
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from . import budget_cash, budget_native_cash
from .access import department_for_user, has_explicit_permission
from .cash_classifications import checksum
from .models import NativeBudgetCashPreparation as Record, BudgetCashEvidence, Fund, AccountingAuditEvent


def permitted(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    return bool(actor.is_active and department_for_user(actor)
        and has_explicit_permission(actor, f'accounting.{action}_native_budget_cash')
        and (action in ('view', 'export') or not is_finance_uat_viewer(actor)))


def visible(actor):
    if not any(permitted(actor, action) for action in ('view', 'prepare', 'export')):
        raise PermissionDenied
    owner = department_for_user(actor)
    try:
        sources = budget_cash.visible(actor).values('pk')  # Both source models live in Finance.
        source_scope = Q(restriction_source__isnull=True) | Q(restriction_source_id__in=sources)
    except PermissionDenied:
        source_scope = Q(restriction_source__isnull=True)
    return Record.objects.filter(Q(department_id=owner.pk) | Q(budget_department_id=owner.pk)
        | Q(treasury_department_id=owner.pk)).filter(source_scope).select_related('fund').defer('certificate', 'reconciliation')


@transaction.atomic(using='finance')
def prepare(*, actor, fund_id, opening_batch_id, budget_department_id, treasury_department_id,
            entity_key, coverage_authority, balance_date, boundary, expected_latest, restriction_source_id=None):
    if not permitted(actor, 'prepare'):
        raise PermissionDenied
    from budget.models import BudgetCall
    from departments.models import Department
    owner = department_for_user(actor)
    if type(balance_date) is not date or balance_date > timezone.localdate() or boundary not in ('start_of_day', 'end_of_day'):
        raise ValidationError('Select a historical cash date and explicit start/end boundary.')
    entity_key = budget_cash.shared.text(entity_key, 'reporting entity', 80).lower()
    if entity_key != 'general' and not re.fullmatch(r'enterprise:[a-z0-9][a-z0-9_-]{0,60}', entity_key):
        raise ValidationError('Use the explicitly designated reporting entity key.')
    if any(type(value) is not int or value <= 0 for value in (fund_id, opening_batch_id, budget_department_id, treasury_department_id)):
        raise ValidationError('Select explicit source and office identities.')
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=owner.pk).first()
    if (not fund or not BudgetCall.objects.filter(department_id=budget_department_id,
        fiscal_year__department_id=owner.pk).exists() or not Department.objects.filter(pk=treasury_department_id).exists()):
        raise ValidationError('Select this Accounting fund and its designated Budget/Treasury offices.')
    group = Record.objects.filter(department_id=owner.pk, fund=fund, entity_key=entity_key,
        balance_date=balance_date, boundary=boundary)
    latest = group.aggregate(n=Max('version'))['n'] or 0
    if type(expected_latest) is not int or expected_latest != latest:
        raise ValidationError('A newer native cash preparation exists; reload its history.')
    if group.exclude(budget_department_id=budget_department_id, treasury_department_id=treasury_department_id).exists():
        raise ValidationError('Do not redirect the offices of an existing cash preparation scope.')
    native = budget_native_cash.capture(actor=actor, fund_id=fund_id, opening_batch_id=opening_batch_id,
        entity_key=entity_key, coverage_authority=coverage_authority, balance_date=balance_date, boundary=boundary)
    budget_native_cash.verify(native)
    restriction, certificate, reconciliation = None, b'', b''
    linked = None
    if restriction_source_id is not None:
        if type(restriction_source_id) is not int or restriction_source_id <= 0:
            raise ValidationError('Select one explicit adopted restriction source.')
        restriction = BudgetCashEvidence.objects.select_for_update().filter(pk=restriction_source_id,
            department_id=owner.pk, fund_id=fund_id, budget_department_id=budget_department_id,
            treasury_department_id=treasury_department_id, entity_key=entity_key,
            balance_date=balance_date, boundary=boundary, status='adopted').first()
        if not restriction:
            raise ValidationError('Restriction evidence must be independently adopted for this exact cash scope.')
        if not budget_cash.visible(actor).filter(pk=restriction.pk).exists():
            raise PermissionDenied('The original restriction source is not visible to this preparer.')
        historical = budget_cash.verify(restriction)
        if budget_cash.money(historical['gross']) != budget_cash.money(native['payload']['gross']):
            raise ValidationError('Native gross cash must reconcile exactly to the adopted restriction source gross.')
        linked = {'id': restriction.pk, 'public_id': str(restriction.public_id), 'version': restriction.version,
            'payload': deepcopy(historical), 'payload_checksum': restriction.payload_checksum,
            'decision': budget_cash.decision(restriction), 'decision_checksum': restriction.decision_checksum}
        certificate, reconciliation = bytes(restriction.certificate), bytes(restriction.reconciliation)
    now = timezone.now(); label = (actor.get_full_name() or actor.username)[:160]
    payload = {'schema': 1, 'kind': 'native_budget_cash_preparation', 'version': latest + 1,
        'scope': {'department_id': owner.pk, 'fund_id': fund.pk, 'budget_department_id': budget_department_id,
            'treasury_department_id': treasury_department_id, 'entity_key': entity_key,
            'balance_date': balance_date.isoformat(), 'boundary': boundary},
        'native': native, 'restriction_source': linked, 'gross': native['payload']['gross'],
        'restricted': linked['payload']['restricted'] if linked else None,
        'net': linked['payload']['net'] if linked else None,
        'restriction_status': 'reconciled_historical_source' if linked else 'not_supplied',
        'certification_status': 'not_certified', 'prepared_by': actor.pk,
        'prepared_by_label': label, 'prepared_at': now.isoformat()}
    record = Record.objects.create(department_id=owner.pk, department_label=owner.name, fund=fund,
        budget_department_id=budget_department_id, treasury_department_id=treasury_department_id,
        entity_key=entity_key, balance_date=balance_date, boundary=boundary, version=latest + 1,
        restriction_source=restriction, payload=payload, payload_checksum=checksum(payload),
        certificate=certificate, reconciliation=reconciliation, prepared_by_id=actor.pk,
        prepared_by_label=label, prepared_at=now)
    verify(record)
    AccountingAuditEvent.objects.create(department_id=owner.pk, department_label=owner.name,
        actor_id=actor.pk, actor_label=label, action='native_budget_cash_prepared',
        snapshot={'preparation': str(record.public_id), 'version': record.version,
            'payload_checksum': record.payload_checksum, 'source_checksum': native['source_checksum']})
    return record


def verify(record):
    try:
        payload = record.payload
        scope = {key: getattr(record, key) for key in ('department_id', 'fund_id', 'budget_department_id',
            'treasury_department_id', 'entity_key', 'boundary')}
        scope['balance_date'] = record.balance_date.isoformat()
        if (checksum(payload) != record.payload_checksum or payload['scope'] != scope
            or payload['schema'] != 1 or payload['kind'] != 'native_budget_cash_preparation'
            or payload['version'] != record.version or payload['prepared_by'] != record.prepared_by_id
            or payload['prepared_by_label'] != record.prepared_by_label
            or payload['prepared_at'] != record.prepared_at.isoformat()
            or payload['certification_status'] != 'not_certified'):
            raise ValidationError('Retained native cash preparation identity or evidence changed.')
        native = budget_native_cash.verify(payload['native'])
        if native['schema'] != 2 or any(native['scope'][key] != scope[key]
            for key in ('entity_key', 'balance_date', 'boundary')) or native['scope']['fund']['id'] != record.fund_id or native['scope']['fund']['department_id'] != record.department_id or native['gross'] != payload['gross']:
            raise ValidationError('Retained native cash preparation does not reproduce its source scope.')
        linked = payload['restriction_source']
        if linked is None:
            if (record.restriction_source_id or payload['restricted'] is not None or payload['net'] is not None
                or payload['restriction_status'] != 'not_supplied' or record.certificate or record.reconciliation):
                raise ValidationError('Missing restrictions cannot establish zero or net cash.')
        else:
            historical, decision = linked['payload'], linked['decision']
            if (linked['id'] != record.restriction_source_id or checksum(historical) != linked['payload_checksum']
                or checksum(decision) != linked['decision_checksum'] or decision['status'] != 'adopted'
                or decision['record'] != linked['public_id'] or decision['payload_checksum'] != linked['payload_checksum']
                or decision['actor'] == historical['prepared_by'] or not decision['actor']
                or linked['version'] != historical['version']
                or any(historical['scope'][key] != value for key, value in scope.items())
                or payload['restriction_status'] != 'reconciled_historical_source'):
                raise ValidationError('Retained restriction source scope or independent decision changed.')
            for field in ('certificate', 'reconciliation'):
                if sha256(bytes(getattr(record, field))).hexdigest() != historical[field]['sha256']:
                    raise ValidationError('Retained original restriction documents changed.')
            rows = budget_cash.restrictions(historical['restrictions'], no_restrictions=historical['no_restrictions'],
                declaration=historical['declaration'], overlap_basis=historical['overlap_basis'])
            total = sum((budget_cash.money(row['amount']) for row in rows), budget_cash.money('0'))
            if (budget_cash.money(payload['gross']) != budget_cash.money(historical['gross'])
                or total != budget_cash.money(payload['restricted']) or payload['restricted'] != historical['restricted']
                or payload['net'] != historical['net']
                or budget_cash.money(payload['gross']) - total != budget_cash.money(payload['net'])):
                raise ValidationError('Native gross, restriction and net cash must reconcile exactly.')
        return payload
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Retained native cash preparation has invalid source structure.') from error


def is_current(record, actor):
    if not visible(actor).filter(pk=record.pk).exists():
        raise PermissionDenied
    payload = verify(record)
    # Source recapture is an Accounting-owner read. Partner access to retained
    # preparations does not grant access to that office's entire live ledger.
    if department_for_user(actor).pk != record.department_id:
        raise PermissionDenied
    if not budget_native_cash.is_current(payload['native'], actor):
        return False
    if record.restriction_source_id:
        source = BudgetCashEvidence.objects.get(pk=record.restriction_source_id)
        budget_cash.verify(source)
        latest = BudgetCashEvidence.objects.filter(department_id=record.department_id, fund_id=record.fund_id,
            entity_key=record.entity_key, balance_date=record.balance_date, boundary=record.boundary).aggregate(n=Max('version'))['n']
        return latest == source.version and source.payload_checksum == payload['restriction_source']['payload_checksum'] and source.decision_checksum == payload['restriction_source']['decision_checksum']
    return True
