from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from vouchers.roles import is_finance_uat_viewer

from .access import can_manage_finance_discovery, can_view_finance_setup, department_for_user
from .models import FinanceDiscoveryDecision


DISCOVERY_ATTENTION_CHOICES = (
    ("needs_preparation", "Draft or returned decisions I may prepare"),
    ("my_reviews", "Submitted decisions assigned to me for review"),
    ("blockers", "Current scope blockers"),
    ("awaiting_review", "All visible decisions awaiting named reviewer"),
    ("overdue", "Overdue open work"),
    ("returned", "All visible decisions returned for correction"),
)

DISCOVERY_ACTION_SPECS = {
    "needs_preparation": {
        "title": "Discovery decisions to prepare or correct",
        "definition": "Draft or returned decisions the signed-in owner or department discovery manager may edit and submit.",
        "next_action": "Open the decision, retain the exact evidence reference and scope, then submit it to the named independent reviewer.",
    },
    "my_reviews": {
        "title": "Discovery decisions assigned for independent review",
        "definition": "Submitted decisions assigned to the signed-in reviewer, excluding self-created, self-owned, or self-submitted rows.",
        "next_action": "Compare the submitted evidence lock with the named scope, then independently record or return the decision.",
    },
}


def visible_discovery_decisions(user):
    query = Q(owner=user) | Q(reviewer=user)
    department = department_for_user(user)
    if department and (
        can_view_finance_setup(user, department)
        or can_manage_finance_discovery(user, department)
    ):
        query |= Q(department=department)
    return FinanceDiscoveryDecision.objects.filter(query).select_related(
        "department", "cycle", "owner", "reviewer", "created_by", "submitted_by",
        "reviewed_by", "predecessor",
    ).distinct()


def discovery_action_choices_for_user(user):
    if is_finance_uat_viewer(user):
        return ()
    department = department_for_user(user)
    choices = []
    if (
        department and can_manage_finance_discovery(user, department)
    ) or user.owned_finance_discovery_decisions.exists():
        choices.append(DISCOVERY_ATTENTION_CHOICES[0])
    if user.assigned_finance_discovery_reviews.exists():
        choices.append(DISCOVERY_ATTENTION_CHOICES[1])
    return tuple(choices)


def discovery_attention_choices_for_user(user):
    action_choices = discovery_action_choices_for_user(user)
    return action_choices + DISCOVERY_ATTENTION_CHOICES[2:]


def discovery_action_queryset(user, attention, *, queryset=None):
    query = queryset if queryset is not None else visible_discovery_decisions(user)
    spec = DISCOVERY_ACTION_SPECS.get(attention)
    if spec is None:
        return query.none(), "", None
    if is_finance_uat_viewer(user):
        return query.none(), attention, spec

    department = department_for_user(user)
    if attention == "needs_preparation":
        scope = Q(owner=user)
        if department and can_manage_finance_discovery(user, department):
            scope |= Q(department=department)
        query = query.filter(
            scope,
            status__in=(FinanceDiscoveryDecision.DRAFT, FinanceDiscoveryDecision.RETURNED),
        )
    else:
        query = query.filter(
            reviewer=user,
            status=FinanceDiscoveryDecision.SUBMITTED,
        ).exclude(Q(owner=user) | Q(created_by=user) | Q(submitted_by=user))
    return query.distinct(), attention, spec


def apply_discovery_filters(
    queryset, user, *, phase="", status="", cycle_id="", attention="", as_of=None,
):
    try:
        parsed_cycle_id = int(cycle_id)
    except (TypeError, ValueError):
        parsed_cycle_id = None
    if parsed_cycle_id and queryset.filter(cycle_id=parsed_cycle_id).exists():
        queryset = queryset.filter(cycle_id=parsed_cycle_id)
        cycle_id = str(parsed_cycle_id)
    else:
        cycle_id = ""

    phase = phase if phase in dict(FinanceDiscoveryDecision.PHASE_CHOICES) else ""
    status = status if status in dict(FinanceDiscoveryDecision.STATUS_CHOICES) else ""
    if phase:
        queryset = queryset.filter(phase=phase)
    if status:
        queryset = queryset.filter(status=status)

    valid_attention = dict(DISCOVERY_ATTENTION_CHOICES)
    attention = attention if attention in valid_attention else ""
    if attention in DISCOVERY_ACTION_SPECS:
        queryset, _selected, _spec = discovery_action_queryset(user, attention, queryset=queryset)
    elif attention == "blockers":
        queryset = queryset.exclude(status=FinanceDiscoveryDecision.SUPERSEDED).filter(
            blocks_affected_scope=True,
        )
    elif attention == "awaiting_review":
        queryset = queryset.filter(status=FinanceDiscoveryDecision.SUBMITTED)
    elif attention == "overdue":
        queryset = queryset.filter(
            due_date__lt=as_of or timezone.localdate(),
            status__in=(
                FinanceDiscoveryDecision.DRAFT,
                FinanceDiscoveryDecision.SUBMITTED,
                FinanceDiscoveryDecision.RETURNED,
            ),
        )
    elif attention == "returned":
        queryset = queryset.filter(status=FinanceDiscoveryDecision.RETURNED)
    return queryset, phase, status, cycle_id, attention
