from __future__ import annotations

from .access import department_for_user, has_explicit_permission
from .models import ReturnedInstrumentReview
from .roles import is_finance_uat_viewer


RETURNED_INSTRUMENT_ATTENTION_CHOICES = (
    ("accounting_review", "Returned payments awaiting Accounting decision"),
    ("treasury_clarification", "Returned payments sent back for Treasury clarification"),
    ("treasury_replacement", "Returned payments cleared for controlled replacement"),
)

RETURNED_INSTRUMENT_ATTENTION_SPECS = {
    "accounting_review": {
        "permission": "vouchers.review_returned_instruments",
        "status": ReturnedInstrumentReview.AWAITING_REVIEW,
        "title": "Returned payments awaiting Accounting decision",
        "definition": "Current returned-instrument review versions awaiting an independent Accounting decision.",
        "next_action": "Review the bank-return evidence and applicable posting rule, then decide or return for clarification.",
        "scope_kind": "accounting",
    },
    "treasury_clarification": {
        "permission": "vouchers.manage_payment_exceptions",
        "status": ReturnedInstrumentReview.RETURNED_FOR_CLARIFICATION,
        "title": "Returned payments sent back for Treasury clarification",
        "definition": "Current review versions returned by Accounting to their owning Treasury office for more evidence.",
        "next_action": "Record the requested clarification and retained evidence to create a traceable successor.",
        "scope_kind": "treasury",
    },
    "treasury_replacement": {
        "permission": "vouchers.issue_payment_instruments",
        "status": ReturnedInstrumentReview.READY_FOR_TREASURY,
        "title": "Returned payments cleared for controlled replacement",
        "definition": "Accounting-complete returned payments whose approved outcome permits a controlled replacement instrument.",
        "next_action": "Open the shared case and issue the linked replacement without reusing or editing the returned check.",
        "scope_kind": "treasury",
    },
}


def returned_instrument_attention_choices_for_user(user):
    """Show only work kinds the current account could actually perform."""
    if is_finance_uat_viewer(user):
        return ()
    labels = dict(RETURNED_INSTRUMENT_ATTENTION_CHOICES)
    return tuple(
        (attention, labels[attention])
        for attention, spec in RETURNED_INSTRUMENT_ATTENTION_SPECS.items()
        if has_explicit_permission(user, spec["permission"])
    )


def _base_query():
    return ReturnedInstrumentReview.objects.select_related(
        "case", "case__configuration_release", "instrument", "exception__policy__treasury_department",
        "prepared_by", "reviewed_by", "posting_request",
    )


def visible_returned_instrument_reviews(user):
    """Preserve the established role-shaped returned-item register scope."""
    query = _base_query()
    department = department_for_user(user)
    if department is None:
        return query.none()
    if has_explicit_permission(user, "vouchers.review_returned_instruments"):
        return query.filter(case__configuration_release__department=department)
    return query.filter(exception__policy__treasury_department=department)


def returned_instrument_attention_queryset(user, attention):
    """Return one exact actionable returned-item state for both source and My Work."""
    spec = RETURNED_INSTRUMENT_ATTENTION_SPECS.get(attention)
    query = _base_query()
    if spec is None:
        return query.none(), "", None
    if is_finance_uat_viewer(user) or not has_explicit_permission(user, spec["permission"]):
        return query.none(), attention, spec
    department = department_for_user(user)
    if department is None:
        return query.none(), attention, spec
    query = query.filter(status=spec["status"])
    if spec["scope_kind"] == "accounting":
        query = query.filter(case__configuration_release__department=department)
    else:
        query = query.filter(exception__policy__treasury_department=department)
    if attention == "treasury_replacement":
        query = query.filter(outcome=ReturnedInstrumentReview.REISSUE)
    return query, attention, spec
