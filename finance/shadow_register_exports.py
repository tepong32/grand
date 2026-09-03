from __future__ import annotations

import csv
import io

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.text import slugify

from src.export_archive import archive_export

from .acceptance_services import build_field_acceptance_board
from .access import can_view_shadow_cycle, department_for_user
from .models import (
    FinanceAuditEvent, FinanceCutoverDecision, FinanceShadowComparison, FinanceShadowCycle,
    FinanceShadowDefect, FinanceShadowReconciliationRun,
)


ATTENTION_CHOICES = (
    ("needs_source", "Draft needs its redacted source lock"),
    ("ready_to_prepare", "Draft has a source lock; complete local plans"),
    ("running", "Field cycle in progress"),
    ("for_review", "Waiting for independent reconciliation"),
    ("reconciled_no_authority", "Reconciled; remaining gates or authority"),
    ("authorized", "Explicitly authorized scope"),
    ("returned", "Returned; another cycle required"),
)

SHADOW_REGISTER_COLUMNS = (
    "cycle_public_id", "cycle_code", "title", "department", "fiscal_year", "run_kind",
    "planned_start", "planned_end", "status", "next_action", "enabled_scope",
    "source_system", "source_reference", "source_checksum", "source_schema_signature",
    "current_source_version", "current_source_review", "comparison_count",
    "matched_comparison_count", "explained_comparison_count", "open_comparison_count",
    "defect_count", "open_defect_count", "resolution_review_count", "resolved_defect_count",
    "reconciliation_run_count", "actionable_run_count", "submitted_run_count",
    "reviewed_run_count", "stakeholder_count", "accepted_stakeholder_count",
    "linked_discovery_decisions", "linked_scope_blockers", "missing_discovery_coverage",
    "accepted_checkpoints", "total_checkpoints", "completion_percent", "cutover_ready",
    "decision_status", "grand_authorized", "evidence_checksum", "predecessor_code",
    "created_by", "created_at", "submitted_by", "submitted_at", "reconciled_by",
    "reconciled_at", "last_audit_action", "last_audit_reason", "last_audit_at",
)


def apply_shadow_cycle_filters(
    queryset, *, status="", run_kind="", fiscal_year="", attention="", search="",
):
    if status in dict(FinanceShadowCycle.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    elif status:
        queryset = queryset.none()
    else:
        status = ""

    if run_kind in dict(FinanceShadowCycle.RUN_KIND_CHOICES):
        queryset = queryset.filter(run_kind=run_kind)
    elif run_kind:
        queryset = queryset.none()
    else:
        run_kind = ""

    available_years = {str(value) for value in queryset.values_list("fiscal_year", flat=True)}
    if fiscal_year:
        if fiscal_year in available_years:
            queryset = queryset.filter(fiscal_year=fiscal_year)
        else:
            queryset = queryset.none()

    if attention == "needs_source":
        queryset = queryset.filter(status=FinanceShadowCycle.DRAFT).filter(
            Q(source_checksum="") | Q(source_schema_signature=""),
        )
    elif attention == "ready_to_prepare":
        queryset = queryset.filter(status=FinanceShadowCycle.DRAFT).exclude(
            Q(source_checksum="") | Q(source_schema_signature=""),
        )
    elif attention == "running":
        queryset = queryset.filter(status=FinanceShadowCycle.RUNNING)
    elif attention == "for_review":
        queryset = queryset.filter(status=FinanceShadowCycle.RECONCILIATION_REVIEW)
    elif attention == "reconciled_no_authority":
        queryset = queryset.filter(status=FinanceShadowCycle.RECONCILED).exclude(
            cutover_decision__status=FinanceCutoverDecision.AUTHORIZED,
        )
    elif attention == "authorized":
        queryset = queryset.filter(cutover_decision__status=FinanceCutoverDecision.AUTHORIZED)
    elif attention == "returned":
        queryset = queryset.filter(status=FinanceShadowCycle.RETURNED)
    elif attention:
        queryset = queryset.none()
    else:
        attention = ""

    search = (search or "").strip()[:160]
    if search:
        queryset = queryset.filter(
            Q(code__icontains=search) | Q(title__icontains=search)
            | Q(enabled_scope__icontains=search) | Q(source_system_label__icontains=search)
            | Q(source_extract_reference__icontains=search),
        )
    return queryset, status, run_kind, fiscal_year, attention, search


def next_shadow_cycle_action(cycle, board=None):
    try:
        decision = cycle.cutover_decision
    except FinanceCutoverDecision.DoesNotExist:
        decision = None
    if decision and decision.status == FinanceCutoverDecision.AUTHORIZED:
        return "Operate only the exact authorized scope/date and use the governed rollback route if triggered"
    if cycle.status == FinanceShadowCycle.DRAFT:
        if not cycle.source_checksum or not cycle.source_schema_signature:
            return "Stage the current redacted source or external lock and resolve any layout drift independently"
        return "Open the Field Acceptance Board and complete the local plans, forms, and exercises before start"
    if cycle.status == FinanceShadowCycle.RUNNING:
        return "Complete due reconciliation runs, resolve defects, and retain witnessed field evidence"
    if cycle.status == FinanceShadowCycle.RECONCILIATION_REVIEW:
        return "A different authorized reviewer decides the exact locked reconciliation evidence"
    if cycle.status == FinanceShadowCycle.RETURNED:
        return "Retain this returned cycle and prepare another linked cycle after correcting the stated gaps"
    if board:
        next_checkpoint = next((item for item in board["milestones"] if not item["passed"]), None)
        if next_checkpoint:
            return next_checkpoint["next_action"]
    return "Complete the remaining Field Acceptance Board gates and record cutover authority last"


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _actor_label(actor):
    return (actor.get_full_name() or actor.username) if actor else ""


def _iso(value):
    return value.isoformat() if value else ""


def build_shadow_cycle_register(
    *, actor, queryset, status="", run_kind="", fiscal_year="", attention="", search="",
):
    cycles = list(queryset.select_related(
        "department", "predecessor", "created_by", "submitted_by", "reconciled_by",
        "cutover_decision",
    ).prefetch_related(
        "source_versions", "comparisons", "defects", "reconciliation_runs",
        "stakeholder_acceptances", "cutover_readiness_exercises", "discovery_decisions",
    ))
    if any(not can_view_shadow_cycle(actor, cycle) for cycle in cycles):
        raise ValidationError("The field-operation register may contain only cycles visible to this user.")

    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(SHADOW_REGISTER_COLUMNS)
    cycle_board_summaries = {}
    for cycle in cycles:
        board = build_field_acceptance_board(cycle)
        cycle_board_summaries[cycle.pk] = {
            "accepted_checkpoints": board["accepted_count"],
            "total_checkpoints": board["total_count"],
            "grand_authorized": board["authorized"],
        }
        sources = [item for item in cycle.source_versions.all() if item.is_current]
        current_source = sorted(sources, key=lambda item: (item.version, item.pk), reverse=True)[0] if sources else None
        comparisons = list(cycle.comparisons.all())
        defects = list(cycle.defects.all())
        runs = list(cycle.reconciliation_runs.all())
        stakeholders = list(cycle.stakeholder_acceptances.all())
        audit = FinanceAuditEvent.objects.filter(
            department=cycle.department, target_type="financeshadowcycle", target_id=str(cycle.pk),
        ).first()
        decision = board["decision"]
        writer.writerow(tuple(_csv_safe(value) for value in (
            cycle.public_id, cycle.code, cycle.title, cycle.department.name, cycle.fiscal_year,
            cycle.get_run_kind_display(), cycle.planned_start, cycle.planned_end,
            cycle.get_status_display(), next_shadow_cycle_action(cycle, board), cycle.enabled_scope,
            cycle.source_system_label, cycle.source_extract_reference, cycle.source_checksum,
            cycle.source_schema_signature, current_source.version if current_source else "",
            current_source.get_review_status_display() if current_source else "",
            len(comparisons),
            sum(item.outcome == FinanceShadowComparison.MATCHED for item in comparisons),
            sum(item.outcome == FinanceShadowComparison.EXPLAINED for item in comparisons),
            sum(item.outcome == FinanceShadowComparison.OPEN_DEFECT for item in comparisons),
            len(defects), sum(item.status == FinanceShadowDefect.OPEN for item in defects),
            sum(item.status == FinanceShadowDefect.RESOLUTION_REVIEW for item in defects),
            sum(item.status == FinanceShadowDefect.RESOLVED for item in defects), len(runs),
            sum(item.status in {FinanceShadowReconciliationRun.OPEN, FinanceShadowReconciliationRun.RETURNED} for item in runs),
            sum(item.status == FinanceShadowReconciliationRun.SUBMITTED for item in runs),
            sum(item.status in {FinanceShadowReconciliationRun.RECONCILED, FinanceShadowReconciliationRun.REVIEWED_WITH_EXCEPTIONS} for item in runs),
            len(stakeholders), sum(item.decision == item.ACCEPTED for item in stakeholders),
            board["discovery_decision_count"], board["discovery_blocking_count"],
            ", ".join(board["missing_discovery_labels"]), board["accepted_count"],
            board["total_count"], board["percent"], board["cutover_ready"],
            decision.get_status_display() if decision else "Not prepared", board["authorized"],
            cycle.evidence_checksum, cycle.predecessor.code if cycle.predecessor_id else "",
            _actor_label(cycle.created_by), _iso(cycle.created_at), _actor_label(cycle.submitted_by),
            _iso(cycle.submitted_at), _actor_label(cycle.reconciled_by), _iso(cycle.reconciled_at),
            audit.action if audit else "", audit.reason if audit else "", _iso(audit.created_at) if audit else "",
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    suffix = "-".join(slugify(value) for value in (
        attention, status, run_kind, f"fy-{fiscal_year}" if fiscal_year else "", search,
    ) if value) or "all-visible"
    filename = f"finance-field-operation-register-{suffix}.csv"
    departments = sorted({cycle.department_id for cycle in cycles})
    if len(departments) == 1:
        # Keep a single-office register with the office that owns the exported
        # records, including when an assigned cross-office reviewer exports it.
        archive_department = cycles[0].department
    else:
        # A mixed-office or empty view has no single data owner, so retain it
        # under the exporting user's assigned office and describe the owners in
        # the manifest metadata below.
        archive_department = department_for_user(actor)
    if archive_department is None:
        raise ValidationError("An export department is required for the field-operation register.")
    metadata = {
        "kind": "finance_field_operation_register", "status_filter": status or "all",
        "run_kind_filter": run_kind or "all", "fiscal_year_filter": fiscal_year or "all",
        "attention_filter": attention or "all", "search_filter": search, "cycle_count": len(cycles),
        "cycle_department_ids": departments,
        "authority_boundary": (
            "Cross-cycle field-operation oversight only. Percentages and rows do not accept a phase or authorize "
            "GRAND; only the separate exact-scope/date cutover decision can do so."
        ),
    }
    receipt = archive_export(
        content=content, department=archive_department, user=actor,
        category="finance-field-operation-register", filename=filename, metadata=metadata,
    )
    if cycles:
        FinanceAuditEvent.objects.bulk_create([
            FinanceAuditEvent(
                department=cycle.department, target_type="financeshadowcycle", target_id=str(cycle.pk),
                action="field_operation_register_exported", actor=actor,
                snapshot={
                    "relative_path": receipt["relative_path"], "sha256": receipt["sha256"],
                    "cycle_count": len(cycles), "status_filter": status or "all",
                    "run_kind_filter": run_kind or "all",
                    "fiscal_year_filter": fiscal_year or "all",
                    "attention_filter": attention or "all", "search_filter": search,
                    **cycle_board_summaries[cycle.pk],
                },
            )
            for cycle in cycles
        ])
    return content, filename, receipt
