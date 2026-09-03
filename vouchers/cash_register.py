from __future__ import annotations

from .access import department_for_user, has_explicit_permission
from .models import TreasuryCashPolicy, TreasuryCashPosition
from .roles import is_finance_uat_viewer


CASH_ATTENTION_CHOICES = (
    ("policy_needs_preparation", "Cash policies to prepare or correct"),
    ("policy_awaiting_review", "Cash policies awaiting independent review"),
    ("position_needs_preparation", "Cash positions to prepare or correct"),
    ("position_awaiting_review", "Cash positions awaiting independent review"),
)

CASH_ATTENTION_SPECS = {
    "policy_needs_preparation": {
        "kind": "policy",
        "permission": "vouchers.prepare_cash_position",
        "statuses": (TreasuryCashPolicy.DRAFT, TreasuryCashPolicy.RETURNED),
        "title": "Cash policies to prepare or correct",
        "definition": "Draft or returned bank/fund policy versions available to the Treasury preparer.",
        "next_action": "Complete or correct the policy, then submit it for independent review.",
    },
    "policy_awaiting_review": {
        "kind": "policy",
        "permission": "vouchers.approve_cash_position",
        "statuses": (TreasuryCashPolicy.FOR_REVIEW,),
        "title": "Cash policies awaiting independent review",
        "definition": "Submitted bank/fund policy versions awaiting an activate-or-return decision.",
        "next_action": "Independently review the policy authority, route, and thresholds; activate or return it.",
    },
    "position_needs_preparation": {
        "kind": "position",
        "permission": "vouchers.prepare_cash_position",
        "statuses": (TreasuryCashPosition.DRAFT, TreasuryCashPosition.RETURNED),
        "title": "Cash positions to prepare or correct",
        "definition": "Draft or returned cash-position versions available to the Treasury preparer.",
        "next_action": "Complete or correct the retained position evidence, then submit it for review.",
    },
    "position_awaiting_review": {
        "kind": "position",
        "permission": "vouchers.approve_cash_position",
        "statuses": (TreasuryCashPosition.FOR_REVIEW,),
        "title": "Cash positions awaiting independent review",
        "definition": "Submitted position snapshots awaiting an approve-or-return decision.",
        "next_action": "Independently compare the position with its pinned reconciliation and decide it.",
    },
}


def visible_cash_policies(user):
    """Return the same policy scope used by cash overview and work-item queries."""
    query = TreasuryCashPolicy.objects.select_related(
        "configuration_release", "treasury_department", "created_by", "submitted_by", "approved_by",
    )
    if has_explicit_permission(user, "vouchers.approve_cash_position") or is_finance_uat_viewer(user):
        return query
    department = department_for_user(user)
    if department is None:
        return query.none()
    return query.filter(treasury_department=department)


def cash_attention_queryset(user, attention):
    """Return one exact actionable record type, never a mixed policy/position count."""
    spec = CASH_ATTENTION_SPECS.get(attention)
    if spec is None:
        return TreasuryCashPolicy.objects.none(), "", None
    if is_finance_uat_viewer(user) or not has_explicit_permission(user, spec["permission"]):
        if spec["kind"] == "position":
            return TreasuryCashPosition.objects.none(), attention, spec
        return TreasuryCashPolicy.objects.none(), attention, spec
    policies = visible_cash_policies(user)
    if spec["kind"] == "position":
        queryset = TreasuryCashPosition.objects.filter(
            policy__in=policies, status__in=spec["statuses"],
        ).select_related("policy", "policy__treasury_department", "created_by", "submitted_by", "approved_by")
    else:
        queryset = policies.filter(status__in=spec["statuses"])
    return queryset, attention, spec
