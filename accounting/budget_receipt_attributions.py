"""Independent, versioned receipt review over authoritative retained sources."""
from copy import deepcopy
from datetime import datetime
import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from .access import department_for_user, has_explicit_permission
from .cash_classifications import checksum
from . import budget_receipt_sources as sources, budget_receipt_partitions as partitions
from .models import (Fund, AccountingAuditEvent, BudgetReceiptAttributionBatch as Batch,
    BudgetReceiptAttribution as Member, BudgetReceiptAttributionHead as Head)


def permitted(actor, action):
    from vouchers.roles import is_finance_uat_viewer
    return has_explicit_permission(actor, 'accounting.' + action + '_budget_receipt_attributions') and (
        action in ('view', 'export') or not is_finance_uat_viewer(actor))


def _owner(actor, action):
    if not permitted(actor, action):
        raise PermissionDenied
    return department_for_user(actor)


def capture(*, actor, fund_id, period_start, period_end):
    if not any(permitted(actor, action) for action in ('view', 'prepare', 'review', 'export')):
        raise PermissionDenied
    return sources._capture_for_owner(department_for_user(actor), fund_id=fund_id,
        period_start=period_start, period_end=period_end)


def _member(record):
    return {'public_id': str(record.public_id), 'entry_id': record.entry_id,
        'version': record.version, 'base_version': record.base_version,
        'partition': deepcopy(record.partition), 'dependencies': deepcopy(record.dependencies)}


def _proposal(batch, members):
    return {'schema': 1, 'kind': 'native_budget_receipt_attribution_batch', 'public_id': str(batch.public_id),
        'department_id': batch.department_id, 'department_label': batch.department_label, 'fund_id': batch.fund_id,
        'period_start': batch.period_start.isoformat(), 'period_end': batch.period_end.isoformat(),
        'prepared_by_id': batch.prepared_by_id, 'prepared_by_label': batch.prepared_by_label,
        'prepared_at': batch.prepared_at.isoformat(), 'reason': batch.payload['reason'],
        'evidence_reference': batch.payload['evidence_reference'], 'inventory': deepcopy(batch.payload['inventory']),
        'predecessor_snapshots': deepcopy(batch.payload['predecessor_snapshots']),
        'members': [_member(item) for item in members]}


def _decision(batch):
    return {'batch': str(batch.public_id), 'proposal_checksum': batch.payload_checksum,
        'status': batch.status, 'prepared_by_id': batch.prepared_by_id, 'prepared_at': batch.prepared_at.isoformat(),
        'reviewed_by_id': batch.reviewed_by_id, 'reviewed_by_label': batch.reviewed_by_label,
        'reviewed_at': batch.reviewed_at.isoformat() if batch.reviewed_at else None, 'review_note': batch.review_note}


def _check_decision(body, digest, *, approved=False):
    if (checksum(body) != digest or body['status'] not in (Batch.APPROVED, Batch.RETURNED)
        or (approved and body['status'] != Batch.APPROVED)
        or not body['reviewed_by_id'] or body['reviewed_by_id'] == body['prepared_by_id']
        or not body['reviewed_by_label'] or not body['review_note'].strip()
        or datetime.fromisoformat(body['reviewed_at']) < datetime.fromisoformat(body['prepared_at'])):
        raise ValidationError('Retain the exact independent receipt review decision.')


def verify_snapshot(retained):
    """Pure integrity/reproduction; checksums do not authenticate supplied artifacts."""
    try:
        body = retained['payload']; inventory = body['inventory']
        uuid.UUID(body['public_id'])
        source = sources.verify(inventory); scope = source['scope']
        if (retained['checksum'] != checksum(body) or body['schema'] != 1
            or body['kind'] != 'native_budget_receipt_attribution_batch'
            or body['department_id'] != scope['fund']['department_id'] or body['fund_id'] != scope['fund']['id']
            or body['period_start'] != scope['period_start'] or body['period_end'] != scope['period_end']
            or not body['prepared_by_id'] or not body['prepared_by_label']
            or not body['reason'].strip() or not body['evidence_reference'].strip() or not body['members']):
            raise ValidationError('Receipt batch does not reproduce its retained source scope and proposal.')
        available = {row['entry_id'] for row in source['journals']}
        seen, identities = set(), set()
        for member in body['members']:
            uuid.UUID(member['public_id'])
            if (member['entry_id'] not in available or member['entry_id'] in seen or member['public_id'] in identities
                or type(member['version']) is not int or member['version'] < 1
                or type(member['base_version']) is not int or not 0 <= member['base_version'] < member['version']
                or partitions.verify(inventory, member['partition'])['entry_id'] != member['entry_id']):
                raise ValidationError('Retain one exact source member and version in each complete batch.')
            seen.add(member['entry_id']); identities.add(member['public_id'])
            dependency = member['partition']['payload']['dependency']
            pins = member['dependencies']
            if not isinstance(pins, list):
                raise ValidationError('Retain a complete predecessor decision manifest.')
            for pin in pins:
                if not dependency or pin['entry_id'] != dependency['payload']['entry_id'] or pin['partition_checksum'] != dependency['checksum']:
                    raise ValidationError('Receipt predecessor decision does not match its exact inherited partition.')
                _check_decision(pin['decision'], pin['decision_checksum'], approved=True)
                if pin['decision']['batch'] != pin['batch'] or pin['decision']['proposal_checksum'] != pin['proposal_checksum']:
                    raise ValidationError('Retain the original predecessor proposal and independent decision identities.')
                uuid.UUID(pin['member']); uuid.UUID(pin['batch'])
                previous = body['predecessor_snapshots'][pin['batch']]
                original = verify_snapshot(previous)
                originals = [item for item in original['members'] if item['public_id'] == pin['member']]
                if (original['public_id'] != pin['batch'] or previous['checksum'] != pin['proposal_checksum']
                    or previous['decision'] != pin['decision']
                    or previous['decision_checksum'] != pin['decision_checksum']
                    or len(originals) != 1 or originals[0]['entry_id'] != pin['entry_id']
                    or originals[0]['partition'] != dependency):
                    raise ValidationError('Retain the complete original reviewed member, proposal and decision evidence.')
                dependency = dependency['payload']['dependency']
            if dependency is not None:
                raise ValidationError('Retain every original predecessor decision in the receipt lineage.')
        decision = retained['decision']
        if decision is None:
            if retained['decision_checksum']:
                raise ValidationError('A pending proposal cannot fabricate review evidence.')
        else:
            _check_decision(decision, retained['decision_checksum'])
            if (decision['batch'] != body['public_id'] or decision['proposal_checksum'] != retained['checksum']
                or decision['prepared_by_id'] != body['prepared_by_id'] or decision['prepared_at'] != body['prepared_at']):
                raise ValidationError('Receipt review must retain the original batch and maker.')
        return body
    except (KeyError, TypeError, ValueError, ArithmeticError, RecursionError) as error:
        raise ValidationError('Invalid retained receipt attribution evidence.') from error


def _snapshot(batch, *, members=None):
    try:
        return _snapshot_checked(batch, members=members)
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Invalid retained receipt batch or member structure.') from error


def _snapshot_checked(batch, *, members=None):
    members = list(batch.members.order_by('entry_id')) if members is None else members
    if batch.payload != _proposal(batch, members):
        raise ValidationError('Receipt members or original batch identity changed.')
    if batch.status == Batch.SUBMITTED:
        if batch.reviewed_by_id or batch.reviewed_by_label or batch.reviewed_at or batch.review_note or batch.decision_checksum:
            raise ValidationError('A pending batch cannot carry a review decision.')
        decision = None
    elif batch.status in (Batch.APPROVED, Batch.RETURNED):
        decision = _decision(batch)
    else:
        raise ValidationError('Unknown receipt review state.')
    result = {'payload': deepcopy(batch.payload), 'checksum': batch.payload_checksum,
        'decision': decision, 'decision_checksum': batch.decision_checksum}
    verify_snapshot(result)
    return result


def snapshot(batch, actor, *, action='view'):
    if action not in ('view', 'export') or _owner(actor, action).pk != batch.department_id:
        raise PermissionDenied
    return _snapshot(batch)


def _pin(member):
    batch = member.batch
    retained = _snapshot(batch)
    if batch.status != Batch.APPROVED:
        raise ValidationError('Independently review the original receipt partition before inheriting it.')
    return {'entry_id': member.entry_id, 'member': str(member.public_id), 'batch': str(batch.public_id),
        'partition_checksum': member.partition['checksum'], 'proposal_checksum': batch.payload_checksum,
        'decision': retained['decision'], 'decision_checksum': batch.decision_checksum}


def _dependencies_current(member, inventory):
    for pin in member.dependencies:
        head = Head.objects.select_related('attribution__batch').filter(entry_id=pin['entry_id']).first()
        if (not head or _pin(head.attribution) != pin
            or Member.objects.filter(entry_id=pin['entry_id']).aggregate(n=Max('version'))['n'] != head.attribution.version):
            raise ValidationError('A predecessor review changed; prepare fresh linked receipt attribution.')
        partitions.verify(inventory, head.attribution.partition)


def _audit(batch, actor, action):
    AccountingAuditEvent.objects.create(department_id=batch.department_id, department_label=batch.department_label,
        action=action, actor_id=actor.pk, actor_label=(actor.get_full_name() or actor.username)[:160],
        reason=batch.review_note or batch.payload['reason'], snapshot={'batch': str(batch.public_id),
            'proposal_checksum': batch.payload_checksum, 'decision_checksum': batch.decision_checksum})


@transaction.atomic(using='finance')
def propose_batch(*, actor, fund_id, period_start, period_end, expected_source_checksum, proposals, reason, evidence_reference):
    owner = _owner(actor, 'prepare')
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=owner.pk).first()
    if not fund:
        raise PermissionDenied
    if (not isinstance(reason, str) or not reason.strip() or len(reason) > 4000
        or not isinstance(evidence_reference, str) or not evidence_reference.strip() or len(evidence_reference) > 255
        or not isinstance(proposals, list) or not proposals):
        raise ValidationError('Submit explicit source members, a reason and evidence reference.')
    inventory = sources._capture_for_owner(owner, fund_id=fund.pk, period_start=period_start, period_end=period_end)
    if inventory['source_checksum'] != expected_source_checksum:
        raise ValidationError('Receipt source cohort changed; inspect a fresh capture before proposing.')
    available = {row['entry_id'] for row in inventory['payload']['journals']}
    members, seen, proofs = [], set(), {}
    for item in proposals:
        if (not isinstance(item, dict) or type(item.get('entry_id')) is not int
            or item['entry_id'] not in available or item['entry_id'] in seen
            or type(item.get('expected_latest')) is not int
            or set(item) not in ({'entry_id', 'expected_latest', 'rows'},
                {'entry_id', 'expected_latest', 'inherit_from', 'line_pairs'})):
            raise ValidationError('Select each exact period journal once with rows or explicit predecessor inheritance.')
        entry_id = item['entry_id']; seen.add(entry_id)
        latest = Member.objects.filter(entry_id=entry_id).aggregate(n=Max('version'))['n'] or 0
        if latest != item['expected_latest']:
            raise ValidationError('A newer receipt attribution exists; inspect it before proposing a successor.')
        head = Head.objects.select_related('attribution__batch').filter(entry_id=entry_id).first()
        pins = []
        if 'inherit_from' in item:
            _, entry, _ = partitions.entry_source(inventory, entry_id)
            parent_head = Head.objects.select_related('attribution__batch').filter(entry_id=entry['reversal_of_id']).first()
            if not parent_head or str(parent_head.attribution.public_id) != item['inherit_from']:
                raise ValidationError('Select the current independently reviewed immediate predecessor.')
            parent = parent_head.attribution
            if Member.objects.filter(entry_id=parent.entry_id).aggregate(n=Max('version'))['n'] != parent.version:
                raise ValidationError('A newer predecessor proposal exists; resolve it before inheriting the approved version.')
            _dependencies_current(parent, inventory)
            pins = [_pin(parent), *deepcopy(parent.dependencies)]
            inherited_proofs = {str(parent.batch.public_id): _snapshot(parent.batch),
                **parent.batch.payload['predecessor_snapshots']}
            for pin in pins:
                previous = inherited_proofs[pin['batch']]
                if pin['batch'] in proofs and proofs[pin['batch']] != previous:
                    raise ValidationError('Conflicting retained predecessor batch evidence.')
                proofs[pin['batch']] = deepcopy(previous)
            partition = partitions.inherit(inventory, entry_id, parent.partition, pairs=item['line_pairs'])
        else:
            partition = partitions.propose(inventory, entry_id, item['rows'])
        members.append(Member(entry_id=entry_id, version=latest+1,
            base_version=head.attribution.version if head else 0, partition=partition, dependencies=pins))
    members.sort(key=lambda member: member.entry_id)
    batch = Batch(department_id=owner.pk, department_label=owner.name, fund=fund,
        period_start=period_start, period_end=period_end, prepared_by_id=actor.pk,
        prepared_by_label=(actor.get_full_name() or actor.username)[:160], prepared_at=timezone.now(),
        payload={'inventory': inventory, 'reason': reason.strip(), 'evidence_reference': evidence_reference.strip(),
            'predecessor_snapshots': proofs})
    batch.payload = _proposal(batch, members); batch.payload_checksum = checksum(batch.payload)
    verify_snapshot({'payload': batch.payload, 'checksum': batch.payload_checksum, 'decision': None, 'decision_checksum': ''})
    batch.save()
    for member in members:
        member.batch = batch; member.save()
    _audit(batch, actor, 'budget_receipt_submitted')
    return batch


@transaction.atomic(using='finance')
def review_batch(*, batch_id, actor, approve, note):
    owner = _owner(actor, 'review')
    original = Batch.objects.filter(public_id=batch_id, department_id=owner.pk).first()
    if not original:
        raise PermissionDenied
    fund = Fund.objects.select_for_update().get(pk=original.fund_id)
    batch = Batch.objects.select_for_update().get(pk=original.pk)
    _snapshot(batch)
    if (type(approve) is not bool or not isinstance(note, str) or not note.strip() or len(note) > 4000
        or batch.status != Batch.SUBMITTED or batch.prepared_by_id == actor.pk):
        raise ValidationError('A different authorized reviewer must decide the complete pending receipt batch.')
    members = list(batch.members.select_related('entry').order_by('entry_id'))
    if approve:
        if fund.department_id != owner.pk:
            raise ValidationError('The original Fund ownership changed; return this batch.')
        current = sources._capture_for_owner(owner, fund_id=fund.pk, period_start=batch.period_start, period_end=batch.period_end)
        if current['source_checksum'] != batch.payload['inventory']['source_checksum']:
            raise ValidationError('Receipt sources changed; return this batch and prepare a fresh cohort.')
        for member in members:
            latest = Member.objects.filter(entry_id=member.entry_id).aggregate(n=Max('version'))['n']
            head = Head.objects.select_related('attribution').filter(entry_id=member.entry_id).first()
            if (member.entry.fund_id != fund.pk or member.entry.department_id != owner.pk
                or latest != member.version or (head.attribution.version if head else 0) != member.base_version):
                raise ValidationError('A newer receipt proposal or approval exists; return this stale batch.')
            partitions.verify(current, member.partition)
            _dependencies_current(member, current)
    batch.status = Batch.APPROVED if approve else Batch.RETURNED
    batch.reviewed_by_id = actor.pk; batch.reviewed_by_label = (actor.get_full_name() or actor.username)[:160]
    batch.reviewed_at = timezone.now(); batch.review_note = note.strip()
    batch.decision_checksum = checksum(_decision(batch)); batch._decision_write = True; batch.save()
    if approve:
        for member in members:
            Head.objects.update_or_create(entry_id=member.entry_id, defaults={'attribution': member})
    _audit(batch, actor, 'budget_receipt_approved' if approve else 'budget_receipt_returned')
    return batch


def is_current(batch, actor):
    _owner(actor, 'view')
    if batch.department_id != department_for_user(actor).pk:
        raise PermissionDenied
    _snapshot(batch)
    if batch.status != Batch.APPROVED:
        return False
    if not Fund.objects.filter(pk=batch.fund_id, department_id=batch.department_id).exists():
        return False
    try:
        current = capture(actor=actor, fund_id=batch.fund_id, period_start=batch.period_start, period_end=batch.period_end)
        if current['source_checksum'] != batch.payload['inventory']['source_checksum']:
            return False
        for member in batch.members.all():
            if (not Head.objects.filter(entry_id=member.entry_id, attribution=member).exists()
                or Member.objects.filter(entry_id=member.entry_id).aggregate(n=Max('version'))['n'] != member.version):
                return False
            _dependencies_current(member, current)
    except ValidationError:
        return False
    return True
