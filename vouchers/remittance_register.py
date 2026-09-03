from __future__ import annotations

from django.db.models import Q

from .access import department_for_user, has_explicit_permission
from .models import TreasuryRemittanceBatch
from .roles import is_finance_uat_viewer


REMITTANCE_ACTION_SPECS = {
    "preparation": {
        "permission": "vouchers.prepare_remittances",
        "statuses": (TreasuryRemittanceBatch.DRAFT,),
        "title": "Remittances to prepare",
        "definition": "Draft remittance batches owned by the acting Treasury office.",
        "next_action": "Complete the exact withholding allocations and evidence, reconcile the control total, then submit for independent Accounting review.",
        "scope": "treasury",
    },
    "returned": {
        "permission": "vouchers.prepare_remittances",
        "statuses": (TreasuryRemittanceBatch.RETURNED,),
        "title": "Returned remittances to correct",
        "definition": "Returned remittance batches owned by the acting Treasury office.",
        "next_action": "Apply the retained Accounting correction instructions through governed line revisions, recheck the total, then resubmit.",
        "scope": "treasury",
    },
    "review": {
        "permission": "vouchers.approve_remittances",
        "statuses": (TreasuryRemittanceBatch.FOR_REVIEW,),
        "title": "Remittances for independent review",
        "definition": "Submitted remittances awaiting a reviewer who neither created nor submitted the batch.",
        "next_action": "Independently reconcile the live withholding lines, pinned posting rule, recipient, fund, and bank route; approve or return with a reason.",
        "scope": "finance",
    },
    "release": {
        "permission": "vouchers.release_remittances",
        "statuses": (TreasuryRemittanceBatch.APPROVED,),
        "title": "Approved remittances awaiting release",
        "definition": "Independently approved remittances owned by the acting Treasury office and awaiting actual release evidence.",
        "next_action": "Reconfirm the exact approved total and payment route, execute the remittance, and record the actual bank or official release reference.",
        "scope": "treasury",
    },
}


def visible_remittance_batches(user, queryset=None):
    """Return the remittance register scope allowed by the user's current duties."""

    base = queryset if queryset is not None else TreasuryRemittanceBatch.objects.all()
    if is_finance_uat_viewer(user):
        return base
    if any(has_explicit_permission(user, permission) for permission in (
        "vouchers.approve_remittances", "vouchers.view_remittance_audit",
    )):
        return base
    department = department_for_user(user)
    if department is None:
        return base.none()
    return base.filter(treasury_department_id=department.pk)


def remittance_action_choices_for_user(user):
    if is_finance_uat_viewer(user):
        return ()
    return tuple(
        (key, spec["title"])
        for key, spec in REMITTANCE_ACTION_SPECS.items()
        if has_explicit_permission(user, spec["permission"])
    )


def remittance_action_queryset(user, action, queryset=None):
    spec = REMITTANCE_ACTION_SPECS.get(action)
    base = visible_remittance_batches(user, queryset)
    department = department_for_user(user)
    if (
        spec is None or department is None or is_finance_uat_viewer(user)
        or not has_explicit_permission(user, spec["permission"])
    ):
        return base.none(), action if spec else "", spec
    if spec["scope"] == "treasury":
        base = base.filter(treasury_department_id=department.pk)
    base = base.filter(status__in=spec["statuses"])
    if action == "review":
        base = base.exclude(Q(created_by=user) | Q(submitted_by=user))
    return base.distinct(), action, spec
