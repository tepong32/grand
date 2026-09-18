"""Read-only continuation from an already scoped OBR to existing payable work."""
from django.core.paginator import Paginator
from django.db.models import Q

from vouchers.access import can_view_workbench, department_for_user, has_explicit_permission
from vouchers.case_exports import visible_cases_for_user
from vouchers.forms import _obligation_capacity
from vouchers.models import VoucherCase
from vouchers.roles import STAGE_NEXT_ACTION, is_finance_uat_viewer
from .models import ObligationRequest, PayableObligationAllocation


def payable_handoff(obligation, actor, page_number=None):
    if obligation.status != ObligationRequest.CERTIFIED or obligation.kind != ObligationRequest.ORIGINAL:
        return None
    current, remaining = _obligation_capacity(obligation)
    department = department_for_user(actor)
    can_prepare = bool(department and department.pk == obligation.requesting_department_id
        and has_explicit_permission(actor, "vouchers.initiate_payable_case")
        and not is_finance_uat_viewer(actor) and remaining > 0)
    cases = VoucherCase.objects.none()
    if can_view_workbench(actor):
        # Materialize Finance IDs before querying the separate default store.
        linked_ids = list(PayableObligationAllocation.objects.filter(obligation=obligation)
            .values_list("voucher_case_public_id", flat=True).distinct())
        if obligation.linked_voucher_case_public_id:
            linked_ids.append(obligation.linked_voucher_case_public_id)
        cases = visible_cases_for_user(actor, VoucherCase.objects.filter(
            Q(public_id__in=linked_ids) | Q(authoritative_obligation_public_id=obligation.public_id)
        )).select_related("current_department").order_by("-created_at", "-pk")
    page = Paginator(cases, 20).get_page(page_number)
    rows = [{"case": case, "next_action": STAGE_NEXT_ACTION.get(case.current_stage, case.get_current_stage_display()),
        "needs_recovery": case.obligation_binding_status in (VoucherCase.BINDING_PENDING, VoucherCase.BINDING_FAILED)}
        for case in page]
    return {"current": current, "allocated": current - remaining, "remaining": remaining,
        "can_prepare": can_prepare, "can_view_cases": can_view_workbench(actor), "page": page, "rows": rows}
