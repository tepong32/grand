"""Append-only documentary corrections; no asset, stock or Finance valuation writes."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .access import has_inventory_permission, gso_department_for_user
from .models import ReceivingReceipt, ReceivingLine, ReceiptCostAmendment, ReceiptCostAmendmentEvent
from .receiving import can_receiving, HEADER_FIELDS, verify_receipt_evidence


def can_amend(actor, action, receipt):
    return bool(action in ("record", "review") and can_receiving(actor, "view", receipt)
        and gso_department_for_user(actor).pk == receipt.department_id
        and has_inventory_permission(actor, f"{action}_receiptcostamendment", mutation=True))


def _value(value):
    if isinstance(value, Decimal):
        return format(value, ".2f")
    return value.isoformat() if hasattr(value, "isoformat") else value


def amendment_content(row):
    return {"uuid": str(row.public_id), "line_local_id": row.line_id,
        "predecessor_local_id": row.predecessor_id, "basis": row.basis,
        "unit_cost": _value(row.unit_cost), "reference": row.reference, "reason": row.reason,
        "sha256": row.sha256, "size": row.size, "original_filename": row.original_filename,
        "recorded_by_local_id": row.recorded_by_id}


def _checksum(content):
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def latest_amendment(line):
    row = line.cost_amendments.filter(status=ReceiptCostAmendment.APPROVED).first()
    if row and _checksum(amendment_content(row)) != row.content_checksum:
        raise ValidationError("The retained cost amendment content changed. Investigate before further processing.")
    return row


def effective_cost(line):
    row = latest_amendment(line)
    return row.unit_cost if row else line.unit_cost


def amendment_basis(line):
    receipt = line.receipt
    row = latest_amendment(line)
    basis = {"receipt_uuid": str(receipt.public_id), "receipt_version": receipt.state_version,
        "owner_local_id": receipt.department_id, "status": receipt.status,
        "header": {key: _value(getattr(receipt, key)) for key in sorted(HEADER_FIELDS)},
        "line_local_id": line.pk, "sequence": line.sequence,
        "description": line.description, "unit": line.unit, "is_void": line.is_void,
        "accepted_quantity": str(line.accepted_quantity), "original_unit_cost": _value(line.unit_cost),
        "effective_unit_cost": _value(row.unit_cost if row else line.unit_cost),
        "predecessor_uuid": str(row.public_id) if row else None,
        "predecessor_checksum": row.content_checksum if row else None}
    if receipt.followup_source_id:
        from .receiving_followups import retained_source
        basis["followup"] = retained_source(receipt)
    from .receipt_quantity_corrections import correction_extension
    correction = correction_extension(line)
    if correction:
        basis["quantity_correction"] = correction
    return basis


def verify_amendment_evidence(row):
    if _checksum(amendment_content(row)) != row.content_checksum:
        raise ValidationError("The retained amendment content changed. Investigate it before review.")
    root = Path(row.file.storage.location).resolve()
    path = root / row.file.name
    try:
        path.resolve().relative_to(root / "inventory" / "receipt-amendments")
        if ".." in Path(row.file.name).parts or path.resolve() != path:
            raise ValueError
        digest, size = hashlib.sha256(), 0
        with row.file.open("rb") as source:
            for block in iter(lambda: source.read(1024*1024), b""):
                digest.update(block)
                size += len(block)
        if digest.hexdigest() != row.sha256 or size != row.size:
            raise ValueError
    except (OSError, ValueError):
        raise ValidationError("The retained amendment document is unavailable or changed. Investigate before approval.")


def _event(row, actor, action):
    ReceiptCostAmendmentEvent.objects.create(amendment=row, actor=actor, action=action, snapshot={
        "content": amendment_content(row), "content_checksum": row.content_checksum,
        "status": row.status, "state_version": row.state_version,
        "reviewed_by_local_id": row.reviewed_by_id, "reviewed_at": _value(row.reviewed_at),
        "review_note": row.review_note})


def _locked_line(line, actor, action):
    receipt = ReceivingReceipt.objects.select_for_update().get(pk=line.receipt_id)
    if not can_amend(actor, action, receipt):
        raise PermissionDenied
    line = ReceivingLine.objects.select_related("receipt").get(pk=line.pk, receipt=receipt)
    if receipt.status != receipt.ACCEPTED or line.is_void or line.accepted_quantity <= 0:
        raise ValidationError("Only accepted, non-void quantities can have a documentary cost amendment.")
    from .receipt_quantity_corrections import require_no_pending, effective_quantities
    require_no_pending(line)
    if effective_quantities(line)["accepted"] <= 0:
        raise ValidationError("A fully corrected erroneous entry cannot receive new cost amendments.")
    return line


@transaction.atomic
def record_amendment(*, actor, line, request_id, expected_basis, unit_cost, reference, reason, upload):
    from .forms import _validate_disposal_upload
    line = _locked_line(line, actor, "record")
    try:
        request_id = UUID(str(request_id))
        if isinstance(unit_cost, (bool, float)):
            raise ValueError
        unit_cost = None if unit_cost is None else Decimal(unit_cost)
        if unit_cost is not None and (not unit_cost.is_finite() or unit_cost < 0 or unit_cost >= Decimal("100000000000")
            or unit_cost != unit_cost.quantize(Decimal("0.01"))):
            raise ValueError
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError("Use a valid request identity and an exact nonnegative cost with at most two decimals, or unknown.")
    reference, reason = str(reference or "").strip(), str(reason or "").strip()
    if not reference or len(reference) > 180 or not reason or len(reason) > 4000:
        raise ValidationError("Record the source reference and reason within their field limits.")
    _validate_disposal_upload(upload)
    digest, size = hashlib.sha256(), 0
    for block in upload.chunks():
        size += len(block)
        if size > 15*1024*1024:
            raise ValidationError("The source file must be 15 MB or smaller.")
        digest.update(block)
    upload.seek(0)
    previous = ReceiptCostAmendment.objects.filter(public_id=request_id).first()
    if previous:
        if (previous.line_id, previous.recorded_by_id, previous.basis, previous.unit_cost,
            previous.reference, previous.reason, previous.sha256, previous.size, previous.original_filename) != (
            line.pk, actor.pk, expected_basis, unit_cost, reference, reason, digest.hexdigest(), size, Path(upload.name).name):
            raise ValidationError("This request identity already belongs to different content.")
        return previous
    if expected_basis != amendment_basis(line):
        raise ValidationError("The receipt or effective cost changed. Reload before recording an amendment.")
    if unit_cost == effective_cost(line):
        raise ValidationError("The proposed cost is unchanged. No cost amendment is needed.")
    if line.cost_amendments.filter(status=ReceiptCostAmendment.PENDING).exists():
        raise ValidationError("Review the pending amendment before recording another for this line.")
    verify_receipt_evidence(line.receipt)
    predecessor = latest_amendment(line)
    if predecessor:
        verify_amendment_evidence(predecessor)
    row = ReceiptCostAmendment(public_id=request_id, line=line, predecessor=predecessor,
        basis=expected_basis, unit_cost=unit_cost, reference=reference, reason=reason,
        file=upload, original_filename=Path(upload.name).name, sha256=digest.hexdigest(), size=size,
        recorded_by=actor)
    row.content_checksum = _checksum(amendment_content(row))
    row.full_clean()
    row.save()
    _event(row, actor, "recorded")
    return row


@transaction.atomic
def decide_amendment(*, actor, amendment, expected_version, action, note):
    line = _locked_line(amendment.line, actor, "review")
    row = ReceiptCostAmendment.objects.select_for_update().get(pk=amendment.pk, line=line)
    if row.recorded_by_id == actor.pk:
        raise PermissionDenied("A different officer must review the documentary correction.")
    if row.status != row.PENDING or isinstance(expected_version, bool) or expected_version != row.state_version:
        raise ValidationError("This amendment was already decided or changed. Reload its history.")
    note = str(note or "").strip()
    if action not in ("approve", "reject") or not note or len(note) > 4000:
        raise ValidationError("Select approve or reject and record a decision reason.")
    if action == "approve":
        if row.basis != amendment_basis(line):
            raise ValidationError("The receipt or predecessor basis changed. Reject and record a new amendment.")
        verify_receipt_evidence(line.receipt)
        verify_amendment_evidence(row)
        if row.predecessor:
            verify_amendment_evidence(row.predecessor)
        row.status = row.APPROVED
        receipt = line.receipt
        receipt.state_version += 1
        receipt.save(update_fields=("state_version",))
    else:
        row.status = row.REJECTED
    row.reviewed_by, row.reviewed_at, row.review_note = actor, timezone.now(), note
    row.state_version += 1
    row.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "state_version"))
    _event(row, actor, row.status)
    return row
