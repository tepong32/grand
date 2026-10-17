"""Supplied approved requisitions and explicit physical issue lineage, default store only."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .access import can_stock, department_model, gso_department_for_user, has_inventory_permission, in_gso_scope
from .models import ConsumableItem, SupplyRequisition as Request, SupplyRequisitionLine as Line, SupplyFulfillment as Fulfillment, SupplyRequisitionEvent as Event
from .services import record_stock_movement


def can_act(actor, action, request=None):
    owner = gso_department_for_user(actor)
    if not owner or not in_gso_scope(actor) or not can_stock(actor, "view"):
        return False
    if request is not None and request.department_id != owner.pk:
        return False
    if action == "issue":
        return can_act(actor, "view", request) and can_stock(actor, "issue")
    actions = ("view", "record", "review") if action == "view" else (action,)
    return action in ("view", "record", "review") and any(has_inventory_permission(
        actor, f"{name}_supply_requisition", mutation=action != "view") for name in actions)


def visible(actor):
    if not can_act(actor, "view"):
        return Request.objects.none()
    return Request.objects.filter(department_id=gso_department_for_user(actor).pk)


def _require(actor, action, request=None):
    if not can_act(actor, action, request):
        raise PermissionDenied


def _text(value, length):
    value = str(value or "").strip()
    if not value or len(value) > length:
        raise ValidationError(f"Record between 1 and {length} characters.")
    return value


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def issued(line):
    return line.fulfillments.aggregate(total=Sum("quantity"))["total"] or Decimal(0)


def snapshot(request):
    result = {name: getattr(request, name) for name in ("department_id", "requesting_department_id",
        "requesting_department_label", "reference", "purpose", "sha256", "size", "original_filename",
        "status", "state_version", "created_by_id", "reviewed_by_id", "review_note", "close_note")}
    result.update(public_id=str(request.public_id), requested_on=str(request.requested_on), file=request.file.name,
        reviewed_at=request.reviewed_at.isoformat() if request.reviewed_at else None)
    result["lines"] = [{"id": line.pk, "public_id": str(line.public_id), "item_id": line.item_id,
        "item_uuid": str(line.item.public_id), "item_name": line.item_name, "unit": line.unit,
        "quantity": format(line.quantity, ".3f"), "fulfillments": [{"public_id": str(row.public_id),
            "movement_uuid": str(row.movement.public_id) if row.movement_id else None,
            "quantity": format(row.quantity, ".3f"), "outcome": row.outcome, "recipient": row.recipient,
            "note": row.note, "actor_id": row.actor_id} for row in line.fulfillments.select_related("movement")]}
        for line in request.lines.select_related("item")]
    return result


def _event(request, actor, action):
    value = snapshot(request)
    Event.objects.create(requisition=request, actor=actor, action=action, snapshot=value,
        checksum=_hash({"actor_id": actor.pk, "action": action, "snapshot": value}))


def verify_history(request):
    events = list(request.events.all())
    if len(events) != request.state_version or not events:
        raise ValidationError("Requisition history is incomplete. Investigate before continuing.")
    for version, event in enumerate(events, 1):
        if event.snapshot.get("state_version") != version or event.checksum != _hash({
            "actor_id": event.actor_id, "action": event.action, "snapshot": event.snapshot}):
            raise ValidationError("Requisition history failed its integrity check.")
    if events[-1].snapshot != snapshot(request):
        raise ValidationError("The requisition no longer matches its retained history.")
    for line in request.lines.all():
        if issued(line) > line.quantity:
            raise ValidationError("Issued quantity exceeds the supplied request. Investigate.")
        for row in line.fulfillments.select_related("movement"):
            movement = row.movement
            if row.outcome == "issued" and (not movement or movement.kind != "issue"
                    or movement.item_id != line.item_id or movement.quantity != row.quantity
                    or movement.department_id != request.requesting_department_id
                    or movement.actor_id != row.actor_id or movement.recipient != row.recipient):
                raise ValidationError("The linked stock movement no longer matches the issue record.")


def verify_source(request):
    root = Path(request.file.storage.location).resolve()
    path = root / request.file.name
    try:
        path.resolve().relative_to(root / "inventory" / "requisitions" / str(request.public_id))
        if ".." in Path(request.file.name).parts or path.resolve() != path:
            raise ValueError
    except ValueError as error:
        raise ValidationError("The requisition evidence has an unsafe location.") from error
    digest, size = hashlib.sha256(), 0
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
    except OSError as error:
        raise ValidationError("The requisition evidence is unavailable. Restore or investigate it.") from error
    if digest.hexdigest() != request.sha256 or size != request.size:
        raise ValidationError("Requisition evidence failed its integrity check.")
    return path


@transaction.atomic
def create_request(*, actor, request_id, requesting_department_id, reference, requested_on, purpose, upload, lines):
    from .forms import _validate_disposal_upload
    _require(actor, "record")
    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Invalid requisition identity.")
    reference, purpose = _text(reference, 120), _text(purpose, 4000)
    requested_on = Request._meta.get_field("requested_on").clean(requested_on, None)
    if requested_on > timezone.localdate():
        raise ValidationError("The supplied request date cannot be in the future.")
    destination = department_model().objects.filter(pk=requesting_department_id).exclude(name="---select one---").first()
    if destination is None:
        raise ValidationError("Select a requesting office from the department directory.")
    if not 1 <= len(lines) <= 50:
        raise ValidationError("Record 1 to 50 distinct supply lines.")
    normalized = [(int(row["item_id"]), Line._meta.get_field("quantity").clean(row["quantity"], None)) for row in lines]
    if len({pk for pk, _ in normalized}) != len(normalized):
        raise ValidationError("Combine repeated items into one requested quantity.")
    normalized.sort()
    items = {item.pk: item for item in ConsumableItem.objects.select_for_update().filter(
        pk__in=[pk for pk, _ in normalized]).order_by("pk")}
    owner = gso_department_for_user(actor)
    if len(items) != len(normalized) or any(item.department_id != owner.pk for item in items.values()):
        raise PermissionDenied
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("The supplied document must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    existing = Request.objects.filter(public_id=request_id).first()
    if existing:
        if (existing.created_by_id != actor.pk or existing.department_id != owner.pk
                or existing.requesting_department_id != destination.pk or existing.reference != reference
                or existing.requested_on != requested_on or existing.purpose != purpose
                or existing.sha256 != digest.hexdigest() or existing.size != size
                or sorted(existing.lines.values_list("item_id", "quantity")) != normalized):
            raise ValidationError("This request identity belongs to different content.")
        verify_history(existing)
        verify_source(existing)
        return existing
    if any(not item.is_active for item in items.values()):
        raise ValidationError("Select active supply items.")
    request = Request(public_id=request_id, department_id=owner.pk, requesting_department_id=destination.pk,
        requesting_department_label=destination.name, reference=reference, requested_on=requested_on,
        purpose=purpose, file=upload, original_filename=Path(upload.name).name, sha256=digest.hexdigest(), size=size,
        created_by=actor)
    request.full_clean(validate_unique=False)
    # Storage is not transactional: retain orphan files for reconciliation after a failed DB commit.
    try:
        with transaction.atomic():
            request.save()
    except IntegrityError:
        raise ValidationError("This request identity was already used. Reload the requisition list.")
    for pk, quantity in normalized:
        line = Line(requisition=request, item=items[pk], item_name=items[pk].name, unit=items[pk].unit, quantity=quantity)
        line.full_clean()
        line.save()
    _event(request, actor, "recorded")
    return request


def _locked(request, actor, action, version):
    _require(actor, action, request)
    # Lines are immutable. All item locks precede the case, matching stock services.
    ids = list(request.lines.values_list("item_id", flat=True))
    items = list(ConsumableItem.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    request = Request.objects.select_for_update().get(pk=request.pk)
    _require(actor, action, request)
    if isinstance(version, bool) or not isinstance(version, int) or version != request.state_version:
        raise ValidationError("This requisition changed. Reload its history before continuing.")
    verify_history(request)
    if len(items) != len(ids) or any(item.department_id != request.department_id for item in items):
        raise ValidationError("A supply item changed owner or is missing. Investigate before continuing.")
    return request


def _save(request, actor, action):
    request.state_version += 1
    request.save()
    _event(request, actor, action)
    return request


@transaction.atomic
def decide_request(*, actor, request, expected_version, action, note):
    if action not in ("approve", "close"):
        raise ValidationError("Choose document review or close remainder.")
    request = _locked(request, actor, "review" if action == "approve" else "record", expected_version)
    note = _text(note, 240)
    if action == "approve":
        if request.status != "pending":
            raise ValidationError("Only a pending document can be reviewed.")
        if request.created_by_id == actor.pk:
            raise PermissionDenied("A different officer must check the supplied approved requisition.")
        verify_source(request)
        request.status, request.reviewed_by, request.reviewed_at, request.review_note = "approved", actor, timezone.now(), note
    else:
        if request.status not in ("pending", "approved"):
            raise ValidationError("The request is already complete or closed.")
        request.status, request.close_note = "closed", note
    return _save(request, actor, "document_reviewed" if action == "approve" else "remainder_closed")


@transaction.atomic
def fulfill(*, actor, request, expected_version, line_id, outcome, quantity, recipient, note):
    request = _locked(request, actor, "issue", expected_version)
    if request.status != "approved":
        raise ValidationError("Review the supplied requisition before recording fulfillment.")
    verify_source(request)
    line = request.lines.select_related("item").filter(pk=line_id).first()
    if line is None:
        raise ValidationError("Select a line from this requisition.")
    quantity = Fulfillment._meta.get_field("quantity").clean(quantity, None)
    note = _text(note, 240)
    remaining = line.quantity - issued(line)
    if remaining <= 0:
        raise ValidationError("The requested quantity for this line is already issued.")
    movement = None
    if outcome == "issued":
        recipient = _text(recipient, 160)
        if quantity <= 0 or quantity > remaining:
            raise ValidationError("Issue a positive quantity no greater than the unissued remainder.")
        if line.item.name != line.item_name or line.item.unit != line.unit:
            raise ValidationError("The item's name or unit changed. Close and record a corrected requisition.")
        movement = record_stock_movement(actor=actor, item=line.item, kind="issue", quantity=quantity,
            department_id=request.requesting_department_id, recipient=recipient, reference=request.reference,
            reason=note)
    elif outcome == "unavailable":
        if quantity != 0 or recipient.strip():
            raise ValidationError("Unavailable observations have zero quantity and no physical recipient.")
        recipient = ""
    else:
        raise ValidationError("Choose issued or unavailable.")
    row = Fulfillment(line=line, movement=movement, quantity=quantity, outcome=outcome, recipient=recipient, note=note, actor=actor)
    row.full_clean()
    row.save()
    if all(issued(candidate) == candidate.quantity for candidate in request.lines.all()):
        request.status = "fulfilled"
    _save(request, actor, outcome)
    return row
