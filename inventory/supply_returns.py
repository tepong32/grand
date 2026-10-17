"""Documented return to usable stock, never an Accounting reversal."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from .access import can_stock, gso_department_for_user, has_inventory_permission, in_gso_scope
from .models import ConsumableItem, StockMovement, SupplyReturn as Return, SupplyReturnEvent as Event
from .services import record_stock_movement


def can_act(actor, action, issue=None):
    owner = gso_department_for_user(actor)
    if not owner or not in_gso_scope(actor) or not can_stock(actor, "view"):
        return False
    if issue is not None and (issue.kind != "issue" or issue.item.department_id != owner.pk):
        return False
    if action == "review" and not can_stock(actor, "receive"):
        return False
    actions = ("view", "record", "review") if action == "view" else (action,)
    return action in ("view", "record", "review") and any(has_inventory_permission(
        actor, f"{name}_supply_return", mutation=action != "view") for name in actions)


def visible(actor):
    if not can_act(actor, "view"):
        return Return.objects.none()
    return Return.objects.filter(issue__item__department_id=gso_department_for_user(actor).pk)


def _require(actor, action, issue):
    if not can_act(actor, action, issue):
        raise PermissionDenied


def _text(value, maximum):
    value = str(value or "").strip()
    if not value or len(value) > maximum:
        raise ValidationError(f"Record 1 to {maximum} characters.")
    return value


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_basis(issue):
    return {"issue_uuid": str(issue.public_id), "item_uuid": str(issue.item.public_id),
        "department_id": issue.item.department_id, "item_name": issue.item.name, "unit": issue.item.unit,
        "use_fifo": issue.item.use_fifo, "kind": issue.kind, "quantity": format(issue.quantity, ".3f"),
        "signed_quantity": format(issue.signed_quantity, ".3f"), "issued_to_id": issue.department_id,
        "issued_to_label": issue.department_label, "recipient": issue.recipient,
        "reference": issue.reference, "actor_id": issue.actor_id, "occurred_at": issue.occurred_at.isoformat(),
        "allocations": [{"id": row.pk, "receipt_uuid": str(row.lot.receipt.public_id),
            "quantity": format(row.quantity, ".3f"), "unit_cost": format(row.lot.unit_cost, ".2f") if row.lot.unit_cost is not None else None}
            for row in issue.lot_allocations.select_related("lot__receipt").order_by("pk")]}


def returned_quantity(issue):
    return issue.supply_returns.filter(status="accepted").aggregate(total=Sum("quantity"))["total"] or Decimal(0)


def _capacity(issue, quantity, allocation):
    if issue.kind != "issue" or issue.quantity <= 0 or issue.signed_quantity != -issue.quantity:
        raise ValidationError("Select a valid original issue.")
    if issue.item.use_fifo:
        allocations = list(issue.lot_allocations.select_related("lot"))
        if (sum((row.quantity for row in allocations), Decimal(0)) != issue.quantity
                or any(row.quantity <= 0 or row.lot.item_id != issue.item_id for row in allocations)):
            raise ValidationError("The original FIFO allocations do not reproduce this issue. Investigate first.")
    for previous in issue.supply_returns.select_related("issue__item", "movement"):
        verify_history(previous)
    # Legacy returns cannot safely be assigned to an issue by matching labels or dates.
    if issue.item.movements.filter(kind="return", supply_return_case__isnull=True).exists():
        raise ValidationError("This item has unlinked legacy returns. Reconcile their issue lineage before accepting another return.")
    if returned_quantity(issue) + quantity > issue.quantity:
        raise ValidationError("The return exceeds the original issue's unreturned quantity.")
    if allocation:
        prior = Return.objects.filter(source_allocation=allocation, status="accepted").aggregate(total=Sum("quantity"))["total"] or Decimal(0)
        if prior + quantity > allocation.quantity:
            raise ValidationError("The return exceeds the selected original allocation's unreturned quantity.")


def snapshot(case):
    data = {name: getattr(case, name) for name in ("issue_id", "source_allocation_id", "reference", "returned_by",
        "condition_note", "cost_basis_note", "source_snapshot", "original_filename", "sha256", "size", "status",
        "state_version", "created_by_id", "decided_by_id", "decision_note", "movement_id")}
    data.update(public_id=str(case.public_id), quantity=format(case.quantity, ".3f"), observed_on=str(case.observed_on),
        file=case.file.name, decided_at=case.decided_at.isoformat() if case.decided_at else None)
    return data


def _event(case, actor, action):
    value = snapshot(case)
    Event.objects.create(case=case, actor=actor, action=action, snapshot=value,
        checksum=_hash({"actor_id": actor.pk, "action": action, "snapshot": value}))


def verify_history(case):
    events = list(case.events.all())
    if len(events) != case.state_version or not events:
        raise ValidationError("Supply return history is incomplete.")
    for version, event in enumerate(events, 1):
        if event.snapshot.get("state_version") != version or event.checksum != _hash({
                "actor_id": event.actor_id, "action": event.action, "snapshot": event.snapshot}):
            raise ValidationError("Supply return history failed its integrity check.")
    if events[-1].snapshot != snapshot(case):
        raise ValidationError("The return no longer matches its retained history.")
    if case.status == "accepted":
        movement = case.movement
        cost = next((row["unit_cost"] for row in case.source_snapshot["allocations"]
            if row["id"] == case.source_allocation_id), None)
        expected_cost = Decimal(cost) if cost is not None else None
        if (not movement or movement.kind != "return" or movement.item_id != case.issue.item_id
                or movement.quantity != case.quantity or movement.signed_quantity != case.quantity
                or movement.unit_cost != expected_cost or movement.actor_id != case.decided_by_id):
            raise ValidationError("The return's stock movement failed its lineage check.")
        if case.source_snapshot["use_fifo"]:
            lot = getattr(movement, "created_lot", None)
            if not lot or lot.quantity != case.quantity or lot.unit_cost != expected_cost or lot.item_id != movement.item_id:
                raise ValidationError("The returned stock lot failed its lineage check.")


def verify_source(case):
    root = Path(case.file.storage.location).resolve()
    path = root / case.file.name
    try:
        path.resolve().relative_to(root / "inventory" / "supply-returns" / str(case.public_id))
        if ".." in Path(case.file.name).parts or path.resolve() != path:
            raise ValueError
    except ValueError as error:
        raise ValidationError("Return evidence has an unsafe location.") from error
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
    except OSError as error:
        raise ValidationError("Return evidence is unavailable; restore or investigate it.") from error
    if digest.hexdigest() != case.sha256 or size != case.size:
        raise ValidationError("Return evidence failed its integrity check.")
    return path


@transaction.atomic
def record_return(*, actor, issue, request_id, expected_source, source_allocation_id, quantity,
        reference, returned_by, observed_on, condition_note, cost_basis_note, upload):
    from .forms import _validate_disposal_upload
    _require(actor, "record", issue)
    ConsumableItem.objects.select_for_update().get(pk=issue.item_id)
    issue = StockMovement.objects.select_related("item").get(pk=issue.pk)
    _require(actor, "record", issue)
    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid return request identity.")
    quantity = Return._meta.get_field("quantity").clean(quantity, None)
    observed_on = Return._meta.get_field("observed_on").clean(observed_on, None)
    reference, returned_by = _text(reference, 120), _text(returned_by, 160)
    condition_note, cost_basis_note = _text(condition_note, 240), _text(cost_basis_note, 240)
    allocation = None
    if source_allocation_id is not None:
        allocation = issue.lot_allocations.select_related("lot").filter(pk=source_allocation_id).first()
        if not allocation or not issue.item.use_fifo:
            raise ValidationError("Choose an allocation belonging to this original FIFO issue, or unknown cost.")
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("Return evidence must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    existing = Return.objects.filter(public_id=request_id).first()
    if existing:
        expected = dict(issue_id=issue.pk, source_allocation_id=source_allocation_id, quantity=quantity,
            reference=reference, returned_by=returned_by, observed_on=observed_on, condition_note=condition_note,
            cost_basis_note=cost_basis_note, created_by_id=actor.pk, source_snapshot=expected_source,
            sha256=digest.hexdigest(), size=size)
        if any(getattr(existing, name) != value for name, value in expected.items()):
            raise ValidationError("This request identity belongs to different return content.")
        verify_history(existing)
        verify_source(existing)
        return existing
    if observed_on > timezone.localdate() or observed_on < timezone.localdate(issue.occurred_at):
        raise ValidationError("The return observation must be on or after the issue and no later than today.")
    if expected_source != source_basis(issue):
        raise ValidationError("The original issue changed. Reload and investigate before recording the return.")
    _capacity(issue, quantity, allocation)
    case = Return(public_id=request_id, issue=issue, source_allocation=allocation, quantity=quantity,
        reference=reference, returned_by=returned_by, observed_on=observed_on, condition_note=condition_note,
        cost_basis_note=cost_basis_note, source_snapshot=expected_source, file=upload,
        original_filename=Path(upload.name).name, sha256=digest.hexdigest(), size=size, created_by=actor)
    case.full_clean(validate_unique=False)
    try:
        with transaction.atomic():
            case.save()
    except IntegrityError:
        raise ValidationError("This request identity was already recorded. Reload the return history.")
    _event(case, actor, "recorded")
    return case


@transaction.atomic
def decide_return(*, actor, case, expected_version, action, note, suitable_for_stock=False):
    if action not in ("accept", "decline", "cancel"):
        raise ValidationError("Choose acceptance, non-acceptance or cancellation.")
    authority = "record" if action == "cancel" else "review"
    _require(actor, authority, case.issue)
    ConsumableItem.objects.select_for_update().get(pk=case.issue.item_id)
    case = Return.objects.select_for_update().select_related("issue__item", "source_allocation__lot").get(pk=case.pk)
    _require(actor, authority, case.issue)
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version != case.state_version or case.status != "pending":
        raise ValidationError("This return changed or was already decided. Reload its history.")
    verify_history(case)
    note = _text(note, 240)
    if action != "cancel" and case.created_by_id == actor.pk:
        raise PermissionDenied("A different receiving officer must review this return.")
    if action == "accept":
        if suitable_for_stock is not True:
            raise ValidationError("Confirm that the observed goods are suitable for return to usable stock.")
        verify_source(case)
        if source_basis(case.issue) != case.source_snapshot:
            raise ValidationError("The original issue or lot basis changed. Investigate before accepting.")
        _capacity(case.issue, case.quantity, case.source_allocation)
        unit_cost = case.source_allocation.lot.unit_cost if case.source_allocation_id else None
        case.movement = record_stock_movement(actor=actor, item=case.issue.item, kind="return", quantity=case.quantity,
            department_id=case.issue.department_id, department_label=case.issue.department_label,
            recipient=case.returned_by, reference=case.reference, reason=note, unit_cost=unit_cost)
        case.status = "accepted"
    else:
        case.status = "cancelled" if action == "cancel" else "declined"
    case.decided_by, case.decided_at, case.decision_note = actor, timezone.now(), note
    case.state_version += 1
    case.save()
    _event(case, actor, case.status)
    return case
