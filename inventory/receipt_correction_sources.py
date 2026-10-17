"""Locked prerequisites for the first, before-use clerical correction.

This module does not authorize or perform a correction. Its caller must retain
the outer default transaction through the reviewed correction's eventual write.
"""
from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .access import gso_department_for_user
from .models import Asset, ConsumableItem, ReceivingLine, ReceivingReceipt, StockLot, StockMovement
from .receiving import HEADER_FIELDS, can_receiving, verify_receipt_evidence


def _original_acceptance(line):
    receipt = line.receipt
    events = list(receipt.events.filter(action="accepted"))
    if len(events) != 1:
        raise ValidationError("The original acceptance history needs reconciliation.")
    snapshot = events[0].snapshot
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get("lines"), list)
            or any(not isinstance(row, dict) for row in snapshot["lines"])
            or not isinstance(snapshot.get("evidence"), list)
            or any(not isinstance(row, dict) or not isinstance(row.get("id"), int)
                   for row in snapshot["evidence"])):
        raise ValidationError("The original acceptance history is malformed; reconcile it first.")
    original = [row for row in snapshot.get("lines", []) if row.get("id") == str(line.pk)]
    current = ReceivingLine.objects.filter(pk=line.pk).values().get()
    current = {key: str(value) if value is not None else None for key, value in current.items()}
    header = {key: value.isoformat() if hasattr(value, "isoformat") else str(value)
              for key in HEADER_FIELDS for value in (getattr(receipt, key),)}
    evidence = list(receipt.evidence.order_by("pk").values(
        "id", "kind", "sha256", "size", "note", "original_filename"))
    if (original != [current] or snapshot.get("header") != header
            or snapshot.get("public_id") != str(receipt.public_id)
            or snapshot.get("status") != receipt.ACCEPTED
            or events[0].actor_id != receipt.reviewed_by_id
            or snapshot.get("reviewed_by_id") != receipt.reviewed_by_id
            or sorted(snapshot.get("evidence", []), key=lambda row: row["id"]) != evidence):
        raise ValidationError("The receipt no longer matches its original acceptance. Reconcile its history.")
    verify_receipt_evidence(receipt)


def _unused_supply(line):
    if not line.supply_item_id or not line.stock_movement_id or line.registered_asset_id:
        raise ValidationError("The original supply materialization is incomplete.")
    item = ConsumableItem.objects.select_for_update().get(pk=line.supply_item_id)
    movement = StockMovement.objects.get(pk=line.stock_movement_id)
    movement.item = item
    if (not item.is_active or item.department_id != line.receipt.department_id
            or item.unit != line.unit or movement.item_id != item.pk
            or movement.kind != StockMovement.RECEIPT
            or movement.quantity != line.accepted_quantity
            or movement.signed_quantity != line.accepted_quantity
            or movement.unit_cost != line.unit_cost
            or movement.actor_id != line.receipt.reviewed_by_id
            or movement.reference != f"Receiving {line.receipt.public_id} line {line.sequence}"):
        raise ValidationError("The receipt's materialized supply facts need reconciliation.")
    # Counts/adjustments can already have reconciled the overstatement. Neither
    # today's positive balance nor a later return proves the original was unused.
    later = item.movements.filter(pk__gt=movement.pk)
    from .receipt_quantity_corrections import approved_corrections
    prior = approved_corrections(line)
    correction_ids = [row.adjustment_id for row in prior]
    later = later.exclude(pk__in=correction_ids)
    if (item.counts.filter(recorded_at__gte=movement.occurred_at).exists()
            or later.filter(kind__in=("adjustment_in", "adjustment_out")).exists()
            or later.filter(kind="return", supply_return_case__isnull=True).exists()):
        raise ValidationError("Later counts, adjustments or unlinked returns need reconciliation first.")
    lots = list(StockLot.objects.filter(receipt=movement))
    if item.use_fifo:
        if (len(lots) != 1 or lots[0].item_id != item.pk
                or lots[0].quantity != movement.quantity or lots[0].unit_cost != movement.unit_cost
                or lots[0].received_at != movement.occurred_at):
            raise ValidationError("The original FIFO lot does not match its receipt.")
        if lots[0].allocations.exclude(issue_id__in=correction_ids).exists():
            raise ValidationError("The original lot has already been used; a before-use correction is unavailable.")
    elif lots or later.filter(signed_quantity__lt=0).exists():
        raise ValidationError("Non-FIFO receipt usage cannot be isolated from the retained history.")
    return movement


def _unused_asset(line):
    from .services import asset_snapshot
    if not line.registered_asset_id or line.stock_movement_id or line.supply_item_id:
        raise ValidationError("The original asset materialization is incomplete.")
    asset = Asset.objects.select_for_update().get(pk=line.registered_asset_id)
    expected = {"department_id": line.receipt.department_id, "asset_name": line.description,
        "asset_kind": line.asset_kind, "property_tag": line.property_tag,
        "serial_number": line.serial_number, "chassis_number": line.chassis_number,
        "quantity": 1, "unit_cost": line.unit_cost, "supplier": line.receipt.supplier,
        "purchase_order_reference": line.receipt.purchase_order_reference,
        "status": Asset.ACTIVE}
    if (any(getattr(asset, field) != value for field, value in expected.items())
            or asset.assigned_department_id or asset.assigned_department_label or asset.assigned_office
            or asset.custodian_user_id or asset.custodian_snapshot or asset.last_custody_return_id
            or asset.returned_date):
        raise ValidationError("The asset's current facts are not an unused original receipt entry.")
    relations = ("transfers", "maintenance_cases", "disposal_cases", "verification_records",
                 "verification_findings_linked", "property_determinations", "property_movements")
    history = list(asset.audit_events.all())
    if (any(getattr(asset, name).exists() for name in relations)
            or len(history) != 1 or history[0].action != "created"
            or history[0].actor_id != line.receipt.reviewed_by_id
            or history[0].snapshot != asset_snapshot(asset)):
        raise ValidationError("The asset has downstream history; reconcile it before correcting the receipt.")
    return asset


def lock_unused_source(*, actor, line_id):
    """Return refreshed (line, stock receipt or asset), retaining caller's locks.

    Only verified approved results of this same source are excluded from prior
    adjustment checks; callers cannot supply movements to ignore.
    """
    if not transaction.get_connection("default").in_atomic_block:
        raise RuntimeError("Inspect correction eligibility inside the complete default transaction.")
    owner = gso_department_for_user(actor)
    if not owner or not can_receiving(actor, "view"):
        raise PermissionDenied
    try:
        candidate = ReceivingLine.objects.get(pk=line_id, receipt__department_id=owner.pk)
        receipt = ReceivingReceipt.objects.select_for_update().get(pk=candidate.receipt_id)
        line = ReceivingLine.objects.get(pk=line_id, receipt=receipt)
    except (ReceivingLine.DoesNotExist, ReceivingReceipt.DoesNotExist):
        raise PermissionDenied
    if receipt.department_id != owner.pk or not can_receiving(actor, "view", receipt):
        raise PermissionDenied
    line.receipt = receipt
    if receipt.status != receipt.ACCEPTED or line.is_void or line.accepted_quantity <= 0:
        raise ValidationError("Select an accepted, non-void original quantity.")
    if receipt.followup_source_id or line.followup_receipts.exists():
        raise ValidationError("Follow-up inspection history needs separate reconciliation.")
    if line.cost_amendments.filter(status="pending").exists():
        raise ValidationError("Resolve the pending documentary cost amendment first.")
    if apps.is_installed("inventory_finance"):
        attribution = apps.get_model("inventory_finance", "ReceiptClaimAttribution")
        if attribution.objects.using("default").filter(receipt_line_id=line.pk).exists():
            raise ValidationError("Finance support history excludes this before-use correction.")
    _original_acceptance(line)
    if line.kind == ReceivingLine.SUPPLY:
        return line, _unused_supply(line)
    if line.kind == ReceivingLine.ASSET:
        return line, _unused_asset(line)
    raise ValidationError("Unknown receiving line kind.")
