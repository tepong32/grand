"""Explicit documentary allocations in default; no valuation or posting authority."""
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q, Sum

from accounting.access import can_view_ledger, department_for_user
from departments.models import Department
from inventory.disposal_evidence import prepare_uploads
from inventory.models import Asset, ReceivingReceipt, ReceivingLine
from inventory.private_evidence import open_checked_private_evidence
from inventory.property_determinations import checksum
from inventory.receipt_amendments import effective_cost, latest_amendment, amendment_content
from inventory.receipt_quantity_corrections import effective_quantities, require_no_pending
from inventory.receiving import can_receiving, HEADER_FIELDS
from vouchers.access import has_explicit_permission
from vouchers.roles import is_finance_uat_viewer
from .models import AssetCostAllocation as Allocation, AssetCostAllocationEvent as Event
from .receipt_basis import receipt_basis


def granted(actor, action):
    return has_explicit_permission(actor, f'inventory_finance.{action}_assetcostallocation')


def can_view_workbench(actor):
    return bool(department_for_user(actor)
                and any(granted(actor, action) for action in ('view', 'propose', 'review')))


def can_propose(actor, line=None):
    owner = department_for_user(actor)
    return bool(owner and can_receiving(actor, 'view', line.receipt if line else None)
        and granted(actor, 'propose') and not is_finance_uat_viewer(actor)
        and (line is None or line.receipt.department_id == owner.pk))


def can_review(actor, row):
    owner = department_for_user(actor)
    return bool(owner and owner.pk == row.finance_department_id and can_view_ledger(actor)
        and granted(actor, 'review') and not is_finance_uat_viewer(actor))


def visible(actor):
    owner = department_for_user(actor)
    rows = Allocation.objects.all()
    if not can_view_workbench(actor):
        return rows.none()
    scope = Q(pk__in=[])
    if can_receiving(actor, 'view'):
        scope |= Q(line__receipt__department_id=owner.pk)
    if can_view_ledger(actor):
        scope |= Q(finance_department_id=owner.pk)
    return rows.filter(scope)


def text(raw, label, maximum):
    if not isinstance(raw, str) or not raw.strip() or len(raw.strip()) > maximum:
        raise ValidationError(f'{label} must contain 1 to {maximum} characters.')
    return raw.strip()


def number(raw, label, places, maximum, *, positive=False):
    if isinstance(raw, (float, bool)) or raw is None:
        raise ValidationError(f'Enter an exact {label}.')
    try:
        result = Decimal(raw)
        if (not result.is_finite() or result < 0 or positive and result == 0
                or result >= maximum or result.as_tuple().exponent < -places):
            raise ValueError
        return result
    except (TypeError, ValueError, InvalidOperation) as error:
        raise ValidationError(f'Enter a valid {label} with at most {places} decimal places.') from error


def components(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
        raise ValidationError('Supply 1 to 50 explicit component allocations.')
    result, labels = [], set()
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != {'label', 'quantity', 'unit', 'amount', 'reference'}:
            raise ValidationError('Each component needs a label, quantity, unit, amount and source reference.')
        label = text(entry['label'], 'Component label', 180)
        if label.casefold() in labels:
            raise ValidationError('Use distinct component labels; combine identical items with an explicit quantity.')
        labels.add(label.casefold())
        result.append(dict(label=label,
            quantity=format(number(entry['quantity'], 'component quantity', 3, Decimal('1000000000'), positive=True), '.3f'),
            unit=text(entry['unit'], 'Component unit', 40),
            amount=format(number(entry['amount'], 'component amount', 2, Decimal('10000000000000000')), '.2f'),
            reference=text(entry['reference'], 'Component source reference', 240)))
    return result


def source(line):
    if (line.receipt.status != ReceivingReceipt.ACCEPTED or line.is_void or line.kind != ReceivingLine.ASSET
            or not line.registered_asset_id or line.registered_asset.department_id != line.receipt.department_id):
        raise ValidationError('Use an accepted, non-void asset receipt in its original owning office.')
    accepted = line.receipt.events.filter(action='accepted').last()
    retained = accepted.snapshot if accepted and isinstance(accepted.snapshot, dict) else {}
    original_line = ReceivingLine.objects.filter(pk=line.pk).values().get()
    original_line = {key: raw.isoformat() if hasattr(raw, 'isoformat') else str(raw) if raw is not None else None
                     for key, raw in original_line.items()}
    header = {key: getattr(line.receipt, key).isoformat() if hasattr(getattr(line.receipt, key), 'isoformat')
              else str(getattr(line.receipt, key)) if getattr(line.receipt, key) is not None else None for key in HEADER_FIELDS}
    if (retained.get('public_id') != str(line.receipt.public_id) or retained.get('header') != header
            or not isinstance(retained.get('lines'), list)
            or original_line not in retained.get('lines', [])
            or retained.get('reviewed_by_id') != line.receipt.reviewed_by_id
            or retained.get('evidence') != list(line.receipt.evidence.values('id', 'kind', 'sha256', 'size', 'note', 'original_filename'))):
        raise ValidationError('The original receipt differs from its retained acceptance. Investigate before allocating it.')
    for amendment in line.cost_amendments.all():
        events = list(amendment.events.all())
        expected = {'content': amendment_content(amendment), 'content_checksum': amendment.content_checksum,
            'status': amendment.status, 'state_version': amendment.state_version,
            'reviewed_by_local_id': amendment.reviewed_by_id,
            'reviewed_at': amendment.reviewed_at.isoformat() if amendment.reviewed_at else None,
            'review_note': amendment.review_note}
        if (not events or len(events) != amendment.state_version or events[-1].snapshot != expected
                or checksum(amendment_content(amendment)) != amendment.content_checksum):
            raise ValidationError('The documentary cost correction history changed. Investigate before allocating it.')
        if amendment.status == amendment.PENDING:
            raise ValidationError('Decide the pending documented cost correction before preparing or approving an allocation.')
    require_no_pending(line)
    quantity = effective_quantities(line)['accepted']
    cost = effective_cost(line)
    if quantity <= 0 or cost is None:
        raise ValidationError('A positive accepted quantity and known documented cost are required; unknown is not zero.')
    amount = quantity * cost
    if amount < 0 or amount != amount.quantize(Decimal('.01')):
        raise ValidationError('The documented source has a sub-cent or invalid total. Obtain a documented cost correction; no rounding rule is assumed.')
    records = list(line.receipt.evidence.all())
    if not {'delivery', 'inspection'} <= {row.kind for row in records}:
        raise ValidationError('Retain delivery and inspection source documents first.')
    try:
        for row in records:
            with open_checked_private_evidence(row, namespace=f'inventory/receiving/{line.receipt.public_id}'):
                pass
        amendment = latest_amendment(line)
        if amendment:
            with open_checked_private_evidence(amendment, namespace=f'inventory/receipt-amendments/{amendment.public_id}'):
                pass
    except (OSError, ValueError) as error:
        raise ValidationError('A retained source document is missing, changed or unsafe. Investigate before proceeding.') from error
    return {'receipt': receipt_basis(line), 'acceptance_event': {'id': accepted.pk, 'checksum': checksum(retained)},
            'accepted_quantity': str(quantity), 'unit': line.unit,
            'unit_cost': format(cost, '.2f'), 'amount': format(amount, '.2f'),
            'files': [{'id': row.pk, 'name': row.file.name, 'sha256': row.sha256, 'size': row.size} for row in records]}


def content(row):
    return dict(public_id=str(row.public_id), line_id=row.line_id, finance_department_id=row.finance_department_id,
        revision=row.revision, predecessor_id=row.predecessor_id, source_snapshot=row.source_snapshot,
        source_amount=format(row.source_amount, '.2f'), components=row.components, basis=row.basis,
        proposed_by_id=row.proposed_by_id, proposed_at=row.proposed_at.isoformat(), file=row.file.name,
        original_filename=row.original_filename, sha256=row.sha256, size=row.size)


def event_snapshot(row, event):
    return dict(allocation=str(row.public_id), version=event.version, action=event.action,
        actor=event.actor_id, time=event.occurred_at.isoformat(), note=event.note, content_checksum=row.content_checksum)


def verify(row, *, files=True):
    if not row.content_checksum or row.content_checksum != checksum(content(row)):
        raise ValidationError('The retained allocation content changed. Investigate or restore it.')
    events = list(row.events.all())
    expected = 1 if row.status == 'proposed' else 2 if row.status in ('approved', 'rejected') else 0
    if not expected or row.state_version != expected or len(events) != expected:
        raise ValidationError('The allocation decision history is incomplete.')
    for version, event in enumerate(events, 1):
        if (event.version != version or event.action != ('proposed' if version == 1 else row.status)
                or event.snapshot != event_snapshot(row, event) or event.checksum != checksum(event.snapshot)
                or version == 1 and event.actor_id != row.proposed_by_id
                or version == 2 and event.actor_id == row.proposed_by_id):
            raise ValidationError('The allocation no longer reproduces its independent decision history.')
    if files:
        try:
            with open_checked_private_evidence(row, namespace=f'inventory/asset-cost-allocations/{row.line.receipt.public_id}'):
                pass
        except (OSError, ValueError) as error:
            raise ValidationError('The retained allocation evidence is unavailable or unsafe.') from error


def reference(row):
    return None if row is None else {'id': row.pk, 'public_id': str(row.public_id),
        'content_checksum': row.content_checksum, 'decision_checksum': list(row.events.all())[-1].checksum}


def basis(line):
    current_source, head = source(line), None
    for row in line.cost_allocations.select_related('line__receipt').prefetch_related('events'):
        verify(row, files=row.status == 'approved')
        if row.status != 'approved':
            continue
        # Prior source facts may legitimately have a reviewed cost/quantity successor.
        # Their immutable approvals stay historical; only the current worksheet can
        # be relied on when its own source snapshot still matches today's source.
        if (row.predecessor_id != (head.pk if head else None)
                or row.source_snapshot.get('approved') != reference(head)):
            raise ValidationError('The allocation predecessor chain requires investigation.')
        head = row
    return {'source': current_source, 'approved': reference(head)}, head


def _lock(line):
    receipt = ReceivingReceipt.objects.select_for_update().get(pk=line.receipt_id)
    line = ReceivingLine.objects.select_related('receipt', 'registered_asset').get(pk=line.pk, receipt=receipt)
    if line.registered_asset_id:
        line.registered_asset = Asset.objects.select_for_update().get(pk=line.registered_asset_id)
    return line


def _event(row, actor, note):
    event = Event(allocation=row, actor=actor, version=row.state_version, action=row.status, note=note)
    event.snapshot = event_snapshot(row, event)
    event.checksum = checksum(event.snapshot)
    event.full_clean()
    event.save(force_insert=True)


@transaction.atomic(using='default')
def propose(*, actor, line, finance_department_id, request_id, expected_basis, entries, allocation_basis, upload):
    line = _lock(line)
    if not can_propose(actor, line):
        raise PermissionDenied
    owner = Department.objects.filter(pk=finance_department_id).exclude(name='---select one---').first()
    if not owner:
        raise ValidationError('Select the native department responsible for independent Accounting review.')
    entries, allocation_basis = components(entries), text(allocation_basis, 'Allocation basis', 4000)
    try:
        identity = UUID(str(request_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError('Reopen the form for a valid allocation request.') from error
    if upload is None:
        raise ValidationError('Attach the document supporting the explicit allocation.')
    prepared = prepare_uploads([('allocation', [upload])])[0]
    digest, size, original_name = prepared[2], prepared[3], Path(upload.name).name
    previous = Allocation.objects.filter(public_id=identity).select_related('line__receipt').first()
    if previous:
        if (previous.line_id != line.pk or previous.proposed_by_id != actor.pk
                or previous.finance_department_id != owner.pk or previous.components != entries
                or previous.basis != allocation_basis or checksum(previous.source_snapshot) != expected_basis
                or previous.sha256 != digest or previous.size != size or previous.original_filename != original_name):
            raise ValidationError('This request already belongs to different allocation content.')
        verify(previous)
        return previous
    snapshot, head = basis(line)
    if checksum(snapshot) != expected_basis:
        raise ValidationError('The source or predecessor changed. Reopen the allocation form.')
    amount = Decimal(snapshot['source']['amount'])
    if sum(Decimal(entry['amount']) for entry in entries) != amount:
        raise ValidationError('The explicit component amounts must equal the documented source total exactly.')
    rows = line.cost_allocations
    if rows.count() >= 20 or (rows.aggregate(total=Sum('size'))['total'] or 0) + size > 100 * 1024 * 1024:
        raise ValidationError('This source already reaches the retained allocation document budget. Arrange storage review.')
    row = Allocation(public_id=identity, line=line, finance_department=owner,
        revision=(rows.aggregate(last=Max('revision'))['last'] or 0) + 1, predecessor=head,
        source_snapshot=snapshot, source_amount=amount, components=entries, basis=allocation_basis,
        proposed_by=actor, file=upload, original_filename=original_name, sha256=digest, size=size)
    row.content_checksum = checksum(content(row))
    row.full_clean(validate_unique=False)
    row.file.save(original_name, upload, save=False)
    row.content_checksum = checksum(content(row))
    row.save(force_insert=True)
    _event(row, actor, allocation_basis)
    return row


@transaction.atomic(using='default')
def decide(*, actor, row, expected_version, action, note):
    line = _lock(row.line)
    row = Allocation.objects.select_for_update().select_related('line__receipt').get(pk=row.pk, line=line)
    if not can_review(actor, row):
        raise PermissionDenied
    note = text(note, 'Independent Accounting findings', 4000)
    verify(row, files=action == 'approved')
    if actor.pk == row.proposed_by_id:
        raise ValidationError('A different authorized Accounting reviewer must decide this allocation.')
    if action not in ('approved', 'rejected'):
        raise ValidationError('Choose a documentary review decision explicitly.')
    if type(expected_version) is not int or expected_version != row.state_version or row.status != 'proposed':
        raise ValidationError('This allocation changed or was already decided. Reload it before reviewing.')
    if action == 'approved':
        snapshot, head = basis(line)
        if row.source_snapshot != snapshot or row.predecessor_id != (head.pk if head else None):
            raise ValidationError('The source or approved predecessor changed. Propose a fresh allocation.')
    row.status, row.state_version, row._decision_write = action, row.state_version + 1, True
    row.save(update_fields=('status', 'state_version'))
    _event(row, actor, note)
    return row
