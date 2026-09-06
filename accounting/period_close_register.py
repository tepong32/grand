from __future__ import annotations

import csv
import io
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import (
    can_approve_period_close, can_export_period_close, can_prepare_period_close,
    can_reopen_period, department_for_user,
)
from .models import AccountingAuditEvent, PeriodCloseRun


PERIOD_CLOSE_ACTION_SPECS = {
    "needs_preparation": {
        "permission_check": can_prepare_period_close,
        "title": "Period-close checklists to prepare or correct",
        "definition": "Draft or returned period-close evidence available to an authorized preparer.",
        "next_action": "Refresh the governed checklist from current evidence, resolve required failures, and submit it for independent close review.",
    },
    "awaiting_review": {
        "permission_check": can_approve_period_close,
        "title": "Period closes for independent review",
        "definition": "Submitted close evidence awaiting a decision by someone other than its preparer or submitter.",
        "next_action": "Independently reproduce the pinned policy and current close evidence, then close the period or return the checklist.",
    },
    "awaiting_reopen_decision": {
        "permission_check": can_reopen_period,
        "title": "Period reopen requests for independent decision",
        "definition": "Closed periods with retained reopen authority awaiting a decision by someone other than the requester.",
        "next_action": "Verify the retained correction authority and period chronology, then approve the reopen or keep the period closed.",
    },
}

PERIOD_CLOSE_ATTENTION_CHOICES = tuple(
    (action, spec["title"]) for action, spec in PERIOD_CLOSE_ACTION_SPECS.items()
)

PERIOD_CLOSE_ATTENTION_STATUSES = {
    "needs_preparation": (PeriodCloseRun.DRAFT, PeriodCloseRun.RETURNED),
    "awaiting_review": (PeriodCloseRun.SUBMITTED,),
    "awaiting_reopen_decision": (PeriodCloseRun.REOPEN_REQUESTED,),
}

PERIOD_CLOSE_REGISTER_COLUMNS = (
    "period", "close_run_public_id", "version", "supersedes_public_id", "period_status",
    "policy_public_id", "policy_version", "policy_mode", "policy_status", "policy_checksum",
    "checklist_checksum", "checklist_ready", "required_failure_count", "warning_count",
    "check_statuses", "status", "next_action", "state_version", "adjustment_review_note",
    "evidence_reference", "preparer_note", "prepared_by", "prepared_at", "submitted_by",
    "submitted_at", "decided_by", "decided_at", "review_note", "reopen_requested_by",
    "reopen_requested_at", "reopen_reason", "reopen_authority_reference", "reopened_by",
    "reopened_at", "reopen_review_note", "last_event", "last_event_reason", "last_event_at",
    "updated_at",
)


def period_close_runs_for_department(department):
    if department is None:
        return PeriodCloseRun.objects.none()
    return PeriodCloseRun.objects.filter(department_id=department.pk).select_related(
        "period", "policy", "supersedes",
    )


def period_close_action_choices_for_user(user):
    """Expose only actions the current non-UAT account can actually perform."""
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user) or department_for_user(user) is None:
        return ()
    return tuple(
        (action, spec["title"])
        for action, spec in PERIOD_CLOSE_ACTION_SPECS.items()
        if spec["permission_check"](user)
    )


def period_close_action_queryset(user, action, *, queryset=None):
    """Return one permission-, office-, state-, checker-, and UAT-scoped close queue."""
    from vouchers.roles import is_finance_uat_viewer

    spec = PERIOD_CLOSE_ACTION_SPECS.get(action)
    department = department_for_user(user)
    base = period_close_runs_for_department(department) if queryset is None else queryset
    if (
        spec is None or department is None or is_finance_uat_viewer(user)
        or not spec["permission_check"](user)
    ):
        return base.none(), action if spec else "", spec
    base = base.filter(
        department_id=department.pk, status__in=PERIOD_CLOSE_ATTENTION_STATUSES[action],
    )
    if action == "awaiting_review":
        base = base.exclude(prepared_by_id=user.pk).exclude(submitted_by_id=user.pk)
    elif action == "awaiting_reopen_decision":
        base = base.exclude(reopen_requested_by_id=user.pk)
    return base.distinct(), action, spec


def apply_period_close_filters(queryset, *, status="", attention="", actor=None):
    """Apply the source-register filters shared by screen, export, counts, and tasks."""
    if status in dict(PeriodCloseRun.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""
    if actor is not None and attention in PERIOD_CLOSE_ACTION_SPECS:
        queryset, attention, _spec = period_close_action_queryset(
            actor, attention, queryset=queryset,
        )
    elif attention in PERIOD_CLOSE_ATTENTION_STATUSES:
        queryset = queryset.filter(status__in=PERIOD_CLOSE_ATTENTION_STATUSES[attention])
    else:
        attention = ""
    return queryset, status, attention


def next_period_close_action(run):
    if run.status == PeriodCloseRun.DRAFT:
        return "Refresh current evidence, resolve required gates, and submit for independent close"
    if run.status == PeriodCloseRun.RETURNED:
        return "Resolve the retained review reason, refresh current evidence, and resubmit"
    if run.status == PeriodCloseRun.SUBMITTED:
        return "Independent Accounting reviewer reproduces the evidence and decides the close"
    if run.status == PeriodCloseRun.CLOSED:
        return "Retain the close evidence; request a governed reopen only with correction authority"
    if run.status == PeriodCloseRun.REOPEN_REQUESTED:
        return "Independent reviewer verifies authority and chronology, then decides the reopen"
    return "Prepare a successor close checklist after the governed correction is posted"


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def build_period_close_register(*, actor, queryset, status="", attention=""):
    department = department_for_user(actor)
    if department is None or not can_export_period_close(actor):
        raise PermissionDenied
    if queryset.exclude(department_id=department.pk).exists():
        raise ValidationError("The period-close register may contain only the acting Accounting department.")

    runs = list(queryset.select_related("period", "policy", "supersedes").prefetch_related("events"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(PERIOD_CLOSE_REGISTER_COLUMNS)
    for run in runs:
        events = list(run.events.all())
        last_event = events[0] if events else None
        checklist = run.checklist_snapshot or {}
        checks = checklist.get("checks", [])
        writer.writerow(tuple(_csv_safe(value) for value in (
            str(run.period), run.public_id, run.version,
            run.supersedes.public_id if run.supersedes_id else "", run.period.get_status_display(),
            run.policy.public_id, run.policy_snapshot.get("version", run.policy.version),
            run.policy_snapshot.get("mode", run.policy.mode), run.policy.get_status_display(),
            run.policy_checksum, run.checklist_checksum, checklist.get("ready", False),
            checklist.get("required_failure_count", 0), checklist.get("warning_count", 0),
            json.dumps({item.get("code"): item.get("status") for item in checks}, sort_keys=True),
            run.get_status_display(), next_period_close_action(run), run.state_version,
            run.adjustment_review_note, run.evidence_reference, run.preparer_note,
            run.prepared_by_label, run.prepared_at.isoformat(), run.submitted_by_label,
            run.submitted_at.isoformat() if run.submitted_at else "", run.decided_by_label,
            run.decided_at.isoformat() if run.decided_at else "", run.review_note,
            run.reopen_requested_by_label,
            run.reopen_requested_at.isoformat() if run.reopen_requested_at else "",
            run.reopen_reason, run.reopen_authority_reference, run.reopened_by_label,
            run.reopened_at.isoformat() if run.reopened_at else "", run.reopen_review_note,
            last_event.action if last_event else "", last_event.reason if last_event else "",
            last_event.created_at.isoformat() if last_event else "", run.updated_at.isoformat(),
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    suffix = "-".join(slugify(value) for value in (attention, status) if value) or "all-visible"
    filename = f"finance-period-close-register-{suffix}.csv"
    metadata = {
        "kind": "finance_period_close_register", "status_filter": status or "all",
        "attention_filter": attention or "all", "close_run_count": len(runs),
        "authority_boundary": (
            "Operational period-close evidence only; this register is not a signed close packet, "
            "reopen authority, or proof that local policy and forms have been accepted."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-period-close-register", filename=filename, metadata=metadata,
    )
    AccountingAuditEvent.objects.create(
        department_id=department.pk, department_label=department.name,
        action="period_close_register_exported", actor_id=actor.pk,
        actor_label=actor.get_full_name() or actor.username,
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt
