"""Require both source visibility and attribution authority; UUIDs grant no access."""
from django.db.models import Q

from vouchers.access import can_view_workbench, department_for_user, has_explicit_permission
from vouchers.case_exports import visible_cases_for_user
from vouchers.models import VoucherCase

from .models import ReceiptClaimAttribution


def visible_attributions(actor):
    rows = ReceiptClaimAttribution.objects.all()
    department = department_for_user(actor)
    if not department or not can_view_workbench(actor) or not any(
        has_explicit_permission(actor, f"inventory_finance.{action}_receiptclaimattribution")
        for action in ("view", "propose", "review")
    ):
        return rows.none()
    cases = visible_cases_for_user(actor, VoucherCase.objects.all())
    return rows.filter(case__in=cases).filter(
        Q(receipt_line__receipt__department_id=department.pk) | Q(finance_department_id=department.pk))
