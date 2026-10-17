"""Resolve a delivered remainder without rewriting an earlier acceptance."""
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum

from .models import ReceivingReceipt, ReceivingLine


def plain(raw):
    if isinstance(raw, dict):
        return {key: plain(value) for key, value in raw.items()}
    if isinstance(raw, (tuple, list)):
        return [plain(value) for value in raw]
    if isinstance(raw, Decimal):
        return format(raw.normalize(), "f")
    if hasattr(raw, "isoformat"):
        return raw.isoformat()
    return raw


def source_basis(line):
    """Original physical facts; later documentary cost amendments are separate."""
    from .receiving import HEADER_FIELDS, LINE_FIELDS
    receipt = line.receipt
    basis = plain({"receipt_uuid": str(receipt.public_id), "sequence": line.sequence,
        "owner": receipt.department_id, "status": receipt.status, "is_void": line.is_void,
        "header": {key: getattr(receipt, key) for key in sorted(HEADER_FIELDS)},
        "line": {key: getattr(line, key) for key in sorted(LINE_FIELDS - {"supply_item"})},
        "supply_item_id": line.supply_item_id, "registered_asset_id": line.registered_asset_id,
        "stock_movement_id": line.stock_movement_id,
        "reviewed_by": receipt.reviewed_by_id, "reviewed_at": receipt.reviewed_at,
        "evidence": list(receipt.evidence.order_by("pk").values(
            "kind", "sha256", "size", "original_filename", "note"))})
    from .receipt_quantity_corrections import correction_extension
    correction = correction_extension(line)
    if correction:
        basis["quantity_correction"] = correction
    return basis


def remaining_quantity(line):
    resolved = ReceivingLine.objects.filter(receipt__followup_source=line,
        receipt__status=ReceivingReceipt.ACCEPTED, is_void=False).aggregate(
            accepted=Sum("accepted_quantity"), rejected=Sum("rejected_quantity"))
    return (line.delivered_quantity - line.accepted_quantity - line.rejected_quantity
        - (resolved["accepted"] or 0) - (resolved["rejected"] or 0))


def retained_source(receipt):
    """Check source lineage for downstream consumers without changing old snapshots."""
    if not receipt.followup_source_id:
        return None
    from .receiving import verify_receipt_evidence
    source = ReceivingLine.objects.select_related("receipt").get(pk=receipt.followup_source_id)
    if (source.receipt.followup_source_id or source.receipt.status != "accepted" or source.is_void
            or source.receipt.department_id != receipt.department_id
            or source_basis(source) != receipt.followup_basis):
        raise ValidationError("The retained original delivery basis changed or is unavailable.")
    verify_receipt_evidence(source.receipt)
    return {"source_receipt_uuid": str(source.receipt.public_id),
            "source_sequence": source.sequence, "basis": receipt.followup_basis}


def lock_receipt(receipt_id):
    """Root receipt precedes its follow-up; no recursive follow-ups are allowed."""
    source_id = ReceivingReceipt.objects.values_list("followup_source_id", flat=True).get(pk=receipt_id)
    if source_id:
        root_id = ReceivingLine.objects.values_list("receipt_id", flat=True).get(pk=source_id)
        root = ReceivingReceipt.objects.select_for_update().get(pk=root_id)
        if root.followup_source_id:
            raise ValidationError("Follow-ups must refer directly to an original delivery line.")
    receipt = ReceivingReceipt.objects.select_for_update().get(pk=receipt_id)
    if receipt.followup_source_id != source_id:
        raise ValidationError("The receipt source changed. Reload before continuing.")
    if source_id and ReceivingLine.objects.get(pk=source_id).receipt_id != root_id:
        raise ValidationError("The original line changed. Investigate its history.")
    return receipt


def validate_followup(receipt, lines):
    if not receipt.followup_source_id:
        if receipt.followup_basis:
            raise ValidationError("An ordinary delivery cannot carry follow-up evidence.")
        return
    source = ReceivingLine.objects.select_related("receipt").get(pk=receipt.followup_source_id)
    original = source.receipt
    from .receipt_quantity_corrections import require_no_pending
    require_no_pending(source)
    retained_source(receipt)
    for name in ("supplier", "delivery_reference", "delivery_date", "purchase_order_reference"):
        if getattr(receipt, name) != getattr(original, name):
            raise ValidationError("A follow-up retains the original delivery facts.")
    if receipt.inspection_date < original.inspection_date:
        raise ValidationError("Follow-up inspection cannot precede the original inspection.")
    if len(lines) != 1:
        raise ValidationError("A follow-up resolves exactly one original delivery line.")
    line = lines[0]
    for name in ("kind", "description", "unit", "supply_item_id", "asset_kind"):
        if getattr(line, name) != getattr(source, name):
            raise ValidationError("A follow-up must retain the original item and unit.")
    for name in ("property_tag", "serial_number", "chassis_number"):
        if getattr(source, name) and getattr(line, name) != getattr(source, name):
            raise ValidationError("Retain the original recorded asset identity.")
    quantity = line.accepted_quantity + line.rejected_quantity
    if quantity <= 0 or line.delivered_quantity != quantity or quantity > remaining_quantity(source):
        raise ValidationError("Resolve a positive quantity no greater than the original unresolved remainder.")


@transaction.atomic
def create_followup(*, actor, source_line_id, request_id, expected_basis, inspection, quantities):
    from .receiving import require_receiving, HEADER_FIELDS, _event
    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Use a valid follow-up request identity.")
    if set(inspection) != {"inspection_reference", "inspection_date", "inspector_label", "evidence_reference"}:
        raise ValidationError("Supply the follow-up inspection facts.")
    if set(quantities) - {"accepted_quantity", "rejected_quantity", "rejection_reason", "unit_cost",
                          "property_tag", "serial_number", "chassis_number"}:
        raise ValidationError("A follow-up cannot replace its original item.")
    source = ReceivingLine.objects.select_related("receipt").get(pk=source_line_id)
    root = lock_receipt(source.receipt_id)
    require_receiving(actor, "view", root)
    owner = require_receiving(actor, "add", root)
    require_receiving(actor, "change", root)
    if owner.pk != root.department_id:
        raise PermissionDenied
    source = ReceivingLine.objects.select_related("receipt").get(pk=source_line_id, receipt=root)
    from .receipt_quantity_corrections import require_no_pending
    require_no_pending(source)
    payload = plain({"source_line_id": source.pk, "basis": expected_basis,
                     "inspection": inspection, "quantities": quantities})
    existing = ReceivingReceipt.objects.filter(public_id=request_id).first()
    if existing:
        created = existing.events.filter(action="created", actor=actor).first()
        if (existing.followup_source_id != source.pk or not created
                or created.snapshot.get("followup_request") != payload):
            raise ValidationError("This request identity was already used with different content.")
        return existing
    data = {key: getattr(root, key) for key in HEADER_FIELDS}
    data.update(inspection)
    receipt = ReceivingReceipt(**data, public_id=request_id, followup_source=source,
        followup_basis=expected_basis, department_id=root.department_id,
        department_label=root.department_label, created_by=actor)
    receipt.full_clean()
    try:
        with transaction.atomic():
            receipt.save()
    except IntegrityError:
        raise ValidationError("This request identity was used concurrently. Reload the receiving register.")
    line = ReceivingLine(receipt=receipt, sequence=1, kind=source.kind,
        description=source.description, unit=source.unit, supply_item_id=source.supply_item_id,
        asset_kind=source.asset_kind, property_tag=source.property_tag,
        serial_number=source.serial_number, chassis_number=source.chassis_number)
    for key, value in quantities.items():
        setattr(line, key, value)
    # Model validation converts and checks precise decimals before arithmetic.
    for name in ("accepted_quantity", "rejected_quantity"):
        setattr(line, name, line._meta.get_field(name).clean(getattr(line, name), line))
    line.delivered_quantity = line.accepted_quantity + line.rejected_quantity
    line.full_clean()
    validate_followup(receipt, [line])
    line.save()
    _event(receipt, actor, "created", followup_request=payload)
    return receipt
