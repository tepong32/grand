"""Retain supplied property decisions without changing custody or Finance."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from .access import can, gso_department_for_user, has_inventory_permission, in_gso_scope
from .models import Asset, ReceivingLine, ReceivingReceipt, PropertyDetermination as Record, PropertyDeterminationEvent as Event
from .receipt_amendments import amendment_basis

ACQUISITION_DEFAULTS = {"acquisition_date": None, "acquisition_reference": "", "receipt_item_number": ""}
CONTENT_FIELDS = ("treatment", "reference", "source_date", "source_authority", "property_class", "fund_label",
    "useful_life", "life_unit", "life_basis", "life_start", "expires_on", "reason", *ACQUISITION_DEFAULTS)
ASSET_FIELDS = ("asset_name", "asset_kind", "inventory_class", "item_type", "property_tag", "serial_number",
    "chassis_number", "purchase_date", "supplier", "purchase_order_reference", "quantity", "unit_cost",
    "fund_code", "coa_account_code", "coa_account_title", "coa_basis")


def value(raw):
    if isinstance(raw, Decimal):
        return format(raw, ".2f")
    return raw.isoformat() if hasattr(raw, "isoformat") else raw


def checksum(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def can_act(actor, action, asset=None):
    owner = gso_department_for_user(actor)
    if action not in ("view", "record", "review") or not owner or not in_gso_scope(actor) or not can(actor, "view"):
        return False
    if asset is not None and asset.department_id != owner.pk:
        return False
    names = ("view", "record", "review") if action == "view" else (action,)
    return any(has_inventory_permission(actor, f"{name}_property_determination", mutation=action != "view") for name in names)


def visible(actor):
    if not can_act(actor, "view"):
        return Record.objects.none()
    return Record.objects.filter(asset__department_id=gso_department_for_user(actor).pk)


def require(actor, action, asset):
    if not can_act(actor, action, asset):
        raise PermissionDenied


def latest_verified(asset):
    return asset.property_determinations.filter(status="verified").order_by("-decided_at", "-pk").first()


def source_basis(asset):
    line = ReceivingLine.objects.select_related("receipt").filter(registered_asset=asset).first()
    return {"asset_uuid": str(asset.public_id), "owner_id": asset.department_id,
        "facts": {name: value(getattr(asset, name)) for name in ASSET_FIELDS},
        "receipt": amendment_basis(line) if line else None}


def lock_asset(asset_id):
    # Match acceptance: receipt -> asset -> property record. Never acquire a
    # receipt after an asset; cost amendments serialize on this same receipt.
    receipt_id = ReceivingLine.objects.filter(registered_asset_id=asset_id).values_list("receipt_id", flat=True).first()
    if receipt_id:
        ReceivingReceipt.objects.select_for_update().get(pk=receipt_id)
    asset = Asset.objects.select_for_update().get(pk=asset_id)
    current = ReceivingLine.objects.filter(registered_asset_id=asset_id).values_list("receipt_id", flat=True).first()
    if current != receipt_id:
        raise ValidationError("The receiving link changed. Reload the property record.")
    return asset


def snapshot(row):
    data = {name: value(getattr(row, name)) for name in CONTENT_FIELDS}
    # Preserve pre-0025 evidence: absent acquisition facts must not rewrite
    # historical snapshots or invalidate existing Finance requests.
    if not any(getattr(row, name) for name in ACQUISITION_DEFAULTS):
        for name in ACQUISITION_DEFAULTS:
            data.pop(name)
    data.update(public_id=str(row.public_id), asset_id=row.asset_id, predecessor_id=row.predecessor_id,
        source_snapshot=row.source_snapshot, file=row.file.name, original_filename=row.original_filename,
        sha256=row.sha256, size=row.size, status=row.status, state_version=row.state_version,
        recorded_by_id=row.recorded_by_id, recorded_at=value(row.recorded_at),
        decided_by_id=row.decided_by_id, decided_at=value(row.decided_at), decision_note=row.decision_note)
    return data


def event(row, actor, action):
    data = snapshot(row)
    Event.objects.create(determination=row, actor=actor, action=action, snapshot=data,
        checksum=checksum({"actor": actor.pk, "action": action, "snapshot": data}))


def verify_history(row):
    events = list(row.events.all())
    if len(events) != row.state_version or not events:
        raise ValidationError("Property determination history is incomplete.")
    for version, entry in enumerate(events, 1):
        if entry.snapshot.get("state_version") != version or entry.checksum != checksum({
                "actor": entry.actor_id, "action": entry.action, "snapshot": entry.snapshot}):
            raise ValidationError("Property history failed its integrity check.")
    if events[-1].snapshot != snapshot(row):
        raise ValidationError("The property record no longer matches its history.")


def verify_source(row):
    root = Path(row.file.storage.location).resolve()
    path = root / row.file.name
    try:
        path.resolve().relative_to(root / "inventory" / "property-determinations" / str(row.public_id))
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
        raise ValidationError("Property evidence is missing, changed or unsafe. Restore or investigate it.") from error
    return path


def clean_content(data):
    data = {**ACQUISITION_DEFAULTS, **data}
    if set(data) != set(CONTENT_FIELDS):
        raise ValidationError("Supply the documented property facts only.")
    content = {name: Record._meta.get_field(name).clean(raw.strip() if isinstance(raw, str) else raw, None)
               for name, raw in data.items()}
    if content["source_date"] > timezone.localdate():
        raise ValidationError("The supplied determination date cannot be in the future.")
    if content["acquisition_date"] and content["acquisition_date"] > timezone.localdate():
        raise ValidationError("The supplied acquisition date cannot be in the future.")
    if (content["acquisition_date"] or content["receipt_item_number"]) and not content["acquisition_reference"]:
        raise ValidationError("Identify the retained acquisition source when supplying its date or receipt-item number.")
    if content["useful_life"] is None:
        if content["life_unit"] or content["life_basis"] or content["life_start"]:
            raise ValidationError("Supply the useful-life duration when recording its unit or start basis.")
    elif not content["life_unit"] or not content["life_basis"]:
        raise ValidationError("Record the documented useful-life unit and start basis.")
    if content["expires_on"] and content["life_start"] and content["expires_on"] < content["life_start"]:
        raise ValidationError("Supplied expiry cannot precede the supplied start date.")
    return content


@transaction.atomic
def record(*, actor, asset, request_id, expected_source, expected_predecessor, data, upload):
    from .forms import _validate_disposal_upload
    require(actor, "record", asset)
    asset = lock_asset(asset.pk)
    require(actor, "record", asset)
    from .receipt_quantity_corrections import require_asset_available
    require_asset_available(asset)
    try:
        request_id = UUID(str(request_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError("Invalid property request identity.") from error
    content = clean_content(data)
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("Property evidence must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    existing = Record.objects.filter(public_id=request_id).first()
    if existing:
        same = dict(content, asset_id=asset.pk, recorded_by_id=actor.pk, source_snapshot=expected_source,
            sha256=digest.hexdigest(), size=size)
        previous_uuid = str(existing.predecessor.public_id) if existing.predecessor_id else None
        if any(getattr(existing, key) != val for key, val in same.items()) or previous_uuid != expected_predecessor:
            raise ValidationError("This request identity belongs to different property content.")
        verify_history(existing)
        verify_source(existing)
        return existing
    if asset.quantity != 1:
        raise ValidationError("Reconcile the legacy grouped quantity before recording individual property facts.")
    previous = latest_verified(asset)
    for prior in asset.property_determinations.all():
        verify_history(prior)
    if expected_source != source_basis(asset) or expected_predecessor != (str(previous.public_id) if previous else None):
        raise ValidationError("The asset, receipt or previous determination changed. Reopen the entry form.")
    if asset.property_determinations.filter(status="pending").exists():
        raise ValidationError("Decide the pending property record before creating another.")
    row = Record(**content, asset=asset, predecessor=previous, public_id=request_id, source_snapshot=expected_source,
        recorded_by=actor, file=upload, original_filename=Path(upload.name).name, sha256=digest.hexdigest(), size=size)
    row.full_clean(validate_unique=False)
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError as error:
        raise ValidationError("A property record was already recorded. Reload its history.") from error
    event(row, actor, "recorded")
    return row


@transaction.atomic
def decide(*, actor, row, expected_version, action, note):
    if action not in ("verify", "reject", "cancel"):
        raise ValidationError("Choose verification, rejection or cancellation.")
    authority = "record" if action == "cancel" else "review"
    require(actor, authority, row.asset)
    asset = lock_asset(row.asset_id)
    if action == "verify":
        from .receipt_quantity_corrections import require_asset_available
        require_asset_available(asset)
    row = Record.objects.select_for_update().get(pk=row.pk)
    require(actor, authority, asset)
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version != row.state_version or row.status != "pending":
        raise ValidationError("This property record changed or was already decided. Reload its history.")
    verify_history(row)
    note = str(note or "").strip()
    if not note or len(note) > 500:
        raise ValidationError("Record a decision note of 1 to 500 characters.")
    if action != "cancel" and row.recorded_by_id == actor.pk:
        raise PermissionDenied("A different officer must verify the supplied property evidence.")
    if action == "verify":
        verify_source(row)
        previous = latest_verified(asset)
        if previous:
            verify_history(previous)
        if asset.quantity != 1 or source_basis(asset) != row.source_snapshot or row.predecessor_id != (previous.pk if previous else None):
            raise ValidationError("The property source basis changed. Cancel or reject this record and document a replacement.")
    row.status = {"verify": "verified", "reject": "rejected", "cancel": "cancelled"}[action]
    row.decided_by, row.decided_at, row.decision_note = actor, timezone.now(), note
    row.state_version += 1
    row._workflow_write = True
    try:
        row.save(update_fields=("status", "decided_by", "decided_at", "decision_note", "state_version"))
    finally:
        row._workflow_write = False
    event(row, actor, row.status)
    return row
