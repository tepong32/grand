"""Explicit actuals source routes; projection is for reconciliation, not adoption."""
from copy import deepcopy
from django.core.exceptions import ValidationError, PermissionDenied
from accounting import summary_actuals
from accounting import budget_actuals_preparations as preparations
from accounting import budget_actuals_certifications as certifications
from accounting.cash_classifications import checksum


def project_native(captured):
    body = certifications.verify_snapshot(captured)
    if body['status'] != 'jointly_certified':
        raise ValidationError('Select jointly certified native actuals, with both officer decisions.')
    original = body['original_preparation']
    identity = original['identity']
    scope = {key: identity[key] for key in ('department_id', 'budget_department_id',
        'treasury_department_id', 'fund_id', 'entity_key', 'entity_label', 'period_start', 'period_end')}
    coverage = original['coverage']['payload']
    scope['fund_code'] = coverage['actuals']['payload']['scope']['fund']['code']
    rows = [dict(kind=kind, **deepcopy(row)) for kind in ('receipt', 'expenditure')
        for row in coverage[kind+'_rows']]
    return dict(scope=scope, rows=rows, totals=deepcopy(body['totals']),
        reference=original['reference'], version=identity['version'])


def capture(*, actor, budget_department_id, identity, route):
    if route == 'native':
        record = preparations.visible(actor).filter(public_id=identity,
            budget_department_id=budget_department_id).first()
        if not record:
            raise ValidationError('Select accessible native actuals for this Budget office.')
        captured = certifications.snapshot(record, actor)
        payload = project_native(captured)
        if not certifications.is_current(record, actor):
            raise ValidationError('Native actuals are stale; prepare and certify a successor.')
        return dict(route=route, id=str(record.public_id), snapshot=deepcopy(captured),
            payload=payload, payload_checksum=checksum(payload))
    if route != 'historical':
        raise ValidationError('Choose one explicit native or historical route per period.')
    record = summary_actuals.visible(actor).filter(public_id=identity, status='approved',
        scope__budget_department_id=budget_department_id).first()
    if not record:
        raise ValidationError('Select accessible adopted joint evidence for both comparison periods.')
    payload = summary_actuals.verify(record)
    return dict(route=route, id=str(record.public_id), payload=deepcopy(payload),
        payload_checksum=record.payload_checksum, decision_checksum=record.decision_checksum,
        decision=deepcopy(summary_actuals.decision_snapshot(record)))


def verify(source):
    try:
        if source['route'] == 'native':
            body = certifications.verify_snapshot(source['snapshot'])
            if (source['id'] != body['original_preparation']['identity']['public_id']
                or source['payload'] != project_native(source['snapshot'])
                or source['payload_checksum'] != checksum(source['payload'])):
                raise ValidationError('Retained native reconciliation source changed.')
        elif source['route'] == 'historical':
            original = source['decision']
            if (checksum(source['payload']) != source['payload_checksum']
                or checksum(original) != source['decision_checksum'] or original['record'] != source['id']
                or original['payload_checksum'] != source['payload_checksum'] or original['status'] != 'approved'
                or not original['reviewed_by'] or original['reviewed_by'] == source['payload']['prepared_by']
                or not original['reviewed_at'] or not original['authority'] or not original['note']):
                raise ValidationError('Retained original adoption evidence changed.')
        else:
            raise ValidationError('Retain one explicit actuals source route per period.')
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError('Retain complete original actuals source evidence.') from error
    return source['payload']


def require_current(source, *, actor, budget_department_id):
    observed = capture(actor=actor, budget_department_id=budget_department_id,
        identity=source['id'], route=source['route'])
    if source['route'] == 'historical':
        record = summary_actuals.visible(actor).get(public_id=source['id'])
        if record.scope.current_version_id != record.pk:
            raise ValidationError('The adopted historical actuals source has been superseded.')
    if observed != source:
        raise ValidationError('Selected actuals evidence changed; retain a successor reconciliation.')


def require_visible(payload, actor, action='view'):
    """Retained source exports must not bypass current source read/export authority."""
    if payload['schema'] != 3:
        return
    for source in payload['actuals'].values():
        if source['route'] == 'native' and not preparations.visible(actor, action).filter(
            public_id=source['id'], budget_department_id=payload['department_id']).exists():
            raise PermissionDenied
