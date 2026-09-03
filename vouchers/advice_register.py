from __future__ import annotations

from django.db.models import Q

from .access import department_for_user, has_explicit_permission
from .models import BankAdviceBatch


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
