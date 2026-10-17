"""Reviewed documentary annotations. No custody, stock or Finance writes."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import property_determinations as properties
from .access import can, gso_department_for_user, has_inventory_permission, in_gso_scope
from .disposal_evidence import prepare_uploads, verify_case_evidence
from .models import (AssetDisposalCase, AssetTransfer, PropertyDetermination,
                     PropertyMovementRecord as Record, PropertyMovementEvent as Event, ReceivingLine)

CONTENT_FIELDS = ("movement_date", "within_day_order", "reference", "item_number",
                  "office_officer_label", "stock_delta", "opening_quantity", "unit_cost", "remarks")


def can_act(actor, action, asset=None):
    owner = gso_department_for_user(actor)
    if action not in ("view", "record", "review") or not owner or not in_gso_scope(actor) or not can(actor, "view"):
        return False
    if asset is not None and asset.department_id != owner.pk:
        return False
    names = ("view", "record", "review") if action == "view" else (action,)
    return any(has_inventory_permission(actor, f"{name}_property_movement", mutation=action != "view") for name in names)


def require(actor, action, asset):
    if not can_act(actor, action, asset):
        raise PermissionDenied


def visible(actor):
    if not can_act(actor, "view"):
        return Record.objects.none()
    return Record.objects.filter(asset__department_id=gso_department_for_user(actor).pk)


def plain(value):
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def model_data(row):
    return plain({field.attname: (getattr(row, field.attname).name if field.name == "file"
                                 else getattr(row, field.attname))
                  for field in row._meta.concrete_fields if not field.generated})


def latest_verified(asset, source_key):
    return asset.property_movements.filter(source_key=source_key, status="verified").order_by("-decided_at", "-pk").first()


def _physical_source(asset, kind, source_id, *, lock=False):
    if kind == "opening":
        if source_id is not None:
            raise ValidationError("An opening uses its own source packet, not a physical-event link.")
        return "opening", {}, {}
    if isinstance(source_id, bool) or not isinstance(source_id, int) or source_id < 1:
        raise ValidationError("Choose an existing source event.")
    if kind == "receipt":
        query = ReceivingLine.objects.filter(pk=source_id, registered_asset=asset)
    elif kind in ("handoff", "return"):
        query = AssetTransfer.objects.filter(pk=source_id, asset=asset)
    elif kind == "disposal":
        query = AssetDisposalCase.objects.filter(pk=source_id, asset=asset)
    else:
        raise ValidationError("Choose a documented opening, receipt, handoff, return or disposal.")
    row = query.first()
    if row is not None and lock:
        row = query.select_for_update().first()
    if row is None:
        raise ValidationError("The source event does not belong to this asset.")
    data = {"record": model_data(row)}
    if kind == "receipt":
        from .receiving import verify_receipt_evidence
        from .receipt_amendments import amendment_basis
        if row.kind != "asset" or row.is_void or row.accepted_quantity != 1 or row.receipt.status != "accepted":
            raise ValidationError("Use an accepted, nonvoid receipt line for one registered asset.")
        verify_receipt_evidence(row.receipt)
        data.update(receipt=amendment_basis(row), evidence=plain(list(row.receipt.evidence.order_by("pk").values())))
        return f"receipt:{row.receipt.public_id}:{row.sequence}", data, {"receipt_line": row}
    if kind in ("handoff", "return"):
        if row.kind != kind or row.status != "accepted" or not row.acknowledged_at or not row.acknowledged_by_id:
            raise ValidationError("Use an acknowledged handoff or independently confirmed return.")
        if kind == "return":
            from .custody_returns import verify_return_evidence
            verify_return_evidence(row)
            data.update(evidence=plain(list(row.return_evidence.order_by("pk").values())),
                        events=plain(list(row.return_events.order_by("pk").values())))
        return f"transfer:{row.public_id}", data, {"transfer": row}
    if row.status != "disposed" or not row.disposal_date or not row.completed_by_id:
        raise ValidationError("Use a completed disposal with its completion date and officer.")
    if not {"authority", "completion"}.issubset(set(row.attachments.values_list("kind", flat=True))):
        raise ValidationError("Retain disposal authority and completion evidence before using this source.")
    verify_case_evidence(row)
    data.update(evidence=plain(list(row.attachments.order_by("pk").values())),
                events=plain(list(row.events.order_by("pk").values())))
    return f"disposal:{row.public_id}", data, {"disposal": row}


def source_basis(*, asset, determination_id, source_kind, source_id=None, lock=False):
    if asset.quantity != 1:
        raise ValidationError("Reconcile grouped property before documenting individual movements.")
    key, physical, relations = _physical_source(asset, source_kind, source_id, lock=lock)
    query = PropertyDetermination.objects.filter(pk=determination_id, asset=asset, status="verified")
    determination = query.first()
    if determination is not None and lock:
        determination = query.select_for_update().first()
    if not determination:
        raise ValidationError("Select a verified property determination for this asset.")
    properties.verify_history(determination)
    properties.verify_source(determination)
    if properties.source_basis(asset) != determination.source_snapshot:
        raise ValidationError("The property determination's asset or receipt basis changed; reconcile its source first.")
    if asset.property_determinations.filter(status="pending").exists():
        raise ValidationError("Decide the pending property determination before using its movement basis.")
    basis = dict(asset_uuid=str(asset.public_id), owner_id=asset.department_id, quantity=asset.quantity,
                 determination=properties.snapshot(determination), physical=physical)
    return key, basis, {"determination": determination, **relations}


def clean_content(data):
    if set(data) != set(CONTENT_FIELDS):
        raise ValidationError("Supply only the documented movement fields.")
    data = dict(data)
    for name in ("reference", "item_number", "office_officer_label", "remarks"):
        if not isinstance(data[name], str):
            raise ValidationError("Documentary labels must be text.")
        data[name] = data[name].strip()
    if not data["reference"] or not data["remarks"]:
        raise ValidationError("Record the source reference and explain its stock effect.")
    if type(data["movement_date"]) is not date or data["movement_date"] > timezone.localdate():
        raise ValidationError("Supply a movement date that is not in the future.")
    for name in ("within_day_order", "stock_delta", "opening_quantity"):
        if name == "opening_quantity" and data[name] is None:
            continue
        if isinstance(data[name], bool) or not isinstance(data[name], int):
            raise ValidationError("Use whole-number chronology and quantities.")
    if data["unit_cost"] is not None:
        try:
            if isinstance(data["unit_cost"], bool):
                raise InvalidOperation
            value = Decimal(str(data["unit_cost"]))
            if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
                raise InvalidOperation
            data["unit_cost"] = value.quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValidationError("Use a nonnegative documented cost with at most two decimal places, or leave it unknown.") from error
    return data


def snapshot(row):
    return model_data(row)


def event(row, actor, action):
    data = snapshot(row)
    Event.objects.create(movement=row, actor=actor, action=action, snapshot=data,
                         checksum=properties.checksum({"actor": actor.pk, "action": action, "snapshot": data}))


def verify_history(row):
    events = list(row.events.all())
    if not events or len(events) != row.state_version:
        raise ValidationError("Property movement history is incomplete.")
    for version, entry in enumerate(events, 1):
        if entry.snapshot.get("state_version") != version or entry.checksum != properties.checksum({
                "actor": entry.actor_id, "action": entry.action, "snapshot": entry.snapshot}):
            raise ValidationError("Property movement history failed its integrity check.")
    if events[-1].snapshot != snapshot(row):
        raise ValidationError("The movement record no longer matches its retained history.")


def verify_evidence(row):
    import hashlib
    root = Path(row.file.storage.location).resolve()
    path = root / row.file.name
    try:
        path.resolve().relative_to(root / "inventory" / "property-movements" / str(row.public_id))
        if ".." in Path(row.file.name).parts or path.resolve() != path:
            raise ValueError
        digest, size = hashlib.sha256(), 0
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
        if digest.hexdigest() != row.sha256 or size != row.size:
            raise ValueError
    except (ValueError, OSError) as error:
        raise ValidationError("Movement evidence is missing, changed or unsafe. Restore or investigate it.") from error
    return path


def source_id(row):
    return row.receipt_line_id or row.transfer_id or row.disposal_id


def physical_date(kind, basis):
    physical = basis["physical"]
    raw = (physical["receipt"]["header"]["inspection_date" if physical["receipt"].get("followup") else "delivery_date"] if kind == "receipt"
           else physical["record"]["disposal_date" if kind == "disposal" else "transfer_date"])
    return date.fromisoformat(raw)


def current_records(asset):
    current = {}
    for row in asset.property_movements.filter(status="verified").order_by("-decided_at", "-pk"):
        current.setdefault(row.source_key, row)
    return current


@transaction.atomic
def project(*, actor, asset, cutoff):
    """Current reviewed reconstruction through cutoff, not historical knowledge or valuation."""
    require(actor, "view", asset)
    if type(cutoff) is not date or cutoff > timezone.localdate():
        raise ValidationError("Choose a cutoff date that is not in the future.")
    asset = properties.lock_asset(asset.pk)
    require(actor, "view", asset)
    current = current_records(asset)
    opening = current.get("opening")
    issues, rows = [], []
    result = dict(asset=asset, cutoff=cutoff, opening=opening, rows=rows, issues=issues, balance=None)
    if asset.status == asset.ENTRY_VOID:
        issues.append("This is a corrected erroneous entry. Its retained receipt is not physical stock history.")
        return result
    if asset.quantity != 1:
        issues.append("Reconcile the grouped asset quantity before calculating individual stock.")
    if not opening:
        issues.append("No independently verified opening balance is recorded.")
        return result
    if opening.movement_date > cutoff:
        issues.append("The current opening is later than the requested cutoff.")
        return result
    if asset.status == asset.RETIRED and not asset.disposal_cases.filter(status="disposed", disposal_date__isnull=False).exists():
        issues.append("The retired asset has no dated completed disposal; reconcile its historical status.")
    if asset.property_movements.filter(status="pending").exists():
        issues.append("A pending movement or opening correction requires a decision.")
    selected = sorted((row for key, row in current.items() if key != "opening"
        and opening.movement_date < row.movement_date <= cutoff), key=lambda r: (r.movement_date, r.within_day_order))
    expected = set()
    for line in ReceivingLine.objects.filter(registered_asset=asset, receipt__status="accepted", is_void=False).select_related("receipt"):
        event_date = line.receipt.inspection_date if line.receipt.followup_source_id else line.receipt.delivery_date
        if opening.movement_date < event_date <= cutoff:
            expected.add(f"receipt:{line.receipt.public_id}:{line.sequence}")
    for transfer in asset.transfers.filter(status="accepted", transfer_date__gt=opening.movement_date, transfer_date__lte=cutoff):
        expected.add(f"transfer:{transfer.public_id}")
    for case in asset.disposal_cases.filter(status="disposed", disposal_date__gt=opening.movement_date, disposal_date__lte=cutoff):
        expected.add(f"disposal:{case.public_id}")
    retained = {row.source_key for row in selected}
    if expected - retained:
        issues.append(f"{len(expected - retained)} confirmed source event(s) lack a verified entry in this period.")
    if retained - expected:
        issues.append("An entry has no corresponding confirmed physical source in this period.")
    balance = opening.opening_quantity
    if balance not in (0, 1):
        issues.append("The retained opening quantity is invalid.")
    if balance and asset.disposal_cases.filter(status="disposed", disposal_date__lte=opening.movement_date).exists():
        issues.append("The opening asserts stock after a recorded completed disposal.")
    positions = set()
    opening_group = None
    for row in [opening, *selected]:
        try:
            verify_history(row)
            verify_evidence(row)
            key, basis, _ = source_basis(asset=asset, determination_id=row.determination_id,
                source_kind=row.source_kind, source_id=source_id(row), lock=True)
            if key != row.source_key or basis != row.source_snapshot:
                raise ValidationError("The retained source changed and needs reconciliation.")
            facts = basis["determination"]
            group = (facts["treatment"], facts["property_class"], facts["fund_label"])
            if row == opening:
                opening_group = group
            elif group != opening_group:
                raise ValidationError("The class/fund basis changed; reconcile it before combining entries.")
            if row != opening and row.movement_date != physical_date(row.source_kind, basis):
                raise ValidationError("The entry date differs from its retained physical source.")
        except ValidationError as error:
            issues.append(f"{row.reference}: {' '.join(error.messages)}")
        if row == opening:
            continue
        position = (row.movement_date, row.within_day_order)
        if position in positions:
            issues.append("Two entries have the same date and within-day order.")
        positions.add(position)
        if balance is not None:
            balance += row.stock_delta
            if balance not in (0, 1):
                issues.append(f"{row.reference}: the supplied effects would put stock outside zero or one.")
            if row.source_kind == "disposal" and balance != 0:
                issues.append(f"{row.reference}: disposal must not leave this item in stock.")
        rows.append(dict(record=row, balance=None))
    if not issues:
        running = opening.opening_quantity
        for item in rows:
            running += item["record"].stock_delta
            item["balance"] = running
        result["balance"] = balance
    return result


@transaction.atomic
def record(*, actor, asset, determination_id, source_kind, source_id, request_id,
           expected_source, expected_predecessor, data, upload):
    require(actor, "record", asset)
    asset = properties.lock_asset(asset.pk)
    require(actor, "record", asset)
    from .receipt_quantity_corrections import require_asset_available
    require_asset_available(asset)
    try:
        request_id = UUID(str(request_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError("Invalid movement request identity.") from error
    content = clean_content(data)
    prepared = prepare_uploads([("source", [upload])])[0]
    _, _, digest, size, _ = prepared
    existing = Record.objects.filter(public_id=request_id).first()
    if existing:
        same = dict(content, asset_id=asset.pk, determination_id=determination_id, source_kind=source_kind,
                    recorded_by_id=actor.pk, source_snapshot=expected_source, sha256=digest, size=size)
        prior_uuid = str(existing.predecessor.public_id) if existing.predecessor_id else None
        if (any(getattr(existing, key) != value for key, value in same.items())
                or (existing.receipt_line_id or existing.transfer_id or existing.disposal_id) != source_id
                or prior_uuid != expected_predecessor):
            raise ValidationError("This request identity belongs to different movement content.")
        verify_history(existing)
        verify_evidence(existing)
        return existing
    key, basis, relations = source_basis(asset=asset, determination_id=determination_id,
        source_kind=source_kind, source_id=source_id, lock=True)
    if source_kind != "opening" and content["movement_date"] != physical_date(source_kind, basis):
        raise ValidationError("Use the retained physical source date; reconcile a different date before recording the card entry.")
    previous = latest_verified(asset, key)
    if previous:
        verify_history(previous)
    if expected_source != basis or expected_predecessor != (str(previous.public_id) if previous else None):
        raise ValidationError("The physical source, property packet or previous annotation changed. Reopen the form.")
    if asset.property_movements.filter(status="pending").exists():
        raise ValidationError("Decide the pending movement record before entering another.")
    row = Record(**content, **relations, asset=asset, source_kind=source_kind, source_key=key,
        predecessor=previous, public_id=request_id, source_snapshot=basis, recorded_by=actor,
        file=upload, original_filename=Path(upload.name).name, sha256=digest, size=size)
    row.full_clean(validate_unique=False)
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError as error:
        raise ValidationError("A movement record was already entered. Reload its history.") from error
    event(row, actor, "recorded")
    return row


@transaction.atomic
def decide(*, actor, row, expected_version, action, note):
    if action not in ("verify", "reject", "cancel"):
        raise ValidationError("Choose verification, rejection or cancellation.")
    authority = "record" if action == "cancel" else "review"
    require(actor, authority, row.asset)
    asset = properties.lock_asset(row.asset_id)
    require(actor, authority, asset)
    if action == "verify":
        from .receipt_quantity_corrections import require_asset_available
        require_asset_available(asset)
    # Read source identity under the asset lock, then lock source before annotation.
    current = Record.objects.get(pk=row.pk)
    if current.asset_id != asset.pk:
        raise ValidationError("The movement's asset changed. Reload the record.")
    basis = None
    if action == "verify":
        key, basis, _ = source_basis(asset=asset, determination_id=current.determination_id,
            source_kind=current.source_kind, source_id=source_id(current), lock=True)
    current = Record.objects.select_for_update().get(pk=current.pk)
    if current.asset_id != asset.pk:
        raise ValidationError("The movement's asset changed. Reload the record.")
    if type(expected_version) is not int or expected_version != current.state_version or current.status != "pending":
        raise ValidationError("This movement was changed or decided. Reload its history.")
    verify_history(current)
    note = str(note or "").strip()
    if not note or len(note) > 500:
        raise ValidationError("Record a decision note of 1 to 500 characters.")
    if action != "cancel" and current.recorded_by_id == actor.pk:
        raise PermissionDenied("A different officer must verify the movement evidence.")
    if action == "verify":
        verify_evidence(current)
        previous = latest_verified(asset, current.source_key)
        if previous:
            verify_history(previous)
        if (key != current.source_key or basis != current.source_snapshot
                or current.predecessor_id != (previous.pk if previous else None)):
            raise ValidationError("The retained movement source or predecessor changed. Record a reviewed replacement.")
    current.status = {"verify": "verified", "reject": "rejected", "cancel": "cancelled"}[action]
    current.decided_by, current.decided_at, current.decision_note = actor, timezone.now(), note
    current.state_version += 1
    current._workflow_write = True
    try:
        current.save(update_fields=("status", "decided_by", "decided_at", "decision_note", "state_version"))
    finally:
        current._workflow_write = False
    event(current, actor, current.status)
    return current
