from __future__ import annotations

from django.db.models import Q

from .access import department_for_user, has_explicit_permission
from .models import BankAdviceBatch
from .roles import is_finance_uat_viewer


BANK_ADVICE_ATTENTION_CHOICES = (
    ("needs_preparation", "Draft or returned for correction"),
    ("awaiting_review", "Awaiting independent Accounting review"),
    ("awaiting_bank_submission", "Approved; submit to the bank"),
    ("awaiting_bank_response", "Submitted; record the bank response"),
)

BANK_ADVICE_ATTENTION_STATUSES = {
    "needs_preparation": (
        BankAdviceBatch.DRAFT,
        BankAdviceBatch.REVIEW_RETURNED,
        BankAdviceBatch.RETURNED,
    ),
    "awaiting_review": (BankAdviceBatch.FOR_REVIEW,),
    "awaiting_bank_submission": (BankAdviceBatch.APPROVED,),
    "awaiting_bank_response": (BankAdviceBatch.SUBMITTED,),
}

BANK_ADVICE_ACTION_SPECS = {
    "needs_preparation": {
        "permission": "vouchers.prepare_bank_advice",
        "title": "Bank advice to prepare or correct",
        "definition": "Draft or returned advice versions available for preparation or a reasoned successor.",
        "next_action": "Complete and submit the draft, or prepare a reasoned successor for the returned version.",
    },
    "awaiting_review": {
        "permission": "vouchers.approve_bank_advice",
        "title": "Bank advice for independent review",
        "definition": "Advice versions awaiting an Accounting decision by someone other than their preparer or submitter.",
        "next_action": "Independently verify the retained instrument, total, authority, and snapshot evidence, then approve or return it.",
    },
    "awaiting_bank_submission": {
        "permission": "vouchers.submit_bank_advice",
        "title": "Approved advice to submit to the bank",
        "definition": "Approved advice versions awaiting retained bank-submission evidence.",
        "next_action": "Submit the approved advice through the accepted bank channel and retain its reference and evidence.",
    },
    "awaiting_bank_response": {
        "permission": "vouchers.acknowledge_bank_advice",
        "title": "Submitted advice awaiting bank response",
        "definition": "Submitted advice versions awaiting a retained acknowledgement or return response.",
        "next_action": "Record the bank response reference and evidence; a return must retain its correction reason.",
    },
}


def visible_bank_advice_batches(user):
    """Return the same role-scoped bank-advice register used by list and detail views."""
    query = BankAdviceBatch.objects.select_related(
        "accounting_department", "configuration_release", "created_by", "approved_by", "supersedes",
    ).prefetch_related("items__instrument__case", "events")
    department = department_for_user(user)
    if department is None:
        return query.none()
    if has_explicit_permission(user, "vouchers.approve_bank_advice") or has_explicit_permission(
        user, "vouchers.acknowledge_bank_advice"
    ):
        return query.filter(accounting_department=department)
    if has_explicit_permission(user, "vouchers.submit_bank_advice"):
        return query.filter(
            Q(accounting_department=department)
            | Q(status__in=(
                BankAdviceBatch.APPROVED,
                BankAdviceBatch.SUBMITTED,
                BankAdviceBatch.ACKNOWLEDGED,
                BankAdviceBatch.RETURNED,
                BankAdviceBatch.SUPERSEDED,
            ))
            | Q(bank_submitted_by=user)
        ).distinct()
    return query.filter(accounting_department=department)


def bank_advice_action_choices_for_user(user):
    """Expose only action filters the account may perform outside UAT preview."""
    if is_finance_uat_viewer(user) or not has_explicit_permission(user, "vouchers.view_bank_advice"):
        return ()
    return tuple(
        (action, spec["title"])
        for action, spec in BANK_ADVICE_ACTION_SPECS.items()
        if has_explicit_permission(user, spec["permission"])
    )


def bank_advice_action_queryset(user, action, *, queryset=None):
    """Return one authoritative permission-, office-, state-, and checker-scoped action queue."""
    base = visible_bank_advice_batches(user) if queryset is None else queryset
    spec = BANK_ADVICE_ACTION_SPECS.get(action)
    if (
        spec is None
        or is_finance_uat_viewer(user)
        or not has_explicit_permission(user, "vouchers.view_bank_advice")
        or not has_explicit_permission(user, spec["permission"])
    ):
        return base.none(), action if spec else "", spec
    base = base.filter(status__in=BANK_ADVICE_ATTENTION_STATUSES[action])
    if action == "awaiting_review":
        base = base.exclude(created_by=user).exclude(review_submitted_by=user)
    return base.distinct(), action, spec


def apply_bank_advice_filters(queryset, *, status="", attention=""):
    """Apply recognized source-register filters used by both My Work and the workspace."""
    if status in dict(BankAdviceBatch.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""
    if attention in BANK_ADVICE_ATTENTION_STATUSES:
        queryset = queryset.filter(status__in=BANK_ADVICE_ATTENTION_STATUSES[attention])
    else:
        attention = ""
    return queryset, status, attention
