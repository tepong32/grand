from __future__ import annotations

from .models import PeriodCloseRun


PERIOD_CLOSE_ATTENTION_CHOICES = (
    ("needs_preparation", "Draft or returned for correction"),
    ("awaiting_review", "Awaiting independent close review"),
    ("awaiting_reopen_decision", "Reopen request awaiting decision"),
)

PERIOD_CLOSE_ATTENTION_STATUSES = {
    "needs_preparation": (PeriodCloseRun.DRAFT, PeriodCloseRun.RETURNED),
    "awaiting_review": (PeriodCloseRun.SUBMITTED,),
    "awaiting_reopen_decision": (PeriodCloseRun.REOPEN_REQUESTED,),
}


def period_close_runs_for_department(department):
    if department is None:
        return PeriodCloseRun.objects.none()
    return PeriodCloseRun.objects.filter(department_id=department.pk).select_related("period", "policy")


def apply_period_close_filters(queryset, *, status="", attention=""):
    """Apply recognized source-register filters used by both My Work and the workspace."""
    if status in dict(PeriodCloseRun.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""
    if attention in PERIOD_CLOSE_ATTENTION_STATUSES:
        queryset = queryset.filter(status__in=PERIOD_CLOSE_ATTENTION_STATUSES[attention])
    else:
        attention = ""
    return queryset, status, attention
