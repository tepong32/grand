from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from vouchers.roles import is_finance_uat_viewer

from .access import (
    can_approve_finance_configuration,
    can_manage_finance_configuration,
    department_for_user,
)
from .models import FinanceConfigurationRelease


SETUP_ATTENTION_CHOICES = (
    ("needs_preparation", "Draft releases to prepare or correct"),
    ("awaiting_review", "Submitted releases awaiting independent review"),
    ("ready_to_schedule", "Approved future releases ready to schedule"),
    ("ready_to_activate", "Approved or scheduled releases ready to activate"),
)

SETUP_ATTENTION_SPECS = {
    "needs_preparation": {
        "role": "manage",
        "title": "Draft configuration releases to prepare or correct",
        "definition": "Draft versions in the acting office that remain editable before submission.",
        "next_action": "Complete the locally reviewed master data, rules, routes, numbering, and template evidence, then submit the release.",
    },
    "awaiting_review": {
        "role": "approve",
        "title": "Configuration releases awaiting independent review",
        "definition": "Submitted office releases awaiting an authorized Accounting approve-or-return decision.",
        "next_action": "Review the retained local basis and preflight evidence, then approve or return without rewriting the submitted version.",
    },
    "ready_to_schedule": {
        "role": "approve",
        "title": "Approved future releases ready to schedule",
        "definition": "Approved releases whose effective date is still in the future and therefore cannot activate yet.",
        "next_action": "Schedule the approved release for its accepted future effective date.",
    },
    "ready_to_activate": {
        "role": "approve",
        "title": "Configuration releases ready to activate",
        "definition": "Approved or scheduled releases whose effective period includes today.",
        "next_action": "Recheck readiness and the accepted effective period, then activate through the governed release action.",
    },
}


def setup_releases_for_department(department):
    return FinanceConfigurationRelease.objects.filter(department=department).prefetch_related(
        "items", "templates", "signatories", "numbering_sequences", "parties",
    )


def _role_allowed(user, department, role):
    if role == "manage":
        return can_manage_finance_configuration(user, department)
    return can_approve_finance_configuration(user, department)


def setup_attention_choices_for_user(user, department=None):
    department = department or department_for_user(user)
    if department is None or is_finance_uat_viewer(user):
        return ()
    labels = dict(SETUP_ATTENTION_CHOICES)
    return tuple(
        (attention, labels[attention])
        for attention, spec in SETUP_ATTENTION_SPECS.items()
        if _role_allowed(user, department, spec["role"])
    )


def setup_attention_queryset(user, attention, *, as_of=None):
    department = department_for_user(user)
    query = setup_releases_for_department(department) if department else FinanceConfigurationRelease.objects.none()
    spec = SETUP_ATTENTION_SPECS.get(attention)
    if spec is None:
        return query.none(), "", None
    if department is None or is_finance_uat_viewer(user) or not _role_allowed(user, department, spec["role"]):
        return query.none(), attention, spec

    as_of = as_of or timezone.localdate()
    if attention == "needs_preparation":
        query = query.filter(status="draft")
    elif attention == "awaiting_review":
        query = query.filter(status="submitted")
    elif attention == "ready_to_schedule":
        query = query.filter(status="approved", effective_from__gt=as_of)
    elif attention == "ready_to_activate":
        query = query.filter(
            Q(status="approved") | Q(status="scheduled"),
            effective_from__lte=as_of,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
    return query, attention, spec
