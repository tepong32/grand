"""Physical supply counts; reviewed differences never post to Finance."""
import hashlib
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .access import can_stock, gso_department_for_user, in_gso_scope
from .models import ConsumableItem, StockCount, StockCountEvent, StockCountEvidence, StockMovement
from .services import record_stock_movement


def can_manage_count(actor, action, item=None):
    if action not in ("record", "review") or not in_gso_scope(actor) or not can_stock(actor, "view"):
        return False
    permission = f"inventory.{action}_stock_count"
    if apps.is_installed("vouchers"):
        from vouchers.access import has_explicit_permission
        from vouchers.roles import is_finance_uat_viewer
        granted = not is_finance_uat_viewer(actor) and has_explicit_permission(actor, permission)
    else:
        granted = actor.has_perm(permission)
    department = gso_department_for_user(actor)
    return bool(granted and (action != "review" or can_stock(actor, "adjust"))
        and (item is None or actor.is_superuser or (department and item.department_id == department.pk)))


def _require(actor, action, item):
    if not can_manage_count(actor, action, item):
        raise PermissionDenied


def stock_basis(item):
    totals = item.movements.aggregate(rows=Count("pk"), balance=Sum("signed_quantity"))
    last = item.movements.order_by("-occurred_at", "-public_id").values_list("public_id", flat=True).first()
    return {"item_uuid": str(item.public_id), "department_id": item.department_id, "name": item.name,
        "unit": item.unit, "use_fifo": item.use_fifo, "is_active": item.is_active,
        "movement_count": totals["rows"], "last_movement_uuid": str(last) if last else None,
        "balance": format(totals["balance"] or Decimal(0), ".3f")}


def _event(count, actor, action):
    StockCountEvent.objects.create(count=count, actor=actor, action=action, snapshot={
        "public_id": str(count.public_id), "basis": count.basis, "quantity": str(count.quantity),
        "counted_on": count.counted_on.isoformat(), "reference": count.reference, "note": count.note,
        "status": count.status, "state_version": count.state_version, "recorded_by_id": count.recorded_by_id,
        "decided_by_id": count.decided_by_id, "decision_note": count.decision_note,
        "adjustment_uuid": str(count.adjustment.public_id) if count.adjustment_id else None,
        "evidence": list(count.evidence.values("id", "sha256", "size", "original_filename", "note", "uploaded_by_id"))})


@transaction.atomic
def record_count(*, actor, item, request_id, expected_basis, counted_on, quantity, reference, note):
    item = ConsumableItem.objects.select_for_update().get(pk=item.pk)
    _require(actor, "record", item)
    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid count request identity.")
    quantity = StockCount._meta.get_field("quantity").clean(quantity, None)
    counted_on = StockCount._meta.get_field("counted_on").clean(counted_on, None)
    reference, note = reference.strip(), note.strip()
    existing = StockCount.objects.filter(public_id=request_id).first()
    if existing:
        if (existing.item_id != item.pk or existing.recorded_by_id != actor.pk or existing.basis != expected_basis
            or (existing.counted_on, existing.quantity, existing.reference, existing.note) != (counted_on, quantity, reference, note)):
            raise ValidationError("This request identity belongs to different recorded content.")
        return existing
    if not item.is_active or expected_basis != stock_basis(item):
        raise ValidationError("The item or ledger changed. Review the current balance and recount before recording.")
    from .receipt_quantity_corrections import require_stock_available
    require_stock_available(item)
    if counted_on != timezone.localdate():
        raise ValidationError("Record today's observed count against today's ledger basis; historical counts need separate reconciliation.")
    if not reference or not note:
        raise ValidationError("Record the count-sheet reference and count or variance facts.")
    if item.counts.filter(status=StockCount.PENDING).exists():
        raise ValidationError("Resolve the pending count before recording another for this item.")
    count = StockCount(public_id=request_id, item=item, counted_on=counted_on, quantity=quantity,
        reference=reference, note=note, basis=expected_basis, recorded_by=actor)
    count.full_clean()
    count.save()
    _event(count, actor, "recorded")
    return count


def _locked(count, actor, action, expected_version):
    item = ConsumableItem.objects.select_for_update().get(pk=count.item_id)
    _require(actor, action, item)
    count = StockCount.objects.select_for_update().get(pk=count.pk, item=item)
    if (isinstance(expected_version, bool) or not isinstance(expected_version, int)
        or expected_version != count.state_version or count.status != StockCount.PENDING):
        raise ValidationError("The count changed or was already decided. Reload its history before continuing.")
    return item, count


@transaction.atomic
def attach_count_evidence(*, actor, count, expected_version, upload, note):
    from .forms import _validate_disposal_upload
    _, count = _locked(count, actor, "record", expected_version)
    if not note.strip() or len(note.strip()) > 240:
        raise ValidationError("Describe the count evidence in 1 to 240 characters.")
    if count.evidence.count() >= 20:
        raise ValidationError("A count supports at most 20 retained files.")
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("Each count file must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    if (count.evidence.aggregate(total=Sum("size"))["total"] or 0) + size > 100 * 1024 * 1024:
        raise ValidationError("Count evidence cannot exceed 100 MB.")
    evidence = StockCountEvidence(count=count, file=upload, original_filename=Path(upload.name).name,
        sha256=digest.hexdigest(), size=size, note=note.strip(), uploaded_by=actor)
    evidence.full_clean()
    evidence.save()
    count.state_version += 1
    count.save(update_fields=("state_version",))
    _event(count, actor, "evidence_added")
    return evidence


def verify_count_evidence(count):
    rows = list(count.evidence.all())
    if not rows:
        raise ValidationError("Retain the count sheet or supporting count evidence before review.")
    for row in rows:
        root = Path(row.file.storage.location).resolve()
        path = root / row.file.name
        try:
            path.resolve().relative_to(root / "inventory" / "stock_counts" / str(count.public_id))
            if ".." in Path(row.file.name).parts or path.resolve() != path:
                raise ValueError
        except ValueError as error:
            raise ValidationError("Count evidence has an unsafe location. Investigate before review.") from error
        digest, size = hashlib.sha256(), 0
        try:
            with row.file.open("rb") as source:
                for block in source.chunks():
                    digest.update(block)
                    size += len(block)
        except OSError as error:
            raise ValidationError("Count evidence is unavailable. Restore or investigate before review.") from error
        if digest.hexdigest() != row.sha256 or size != row.size:
            raise ValidationError("Count evidence failed its integrity check. Investigate before review.")


@transaction.atomic
def decide_count(*, actor, count, expected_version, action, note):
    if action not in ("approve", "cancel"):
        raise ValidationError("Choose review approval or cancellation.")
    authority = "review" if action == "approve" or not can_manage_count(actor, "record") else "record"
    item, count = _locked(count, actor, authority, expected_version)
    if not note.strip() or len(note.strip()) > 240:
        raise ValidationError("Record the decision basis in 1 to 240 characters.")
    if action == "approve":
        if actor.pk == count.recorded_by_id or count.evidence.filter(uploaded_by=actor).exists():
            raise PermissionDenied("An independent officer must review this count and its evidence.")
        if not item.is_active or stock_basis(item) != count.basis:
            raise ValidationError("The item or ledger changed after counting. Cancel this record and recount; no adjustment was made.")
        verify_count_evidence(count)
        difference = count.quantity - Decimal(count.basis["balance"])
        if difference:
            count.adjustment = record_stock_movement(actor=actor, item=item,
                kind=StockMovement.ADJUSTMENT_IN if difference > 0 else StockMovement.ADJUSTMENT_OUT,
                quantity=abs(difference), reference=f"Physical count {count.public_id}",
                reason=count.note, unit_cost=None)
        count.status = StockCount.APPROVED
    else:
        count.status = StockCount.CANCELLED
    count.decided_by, count.decided_at, count.decision_note = actor, timezone.now(), note.strip()
    count.state_version += 1
    count.save(update_fields=("status", "decided_by", "decided_at", "decision_note", "state_version", "adjustment"))
    _event(count, actor, "approved" if action == "approve" else "cancelled")
    return count
