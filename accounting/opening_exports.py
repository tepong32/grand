from __future__ import annotations

import csv
import io

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import can_view_accounting, department_for_user
from .models import AccountingAuditEvent, OpeningBalanceBatch
from .services import actor_label


OPENING_ATTENTION_CHOICES = (
    ("needs_preparation", "Needs staging or correction"),
    ("ready_to_submit", "Ready for submission"),
    ("awaiting_review", "Awaiting independent review"),
    ("awaiting_posting", "Awaiting posting"),
    ("awaiting_reconciliation", "Awaiting reconciliation"),
    ("complete", "Reconciled / complete"),
)

OPENING_ATTENTION_STATUSES = {
    "needs_preparation": (OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED),
    "ready_to_submit": (OpeningBalanceBatch.VALIDATED,),
    "awaiting_review": (OpeningBalanceBatch.FOR_REVIEW,),
    "awaiting_posting": (OpeningBalanceBatch.APPROVED,),
    "awaiting_reconciliation": (OpeningBalanceBatch.POSTED,),
    "complete": (OpeningBalanceBatch.RECONCILED,),
}

OPENING_NEXT_ACTIONS = {
    OpeningBalanceBatch.DRAFT: "Stage or correct, then validate",
    OpeningBalanceBatch.RETURNED: "Correct returned items, then revalidate",
    OpeningBalanceBatch.VALIDATED: "Submit for independent review",
    OpeningBalanceBatch.FOR_REVIEW: "Independent reviewer: approve or return",
    OpeningBalanceBatch.APPROVED: "Authorized poster: post opening JEVs",
    OpeningBalanceBatch.POSTED: "Authorized poster: reconcile posted controls",
    OpeningBalanceBatch.RECONCILED: "Complete; retain evidence",
}

OPENING_REGISTER_COLUMNS = (
    "batch_public_id",
    "department",
    "fiscal_year",
    "period",
    "source_reference",
    "title",
    "workflow_status",
    "next_action",
    "zero_balance_declaration",
    "declared_row_count",
    "declared_debit",
    "declared_credit",
    "staged_row_count",
    "valid_row_count",
    "error_row_count",
    "staged_debit",
    "staged_credit",
    "batch_errors",
    "source_filename",
    "source_checksum",
    "prepared_by",
    "submitted_by",
    "approved_by",
    "posted_by",
    "reconciled_by",
    "state_version",
    "updated_at",
)


def _csv_safe(value):
    value = str(value or "")
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def apply_opening_filters(queryset, *, fiscal_year=None, status="", attention=""):
    """Apply only recognized F2.2 filters so screen and export remain synchronized."""
    if fiscal_year is not None:
        queryset = queryset.filter(fiscal_year=fiscal_year)
    if status in dict(OpeningBalanceBatch.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""
    if attention in OPENING_ATTENTION_STATUSES:
        queryset = queryset.filter(status__in=OPENING_ATTENTION_STATUSES[attention])
    else:
        attention = ""
    return queryset, status, attention


def next_opening_action(status):
    return OPENING_NEXT_ACTIONS.get(status, "Review current status")


def build_opening_register(department, actor, queryset, *, fiscal_year=None, status="", attention=""):
    """Build, archive, and audit the filtered department opening-control register."""
    actor_department = department_for_user(actor)
    if not can_view_accounting(actor) or actor_department is None or actor_department.pk != department.pk:
        raise PermissionDenied
    if fiscal_year is not None and fiscal_year.department_id != department.pk:
        raise ValidationError("Choose a fiscal year from the current Accounting office.")
    if queryset.exclude(department_id=department.pk).exists():
        raise ValidationError("The opening register may contain only the current Accounting office.")

    batches = list(queryset.select_related("fiscal_year", "period"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(OPENING_REGISTER_COLUMNS)
    for batch in batches:
        summary = batch.validation_summary or {}
        writer.writerow(tuple(_csv_safe(value) for value in (
            batch.public_id,
            batch.department_label,
            batch.fiscal_year.year,
            batch.period.label,
            batch.source_reference,
            batch.title,
            batch.get_status_display(),
            next_opening_action(batch.status),
            "yes" if batch.is_zero_balance_declaration else "no",
            batch.expected_row_count,
            batch.expected_debit,
            batch.expected_credit,
            summary.get("row_count", ""),
            summary.get("valid_row_count", ""),
            summary.get("error_row_count", ""),
            summary.get("debit", ""),
            summary.get("credit", ""),
            " | ".join(summary.get("batch_errors", [])),
            batch.source_filename,
            batch.source_checksum,
            batch.created_by_label,
            batch.submitted_by_label,
            batch.approved_by_label,
            batch.posted_by_label,
            batch.reconciled_by_label,
            batch.state_version,
            batch.updated_at.isoformat(),
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    year_label = str(fiscal_year.year) if fiscal_year is not None else "all-years"
    filename = f"finance-opening-register-{slugify(year_label)}.csv"
    metadata = {
        "kind": "finance_opening_control_register",
        "fiscal_year_public_id": str(fiscal_year.public_id) if fiscal_year is not None else "",
        "fiscal_year": fiscal_year.year if fiscal_year is not None else "all",
        "status_filter": status or "all",
        "attention_filter": attention or "all",
        "batch_count": len(batches),
        "authority_boundary": (
            "Opening-control oversight evidence only; this export does not approve, post, reconcile, "
            "or replace an accepted LGU/COA opening schedule."
        ),
    }
    receipt = archive_export(
        content=content,
        department=department,
        user=actor,
        category="finance-opening-register",
        filename=filename,
        metadata=metadata,
    )
    AccountingAuditEvent.objects.create(
        department_id=department.pk,
        department_label=department.name,
        action="opening_register_exported",
        actor_id=actor.pk,
        actor_label=actor_label(actor),
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt
