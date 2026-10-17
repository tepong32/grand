"""Receiving writes stay in the operational database and never post to Finance."""
import hashlib
from pathlib import Path

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .access import in_gso_scope, gso_department_for_user, department_model
from .models import ReceivingReceipt, ReceivingLine, ReceivingEvent, ReceivingEvidence, Asset


HEADER_FIELDS = {"supplier", "delivery_reference", "delivery_date", "purchase_order_reference",
                 "inspection_reference", "inspection_date", "inspector_label", "evidence_reference"}
LINE_FIELDS = {"kind", "description", "unit", "delivered_quantity", "accepted_quantity",
               "rejected_quantity", "rejection_reason", "unit_cost", "supply_item", "asset_kind",
               "property_tag", "serial_number", "chassis_number"}
PREPARATION_ACTIONS = ("created", "header_saved", "line_saved", "line_voided", "submitted", "evidence_added")


def can_receiving(actor, action, receipt=None):
    if action not in ("view", "add", "change", "submit", "review") or not in_gso_scope(actor):
        return False
    permission = f"inventory.{action}_receivingreceipt"
    if apps.is_installed("vouchers"):
        from vouchers.access import has_explicit_permission
        from vouchers.roles import is_finance_uat_viewer
        if action != "view" and is_finance_uat_viewer(actor):
            return False
        granted = has_explicit_permission(actor, permission)
    else:
        granted = actor.has_perm(permission)
    department = gso_department_for_user(actor)
    return bool(granted and department and
        (receipt is None or actor.is_superuser or receipt.department_id == department.pk))


def require_receiving(actor, action, receipt=None):
    if not can_receiving(actor, action, receipt):
        raise PermissionDenied
    return gso_department_for_user(actor)


def _data(data, fields):
    if set(data) - fields:
        raise ValidationError("This workflow cannot change the supplied fields.")
    return dict(data)


def _event(receipt, actor, action, note="", followup_request=None):
    def value(v):
        return v.isoformat() if hasattr(v, "isoformat") else str(v) if v is not None else None
    header = {field: value(getattr(receipt, field)) for field in HEADER_FIELDS}
    lines = list(receipt.lines.values())
    snapshot = {
        "public_id": str(receipt.public_id), "version": receipt.state_version,
        "status": receipt.status, "header": header, "note": note,
        "review_note": receipt.review_note, "reviewed_by_id": receipt.reviewed_by_id,
        "evidence": list(receipt.evidence.values("id", "kind", "sha256", "size", "note", "original_filename")),
        "lines": [{key: value(val) for key, val in line.items()} for line in lines],
    }
    if receipt.followup_source_id:
        snapshot["followup"] = {"source_line_id": receipt.followup_source_id,
                                "basis": receipt.followup_basis}
    if followup_request is not None:
        snapshot["followup_request"] = followup_request
    ReceivingEvent.objects.create(receipt=receipt, actor=actor, action=action, snapshot=snapshot)


def _locked(receipt, actor, action, expected_version):
    from .receiving_followups import lock_receipt
    receipt = lock_receipt(receipt.pk)
    require_receiving(actor, action, receipt)
    if receipt.state_version != expected_version:
        raise ValidationError("This receipt changed. Reload it before continuing.")
    return receipt


def _require_editable(receipt):
    if receipt.status not in (receipt.DRAFT, receipt.RETURNED):
        raise ValidationError("Only draft or returned receipts can be edited.")


@transaction.atomic
def update_receipt(*, actor, receipt, data, expected_version):
    receipt = _locked(receipt, actor, "change", expected_version)
    _require_editable(receipt)
    data = _data(data, HEADER_FIELDS)
    if receipt.followup_source_id:
        original = receipt.followup_source.receipt
        for key in ("supplier", "delivery_reference", "delivery_date", "purchase_order_reference"):
            if key in data and data[key] != getattr(original, key):
                raise ValidationError("A follow-up retains the original delivery facts.")
    for key, value in data.items():
        setattr(receipt, key, value)
    receipt.full_clean()
    if receipt.followup_source_id and receipt.inspection_date < original.inspection_date:
        raise ValidationError("Follow-up inspection cannot precede the original inspection.")
    receipt.state_version += 1
    receipt.save()
    _event(receipt, actor, "header_saved")
    return receipt


@transaction.atomic
def void_receipt_line(*, actor, receipt, line_id, reason, expected_version):
    receipt = _locked(receipt, actor, "change", expected_version)
    _require_editable(receipt)
    if receipt.followup_source_id:
        raise ValidationError("Correct the follow-up line instead of voiding its source link.")
    if not reason.strip():
        raise ValidationError("Explain why this line is being removed from the receipt.")
    try:
        line = receipt.lines.get(pk=line_id, is_void=False)
    except ReceivingLine.DoesNotExist:
        raise ValidationError("The selected line is unavailable.")
    line.is_void = True
    line.save(update_fields=("is_void",))
    receipt.state_version += 1
    receipt.save(update_fields=("state_version",))
    _event(receipt, actor, "line_voided", note=reason.strip())
    return receipt


def _independent_reviewer(receipt, actor):
    if receipt.events.filter(actor=actor, action__in=PREPARATION_ACTIONS).exists():
        raise PermissionDenied("A different officer must review a receipt you prepared or submitted.")


@transaction.atomic
def return_receipt(*, actor, receipt, expected_version, reason):
    receipt = _locked(receipt, actor, "review", expected_version)
    _independent_reviewer(receipt, actor)
    if receipt.status != receipt.SUBMITTED:
        raise ValidationError("Only submitted receipts can be returned.")
    if not reason.strip():
        raise ValidationError("Record the correction needed.")
    receipt.status = receipt.RETURNED
    receipt.review_note = reason.strip()
    receipt.reviewed_by = actor
    receipt.reviewed_at = timezone.now()
    receipt.state_version += 1
    receipt.save()
    _event(receipt, actor, "returned")
    return receipt


@transaction.atomic
def create_receipt(*, actor, data):
    department = require_receiving(actor, "add")
    receipt = ReceivingReceipt(**_data(data, HEADER_FIELDS), department_id=department.pk,
                               department_label=department.name, created_by=actor)
    receipt.full_clean()
    receipt.save()
    _event(receipt, actor, "created")
    return receipt


@transaction.atomic
def save_receipt_line(*, actor, receipt, data, expected_version, line_id=None):
    receipt = _locked(receipt, actor, "change", expected_version)
    if receipt.status not in (receipt.DRAFT, receipt.RETURNED):
        raise ValidationError("Only draft or returned receipts can be edited.")
    if line_id is None:
        if receipt.followup_source_id:
            raise ValidationError("Edit the existing follow-up line; a follow-up cannot add another item.")
        if receipt.lines.count() >= 50:
            raise ValidationError("A receipt supports at most 50 lines.")
        last = receipt.lines.order_by("-sequence").first()
        line = ReceivingLine(receipt=receipt, sequence=last.sequence + 1 if last else 1)
    else:
        try:
            line = receipt.lines.get(pk=line_id, is_void=False)
        except ReceivingLine.DoesNotExist:
            raise ValidationError("The selected line is unavailable.")
    for key, val in _data(data, LINE_FIELDS).items():
        setattr(line, key, val)
    line.full_clean()
    if receipt.followup_source_id:
        from .receiving_followups import validate_followup
        validate_followup(receipt, [line])
    line.save()
    receipt.state_version += 1
    receipt.save(update_fields=("state_version",))
    _event(receipt, actor, "line_saved")
    return line


@transaction.atomic
def submit_receipt(*, actor, receipt, expected_version):
    receipt = _locked(receipt, actor, "submit", expected_version)
    if receipt.status not in (receipt.DRAFT, receipt.RETURNED):
        raise ValidationError("Only a draft or returned receipt can be submitted.")
    receipt.full_clean()
    lines = list(receipt.lines.filter(is_void=False))
    if not lines:
        raise ValidationError("Record at least one delivery line.")
    for line in lines:
        line.full_clean()
    from .receiving_followups import validate_followup
    validate_followup(receipt, lines)
    verify_receipt_evidence(receipt)
    receipt.status = receipt.SUBMITTED
    receipt.state_version += 1
    receipt.save(update_fields=("status", "state_version"))
    _event(receipt, actor, "submitted")
    return receipt


def verify_receipt_evidence(receipt):
    evidence = list(receipt.evidence.all())
    if not {"delivery", "inspection"}.issubset({row.kind for row in evidence}):
        raise ValidationError("Retain both delivery and inspection documents before submission.")
    for row in evidence:
        try:
            digest = hashlib.sha256()
            size = 0
            with row.file.open("rb") as source:
                for block in source.chunks():
                    digest.update(block)
                    size += len(block)
            if digest.hexdigest() != row.sha256 or size != row.size:
                raise ValidationError("Retained evidence failed its integrity check. Ask the administrator to investigate.")
        except OSError as error:
            raise ValidationError("Retained evidence is unavailable. Restore or investigate it before proceeding.") from error


@transaction.atomic
def attach_receipt_evidence(*, actor, receipt, expected_version, kind, upload, note):
    from .forms import _validate_disposal_upload
    receipt = _locked(receipt, actor, "change", expected_version)
    _require_editable(receipt)
    if kind not in dict(ReceivingEvidence.KIND_CHOICES) or not note.strip():
        raise ValidationError("Choose a document type and explain what the document establishes or corrects.")
    if receipt.evidence.count() >= 20:
        raise ValidationError("A receipt supports at most 20 retained documents.")
    _validate_disposal_upload(upload)
    digest = hashlib.sha256()
    size = 0
    for block in upload.chunks():
        size += len(block)
        if size > 15 * 1024 * 1024:
            raise ValidationError("Each file must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    total = receipt.evidence.aggregate(total=Sum("size"))["total"] or 0
    if total + size > 100 * 1024 * 1024:
        raise ValidationError("The receipt's retained documents cannot exceed 100 MB.")
    evidence = ReceivingEvidence(receipt=receipt, kind=kind, file=upload,
        original_filename=Path(upload.name).name, sha256=digest.hexdigest(), size=size,
        note=note.strip(), uploaded_by=actor)
    evidence.full_clean()
    evidence.save()
    receipt.state_version += 1
    receipt.save(update_fields=("state_version",))
    _event(receipt, actor, "evidence_added")
    return evidence


@transaction.atomic
def accept_receipt(*, actor, receipt, expected_version, note):
    from .services import create_asset, record_stock_movement
    receipt = _locked(receipt, actor, "review", expected_version)
    _independent_reviewer(receipt, actor)
    if receipt.status != receipt.SUBMITTED:
        raise ValidationError("Only a submitted receipt can be accepted; this receipt may already be processed.")
    if not note.strip():
        raise ValidationError("Record the basis of your inspection-document and quantity review.")
    # Preserve the receipt's physical owner even when a central administrator reviews.
    if gso_department_for_user(actor).pk != receipt.department_id:
        raise PermissionDenied("Review this receipt through its owning GSO office.")
    department_model().objects.select_for_update().get(pk=receipt.department_id)
    verify_receipt_evidence(receipt)
    lines = list(receipt.lines.filter(is_void=False).order_by("sequence"))
    if not lines:
        raise ValidationError("An empty receipt cannot be accepted.")
    from .receiving_followups import validate_followup
    validate_followup(receipt, lines)
    for line in lines:
        line.full_clean()
        if line.registered_asset_id or line.stock_movement_id:
            raise ValidationError("A receipt line has already been registered. Investigate its retained history.")
        if not line.accepted_quantity:
            continue
        if line.kind == ReceivingLine.ASSET:
            line.registered_asset = create_asset(actor=actor, data={
                "asset_name": line.description, "asset_kind": line.asset_kind,
                "inventory_class": Asset.CLASS_TRANSPORT if line.asset_kind == Asset.VEHICLE else Asset.CLASS_PENDING,
                "item_type": "motor_vehicle" if line.asset_kind == Asset.VEHICLE else "other",
                "property_tag": line.property_tag, "serial_number": line.serial_number,
                "chassis_number": line.chassis_number, "quantity": 1, "unit_cost": line.unit_cost,
                "supplier": receipt.supplier, "purchase_order_reference": receipt.purchase_order_reference,
            })
        else:
            line.stock_movement = record_stock_movement(actor=actor, item=line.supply_item,
                kind="receipt", quantity=line.accepted_quantity, unit_cost=line.unit_cost,
                reference=f"Receiving {receipt.public_id} line {line.sequence}")
        line.save(update_fields=("registered_asset", "stock_movement"))
    receipt.status = receipt.ACCEPTED
    receipt.review_note = note.strip()
    receipt.reviewed_by = actor
    receipt.reviewed_at = timezone.now()
    receipt.state_version += 1
    receipt.save()
    _event(receipt, actor, "accepted")
    return receipt
