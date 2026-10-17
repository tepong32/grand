"""Read GRAND claim sources without granting Finance visibility or posting authority.

Optional integration seam: unavailable in the standalone shell. Source snapshots
are observations, never approvals or budget/claim capacity reservations.
"""
import hashlib
import json
from uuid import UUID

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction


def claim_line_snapshot(case, line):
    """Called only after scoped lookup; includes no tax identifiers or bank details."""
    release = case.configuration_release
    if release is None or line.voucher.case_id != case.pk:
        raise ValidationError("The claim line has no consistent Finance case and owner.")
    party = case.payee
    if party is not None and party.department_id != release.department_id:
        raise ValidationError("The claim party and Finance owner are inconsistent.")
    payload = {
        "schema": "gso-grand-claim-line-v1",
        "case_public_id": str(case.public_id),
        "case_state_version": case.state_version,
        "case_stage": case.current_stage,
        "case_reference": case.reference_code,
        "finance_department_id": release.department_id,
        "configuration_release_id": release.pk,
        "requesting_department_id": case.requesting_department_id,
        "party": None if party is None else {
            "department_id": party.department_id, "code": party.code,
            "version": party.version, "release_id": party.release_id,
            "display_name": party.display_name,
        },
        "voucher_number": line.voucher.dv_number,
        "voucher_date": line.voucher.voucher_date.isoformat(),
        "voucher_gross_amount": str(line.voucher.gross_amount),
        "line_local_id": line.pk,
        "line_description": line.description,
        "line_account_code": line.account_code,
        "line_amount": str(line.amount),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {"source": payload, "sha256": hashlib.sha256(encoded).hexdigest()}


def resolve_claim_line(*, actor, case_public_id, line_id):
    """Resolve only a currently visible native GRAND line under its case lock.

    Numeric line IDs are scoped to the selected case, not portable identities.
    A future attribution write must re-resolve under its transaction and compare
    the reviewed fingerprint; a successful read does not authorize a later write.
    """
    if not apps.is_installed("vouchers") or not apps.is_installed("finance"):
        raise ValidationError("Finance source lookup is available only after GRAND integration.")
    from vouchers.access import can_view_workbench
    from vouchers.case_exports import visible_cases_for_user
    from vouchers.models import VoucherCase, VoucherLineItem

    if not can_view_workbench(actor):
        raise PermissionDenied
    try:
        case_id = UUID(str(case_public_id))
        if isinstance(line_id, bool) or int(line_id) <= 0 or str(int(line_id)) != str(line_id):
            raise ValueError
        line_id = int(line_id)
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Select a valid claim and line.")
    with transaction.atomic(using="default"):
        # GRAND preparation serializes changes on this same default-store case.
        rows = visible_cases_for_user(actor, VoucherCase.objects.using("default").all())
        case = rows.select_for_update().filter(public_id=case_id).first()
        if case is None:
            raise PermissionDenied
        line = VoucherLineItem.objects.using("default").select_related("voucher").filter(
            pk=line_id, voucher__case_id=case.pk).first()
        if line is None:
            raise ValidationError("The selected claim line is unavailable or has been replaced. Reload the claim.")
        return claim_line_snapshot(case, line)
