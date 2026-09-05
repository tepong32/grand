from __future__ import annotations

import csv
import io
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import (
    can_approve_bank_reconciliation, can_export_bank_reconciliation,
    can_prepare_bank_reconciliation, can_view_bank_reconciliation, department_for_user,
)
from .models import AccountingAuditEvent, BankStatementBatch, Fund
from .services import bank_reconciliation_snapshot


ATTENTION_CHOICES = (
    ("needs_statement", "Needs a statement CSV"),
    ("needs_control_correction", "Staged controls need correction"),
    ("returned_correction", "Returned for correction"),
    ("needs_matching", "Validated; match and explain items"),
    ("for_review", "Waiting for independent review"),
    ("reconciled", "Reconciled evidence"),
)

BANK_RECONCILIATION_ACTION_SPECS = {
    "needs_statement": {
        "permission_check": can_prepare_bank_reconciliation,
        "title": "Bank batches needing a statement",
        "definition": "Draft bank batches that do not yet have a staged statement source.",
        "next_action": "Stage the current bank statement CSV and validate its declared controls.",
    },
    "needs_control_correction": {
        "permission_check": can_prepare_bank_reconciliation,
        "title": "Staged bank controls to correct",
        "definition": "Staged draft statements whose declared or imported controls need correction.",
        "next_action": "Correct the declared controls or restage a reasoned source version, then validate again.",
    },
    "returned_correction": {
        "permission_check": can_prepare_bank_reconciliation,
        "title": "Returned bank reconciliations to correct",
        "definition": "Bank reconciliations returned with an independent review reason.",
        "next_action": "Resolve the retained return reason, revalidate the current evidence, and resubmit.",
    },
    "needs_matching": {
        "permission_check": can_prepare_bank_reconciliation,
        "title": "Validated bank statements to match",
        "definition": "Validated bank statements ready for exact matching, timing-item classification, zero-difference resolution, and submission.",
        "next_action": "Match statement rows, classify every ledger-only timing item, resolve the difference to zero, and submit.",
    },
    "for_review": {
        "permission_check": can_approve_bank_reconciliation,
        "title": "Bank reconciliations for independent review",
        "definition": "Zero-difference reconciliation submissions awaiting a decision by someone other than the creator or submitter.",
        "next_action": "Independently reproduce the source, matching, timing-item, and zero-difference evidence, then reconcile or return it.",
    },
}


def visible_bank_reconciliation_batches(user):
    """Return the current Accounting office's visible bank-reconciliation register."""
    department = department_for_user(user)
    if department is None or not can_view_bank_reconciliation(user):
        return BankStatementBatch.objects.none()
    return BankStatementBatch.objects.filter(department_id=department.pk)


def bank_reconciliation_action_choices_for_user(user):
    """Expose only personal actions held by a non-UAT account."""
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user) or not can_view_bank_reconciliation(user):
        return ()
    return tuple(
        (action, spec["title"])
        for action, spec in BANK_RECONCILIATION_ACTION_SPECS.items()
        if spec["permission_check"](user)
    )


def bank_reconciliation_attention_choices_for_user(user):
    """Keep completed evidence available as oversight without presenting it as work."""
    choices = list(bank_reconciliation_action_choices_for_user(user))
    if can_view_bank_reconciliation(user):
        choices.append(("reconciled", "Reconciled evidence"))
    return tuple(choices)


def bank_reconciliation_action_queryset(user, action, *, queryset=None):
    """Return one permission-, office-, state-, checker-, and UAT-scoped action queue."""
    from vouchers.roles import is_finance_uat_viewer

    spec = BANK_RECONCILIATION_ACTION_SPECS.get(action)
    base = visible_bank_reconciliation_batches(user) if queryset is None else queryset
    department = department_for_user(user)
    if (
        spec is None or department is None or is_finance_uat_viewer(user)
        or not can_view_bank_reconciliation(user) or not spec["permission_check"](user)
    ):
        return base.none(), action if spec else "", spec
    base = base.filter(department_id=department.pk)
    if action == "needs_statement":
        base = base.filter(status=BankStatementBatch.DRAFT, source_version=0)
    elif action == "needs_control_correction":
        base = base.filter(status=BankStatementBatch.DRAFT, source_version__gt=0)
    elif action == "returned_correction":
        base = base.filter(status=BankStatementBatch.RETURNED)
    elif action == "needs_matching":
        base = base.filter(status=BankStatementBatch.VALIDATED)
    else:
        base = base.filter(status=BankStatementBatch.FOR_REVIEW).exclude(
            created_by_id=user.pk,
        ).exclude(submitted_by_id=user.pk)
    return base.distinct(), action, spec

BANK_REGISTER_COLUMNS = (
    "statement_reference", "batch_public_id", "bank_name", "bank_account_code",
    "account_number_masked", "fund_code", "period_start", "period_end", "received_on",
    "opening_balance", "closing_balance", "declared_row_count", "declared_deposits",
    "declared_withdrawals", "source_version", "source_filename", "source_checksum",
    "validation_valid", "validation_errors", "status", "next_action", "snapshot_checksum",
    "statement_rows", "matched_rows", "unmatched_statement_rows", "unmatched_ledger_lines",
    "classified_outstanding", "carried_forward", "overdue_outstanding",
    "unclassified_ledger_lines", "adjusted_bank_balance", "book_balance", "difference",
    "ready_for_review", "state_version", "prepared_by", "submitted_by", "submitted_at",
    "reconciled_by", "reconciled_at", "reconciliation_checksum", "last_event",
    "last_event_reason", "last_event_at", "updated_at", "snapshot_error",
)


def apply_bank_register_filters(
    queryset, *, status="", fund="", bank_account="", period_year="", attention="", search="",
    actor=None,
):
    department_ids = queryset.values("department_id")
    if status in dict(BankStatementBatch.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    elif status:
        queryset = queryset.none()
    else:
        status = ""

    if fund:
        if fund.isdigit() and Fund.objects.filter(
            pk=fund, department_id__in=department_ids,
        ).exists():
            queryset = queryset.filter(fund_id=fund)
        else:
            queryset = queryset.none()

    available_accounts = set(queryset.values_list("bank_account_code", flat=True))
    if bank_account:
        if bank_account in available_accounts:
            queryset = queryset.filter(bank_account_code=bank_account)
        else:
            queryset = queryset.none()

    available_years = {str(value.year) for value in queryset.values_list("period_end", flat=True)}
    if period_year:
        if period_year in available_years:
            queryset = queryset.filter(period_end__year=period_year)
        else:
            queryset = queryset.none()

    if actor is not None and attention in BANK_RECONCILIATION_ACTION_SPECS:
        queryset, attention, _spec = bank_reconciliation_action_queryset(
            actor, attention, queryset=queryset,
        )
    elif attention == "needs_statement":
        queryset = queryset.filter(status=BankStatementBatch.DRAFT, source_version=0)
    elif attention == "needs_control_correction":
        queryset = queryset.filter(status=BankStatementBatch.DRAFT, source_version__gt=0)
    elif attention == "returned_correction":
        queryset = queryset.filter(status=BankStatementBatch.RETURNED)
    elif attention == "needs_matching":
        queryset = queryset.filter(status=BankStatementBatch.VALIDATED)
    elif attention == "for_review":
        queryset = queryset.filter(status=BankStatementBatch.FOR_REVIEW)
    elif attention == "reconciled":
        queryset = queryset.filter(status=BankStatementBatch.RECONCILED)
    elif attention:
        queryset = queryset.none()
    else:
        attention = ""

    search = (search or "").strip()[:160]
    if search:
        queryset = queryset.filter(
            Q(statement_reference__icontains=search) | Q(bank_name__icontains=search)
            | Q(bank_account_code__icontains=search) | Q(account_number_masked__icontains=search),
        )
    return queryset, status, fund, bank_account, period_year, attention, search


def bank_batch_snapshot(batch):
    try:
        snapshot, checksum, _rows, _matches, _unmatched, _items = bank_reconciliation_snapshot(batch)
        return snapshot, checksum, ""
    except ValidationError as exc:
        return {}, "", " ".join(exc.messages)


def next_bank_action(batch, snapshot=None, snapshot_error=""):
    snapshot = snapshot or {}
    if batch.status == BankStatementBatch.DRAFT:
        if batch.source_version == 0:
            return "Stage the current bank statement CSV and validate its controls"
        return "Correct the declared controls or restage a reasoned source version"
    if batch.status == BankStatementBatch.RETURNED:
        return "Resolve the independent review reason, revalidate, and resubmit"
    if batch.status == BankStatementBatch.FOR_REVIEW:
        return "Independent Accounting reviewer verifies zero difference and decides"
    if batch.status == BankStatementBatch.RECONCILED:
        return "Retain the approved evidence and carry unresolved items into the next statement"
    if snapshot_error:
        return "Resolve the bank-account ledger mapping or source setup before matching"
    if snapshot.get("ready_for_review"):
        return "Submit the zero-difference reconciliation for independent review"
    if snapshot.get("unmatched_statement_row_count", 0):
        return "Match each statement row to one posted bank-account JEV line"
    if snapshot.get("unclassified_ledger_line_count", 0):
        return "Explain each ledger-only line as a supported timing item or post its correction"
    if Decimal(snapshot.get("difference", "0.00")) != 0:
        return "Resolve the adjusted-bank-to-book difference through evidence or a governed JEV"
    return "Review matching and timing-item evidence before submission"


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _currency(value):
    return Decimal(value or "0.00").quantize(Decimal("0.01"))


def build_bank_control_register(
    *, actor, queryset, status="", fund="", bank_account="", period_year="", attention="", search="",
):
    department = department_for_user(actor)
    if department is None or not can_export_bank_reconciliation(actor):
        raise PermissionDenied
    if queryset.exclude(department_id=department.pk).exists():
        raise ValidationError("The bank-reconciliation register may contain only the acting Accounting department.")

    batches = list(queryset.select_related("fund").prefetch_related("events"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(BANK_REGISTER_COLUMNS)
    for batch in batches:
        snapshot, snapshot_checksum, snapshot_error = bank_batch_snapshot(batch)
        events = list(batch.events.all())
        last_event = events[0] if events else None
        validation = batch.validation_summary or {}
        writer.writerow(tuple(_csv_safe(value) for value in (
            batch.statement_reference, batch.public_id, batch.bank_name, batch.bank_account_code,
            batch.account_number_masked, batch.fund.code, batch.period_start, batch.period_end,
            batch.received_on, _currency(batch.opening_balance), _currency(batch.closing_balance),
            batch.expected_row_count, _currency(batch.expected_deposits),
            _currency(batch.expected_withdrawals), batch.source_version, batch.source_filename,
            batch.source_checksum, validation.get("valid", False),
            " | ".join(validation.get("errors", [])), batch.get_status_display(),
            next_bank_action(batch, snapshot, snapshot_error), snapshot_checksum,
            snapshot.get("statement_row_count", 0), snapshot.get("matched_row_count", 0),
            snapshot.get("unmatched_statement_row_count", 0),
            snapshot.get("unmatched_ledger_line_count", 0),
            snapshot.get("classified_outstanding_count", 0), snapshot.get("carried_forward_count", 0),
            snapshot.get("overdue_outstanding_count", 0),
            snapshot.get("unclassified_ledger_line_count", 0),
            _currency(snapshot.get("adjusted_bank_balance", "0.00")),
            _currency(snapshot.get("book_balance", "0.00")), _currency(snapshot.get("difference", "0.00")),
            snapshot.get("ready_for_review", False), batch.state_version, batch.created_by_label,
            batch.submitted_by_label, batch.submitted_at.isoformat() if batch.submitted_at else "",
            batch.reconciled_by_label, batch.reconciled_at.isoformat() if batch.reconciled_at else "",
            batch.reconciliation_checksum, last_event.action if last_event else "",
            last_event.reason if last_event else "", last_event.created_at.isoformat() if last_event else "",
            batch.updated_at.isoformat(), snapshot_error,
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    suffix = "-".join(slugify(value) for value in (
        attention, status, bank_account, f"fund-{fund}" if fund else "",
        f"year-{period_year}" if period_year else "", search,
    ) if value) or "all-visible"
    filename = f"finance-bank-reconciliation-register-{suffix}.csv"
    metadata = {
        "kind": "finance_bank_reconciliation_register", "status_filter": status or "all",
        "fund_filter": fund or "all", "bank_account_filter": bank_account or "all",
        "period_year_filter": period_year or "all", "attention_filter": attention or "all",
        "search_filter": search, "batch_count": len(batches),
        "authority_boundary": (
            "Operational bank-reconciliation control evidence only; this register is not an approved or "
            "signed BRS, a bank confirmation, or proof that a COA/local form has been accepted."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-bank-reconciliation-register", filename=filename, metadata=metadata,
    )
    AccountingAuditEvent.objects.create(
        department_id=department.pk, department_label=department.name,
        action="bank_register_exported", actor_id=actor.pk,
        actor_label=actor.get_full_name() or actor.username,
        snapshot={**metadata, "relative_path": receipt["relative_path"], "sha256": receipt["sha256"]},
    )
    return content, filename, receipt
