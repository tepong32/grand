"""Reviewed clerical overstatement before use; never a Finance reversal."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .access import can, can_stock, gso_department_for_user, has_inventory_permission
from .models import (Asset, AssetAuditEvent, ConsumableItem, ReceivingLine, ReceivingReceipt,
                     StockMovement, StockLot, StockLotAllocation,
                     ReceiptQuantityCorrection as Correction, ReceiptQuantityCorrectionEvent as Event)
from .receiving import can_receiving


def can_correct(actor, action, receipt):
    owner = gso_department_for_user(actor)
    return bool(action in ("record", "review") and owner and owner.pk == receipt.department_id
        and can_receiving(actor, "view", receipt)
        and has_inventory_permission(actor, f"{action}_receipt_quantity_correction", mutation=True))


def _require(actor, action, receipt):
    if not can_correct(actor, action, receipt):
        raise PermissionDenied


def _hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def content(row):
    return {"uuid": str(row.public_id), "line_id": row.line_id, "predecessor_id": row.predecessor_id,
        "quantity": format(row.quantity, ".3f"), "basis": row.basis, "reference": row.reference,
        "reason": row.reason, "file": row.file.name, "original_filename": row.original_filename,
        "sha256": row.sha256, "size": row.size, "recorded_by_id": row.recorded_by_id}


def snapshot(row):
    from .receiving_followups import plain
    result = None
    if row.adjustment_id:
        movement = row.adjustment
        result = {"movement": {field.attname: getattr(movement, field.attname)
                                for field in movement._meta.concrete_fields},
                  "allocations": list(movement.lot_allocations.order_by("pk").values())}
        result["movement"]["public_id"] = str(movement.public_id)
    elif row.asset_event_id:
        event = row.asset_event
        result = {"asset_event_id": event.pk, "asset_id": event.asset_id, "actor_id": event.actor_id,
                  "action": event.action, "occurred_at": event.occurred_at, "snapshot": event.snapshot}
    return {"content": content(row), "content_checksum": row.content_checksum, "status": row.status,
        "version": row.state_version, "decided_by_id": row.decided_by_id,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "decision_note": row.decision_note, "adjustment_id": row.adjustment_id,
        "asset_event_id": row.asset_event_id, "result": plain(result)}


def _event(row, actor, action):
    data = snapshot(row)
    Event.objects.create(correction=row, actor=actor, action=action, snapshot=data,
        checksum=_hash({"actor_id": actor.pk, "action": action, "snapshot": data}))


def verify_history(row):
    events = list(row.events.all())
    if (_hash(content(row)) != row.content_checksum or len(events) != row.state_version
            or not events or events[0].action != "recorded"
            or events[0].actor_id != row.recorded_by_id):
        raise ValidationError("The retained correction content or history changed. Reconcile it first.")
    for version, event in enumerate(events, 1):
        if (not isinstance(event.snapshot, dict) or event.snapshot.get("version") != version
                or event.snapshot.get("content") != content(row)
                or event.checksum != _hash({"actor_id": event.actor_id, "action": event.action,
                                           "snapshot": event.snapshot})):
            raise ValidationError("The retained correction event history failed its integrity check.")
    if events[-1].snapshot != snapshot(row):
        raise ValidationError("The correction does not match its retained final event.")
    if row.status == row.APPROVED and (row.decided_by_id == row.recorded_by_id
            or not row.decided_at or events[-1].actor_id != row.decided_by_id):
        raise ValidationError("The retained independent correction decision is incomplete.")


def verify_evidence(row):
    verify_history(row)
    root = Path(row.file.storage.location).resolve()
    path = root / row.file.name
    try:
        path.resolve().relative_to(root / "inventory" / "receipt-quantity-corrections")
        if ".." in Path(row.file.name).parts or path.resolve() != path:
            raise ValueError
        digest, size = hashlib.sha256(), 0
        with row.file.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
        if size != row.size or digest.hexdigest() != row.sha256:
            raise ValueError
    except (OSError, ValueError):
        raise ValidationError("The correction packet is missing or changed. Restore or reconcile it first.")


def approved_corrections(line, *, evidence=True):
    """Validate the retained chain and physical results, never a caller's exclusion list."""
    rows = list(line.quantity_corrections.filter(status=Correction.APPROVED).order_by("pk"))
    predecessor, total = None, Decimal(0)
    for row in rows:
        verify_evidence(row) if evidence else verify_history(row)
        if row.predecessor_id != predecessor or row.quantity <= 0:
            raise ValidationError("The approved quantity correction chain is incomplete.")
        total += row.quantity
        if total > line.accepted_quantity:
            raise ValidationError("Corrections exceed the original accepted quantity.")
        if line.kind == ReceivingLine.SUPPLY:
            movement = row.adjustment
            if (not movement or row.asset_event_id or movement.item_id != line.supply_item_id
                    or movement.kind != StockMovement.ADJUSTMENT_OUT or movement.quantity != row.quantity
                    or movement.signed_quantity != -row.quantity or movement.unit_cost != line.unit_cost
                    or movement.actor_id != row.decided_by_id
                    or movement.public_id != row.public_id):
                raise ValidationError("The retained correction adjustment does not match its decision.")
            allocations = list(movement.lot_allocations.select_related("lot"))
            if line.supply_item.use_fifo:
                if (len(allocations) != 1 or allocations[0].quantity != row.quantity
                        or allocations[0].lot.receipt_id != line.stock_movement_id
                        or allocations[0].lot.item_id != line.supply_item_id):
                    raise ValidationError("The correction no longer matches its original FIFO lot.")
            elif allocations:
                raise ValidationError("A non-FIFO correction has unexpected lot allocations.")
        else:
            event = row.asset_event
            if (row.adjustment_id or not event or event.asset_id != line.registered_asset_id
                    or event.actor_id != row.decided_by_id or event.action != "updated"
                    or event.snapshot.get("status") != Asset.ENTRY_VOID or row.quantity != 1
                    or not Asset.objects.filter(pk=line.registered_asset_id, status=Asset.ENTRY_VOID).exists()):
                raise ValidationError("The retained erroneous-entry correction is inconsistent.")
        predecessor = row.pk
    return rows


def effective_quantities(line):
    rows = approved_corrections(line)
    corrected = sum((row.quantity for row in rows), Decimal(0))
    return {"delivered": line.delivered_quantity - corrected,
            "accepted": line.accepted_quantity - corrected, "corrected": corrected}


def correction_extension(line):
    rows = approved_corrections(line)
    if not rows:
        return None
    corrected = sum((row.quantity for row in rows), Decimal(0))
    return {"corrections": [{"uuid": str(row.public_id), "checksum": row.content_checksum,
                             "quantity": format(row.quantity, ".3f")} for row in rows],
        "effective_delivered": format(line.delivered_quantity - corrected, ".3f"),
        "effective_accepted": format(line.accepted_quantity - corrected, ".3f")}


def require_no_pending(line):
    if line.quantity_corrections.filter(status=Correction.PENDING).exists():
        raise ValidationError("Resolve the pending receipt quantity correction first.")


def require_stock_available(item):
    # Called while holding item lock; never acquire a receipt lock here.
    if Correction.objects.filter(line__supply_item=item, status=Correction.PENDING).exists():
        raise ValidationError("This item has a receipt quantity correction awaiting review.")


def require_asset_available(asset):
    # Called while holding asset lock; never reverse receipt -> asset order.
    if asset.status == Asset.ENTRY_VOID:
        raise ValidationError("This is a retained erroneous entry, not an operational asset.")
    if Correction.objects.filter(line__registered_asset=asset, status=Correction.PENDING).exists():
        raise ValidationError("This asset has a receipt quantity correction awaiting review.")


def source_basis(line):
    from .receiving_followups import source_basis as physical_basis
    from .receipt_amendments import latest_amendment, verify_amendment_evidence
    amendment = latest_amendment(line)
    if amendment:
        verify_amendment_evidence(amendment)
    return {"physical": physical_basis(line), "receipt_version": line.receipt.state_version,
        "cost_amendment": str(amendment.public_id) if amendment else None,
        "cost_checksum": amendment.content_checksum if amendment else None,
        "quantity_correction": correction_extension(line)}


def _packet(upload):
    from .forms import _validate_disposal_upload
    if not upload or not hasattr(upload, "seek"):
        raise ValidationError("Retain a readable correction packet.")
    try:
        upload.seek(0)
    except (OSError, ValueError):
        raise ValidationError("Retain a readable correction packet.")
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("The correction packet must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    return digest.hexdigest(), size, Path(upload.name).name


@transaction.atomic(using="default")
def record(*, actor, line_id, request_id, expected_basis, quantity, reference, reason, upload):
    # Lock/authorize before accessing an existing request, including exact retries.
    try:
        candidate = ReceivingLine.objects.get(pk=line_id)
        receipt = ReceivingReceipt.objects.select_for_update().get(pk=candidate.receipt_id)
    except (ReceivingLine.DoesNotExist, ReceivingReceipt.DoesNotExist):
        raise PermissionDenied
    _require(actor, "record", receipt)
    try:
        request_id = UUID(str(request_id))
        if isinstance(quantity, (bool, float)):
            raise ValueError
        quantity = Decimal(quantity)
        if (not quantity.is_finite() or quantity <= 0 or quantity >= Decimal("1000000000")
                or quantity != quantity.quantize(Decimal("0.001"))):
            raise ValueError
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError("Use a valid request identity and positive exact quantity with at most three decimals.")
    reference, reason = str(reference or "").strip(), str(reason or "").strip()
    if not reference or len(reference) > 180 or not reason or len(reason) > 4000:
        raise ValidationError("Record the source reference and correction reason within their field limits.")
    digest, size, filename = _packet(upload)
    previous = Correction.objects.filter(public_id=request_id).first()
    if previous:
        if (previous.line_id, previous.recorded_by_id, previous.basis, previous.quantity,
                previous.reference, previous.reason, previous.sha256, previous.size, previous.original_filename) != (
                line_id, actor.pk, expected_basis, quantity, reference, reason, digest, size, filename):
            raise ValidationError("This request identity already belongs to different content.")
        verify_history(previous)
        return previous
    from .receipt_correction_sources import lock_unused_source
    line, materialized = lock_unused_source(actor=actor, line_id=line_id)
    require_no_pending(line)
    if isinstance(materialized, StockMovement):
        require_stock_available(materialized.item)
    if expected_basis != source_basis(line):
        raise ValidationError("The source changed. Reload it before recording a correction.")
    prior = approved_corrections(line)
    if quantity > line.accepted_quantity - sum((row.quantity for row in prior), Decimal(0)):
        raise ValidationError("The correction exceeds effective accepted quantity.")
    if line.kind == line.ASSET and quantity != 1:
        raise ValidationError("An individually tracked erroneous entry must be corrected as one whole unit.")
    row = Correction(public_id=request_id, line=line, predecessor=prior[-1] if prior else None,
        quantity=quantity, basis=expected_basis, reference=reference, reason=reason,
        original_filename=filename, sha256=digest, size=size, recorded_by=actor)
    # Save the private packet before hashing its final storage name. A failed DB
    # transaction may leave an orphan file; recovery tools must not delete it blindly.
    row.file.save(filename, upload, save=False)
    row.content_checksum = _hash(content(row))
    row.full_clean()
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError:
        raise ValidationError("A competing correction or reused request identity was recorded. Reload the source.")
    _event(row, actor, "recorded")
    return row


@transaction.atomic(using="default")
def decide(*, actor, correction_id, expected_version, action, note):
    try:
        candidate = Correction.objects.select_related("line").get(pk=correction_id)
        receipt = ReceivingReceipt.objects.select_for_update().get(pk=candidate.line.receipt_id)
    except (Correction.DoesNotExist, ReceivingReceipt.DoesNotExist):
        raise PermissionDenied
    _require(actor, "record" if action == "cancel" else "review", receipt)
    # Cancel/reject can release the hold without requiring valid source files.
    # Lock the materialized owner before the correction even on these paths.
    line = ReceivingLine.objects.get(pk=candidate.line_id, receipt=receipt)
    if line.supply_item_id:
        ConsumableItem.objects.select_for_update().get(pk=line.supply_item_id)
    elif line.registered_asset_id:
        Asset.objects.select_for_update().get(pk=line.registered_asset_id)
    row = Correction.objects.select_for_update().get(pk=candidate.pk, line=line)
    if row.status != row.PENDING or type(expected_version) is not int or row.state_version != expected_version:
        raise ValidationError("This correction changed or was already decided. Reload its history.")
    if (action == "cancel" and actor.pk != row.recorded_by_id
            or action != "cancel" and actor.pk == row.recorded_by_id):
        raise PermissionDenied("The recorder cancels; a different authorized officer reviews.")
    note = str(note or "").strip()
    if action not in ("approve", "reject", "cancel") or not note or len(note) > 4000:
        raise ValidationError("Select a correction decision and record its reason.")
    verify_history(row)
    if action == "approve":
        from .receipt_correction_sources import lock_unused_source
        line, original = lock_unused_source(actor=actor, line_id=line.pk)
        if row.basis != source_basis(line):
            raise ValidationError("The source changed. Reject or cancel and record a new correction.")
        verify_evidence(row)
        available = effective_quantities(line)["accepted"]
        if row.quantity > available:
            raise ValidationError("The correction exceeds effective accepted quantity.")
        if line.kind == line.SUPPLY:
            if not can_stock(actor, "adjust"):
                raise PermissionDenied
            from .services import _stock_signed_total
            if _stock_signed_total(original.item) < row.quantity:
                raise ValidationError("Stock history cannot cover the correction. Reconcile it first.")
            movement = StockMovement(public_id=row.public_id, item=original.item,
                kind=StockMovement.ADJUSTMENT_OUT, quantity=row.quantity, signed_quantity=-row.quantity,
                unit_cost=original.unit_cost, reference=f"Receipt correction {row.public_id}",
                reason="Reviewed clerical overstatement before use", actor=actor)
            movement.full_clean()
            movement.save()
            if original.item.use_fifo:
                lot = StockLot.objects.select_for_update().get(receipt=original)
                StockLotAllocation.objects.create(issue=movement, lot=lot, quantity=row.quantity)
            row.adjustment = movement
        else:
            if not can(actor, "change") or row.quantity != 1:
                raise PermissionDenied
            from .services import asset_snapshot
            original.status, original.updated_by = Asset.ENTRY_VOID, actor
            original.save(update_fields=("status", "updated_by", "updated_at"))
            row.asset_event = AssetAuditEvent.objects.create(asset=original,
                department_id=original.department_id, actor=actor, action="updated", snapshot=asset_snapshot(original))
        row.status = row.APPROVED
        receipt.state_version += 1
        receipt.save(update_fields=("state_version",))
    else:
        row.status = row.CANCELLED if action == "cancel" else row.REJECTED
    row.decided_by, row.decided_at, row.decision_note = actor, timezone.now(), note
    row.state_version += 1
    row._workflow_write = True
    row.save(update_fields=("status", "decided_by", "decided_at", "decision_note",
                            "state_version", "adjustment", "asset_event"))
    _event(row, actor, row.status)
    return row
