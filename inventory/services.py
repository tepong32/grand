from decimal import Decimal, InvalidOperation
from datetime import date
import csv
import hashlib
from io import StringIO
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models.functions import Lower, Trim
from django.utils import timezone

from .access import (
    asset_in_scope, can, can_acknowledge_asset_transfer, can_request_asset_disposal,
    can_review_asset_disposal, can_transfer_asset, can_manage_asset_verification,
    department_model, department_for_user, gso_department_for_user,
)
from .models import (
    Asset, AssetAuditEvent, AssetDisposalAttachment, AssetDisposalCase,
    AssetDisposalEvent, AssetTransfer, AssetVerificationEvent, AssetVerificationRecord,
    AssetVerificationRound, AssetVerificationFinding, AssetVerificationFindingEvent,
    AssetAccountingImport, AssetAccountingLine, ConsumableAuditEvent, ConsumableItem,
    StockLot, StockLotAllocation, StockMovement,
)


SNAPSHOT_FIELDS = (
    "asset_kind", "inventory_class", "item_type", "asset_name", "category", "property_tag", "brand", "model_number", "serial_number",
    "plate_number", "engine_number", "chassis_number", "registration_due", "obr_reference",
    "purchase_order_reference", "voucher_reference", "journal_reference", "fund_code",
    "coa_account_code", "coa_account_title", "coa_basis", "purchase_date", "supplier", "unit_cost",
    "quantity", "assigned_office", "status",
    "assigned_department_id", "assigned_department_label", "returned_date", "notes",
)


def asset_snapshot(asset):
    result = {}
    for name in SNAPSHOT_FIELDS:
        value = getattr(asset, name)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        result[name] = value
    result["custodian_user_local_id"] = asset.custodian_user_id
    result["custodian_source"] = asset.custodian_snapshot
    result["last_custody_return_uuid"] = str(asset.last_custody_return.public_id) if asset.last_custody_return_id else None
    return result


def _require(user, permission, asset=None):
    if not can(user, permission):
        raise PermissionDenied
    if asset is not None and not asset_in_scope(user, asset):
        raise PermissionDenied


def _editable_data(data, allowed):
    """Do not let adapters or future forms replace identity, ownership or actors."""
    if set(data) - set(allowed):
        raise ValidationError("The request contains fields that this workflow cannot change.")
    return dict(data)


ASSET_INPUT_FIELDS = (set(SNAPSHOT_FIELDS) - {"assigned_department_id", "assigned_department_label"}) | {"assigned_department"}
RECEIVED_ASSET_FACTS = ("unit_cost", "quantity", "supplier", "purchase_order_reference")
CONSUMABLE_INPUT_FIELDS = {"name", "category", "unit", "use_fifo", "minimum_stock", "is_active", "notes"}


def validate_asset_identifiers(department_id, data, existing=None):
    # All normal asset create/edit paths serialize identifier allocation per owner.
    model = department_model()
    model.objects.select_for_update().get(pk=department_id)
    for field in ("property_tag", "serial_number", "chassis_number"):
        if field not in data:
            continue
        value = data[field].strip()
        data[field] = value
        if not value or (existing and value == getattr(existing, field)):
            continue
        candidates = Asset.objects.filter(department_id=department_id)
        if existing:
            candidates = candidates.exclude(pk=existing.pk)
        if candidates.annotate(identity=Lower(Trim(field))).filter(identity=value.lower()).exists():
            raise ValidationError({field: "This identifier already exists in the register. Review the existing record before proceeding."})


@transaction.atomic
def create_asset(*, actor, data):
    _require(actor, "add")
    department = gso_department_for_user(actor)
    if department is None:
        raise PermissionDenied
    data = _editable_data(data, ASSET_INPUT_FIELDS)
    if data.get("status") == Asset.RETIRED:
        raise ValidationError("Use the documented disposal case workflow to retire an asset.")
    if data.get("status") == Asset.ENTRY_VOID:
        raise ValidationError("Only a reviewed receipt correction can mark an erroneous entry.")
    validate_asset_identifiers(department.pk, data)
    assigned_department_pk = data.pop("assigned_department", None)
    assigned_department = _resolve_assigned_department(assigned_department_pk)
    asset = Asset.objects.create(
        **data,
        assigned_department_id=assigned_department.pk if assigned_department else None,
        assigned_department_label=assigned_department.name if assigned_department else "",
        department_id=department.pk,
        department_label=department.name, created_by=actor, updated_by=actor,
    )
    AssetAuditEvent.objects.create(
        asset=asset, department_id=asset.department_id, actor=actor,
        action=AssetAuditEvent.CREATED, snapshot=asset_snapshot(asset),
    )
    return asset


@transaction.atomic
def update_asset(*, actor, asset, data):
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    _require(actor, "change", asset)
    if data.get("status") == Asset.RETIRED:
        raise ValidationError("Use the documented disposal case workflow to retire an asset.")
    from .receipt_quantity_corrections import require_asset_available
    require_asset_available(asset)
    if data.get("status") == Asset.ENTRY_VOID:
        raise ValidationError("Only a reviewed receipt correction can mark an erroneous entry.")
    from .maintenance import require_no_open_maintenance
    require_no_open_maintenance(asset)
    if asset.transfers.filter(status=AssetTransfer.PENDING).exists():
        raise PermissionDenied("This asset has a handoff waiting for acknowledgment.")
    if asset.disposal_cases.filter(status__in=(
        AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
        AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED,
    )).exists():
        raise PermissionDenied("This asset has an open disposal case and cannot be edited.")
    if asset.status == Asset.RETIRED:
        raise PermissionDenied("Retired asset records are read-only.")
    data = _editable_data(data, ASSET_INPUT_FIELDS)
    # Acceptance creates the asset and its receipt link in one transaction. Read
    # the link after locking the asset; do not invert receipt -> asset lock order.
    from .models import ReceivingLine
    if ReceivingLine.objects.filter(registered_asset_id=asset.pk).exists():
        changed = [field for field in RECEIVED_ASSET_FACTS
                   if field in data and data[field] != getattr(asset, field)]
        if changed:
            raise ValidationError("Retain the accepted receipt's cost, quantity, supplier and purchase order. "
                                  "Use the receipt cost amendment workflow for documentary cost corrections.")
    validate_asset_identifiers(asset.department_id, data, existing=asset)
    has_department = "assigned_department" in data
    assigned_department = _resolve_assigned_department(data.pop("assigned_department", None)) if has_department else None
    if (asset.custodian_user_id or asset.last_custody_return_id) and (
        (has_department and (assigned_department.pk if assigned_department else None) != asset.assigned_department_id)
        or ("assigned_office" in data and data["assigned_office"] != asset.assigned_office)
    ):
        raise ValidationError("Use an acknowledged handoff to change named employee custody.")
    for field, value in data.items():
        setattr(asset, field, value)
    if has_department:
        asset.assigned_department_id = assigned_department.pk if assigned_department else None
        asset.assigned_department_label = assigned_department.name if assigned_department else ""
    asset.updated_by = actor
    asset.save()
    AssetAuditEvent.objects.create(
        asset=asset, department_id=asset.department_id, actor=actor,
        action=AssetAuditEvent.UPDATED, snapshot=asset_snapshot(asset),
    )
    return asset


@transaction.atomic
def retire_asset(*, actor, asset):
    raise PermissionDenied("Use the documented disposal case workflow to retire an asset.")


def _resolve_assigned_department(pk):
    if not pk:
        return None
    model = department_model()
    department = model.objects.filter(pk=pk).first() if model else None
    if department is None:
        raise PermissionDenied("The selected department is no longer available.")
    return department


@transaction.atomic
def create_asset_transfer(*, actor, asset, data, request_id=None, expected_custody=None):
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    if not can_transfer_asset(actor) or not asset_in_scope(actor, asset):
        raise PermissionDenied
    data = _editable_data(data, {"destination_department", "destination_custodian", "transfer_date", "reason", "reference",
                                 "destination_employee_id", "employee_source_checksum"})
    if data.get("destination_employee_id") is not None:
        from .employee_sources import require_employee_custody_manager
        require_employee_custody_manager(actor)
    if request_id is not None:
        try:
            request_id = UUID(str(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError("Invalid handoff request identity.")
        if not data.get("destination_employee_id"):
            raise ValidationError("A named handoff request must select an employee.")
        existing = AssetTransfer.objects.filter(public_id=request_id).first()
        if existing:
            if (existing.asset_id != asset.pk or existing.requested_by_id != actor.pk
                    or str(existing.destination_custodian_user_id) != str(data.get("destination_employee_id"))
                    or existing.destination_employee_checksum != data.get("employee_source_checksum")
                    or existing.reference != data.get("reference", "").strip()
                    or existing.reason != data.get("reason", "").strip()
                    or existing.transfer_date.isoformat() != str(data.get("transfer_date"))):
                raise ValidationError("This handoff request identity already belongs to different recorded content.")
            return existing
    if expected_custody is not None and expected_custody != custody_source(asset):
        raise ValidationError("The asset custody changed after this preview. Review the handoff again.")
    from .receipt_quantity_corrections import require_asset_available
    require_asset_available(asset)
    from .maintenance import require_no_open_maintenance
    require_no_open_maintenance(asset)
    if asset.status == Asset.RETIRED:
        raise ValidationError("Retired assets cannot be handed off.")
    if asset.transfers.filter(status=AssetTransfer.PENDING).exists():
        raise ValidationError("This asset already has a handoff waiting for acknowledgment.")
    if asset.disposal_cases.filter(status__in=(
        AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
        AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED,
    )).exists():
        raise ValidationError("This asset has an open disposal case and cannot be transferred.")
    employee = None
    if data.get("destination_employee_id") is not None:
        from .employee_sources import resolve_employee_custodian
        employee = resolve_employee_custodian(actor=actor, user_id=data["destination_employee_id"])
        if employee["sha256"] != data.get("employee_source_checksum"):
            raise ValidationError("The selected employee record changed. Review the current identity and department.")
        if not data.get("reference", "").strip():
            raise ValidationError("Named custody needs a documented handoff reference.")
        destination = _resolve_assigned_department(employee["source"]["department_local_id"])
        custodian = employee["source"]["display_name"] or employee["source"]["username"]
    else:
        if asset.custodian_user_id or asset.last_custody_return_id:
            raise ValidationError("Select a named employee to hand off existing employee custody.")
        destination = _resolve_assigned_department(data["destination_department"])
        custodian = data["destination_custodian"].strip()
    same_identity = asset.custodian_user_id == (employee["source"]["user_local_id"] if employee else None)
    if same_identity and destination.pk == asset.assigned_department_id and custodian == asset.assigned_office.strip():
        raise ValidationError("Choose a different department or custodian.")
    transfer = AssetTransfer(
        asset=asset,
        source_custodian_user_id=asset.custodian_user_id, source_employee_snapshot=asset.custodian_snapshot,
        destination_custodian_user_id=employee["source"]["user_local_id"] if employee else None,
        destination_employee_snapshot=employee["source"] if employee else {},
        destination_employee_checksum=employee["sha256"] if employee else "",
        source_department_id=asset.assigned_department_id,
        source_department_label=asset.assigned_department_label,
        source_custodian=asset.assigned_office,
        destination_department_id=destination.pk,
        destination_department_label=destination.name,
        destination_custodian=custodian,
        transfer_date=data["transfer_date"], reason=data["reason"].strip(),
        reference=data.get("reference", "").strip(), requested_by=actor,
    )
    if request_id is not None:
        transfer.public_id = request_id
    transfer.full_clean()
    transfer.save()
    return transfer


def custody_source(asset):
    return {"department_id": asset.assigned_department_id, "custodian": asset.assigned_office,
            "employee_id": asset.custodian_user_id, "employee_source": asset.custodian_snapshot,
            "last_return_id": asset.last_custody_return_id}


@transaction.atomic
def acknowledge_asset_transfer(*, actor, transfer):
    asset = Asset.objects.select_for_update().get(pk=transfer.asset_id)
    transfer = AssetTransfer.objects.select_for_update().get(pk=transfer.pk, asset=asset)
    if not can_acknowledge_asset_transfer(actor, transfer):
        raise PermissionDenied
    if transfer.status != AssetTransfer.PENDING:
        raise ValidationError("This handoff has already been processed.")
    if (asset.assigned_department_id != transfer.source_department_id
            or asset.assigned_office != transfer.source_custodian
            or asset.custodian_user_id != transfer.source_custodian_user_id
            or asset.custodian_snapshot != transfer.source_employee_snapshot):
        raise ValidationError("The asset assignment changed after this handoff was started. Ask GSO to review it.")
    if transfer.destination_custodian_user_id:
        from .employee_sources import resolve_own_custodian
        employee = resolve_own_custodian(actor=actor)
        if employee["sha256"] != transfer.destination_employee_checksum:
            raise ValidationError("Your employee identity or department changed. Ask GSO to review this handoff.")
    asset.custodian_user_id = transfer.destination_custodian_user_id
    asset.custodian_snapshot = transfer.destination_employee_snapshot
    asset.assigned_department_id = transfer.destination_department_id
    asset.assigned_department_label = transfer.destination_department_label
    asset.assigned_office = transfer.destination_custodian
    asset.updated_by = actor
    asset.save(update_fields=(
        "assigned_department_id", "assigned_department_label", "assigned_office", "updated_by", "updated_at",
        "custodian_user", "custodian_snapshot",
    ))
    transfer.status = AssetTransfer.ACCEPTED
    transfer.acknowledged_by = actor
    transfer.acknowledged_at = timezone.now()
    transfer.save(update_fields=("status", "acknowledged_by", "acknowledged_at"))
    AssetAuditEvent.objects.create(
        asset=asset, department_id=asset.department_id, actor=actor,
        action=AssetAuditEvent.TRANSFERRED, snapshot=asset_snapshot(asset),
    )
    return transfer


@transaction.atomic
def cancel_asset_transfer(*, actor, transfer, reason):
    asset = Asset.objects.select_for_update().get(pk=transfer.asset_id)
    transfer = AssetTransfer.objects.select_for_update().get(pk=transfer.pk, asset=asset)
    if transfer.kind == AssetTransfer.RETURN:
        raise PermissionDenied("Use the witnessed return review to cancel this record.")
    if not can_transfer_asset(actor) or not asset_in_scope(actor, transfer.asset):
        raise PermissionDenied
    if transfer.destination_custodian_user_id:
        from .employee_sources import require_employee_custody_manager
        require_employee_custody_manager(actor)
    if transfer.status != AssetTransfer.PENDING:
        raise ValidationError("Only a pending handoff can be cancelled.")
    if not reason.strip() or len(reason.strip()) > 240:
        raise ValidationError("Explain cancellation in 1 to 240 characters.")
    transfer.status = AssetTransfer.CANCELLED
    transfer.cancelled_by = actor
    transfer.cancelled_at = timezone.now()
    transfer.cancellation_reason = reason.strip()
    transfer.save(update_fields=("status", "cancelled_by", "cancelled_at", "cancellation_reason"))
    return transfer


@transaction.atomic
def start_asset_verification_round(*, actor, title, as_of_date):
    if not can_manage_asset_verification(actor, "start"):
        raise PermissionDenied
    department = gso_department_for_user(actor)
    if department is None:
        raise PermissionDenied
    title = title.strip()
    if not title:
        raise ValidationError("Enter a name for this verification round.")
    if as_of_date > timezone.localdate():
        raise ValidationError("The physical count date cannot be in the future.")
    verification_round = AssetVerificationRound.objects.create(
        title=title, as_of_date=as_of_date,
        department_id=department.pk, department_label=department.name, created_by=actor,
    )
    assets = list(Asset.objects.select_for_update().filter(department_id=department.pk)
                  .exclude(status__in=(Asset.RETIRED, Asset.ENTRY_VOID)).order_by("pk"))
    from .receipt_quantity_corrections import require_asset_available
    for asset in assets:
        require_asset_available(asset)
    AssetVerificationRecord.objects.bulk_create([
        AssetVerificationRecord(
            verification_round=verification_round, asset=asset,
            asset_name_snapshot=asset.asset_name, property_tag_snapshot=asset.property_tag,
            serial_number_snapshot=asset.serial_number,
            assigned_department_snapshot=asset.assigned_department_label,
            assigned_office_snapshot=asset.assigned_office,
            account_code_snapshot=asset.coa_account_code,
            account_title_snapshot=asset.coa_account_title,
            purchase_date_snapshot=asset.purchase_date,
            acquisition_cost_snapshot=asset.unit_cost,
        )
        for asset in assets
    ])
    return verification_round


@transaction.atomic
def record_asset_verification(*, actor, record, data):
    if not can_manage_asset_verification(actor, "record"):
        raise PermissionDenied
    record = AssetVerificationRecord.objects.select_for_update().select_related("verification_round").get(pk=record.pk)
    verification_round = AssetVerificationRound.objects.select_for_update().get(pk=record.verification_round_id)
    if verification_round.closed_at:
        raise ValidationError("This verification round is closed.")
    if not actor.is_superuser:
        department = gso_department_for_user(actor)
        if not department or verification_round.department_id != department.pk:
            raise PermissionDenied
    if data.get("result") not in {AssetVerificationRecord.MATCHED, AssetVerificationRecord.DISCREPANCY, AssetVerificationRecord.NOT_FOUND}:
        raise ValidationError("Choose a physical verification result.")
    if data["result"] in (AssetVerificationRecord.DISCREPANCY, AssetVerificationRecord.NOT_FOUND) and not data.get("notes", "").strip():
        raise ValidationError("Add a brief note for a discrepancy or missing asset.")
    record.result = data["result"]
    record.observed_department = data.get("observed_department", "").strip()
    record.observed_office = data.get("observed_office", "").strip()
    record.condition = data.get("condition", "")
    record.notes = data.get("notes", "").strip()
    # A decision applies to its observed facts, never to a later physical check.
    record.follow_up_status = AssetVerificationRecord.FOLLOW_UP_OPEN
    record.resolution_note = ""
    record.resolved_by = None
    record.resolved_at = None
    record.verified_by = actor
    record.verified_at = timezone.now()
    record.save(update_fields=("result", "observed_department", "observed_office", "condition", "notes", "verified_by", "verified_at", "follow_up_status", "resolution_note", "resolved_by", "resolved_at"))
    AssetVerificationEvent.objects.create(
        record=record, actor=actor,
        snapshot={
            "asset_name": record.asset_name_snapshot,
            "property_tag": record.property_tag_snapshot,
            "serial_number": record.serial_number_snapshot,
            "recorded_department": record.assigned_department_snapshot,
            "recorded_office": record.assigned_office_snapshot,
            "account_code": record.account_code_snapshot,
            "account_title": record.account_title_snapshot,
            "purchase_date": record.purchase_date_snapshot.isoformat() if record.purchase_date_snapshot else None,
            "acquisition_cost": str(record.acquisition_cost_snapshot) if record.acquisition_cost_snapshot is not None else None,
            "result": record.result,
            "observed_department": record.observed_department,
            "observed_office": record.observed_office,
            "condition": record.condition,
            "notes": record.notes,
        },
    )
    return record


def verification_observation(record):
    return {field: getattr(record, field) for field in (
        "result", "observed_department", "observed_office", "condition", "notes")}


@transaction.atomic
def resolve_asset_verification_followup(*, actor, record, status, note, expected_event_id, expected_observation):
    if not can_manage_asset_verification(actor, "record"):
        raise PermissionDenied
    record = AssetVerificationRecord.objects.select_for_update().select_related("verification_round").get(pk=record.pk)
    if not actor.is_superuser:
        department = gso_department_for_user(actor)
        if not department or record.verification_round.department_id != department.pk:
            raise PermissionDenied
    latest_event_id = record.events.order_by("-pk").values_list("pk", flat=True).first()
    if (type(expected_event_id) is not int or latest_event_id != expected_event_id
            or expected_observation != verification_observation(record)):
        raise ValidationError("The physical check or follow-up changed. Reload and review it again.")
    if record.result not in (AssetVerificationRecord.DISCREPANCY, AssetVerificationRecord.NOT_FOUND):
        raise ValidationError("Only a discrepancy or missing asset needs a follow-up decision.")
    if status not in (AssetVerificationRecord.FOLLOW_UP_RESOLVED, AssetVerificationRecord.FOLLOW_UP_ACCEPTED):
        raise ValidationError("Choose a follow-up decision.")
    note = note.strip()
    if not note:
        raise ValidationError("Record how the follow-up was resolved or reviewed.")
    record.follow_up_status = status
    record.resolution_note = note
    record.resolved_by = actor
    record.resolved_at = timezone.now()
    record.save(update_fields=("follow_up_status", "resolution_note", "resolved_by", "resolved_at"))
    AssetVerificationEvent.objects.create(
        record=record, actor=actor,
        snapshot={
            "action": "follow_up_resolved", "result": record.result,
            "reviewed_event_id": latest_event_id,
            "follow_up_status": record.follow_up_status,
            "resolution_note": record.resolution_note,
            "resolved_at": record.resolved_at.isoformat(),
        },
    )
    return record


@transaction.atomic
def record_unregistered_verification_finding(*, actor, verification_round, data):
    if not can_manage_asset_verification(actor, "record"):
        raise PermissionDenied
    verification_round = AssetVerificationRound.objects.select_for_update().get(pk=verification_round.pk)
    if verification_round.closed_at:
        raise ValidationError("This verification round is closed.")
    if not actor.is_superuser:
        department = gso_department_for_user(actor)
        if not department or verification_round.department_id != department.pk:
            raise PermissionDenied
    finding = AssetVerificationFinding.objects.create(
        verification_round=verification_round,
        asset_name=data["asset_name"].strip(), property_tag=data.get("property_tag", "").strip(),
        serial_number=data.get("serial_number", "").strip(),
        found_department=data.get("found_department", "").strip(),
        found_office=data.get("found_office", "").strip(),
        condition=data.get("condition", ""), notes=data["notes"].strip(), recorded_by=actor,
    )
    AssetVerificationFindingEvent.objects.create(
        finding=finding, actor=actor,
        snapshot={"action": "recorded", "asset_name": finding.asset_name, "property_tag": finding.property_tag,
                  "serial_number": finding.serial_number, "found_department": finding.found_department,
                  "found_office": finding.found_office, "condition": finding.condition, "notes": finding.notes},
    )
    return finding


@transaction.atomic
def review_unregistered_verification_finding(*, actor, finding, data):
    if not can_manage_asset_verification(actor, "record"):
        raise PermissionDenied
    finding = AssetVerificationFinding.objects.select_for_update().select_related("verification_round").get(pk=finding.pk)
    if not actor.is_superuser:
        department = gso_department_for_user(actor)
        if not department or finding.verification_round.department_id != department.pk:
            raise PermissionDenied
    status = data["status"]
    if status == AssetVerificationFinding.PENDING:
        raise ValidationError("Choose a review outcome.")
    related_asset = data.get("related_asset")
    if status in (AssetVerificationFinding.REGISTERED, AssetVerificationFinding.DUPLICATE) and related_asset is None:
        raise ValidationError("Link the finding to the relevant asset record.")
    if related_asset:
        related_asset = Asset.objects.select_for_update().get(pk=related_asset.pk)
        from .receipt_quantity_corrections import require_asset_available
        require_asset_available(related_asset)
    if related_asset and related_asset.department_id != finding.verification_round.department_id:
        raise PermissionDenied
    finding.status = status
    finding.related_asset = related_asset
    finding.resolution_note = data["resolution_note"].strip()
    finding.reviewed_by = actor
    finding.reviewed_at = timezone.now()
    finding.save(update_fields=("status", "related_asset", "resolution_note", "reviewed_by", "reviewed_at"))
    AssetVerificationFindingEvent.objects.create(
        finding=finding, actor=actor,
        snapshot={"action": "reviewed", "status": finding.status,
                  "related_asset_id": finding.related_asset_id,
                  "resolution_note": finding.resolution_note},
    )
    return finding


@transaction.atomic
def import_accounting_asset_snapshot(*, actor, verification_round, upload):
    if not can_manage_asset_verification(actor, "import"):
        raise PermissionDenied
    verification_round = AssetVerificationRound.objects.select_for_update().get(pk=verification_round.pk)
    if not actor.is_superuser:
        department = gso_department_for_user(actor)
        if not department or verification_round.department_id != department.pk:
            raise PermissionDenied
    raw = upload.read()
    upload.seek(0)
    if len(raw) > 10 * 1024 * 1024:
        raise ValidationError("The CSV file must be 10 MB or smaller.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationError("Save the Accounting CSV as UTF-8 and upload it again.")
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ValidationError("The CSV file has no header row.")
    headers = {header.strip().lower(): header for header in reader.fieldnames if header}
    required = {"property_tag", "asset_name"}
    if not required.issubset(headers):
        raise ValidationError("The CSV must include the property_tag and asset_name columns. Download the template for the full column list.")
    parsed_rows = []
    seen_tags = set()
    optional_fields = ("serial_number", "department", "account_code", "account_title", "purchase_date", "acquisition_cost")
    for row_number, source_row in enumerate(reader, start=2):
        if len(parsed_rows) >= 20000:
            raise ValidationError("A single Accounting snapshot can contain up to 20,000 rows.")
        row = {name: (source_row.get(headers.get(name, ""), "") or "").strip() for name in (*required, *optional_fields)}
        if not any(row.values()):
            continue
        if not row["asset_name"]:
            raise ValidationError(f"CSV row {row_number}: asset_name is required.")
        max_lengths = {"property_tag": 100, "asset_name": 180, "serial_number": 120,
                       "department": 160, "account_code": 40, "account_title": 140}
        for field, max_length in max_lengths.items():
            if len(row[field]) > max_length:
                raise ValidationError(f"CSV row {row_number}: {field} must be {max_length} characters or fewer.")
        normalized_tag = row["property_tag"].casefold()
        if normalized_tag and normalized_tag in seen_tags:
            raise ValidationError(f"CSV row {row_number}: duplicate property_tag {row['property_tag']!r}.")
        if normalized_tag:
            seen_tags.add(normalized_tag)
        try:
            purchase_date = date.fromisoformat(row["purchase_date"]) if row["purchase_date"] else None
        except ValueError:
            raise ValidationError(f"CSV row {row_number}: purchase_date must use YYYY-MM-DD format.")
        try:
            acquisition_cost = Decimal(row["acquisition_cost"]) if row["acquisition_cost"] else None
            if acquisition_cost is not None and (
                not acquisition_cost.is_finite() or acquisition_cost < 0
                or acquisition_cost > Decimal("99999999999.99")
                or acquisition_cost.as_tuple().exponent < -2
            ):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            raise ValidationError(f"CSV row {row_number}: acquisition_cost must be a non-negative amount.")
        parsed_rows.append({
            "row_number": row_number, "property_tag": row["property_tag"],
            "asset_name": row["asset_name"], "serial_number": row["serial_number"],
            "department": row["department"], "account_code": row["account_code"],
            "account_title": row["account_title"], "purchase_date": purchase_date,
            "acquisition_cost": acquisition_cost,
        })
    if not parsed_rows:
        raise ValidationError("The Accounting CSV contains no asset rows.")
    snapshot = AssetAccountingImport.objects.create(
        verification_round=verification_round, source_filename=upload.name[:255],
        source_file=upload, source_sha256=hashlib.sha256(raw).hexdigest(), imported_by=actor,
        line_count=len(parsed_rows),
    )
    AssetAccountingLine.objects.bulk_create([
        AssetAccountingLine(accounting_import=snapshot, **row) for row in parsed_rows
    ])
    return snapshot


@transaction.atomic
def close_asset_verification_round(*, actor, verification_round):
    if not can_manage_asset_verification(actor, "close"):
        raise PermissionDenied
    verification_round = AssetVerificationRound.objects.select_for_update().get(pk=verification_round.pk)
    if not actor.is_superuser:
        department = gso_department_for_user(actor)
        if not department or verification_round.department_id != department.pk:
            raise PermissionDenied
    if verification_round.closed_at:
        raise ValidationError("This verification round is already closed.")
    if verification_round.records.filter(result=AssetVerificationRecord.NOT_CHECKED).exists():
        raise ValidationError("Record a result for every listed asset before closing this round.")
    if verification_round.findings.filter(status=AssetVerificationFinding.PENDING).exists():
        raise ValidationError("Review every unregistered asset found during the count before closing this round.")
    verification_round.closed_by = actor
    verification_round.closed_at = timezone.now()
    verification_round.save(update_fields=("closed_by", "closed_at"))
    return verification_round


def _disposal_snapshot(case, note=""):
    return {
        "asset_id": case.asset_id,
        "asset_tag": case.asset.property_tag,
        "asset_name": case.asset.asset_name,
        "status": case.status,
        "reason": case.reason,
        "condition_details": case.condition_details,
        "review_note": case.review_note,
        "authority_reference": case.authority_reference,
        "disposal_method": case.disposal_method,
        "disposal_date": case.disposal_date.isoformat() if case.disposal_date else None,
        "completion_reference": case.completion_reference,
        "note": note,
        "attachments": list(case.attachments.values_list("original_filename", flat=True)),
    }


def _record_disposal_event(case, actor, action, note=""):
    AssetDisposalEvent.objects.create(
        disposal_case=case, actor=actor, action=action,
        snapshot=_disposal_snapshot(case, note),
    )


def _save_disposal_attachments(*, case, actor, groups):
    from .disposal_evidence import prepare_uploads
    prepared = prepare_uploads(groups)
    attachments = []
    for upload, kind, digest, size, content_type in prepared:
        attachment = AssetDisposalAttachment(
            disposal_case=case, kind=kind, original_filename=upload.name[:255],
            content_type=content_type, size=size, sha256=digest, uploaded_by=actor,
        )
        attachment.file.save(upload.name, upload, save=False)
        attachment.save()
        attachments.append(attachment)
    return attachments


@transaction.atomic
def submit_asset_disposal_request(*, actor, asset, data):
    if not can_request_asset_disposal(actor, asset):
        raise PermissionDenied
    if not data.get("photos") or not data.get("signed_request"):
        raise ValidationError("Attach at least one condition photo and the signed request form.")
    asset = Asset.objects.select_for_update().get(pk=asset.pk)
    if not can_request_asset_disposal(actor, asset):
        raise PermissionDenied
    from .receipt_quantity_corrections import require_asset_available
    require_asset_available(asset)
    from .maintenance import require_no_open_maintenance
    require_no_open_maintenance(asset)
    if asset.status == Asset.RETIRED:
        raise ValidationError("This asset is already retired.")
    if asset.transfers.filter(status=AssetTransfer.PENDING).exists():
        raise ValidationError("Finish or cancel the pending handoff before requesting disposal review.")
    open_statuses = (
        AssetDisposalCase.SUBMITTED, AssetDisposalCase.UNDER_REVIEW,
        AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED,
    )
    if asset.disposal_cases.filter(status__in=open_statuses).exists():
        raise ValidationError("This asset already has an open disposal request.")
    case = AssetDisposalCase.objects.create(
        asset=asset, reason=data["reason"].strip(),
        condition_details=data["condition_details"].strip(), submitted_by=actor,
    )
    _save_disposal_attachments(case=case, actor=actor, groups=[
        (AssetDisposalAttachment.PHOTO, data["photos"]),
        (AssetDisposalAttachment.REQUEST_FORM, [data["signed_request"]]),
        (AssetDisposalAttachment.SUPPORTING, data.get("supporting_documents", [])),
    ])
    _record_disposal_event(case, actor, "submitted")
    return case


def _lock_disposal_case(case):
    # Match handoff, maintenance and property operations. A joined FOR UPDATE
    # does not establish a portable asset-before-case lock order.
    asset = Asset.objects.select_for_update().get(pk=case.asset_id)
    locked = AssetDisposalCase.objects.select_for_update().get(pk=case.pk)
    if locked.asset_id != asset.pk:
        raise ValidationError("The disposal asset changed. Reopen the case before continuing.")
    locked.asset = asset
    return locked


@transaction.atomic
def review_asset_disposal_case(*, actor, case, data):
    if not can_review_asset_disposal(actor) or not asset_in_scope(actor, case.asset):
        raise PermissionDenied
    case = _lock_disposal_case(case)
    if not can_review_asset_disposal(actor) or not asset_in_scope(actor, case.asset):
        raise PermissionDenied
    allowed = {
        AssetDisposalCase.SUBMITTED: {AssetDisposalCase.UNDER_REVIEW, AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.REJECTED},
        AssetDisposalCase.UNDER_REVIEW: {AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.AUTHORIZED, AssetDisposalCase.REJECTED},
        AssetDisposalCase.NEEDS_INFORMATION: {AssetDisposalCase.UNDER_REVIEW, AssetDisposalCase.REJECTED},
        AssetDisposalCase.AUTHORIZED: {AssetDisposalCase.DISPOSED},
    }
    action = data["action"]
    if action not in allowed.get(case.status, set()):
        raise ValidationError("This case cannot move to that status. Refresh the page and review its current status.")
    note = data.get("note", "").strip()
    if action in (AssetDisposalCase.NEEDS_INFORMATION, AssetDisposalCase.REJECTED) and not note:
        raise ValidationError("Add a note explaining the request for information or rejection.")
    authority_reference = data.get("authority_reference", "").strip()
    authority_document = data.get("authority_document")
    disposal_method = data.get("disposal_method")
    disposal_date = data.get("disposal_date")
    completion_reference = data.get("completion_reference", "").strip()
    completion_document = data.get("completion_document")
    if action == AssetDisposalCase.AUTHORIZED:
        if not authority_reference:
            raise ValidationError("Record the approval or authority reference before authorizing disposal.")
        if not authority_document and not case.attachments.filter(kind="authority").exists():
            raise ValidationError("Attach the approval or authority document before authorizing disposal.")
    if action == AssetDisposalCase.DISPOSED:
        if not disposal_method or not disposal_date or not completion_reference:
            raise ValidationError("Record the disposal method, completion date, and completion reference.")
        if not completion_document and not case.attachments.filter(kind="completion").exists():
            raise ValidationError("Attach evidence that the disposal was completed.")
        if case.asset.status == Asset.RETIRED:
            raise ValidationError("This asset is already retired; ask an administrator to review the record.")
    if action in (AssetDisposalCase.AUTHORIZED, AssetDisposalCase.DISPOSED):
        from .disposal_evidence import verify_case_evidence
        verify_case_evidence(case, allow_legacy=True)
    _save_disposal_attachments(case=case, actor=actor, groups=[
        (AssetDisposalAttachment.SUPPORTING, data.get("supporting_documents", [])),
        ("authority", [authority_document] if authority_document else []),
        ("completion", [completion_document] if completion_document else []),
    ])
    case.status = action
    case.review_note = note
    case.reviewed_by = actor
    case.reviewed_at = timezone.now()
    fields = ["status", "review_note", "reviewed_by", "reviewed_at"]
    if action == AssetDisposalCase.AUTHORIZED:
        case.authority_reference = authority_reference
        fields.append("authority_reference")
    if action == AssetDisposalCase.DISPOSED:
        case.disposal_method = disposal_method
        case.disposal_date = disposal_date
        case.completion_reference = completion_reference
        case.completed_by = actor
        case.completed_at = timezone.now()
        fields.extend(("disposal_method", "disposal_date", "completion_reference", "completed_by", "completed_at"))
    case.save(update_fields=fields)
    _record_disposal_event(case, actor, action, note)
    if action == AssetDisposalCase.DISPOSED:
        asset = case.asset
        asset.status = Asset.RETIRED
        asset.updated_by = actor
        asset.save(update_fields=("status", "updated_by", "updated_at"))
        AssetAuditEvent.objects.create(
            asset=asset, department_id=asset.department_id, actor=actor,
            action=AssetAuditEvent.DISPOSED, snapshot=asset_snapshot(asset),
        )
    return case


@transaction.atomic
def respond_to_disposal_case(*, actor, case, data):
    if case.submitted_by_id != actor.pk or not can_request_asset_disposal(actor, case.asset):
        raise PermissionDenied
    case = _lock_disposal_case(case)
    if case.submitted_by_id != actor.pk or not can_request_asset_disposal(actor, case.asset):
        raise PermissionDenied
    if case.status != AssetDisposalCase.NEEDS_INFORMATION:
        raise ValidationError("This case is not waiting for more information.")
    note = data["response"].strip()
    if not note:
        raise ValidationError("Add a short response for GSO.")
    uploads = data.get("supporting_documents", [])
    _save_disposal_attachments(case=case, actor=actor, groups=[(AssetDisposalAttachment.SUPPORTING, uploads)])
    case.status = AssetDisposalCase.SUBMITTED
    case.review_note = note
    case.submitted_at = timezone.now()
    case.save(update_fields=("status", "review_note", "submitted_at"))
    _record_disposal_event(case, actor, "resubmitted", note)
    return case


def _stock_permission(actor, action, item=None):
    from .access import can_stock

    if not can_stock(actor, action):
        raise PermissionDenied
    if item is not None and not actor.is_superuser:
        department = gso_department_for_user(actor)
        if department is None or item.department_id != department.pk:
            raise PermissionDenied


@transaction.atomic
def create_consumable(*, actor, data):
    _stock_permission(actor, "add")
    data = _editable_data(data, CONSUMABLE_INPUT_FIELDS)
    department = gso_department_for_user(actor)
    if department is None:
        raise PermissionDenied
    item = ConsumableItem(
        **data, department_id=department.pk, department_label=department.name, created_by=actor,
    )
    item.full_clean()
    item.save()
    ConsumableAuditEvent.objects.create(
        item=item, actor=actor, action=ConsumableAuditEvent.CREATED, snapshot=consumable_snapshot(item),
    )
    return item


def consumable_snapshot(item):
    return {
        "name": item.name, "category": item.category, "unit": item.unit,
        "use_fifo": item.use_fifo, "minimum_stock": str(item.minimum_stock),
        "is_active": item.is_active, "notes": item.notes,
        "department_id": item.department_id, "department_label": item.department_label,
    }


@transaction.atomic
def update_consumable(*, actor, item, data):
    _stock_permission(actor, "change")
    data = _editable_data(data, CONSUMABLE_INPUT_FIELDS)
    item = ConsumableItem.objects.select_for_update().get(pk=item.pk)
    _stock_permission(actor, "change", item)
    from .receipt_quantity_corrections import require_stock_available
    require_stock_available(item)
    if item.use_fifo != data.get("use_fifo", item.use_fifo) and item.movements.exists():
        raise ValidationError("FIFO tracking cannot be changed after stock movements exist.")
    for field, value in data.items():
        setattr(item, field, value)
    item.updated_by = actor
    item.full_clean()
    item.save()
    ConsumableAuditEvent.objects.create(
        item=item, actor=actor, action=ConsumableAuditEvent.UPDATED, snapshot=consumable_snapshot(item),
    )
    return item


def _stock_signed_total(item):
    return item.movements.aggregate(total=Sum("signed_quantity"))["total"] or Decimal("0")


def _create_stock_lot(item, movement):
    return StockLot.objects.create(
        item=item, receipt=movement, received_at=movement.occurred_at,
        quantity=movement.quantity, unit_cost=movement.unit_cost,
    )


def _allocate_fifo(item, issue, quantity):
    remaining = quantity
    for lot in item.lots.select_for_update().order_by("received_at", "pk"):
        allocated = lot.allocations.aggregate(total=Sum("quantity"))["total"] or Decimal("0")
        available = lot.quantity - allocated
        if available <= 0:
            continue
        take = min(available, remaining)
        StockLotAllocation.objects.create(issue=issue, lot=lot, quantity=take)
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        raise ValidationError("FIFO lot balances do not cover the requested quantity. Review stock history first.")


@transaction.atomic
def record_stock_movement(*, actor, item, kind, quantity, reference="", reason="", unit_cost=None,
                          department_id=None, department_label="", recipient="", request_id=None):
    permission = {
        StockMovement.RECEIPT: "receive",
        StockMovement.ISSUE: "issue",
        StockMovement.ADJUSTMENT_IN: "adjust",
        StockMovement.ADJUSTMENT_OUT: "adjust",
        StockMovement.RETURN: "receive",
    }.get(kind)
    if permission is None:
        raise ValidationError("Unknown stock movement type.")
    _stock_permission(actor, permission)
    item = ConsumableItem.objects.select_for_update().get(pk=item.pk)
    _stock_permission(actor, permission, item)
    # Validate before balance comparisons or persistence: databases may otherwise
    # round excess precision differently from the in-memory FIFO allocation.
    quantity = StockMovement._meta.get_field("quantity").clean(quantity, None)
    if quantity <= 0:
        raise ValidationError("Enter a quantity greater than zero.")
    unit_cost = StockMovement._meta.get_field("unit_cost").clean(unit_cost, None)
    if unit_cost is not None and unit_cost < 0:
        raise ValidationError("Unit cost cannot be negative.")
    if kind in (StockMovement.ADJUSTMENT_IN, StockMovement.ADJUSTMENT_OUT) and not reason.strip():
        raise ValidationError("Record the reason for the stock adjustment.")
    if kind == StockMovement.ISSUE:
        destination = _resolve_assigned_department(department_id)
        if destination is None or not recipient.strip():
            raise ValidationError("Select the receiving department and record who received the supplies.")
        department_id, department_label = destination.pk, destination.name
    if request_id is not None:
        try:
            request_id = UUID(str(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError("Invalid stock movement request identity.")
        existing = StockMovement.objects.filter(public_id=request_id).first()
        if existing:
            expected = {"item_id": item.pk, "actor_id": actor.pk, "kind": kind, "quantity": quantity,
                "unit_cost": unit_cost, "department_id": department_id, "recipient": recipient,
                "reference": reference, "reason": reason}
            if any(getattr(existing, name) != value for name, value in expected.items()):
                raise ValidationError("This request identity belongs to different recorded movement content.")
            return existing
    if not item.is_active:
        raise ValidationError("Inactive supply items cannot receive new movements.")
    from .receipt_quantity_corrections import require_stock_available
    require_stock_available(item)
    inbound = kind in (StockMovement.RECEIPT, StockMovement.RETURN, StockMovement.ADJUSTMENT_IN)
    if not inbound and _stock_signed_total(item) < quantity:
        raise ValidationError(f"Only {_stock_signed_total(item):g} {item.unit} are available.")
    signed = quantity if inbound else -quantity
    movement = StockMovement(
        item=item, kind=kind, quantity=quantity, signed_quantity=signed,
        department_id=department_id, department_label=department_label,
        recipient=recipient, reference=reference, reason=reason, unit_cost=unit_cost, actor=actor,
    )
    if request_id is not None:
        movement.public_id = request_id
    movement.full_clean(validate_unique=False)
    try:
        with transaction.atomic():
            movement.save()
    except IntegrityError:
        # The item lock serializes ordinary retries. A UUID collision across
        # different items must fail cleanly without allocating any stock.
        if request_id is not None and StockMovement.objects.filter(public_id=request_id).exists():
            raise ValidationError("This request identity already belongs to another stock movement.")
        raise
    if item.use_fifo:
        if inbound:
            _create_stock_lot(item, movement)
        else:
            _allocate_fifo(item, movement, quantity)
    return movement
