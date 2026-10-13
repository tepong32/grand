"""Coherent reviewed receipt coverage, separate from certified/entity actuals."""
from collections import defaultdict
from copy import deepcopy
from datetime import date
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from . import budget_receipt_sources as sources, budget_receipt_partitions as partitions
from . import budget_receipt_attributions as reviews
from .access import department_for_user
from .cash_classifications import checksum
from .models import Fund, BudgetReceiptAttributionBatch as Batch, BudgetReceiptAttribution as Member, BudgetReceiptAttributionHead as Head


def required_entries(payload):
    ledger = {row['id']: row for row in payload['ledger']['payload']['journals']}
    selected = {row['entry_id'] for row in payload['journals']}
    return selected | {key for entry_id in selected for key in ledger[entry_id]['lineage']['ancestor_ids']}


def _pin(snapshot, member):
    body = snapshot['payload']
    return {'entry_id': member['entry_id'], 'member': member['public_id'], 'batch': body['public_id'],
        'partition_checksum': member['partition']['checksum'], 'proposal_checksum': snapshot['checksum'],
        'decision': snapshot['decision'], 'decision_checksum': snapshot['decision_checksum']}


def project(inventory, heads, batches):
    try:
        return _project(inventory, heads, batches)
    except (KeyError, TypeError, ValueError, ArithmeticError, RecursionError) as error:
        raise ValidationError('Invalid retained receipt review cohort.') from error


def _project(inventory, heads, batches):
    payload = sources.verify(inventory)
    required = required_entries(payload)
    if not isinstance(heads, list) or not isinstance(batches, dict):
        raise ValidationError('Retain an explicit complete receipt head and batch manifest.')
    indexed = {}
    for head in heads:
        if (set(head) != {'entry_id', 'member', 'batch', 'latest_version'}
            or type(head['entry_id']) is not int or head['entry_id'] not in required or head['entry_id'] in indexed
            or type(head['latest_version']) is not int or head['latest_version'] < 0
            or (head['member'] is None) != (head['batch'] is None)):
            raise ValidationError('Retain every selected journal and predecessor head exactly once.')
        indexed[head['entry_id']] = head
    if set(indexed) != required or set(batches) != {h['batch'] for h in heads if h['batch'] is not None}:
        raise ValidationError('Receipt head/batch coverage is incomplete or contains unrelated sources.')
    members = {}
    for key, snapshot in batches.items():
        body = reviews.verify_snapshot(snapshot)
        if (body['public_id'] != key or body['fund_id'] != payload['scope']['fund']['id']
            or body['department_id'] != payload['scope']['fund']['department_id']
            or not snapshot['decision'] or snapshot['decision']['status'] != Batch.APPROVED):
            raise ValidationError('Use independently reviewed batch evidence for this exact source owner/Fund.')
        members[key] = {item['public_id']: item for item in body['members']}
    eligible, status = {}, {}
    for entry_id, head in indexed.items():
        if head['member'] is None:
            status[entry_id] = 'missing_review'
            continue
        member = members[head['batch']].get(head['member'])
        if not member or member['entry_id'] != entry_id:
            raise ValidationError('The selected head must retain its exact independently reviewed journal member.')
        if member['version'] > head['latest_version']:
            raise ValidationError('The latest version manifest cannot precede the approved head.')
        if member['version'] != head['latest_version']:
            status[entry_id] = 'newer_proposal'
            continue
        try:
            partitions.verify(inventory, member['partition'])
        except ValidationError:
            status[entry_id] = 'changed_source'
            continue
        eligible[entry_id] = member
        status[entry_id] = 'reviewed'
    # Validate inherited decisions against one retained current head set. Do not
    # reread live pointers between totals and evidence or add ancestors as activity.
    for entry_id, member in list(eligible.items()):
        for pin in member['dependencies']:
            parent_head = indexed.get(pin['entry_id'])
            if (not parent_head or parent_head['member'] != pin['member']
                or parent_head['batch'] != pin['batch'] or pin['entry_id'] not in eligible
                or _pin(batches[parent_head['batch']], eligible[pin['entry_id']]) != pin):
                status[entry_id] = 'changed_predecessor'; break
    # All chain pins are explicit, so a descendant also detects a stale ancestor
    # directly rather than depending on traversal/order of this dictionary.
    eligible = {key: member for key, member in eligible.items() if status[key] == 'reviewed'}
    totals = {key: Decimal('0.00') for key in payload['receipt_categories']}
    controls = {kind: {'debit': Decimal('0.00'), 'credit': Decimal('0.00'), 'cash_movement': Decimal('0.00')}
        for kind in ('include', 'exclude', 'unresolved')}
    lines = {(row['entry_id'], row['line_id']): row for row in payload['lines']}
    bridge, issues = [], []
    for journal in payload['journals']:
        entry_id = journal['entry_id']; member = eligible.get(entry_id)
        if not member:
            issues.append({'entry_id': entry_id, 'kind': status[entry_id]})
        rows = member['partition']['payload']['allocations'] if member else [
            {'line_id': key[1], 'account_id': line['account']['id'],
                'amount': str(Decimal(line['debit']) + Decimal(line['credit'])),
                'signed_amount': str(Decimal(line['debit']) - Decimal(line['credit'])),
                'disposition': 'unresolved', 'purpose': 'unresolved', 'category': '',
                'basis': 'Current source lacks an eligible independently reviewed partition.'}
            for key, line in lines.items() if key[0] == entry_id]
        for row in rows:
            line = lines[(entry_id, row['line_id'])]
            value = Decimal(row['amount']); kind = row['disposition']
            signed = value if Decimal(line['debit']) > 0 else -value
            controls[kind]['debit' if signed > 0 else 'credit'] += value
            if line['cash_account']:
                controls[kind]['cash_movement'] += signed
            if kind == 'include':
                totals[row['category']] += signed
            if kind == 'unresolved':
                issues.append({'entry_id': entry_id, 'line_id': row['line_id'], 'kind': 'unresolved_component'})
            bridge.append({'entry_id': entry_id, 'reference': journal['reference'],
                'date': journal['date'], 'cash_account': line['cash_account'],
                'account': line['account'], 'allocation': deepcopy(row),
                'member': indexed[entry_id]['member'] if member else None,
                'review_status': status[entry_id]})
    if not payload['journals']:
        issues.append({'kind': 'empty_period_requires_evidence'})
    expected_debit = sum((Decimal(row['debit']) for row in payload['lines']), Decimal('0.00'))
    expected_credit = sum((Decimal(row['credit']) for row in payload['lines']), Decimal('0.00'))
    if (sum((row['debit'] for row in controls.values()), Decimal('0.00')) != expected_debit
        or sum((row['credit'] for row in controls.values()), Decimal('0.00')) != expected_credit
        or sum((row['cash_movement'] for row in controls.values()), Decimal('0.00')) != Decimal(payload['controls']['cash_movement'])):
        raise ValidationError('Receipt classification bridge does not reproduce all financial/cash source controls.')
    return {'schema': 1, 'kind': 'native_budget_reviewed_receipt_cohort',
        'scope': deepcopy(payload['scope']), 'inventory': deepcopy(inventory),
        'heads': deepcopy(heads), 'batches': deepcopy(batches), 'bridge': bridge,
        'classification_complete': not issues, 'issues': issues,
        'category_totals': {key: str(value) for key, value in totals.items()},
        'coverage_controls': {key: {label: str(value) for label, value in row.items()} for key, row in controls.items()},
        'classified_receipts': str(sum(totals.values(), Decimal('0.00'))),
        'receipt_total': None, 'category_coverage': 'not_declared', 'entity_coverage': 'not_declared',
        'certification_status': 'not_certified'}


def source_checksum(payload):
    return checksum({'inventory': payload['inventory']['source_checksum'], 'heads': payload['heads'],
        'batches': {key: {'proposal': value['checksum'], 'decision': value['decision_checksum']}
            for key, value in payload['batches'].items()}})


def capture(*, actor, fund_id, period_start, period_end):
    if not any(reviews.permitted(actor, action) for action in ('view', 'prepare', 'review', 'export')):
        raise PermissionDenied
    return _capture_for_owner(owner=department_for_user(actor), fund_id=fund_id,
        period_start=period_start, period_end=period_end)


@transaction.atomic(using='finance')
def _capture_for_owner(*, owner, fund_id, period_start, period_end):
    """Internal observation after exact role/scope authorization by the caller."""
    if type(fund_id) is not int or fund_id <= 0:
        raise ValidationError('Select an exact Finance Fund identity.')
    fund = Fund.objects.select_for_update().filter(pk=fund_id, department_id=owner.pk).first()
    if not fund:
        raise PermissionDenied
    inventory = sources._capture_for_owner(owner, fund_id=fund.pk, period_start=period_start, period_end=period_end)
    required = required_entries(inventory['payload'])
    head_rows = list(Head.objects.filter(entry_id__in=required).values('entry_id', 'attribution_id', 'attribution__batch_id'))
    latest = {row['entry_id']: row['version'] for row in Member.objects.filter(entry_id__in=required)
        .values('entry_id').annotate(version=Max('version'))}
    batch_ids = {row['attribution__batch_id'] for row in head_rows}
    batch_records = list(Batch.objects.filter(pk__in=batch_ids, fund=fund, department_id=owner.pk))
    if len(batch_records) != len(batch_ids):
        raise ValidationError('A receipt head points outside the exact authorized source owner/Fund.')
    grouped, member_index = defaultdict(list), {}
    for member in Member.objects.filter(batch_id__in=batch_ids).order_by('entry_id'):
        grouped[member.batch_id].append(member); member_index[member.pk] = member
    retained = {str(batch.public_id): reviews._snapshot(batch, members=grouped[batch.pk]) for batch in batch_records}
    batch_index = {batch.pk: str(batch.public_id) for batch in batch_records}
    selected = {row['entry_id']: row for row in head_rows}
    heads = []
    for entry_id in sorted(required):
        row = selected.get(entry_id)
        heads.append({'entry_id': entry_id, 'member': str(member_index[row['attribution_id']].public_id) if row else None,
            'batch': batch_index[row['attribution__batch_id']] if row else None, 'latest_version': latest.get(entry_id, 0)})
    payload = project(inventory, heads, retained)
    return {'payload': payload, 'checksum': checksum(payload), 'source_checksum': source_checksum(payload),
        'captured_at': timezone.now().isoformat()}


def verify(captured):
    try:
        payload = captured['payload']
        if (captured['checksum'] != checksum(payload) or captured['source_checksum'] != source_checksum(payload)
            or payload != project(payload['inventory'], payload['heads'], payload['batches'])):
            raise ValidationError('Receipt cohort no longer reproduces its retained review/source coverage.')
        return payload
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValidationError('Invalid retained reviewed receipt cohort.') from error


def is_current(captured, actor):
    payload = verify(captured); scope = payload['scope']
    current = capture(actor=actor, fund_id=scope['fund']['id'],
        period_start=date.fromisoformat(scope['period_start']), period_end=date.fromisoformat(scope['period_end']))
    return current['source_checksum'] == captured['source_checksum']
