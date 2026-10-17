"""Reviewed claim support only: no accounting, payment or Budget capacity writes."""
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from inventory.access import department_for_user, gso_department_for_user
from inventory.finance_sources import resolve_claim_line
from inventory.models import ReceivingLine, ReceivingReceipt
from inventory.receipt_amendments import latest_amendment, verify_amendment_evidence
from vouchers.access import can_manage_owned_case_artifact, has_explicit_permission
from vouchers.roles import is_finance_uat_viewer

from .models import ReceiptClaimAttribution, ReceiptClaimEvent
from .access import visible_attributions
from .receipt_basis import receipt_basis, receipt_basis_current


def _amount(value):
    try:
        if isinstance(value, (bool, float)):
            raise ValueError
        result = Decimal(value)
        if not result.is_finite() or result <= 0 or result >= Decimal("10000000000000000"):
            raise ValueError
        if result != result.quantize(Decimal("0.01")):
            raise ValueError
        return result
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError("Enter a positive amount with at most two decimal places.")


def _event(row, actor, action, note=""):
    ReceiptClaimEvent.objects.create(attribution=row, actor=actor, action=action, snapshot={
        "public_id": str(row.public_id), "version": row.state_version, "status": row.status,
        "receipt_public_id": str(row.receipt_line.receipt.public_id),
        "receipt_line_sequence": row.receipt_line.sequence,
        "case_public_id": str(row.case.public_id), "source": row.source_snapshot,
        "source_checksum": row.source_checksum, "receipt": row.receipt_snapshot, "amount": str(row.amount),
        "basis": row.basis, "note": note,
    })


def _accepted_line(pk, *, owner_id=None):
    # All attribution writes lock case first, then receipt, then attribution.
    lines = ReceivingLine.objects.select_related("receipt")
    if owner_id is not None:
        lines = lines.filter(receipt__department_id=owner_id)
    try:
        line = lines.get(pk=pk)
    except ReceivingLine.DoesNotExist:
        raise PermissionDenied
    receipt = ReceivingReceipt.objects.select_for_update().get(pk=line.receipt_id)
    try:
        line = lines.get(pk=pk)
    except ReceivingLine.DoesNotExist:
        raise PermissionDenied
    if receipt.status != receipt.ACCEPTED or line.is_void or line.accepted_quantity <= 0:
        raise ValidationError("Only an accepted, non-void receipt line can support a claim.")
    from inventory.receipt_quantity_corrections import require_no_pending, effective_quantities
    require_no_pending(line)
    if effective_quantities(line)["accepted"] <= 0:
        raise ValidationError("A fully corrected erroneous receipt cannot support a claim.")
    # Refresh after acquiring the receipt lock: a future reviewed amendment may
    # have committed while this operation waited. Never use the pre-lock line.
    return line


def _receipt_support_limit(line):
    amendment = latest_amendment(line)
    if amendment:
        verify_amendment_evidence(amendment)
    cost = amendment.unit_cost if amendment else line.unit_cost
    if cost is None or cost <= 0:
        raise ValidationError("This receipt needs a positive documented unit cost before claim support can be recorded.")
    # Documentary ceiling, not an Accounting acquisition-cost determination.
    from inventory.receipt_quantity_corrections import effective_quantities
    return effective_quantities(line)["accepted"] * cost


@transaction.atomic(using="default")
def propose_attribution(*, actor, receipt_line_id, case_public_id, source_line_id,
                        source_checksum, amount, basis, request_id, expected_receipt_basis):
    if is_finance_uat_viewer(actor) or not has_explicit_permission(
            actor, "inventory_finance.propose_receiptclaimattribution"):
        raise PermissionDenied
    department = department_for_user(actor)
    if department is None or gso_department_for_user(actor) != department:
        raise PermissionDenied
    amount = _amount(amount)
    basis = str(basis).strip() if basis is not None else ""
    if not basis or len(basis) > 4000:
        raise ValidationError("Explain the attribution basis in at most 4,000 characters.")
    try:
        request_id = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A valid proposal request identity is required.")
    source = resolve_claim_line(actor=actor, case_public_id=case_public_id, line_id=source_line_id)
    if source["sha256"] != source_checksum:
        raise ValidationError("The claim source changed. Reload and review it before proposing a link.")
    line = _accepted_line(receipt_line_id, owner_id=department.pk)
    if line.receipt.department_id != department.pk:
        raise PermissionDenied
    recorded_receipt = receipt_basis(line)
    if recorded_receipt != expected_receipt_basis:
        raise ValidationError("The receipt source changed. Preview the current receipt before proposing support.")
    if amount > Decimal(source["source"]["line_amount"]):
        raise ValidationError("The supported amount exceeds the selected claim line.")
    if amount > _receipt_support_limit(line):
        raise ValidationError("The supported amount exceeds the documented accepted receipt value.")
    existing = ReceiptClaimAttribution.objects.filter(public_id=request_id).first()
    if existing:
        if (existing.proposed_by_id == actor.pk and existing.receipt_line_id == line.pk
                and existing.source_checksum == source_checksum and existing.amount == amount
                and existing.receipt_snapshot == recorded_receipt
                and existing.basis == basis):
            return existing
        raise ValidationError("This proposal request identity already belongs to different content.")
    from vouchers.models import VoucherCase
    case = VoucherCase.objects.get(public_id=source["source"]["case_public_id"])
    row = ReceiptClaimAttribution(
        public_id=request_id, receipt_line=line, case=case,
        finance_department_id=source["source"]["finance_department_id"],
        source_line_id=source["source"]["line_local_id"], source_snapshot=source["source"],
        source_checksum=source_checksum, receipt_snapshot=recorded_receipt,
        amount=amount, basis=basis, proposed_by=actor)
    row.full_clean()
    row.save()
    _event(row, actor, "proposed")
    return row


@transaction.atomic(using="default")
def approve_attribution(*, actor, attribution_id, expected_version, note):
    candidate = visible_attributions(actor).select_related("case__configuration_release").get(public_id=attribution_id)
    if not can_manage_owned_case_artifact(actor, candidate.case,
            "inventory_finance.review_receiptclaimattribution"):
        raise PermissionDenied
    source = resolve_claim_line(actor=actor, case_public_id=candidate.case.public_id,
                                line_id=candidate.source_line_id)
    receipt_line = _accepted_line(candidate.receipt_line_id)
    row = ReceiptClaimAttribution.objects.select_for_update().get(pk=candidate.pk)
    if row.state_version != expected_version or row.status != row.PROPOSED:
        raise ValidationError("This proposal changed. Reload it before review.")
    if row.proposed_by_id == actor.pk:
        raise PermissionDenied("A different officer must review your proposal.")
    if not receipt_basis_current(row, receipt_line):
        raise ValidationError("The receipt basis changed or was not retained. Withdraw or reject this link and review a new proposal.")
    if source["sha256"] != row.source_checksum or source["source"]["finance_department_id"] != row.finance_department_id:
        raise ValidationError("The source changed after proposal. A new reviewed proposal is required.")
    if not str(note or "").strip() or len(str(note)) > 4000:
        raise ValidationError("Record the review basis in at most 4,000 characters.")
    case_approved = ReceiptClaimAttribution.objects.filter(case=row.case, status=row.APPROVED)
    # Replacement gives a new line ID. Checking only today's line would miss old
    # approved support and permit duplicate attribution after re-preparation.
    for previous in case_approved:
        try:
            current = resolve_claim_line(actor=actor, case_public_id=row.case.public_id,
                                         line_id=previous.source_line_id)
        except ValidationError:
            raise ValidationError("Earlier approved links have stale source evidence; review and withdraw them first.")
        if current["sha256"] != previous.source_checksum:
            raise ValidationError("Earlier approved links have stale source evidence; review and withdraw them first.")
    approved = case_approved.filter(source_line_id=row.source_line_id)
    total = approved.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    if total + row.amount > Decimal(source["source"]["line_amount"]):
        raise ValidationError("Approved receipt support would exceed the claim line amount.")
    receipt_approved = ReceiptClaimAttribution.objects.filter(receipt_line=receipt_line, status=row.APPROVED)
    if any(not receipt_basis_current(previous, receipt_line) for previous in receipt_approved):
        raise ValidationError("Earlier approved links have a stale or missing receipt basis; review and withdraw them first.")
    receipt_total = receipt_approved.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    if receipt_total + row.amount > _receipt_support_limit(receipt_line):
        raise ValidationError("Approved support across claims would exceed the documented accepted receipt value.")
    row.status = row.APPROVED
    row.reviewed_by = actor
    row.reviewed_at = timezone.now()
    row.review_note = str(note).strip()
    row.state_version += 1
    row.full_clean()
    row.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "state_version"))
    _event(row, actor, "approved", row.review_note)
    return row


@transaction.atomic(using="default")
def close_attribution(*, actor, attribution_id, expected_version, action, reason):
    """Retain rejected/withdrawn history even when the original DV line is gone."""
    if action not in ("reject", "withdraw"):
        raise ValidationError("Choose reject or withdraw.")
    reason = str(reason or "").strip()
    if not reason or len(reason) > 4000:
        raise ValidationError("Record a reason in at most 4,000 characters.")
    candidate = visible_attributions(actor).get(public_id=attribution_id)
    from vouchers.models import VoucherCase
    case = VoucherCase.objects.select_for_update().get(pk=candidate.case_id)
    if not can_manage_owned_case_artifact(actor, case,
            "inventory_finance.review_receiptclaimattribution"):
        raise PermissionDenied
    # No resolve_claim_line call: a replaced line must not trap its old linkage.
    ReceivingReceipt.objects.select_for_update().get(pk=candidate.receipt_line.receipt_id)
    row = ReceiptClaimAttribution.objects.select_for_update().get(pk=candidate.pk)
    if row.state_version != expected_version:
        raise ValidationError("This attribution changed. Reload it before continuing.")
    if action == "reject":
        if row.status != row.PROPOSED:
            raise ValidationError("Only proposed links can be rejected.")
        if row.proposed_by_id == actor.pk:
            raise PermissionDenied("A different officer must review your proposal.")
        row.status = row.REJECTED
        row.reviewed_by = actor
        row.reviewed_at = timezone.now()
        row.review_note = reason
    else:
        if row.status not in (row.PROPOSED, row.APPROVED):
            raise ValidationError("Only proposed or approved links can be withdrawn.")
        if row.journal_mappings.filter(status="approved").exists():
            raise ValidationError("Withdraw the approved recognition mappings before withdrawing their claim support.")
        row.status = row.WITHDRAWN
        # Preserve the original approval actor/date/note; withdrawal has its own event.
    row.state_version += 1
    row.full_clean()
    row.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "state_version"))
    _event(row, actor, "rejected" if action == "reject" else "withdrawn", reason)
    return row
