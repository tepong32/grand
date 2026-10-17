"""Retained physical receipt facts supporting a claim; never financial valuation."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from inventory.receipt_amendments import latest_amendment

from inventory.receiving import HEADER_FIELDS


def receipt_basis(line):
    receipt = line.receipt

    def value(raw):
        if raw is None:
            return None
        if isinstance(raw, Decimal):
            return format(raw, "f")
        return raw.isoformat() if hasattr(raw, "isoformat") else raw

    basis = {
        "schema": 1,
        "receipt_uuid": str(receipt.public_id), "receipt_version": receipt.state_version,
        "status": receipt.status, "department_local_id": receipt.department_id,
        "department_label": receipt.department_label,
        "header": {key: value(getattr(receipt, key)) for key in sorted(HEADER_FIELDS)},
        "reviewed_by_local_id": receipt.reviewed_by_id, "reviewed_at": value(receipt.reviewed_at),
        "line": {key: value(getattr(line, key)) for key in (
            "sequence", "kind", "description", "unit", "delivered_quantity", "accepted_quantity",
            "rejected_quantity", "rejection_reason", "unit_cost", "is_void", "asset_kind",
            "property_tag", "serial_number", "chassis_number")},
        "supply_uuid": str(line.supply_item.public_id) if line.supply_item_id else None,
        "asset_uuid": str(line.registered_asset.public_id) if line.registered_asset_id else None,
        "movement_uuid": str(line.stock_movement.public_id) if line.stock_movement_id else None,
        "evidence": list(receipt.evidence.order_by("pk").values(
            "kind", "sha256", "size", "original_filename", "note")),
    }
    amendment = latest_amendment(line)
    if amendment:
        basis["documentary_amendment"] = {"uuid": str(amendment.public_id),
            "content_checksum": amendment.content_checksum, "unit_cost": value(amendment.unit_cost),
            "reference": amendment.reference, "reviewed_by_local_id": amendment.reviewed_by_id,
            "reviewed_at": value(amendment.reviewed_at)}
    if receipt.followup_source_id:
        from inventory.receiving_followups import retained_source
        basis["followup"] = retained_source(receipt)
    from inventory.receipt_quantity_corrections import correction_extension
    correction = correction_extension(line)
    if correction:
        basis["quantity_correction"] = correction
    return basis



def receipt_basis_current(row, line=None):
    # NULL is an explicit pre-migration unknown, never a fabricated approval basis.
    try:
        return bool(row.receipt_snapshot and row.receipt_snapshot == receipt_basis(line or row.receipt_line))
    except ValidationError:
        return False
