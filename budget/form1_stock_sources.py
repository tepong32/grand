"""Authorized exact-boundary cash sources for Form 1; no forecast or issuance.

Capture uses the existing cash authorities, including original document validation.
Retained visibility does not certify freshness. Checksums alone authorize nothing.
"""
from copy import deepcopy
from datetime import date
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Max
from django.utils import timezone
from accounting import budget_cash, budget_cash_preparations as preparations
from accounting import budget_cash_certifications as joint
from accounting.cash_classifications import checksum

SCOPE_FIELDS={'department_id','budget_department_id','treasury_department_id',
    'fund_id','entity_key','balance_date','boundary'}


def scope(value):
    try:
        if (set(value)!=SCOPE_FIELDS or any(type(value[key]) is not int or value[key]<=0
            for key in ('department_id','budget_department_id','treasury_department_id','fund_id'))
            or not isinstance(value['entity_key'],str) or not value['entity_key']
            or value['boundary'] not in ('start_of_day','end_of_day')
            or not isinstance(value['balance_date'],str)
            or date.fromisoformat(value['balance_date']).isoformat()!=value['balance_date']
            or date.fromisoformat(value['balance_date'])>timezone.localdate()):
            raise ValidationError('Retain exact original cash owners, Fund, entity and historical date/boundary.')
        return deepcopy(value)
    except (KeyError,TypeError,ValueError) as error:
        raise ValidationError('Invalid exact cash stock scope.') from error


def _observe(*,route,identity,expected_scope,actor,export,current):
    expected=scope(expected_scope)
    try:
        if not isinstance(identity,str) or str(UUID(identity))!=identity:
            raise ValidationError('Select the original public cash source identity.')
    except (ValueError,TypeError,AttributeError) as error:
        raise ValidationError('Select the original public cash source identity.') from error
    if route=='historical':
        if export and not budget_cash.permitted(actor,'export'):raise PermissionDenied
        record=budget_cash.visible(actor).filter(public_id=identity,status='adopted').first()
        if not record:raise ValidationError('Select accessible independently adopted historical cash evidence.')
        original=budget_cash.verify(record)
        snapshot=dict(payload=deepcopy(original),payload_checksum=record.payload_checksum,
            decision=deepcopy(budget_cash.decision(record)),decision_checksum=record.decision_checksum)
        if current:
            latest=type(record).objects.filter(**{key:getattr(record,key) for key in (
                'department_id','fund_id','entity_key','balance_date','boundary')}).aggregate(n=Max('version'))['n']
            if record.version!=latest or record.fund.department_id!=record.department_id:
                raise ValidationError('Historical cash has a successor or changed Fund owner; select current evidence.')
        restrictions=original
    elif route=='native':
        if export and not preparations.permitted(actor,'export'):raise PermissionDenied
        record=preparations.visible(actor).filter(public_id=identity).first()
        if not record:raise ValidationError('Select accessible native cash evidence with its original restriction source.')
        snapshot=joint.snapshot(record,actor)
        if snapshot['payload']['status']!='jointly_certified':
            raise ValidationError('Select both original cash officer certifications; preparation or missing restrictions is insufficient.')
        original=snapshot['payload']['original_preparation']
        if current and not joint.is_current(record,actor):
            raise ValidationError('Native cash sources or preparation changed; select a certified successor.')
        restrictions=original['restriction_source']['payload']
    else:raise ValidationError('Choose an explicit historical or native cash source route.')
    actual={key:original['scope'][key] for key in SCOPE_FIELDS}
    if actual!=expected:
        raise ValidationError('Cash source owners, Fund, entity and exact balance date/boundary must match.')
    if original['restricted'] is None or original['net'] is None:
        raise ValidationError('Missing restriction evidence is not zero or net cash.')
    rows=budget_cash.restrictions(restrictions['restrictions'],no_restrictions=restrictions['no_restrictions'],
        declaration=restrictions['declaration'],overlap_basis=restrictions['overlap_basis'])
    total=sum((budget_cash.money(row['amount']) for row in rows),budget_cash.money('0'))
    if total!=budget_cash.money(original['restricted']) or budget_cash.money(original['gross'])-total!=budget_cash.money(original['net']):
        raise ValidationError('Original gross/restriction/net cash controls must reproduce exactly.')
    body=dict(schema=1,kind='form1_actual_stock_source',route=route,public_id=identity,
        scope=actual,snapshot=deepcopy(snapshot),gross=original['gross'],restricted=original['restricted'],
        net=original['net'],restrictions=deepcopy(rows),no_restrictions=restrictions['no_restrictions'],
        declaration=restrictions['declaration'],overlap_basis=restrictions['overlap_basis'],
        form_issued=False,cash_available=False,source_freshness_certified=False)
    return dict(payload=body,checksum=checksum(body))


def capture(*,route,identity,expected_scope,actor,export=False):
    """New source selection checks currentness at read time, not a posting lock."""
    return _observe(route=route,identity=identity,expected_scope=expected_scope,
        actor=actor,export=export,current=True)


def require_visible(source,actor,*,export=False):
    """Recheck original authorities without replacing historical source evidence."""
    try:
        body=source['payload']
        if source['checksum']!=checksum(body):raise ValidationError('Retained cash stock evidence changed.')
        observed=_observe(route=body['route'],identity=body['public_id'],expected_scope=body['scope'],
            actor=actor,export=export,current=False)
        if observed!=source:raise ValidationError('Retain the exact original cash source and decisions.')
        return deepcopy(body)
    except (KeyError,TypeError,ValueError,AttributeError) as error:
        raise ValidationError('Invalid retained original cash stock source.') from error
