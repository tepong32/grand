from __future__ import annotations

import csv
import io

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.text import slugify

from src.export_archive import archive_export

from .acceptance_services import build_field_acceptance_board
from vouchers.roles import is_finance_uat_viewer

from .access import (
    can_authorize_finance_cutover,
    can_manage_shadow_operation,
    can_review_shadow_reconciliation,
    can_view_shadow_cycle,
    department_for_user,
)
from .models import (
    FinanceAuditEvent, FinanceCutoverDecision, FinanceCutoverReadinessExercise,
    FinanceShadowComparison, FinanceShadowCycle, FinanceShadowDefect,
    FinanceShadowReconciliationRun, FinanceStakeholderAcceptance,
)


ATTENTION_CHOICES = (
    ("needs_source", "Draft needs its redacted source lock"),
    ("ready_to_prepare", "Draft has a source lock; complete local plans"),
    ("running", "Field cycle in progress"),
    ("for_review", "Waiting for independent reconciliation"),
    ("my_defects", "Open defects assigned to me"),
    ("review_defects", "Defect corrections for independent review"),
    ("my_exercises", "Readiness exercises I must complete or rerun"),
    ("witness_exercises", "Readiness exercises assigned to me as witness"),
    ("my_acceptances", "Stakeholder decisions assigned to me"),
    ("authorize_cutover", "Cutover records awaiting my authority role"),
    ("reconciled_no_authority", "Reconciled; remaining gates or authority"),
    ("authorized", "Explicitly authorized scope"),
    ("returned", "Returned; another cycle required"),
)

SHADOW_ACTION_SPECS = {
    "needs_source": {
        "role": "manage",
        "title": "Field cycles needing a redacted source lock",
        "definition": "Draft cycles in the acting Finance office whose current redacted source checksum or layout signature is still missing.",
        "next_action": "Stage the redacted CSV or record the externally retained source lock before preparing the cycle controls.",
    },
    "ready_to_prepare": {
        "role": "manage",
        "title": "Field cycles whose local controls need preparation",
        "definition": "Source-locked draft cycles in the acting Finance office that still need their locally accepted plans, forms, and exercises completed before start.",
        "next_action": "Open the cycle and complete the editable local controls; submit each governed plan for independent review when ready.",
    },
    "running": {
        "role": "manage",
        "title": "Field cycles in progress",
        "definition": "Running cycles in the acting Finance office requiring comparisons, scheduled reconciliation runs, defect resolution, or final evidence submission.",
        "next_action": "Record the actual limited-run evidence and resolve every open item before submitting the locked cycle for independent reconciliation.",
    },
    "for_review": {
        "role": "review",
        "title": "Field cycles for independent reconciliation",
        "definition": "Submitted cycles in the acting Finance office awaiting a reviewer other than the cycle submitter.",
        "next_action": "Compare the locked evidence and record an independent reconcile-or-return decision without editing the submitted cycle.",
    },
    "my_defects": {
        "role": "defect_owner",
        "title": "Open field defects assigned to me",
        "definition": "Visible cycles containing an open defect that names the signed-in user as correction owner.",
        "next_action": "Open the cycle, record the correction and retained evidence on the named defect, then submit it for independent review.",
    },
    "review_defects": {
        "role": "review",
        "title": "Field-defect corrections for independent review",
        "definition": "Cycles in the acting Finance office containing submitted defect resolutions not prepared by the signed-in reviewer.",
        "next_action": "Verify the correction evidence and independently accept the resolution or reopen the defect with a reason.",
    },
    "my_exercises": {
        "role": "exercise_owner",
        "title": "Readiness exercises I must complete or rerun",
        "definition": "Visible cycles containing a planned or returned exercise that names the signed-in user as owner.",
        "next_action": "Perform the named field exercise, retain the actual result and evidence reference, then submit it to the assigned witness.",
    },
    "witness_exercises": {
        "role": "exercise_witness",
        "title": "Readiness exercises assigned to me as witness",
        "definition": "Visible cycles containing submitted exercise evidence assigned to the signed-in independent witness.",
        "next_action": "Compare what was observed with the expected result and independently pass or return the exercise.",
    },
    "my_acceptances": {
        "role": "stakeholder",
        "title": "Stakeholder decisions assigned to me",
        "definition": "Independently reconciled cycles containing a pending exact-scope stakeholder decision assigned to the signed-in reviewer.",
        "next_action": "Review the role-specific training and UAT evidence, then record the retained attributable decision for only the named scope.",
    },
    "authorize_cutover": {
        "role": "authorize",
        "title": "Cutover records awaiting my authority role",
        "definition": "Submitted cutover records in the acting Finance office that the signed-in authority did not prepare or submit.",
        "next_action": "Recheck the exact scope, date, signed authority, recovery evidence, and live acceptance gates before authorizing or declining.",
    },
}

SHADOW_OVERSIGHT_CHOICES = tuple(
    choice for choice in ATTENTION_CHOICES if choice[0] not in SHADOW_ACTION_SPECS
)


def visible_shadow_cycles(user):
    department = department_for_user(user)
    query = (
        Q(stakeholder_acceptances__assigned_reviewer=user)
        | Q(defects__owner=user)
        | Q(cutover_readiness_exercises__owner=user)
        | Q(cutover_readiness_exercises__witness=user)
    )
    if department:
        query |= Q(department=department)
    return FinanceShadowCycle.objects.filter(query).select_related(
        "department", "created_by", "submitted_by", "reconciled_by",
    ).prefetch_related("stakeholder_acceptances").distinct()


def _shadow_action_role_allowed(user, department, role):
    if is_finance_uat_viewer(user):
        return False
    if role == "manage":
        return can_manage_shadow_operation(user, department)
    if role == "review":
        return can_review_shadow_reconciliation(user, department)
    if role == "authorize":
        return can_authorize_finance_cutover(user, department)
    if role == "defect_owner":
        return user.assigned_finance_shadow_defects.filter(status=FinanceShadowDefect.OPEN).exists()
    if role == "exercise_owner":
        return user.owned_finance_cutover_readiness_exercises.filter(
            status__in=(FinanceCutoverReadinessExercise.PLANNED, FinanceCutoverReadinessExercise.RETURNED),
        ).exists()
    if role == "exercise_witness":
        return user.witnessed_finance_cutover_readiness_exercises.filter(
            status=FinanceCutoverReadinessExercise.SUBMITTED,
        ).exists()
    if role == "stakeholder":
        return user.assigned_finance_shadow_acceptances.filter(
            decision=FinanceStakeholderAcceptance.PENDING,
            cycle__status=FinanceShadowCycle.RECONCILED,
        ).exists()
    return False


def shadow_action_choices_for_user(user, department=None):
    department = department or department_for_user(user)
    labels = dict(ATTENTION_CHOICES)
    return tuple(
        (attention, labels[attention])
        for attention, spec in SHADOW_ACTION_SPECS.items()
        if _shadow_action_role_allowed(user, department, spec["role"])
    ) if department else ()


def shadow_attention_choices_for_user(user, department=None):
    return shadow_action_choices_for_user(user, department) + SHADOW_OVERSIGHT_CHOICES


def shadow_action_queryset(user, attention, *, queryset):
    spec = SHADOW_ACTION_SPECS.get(attention)
    if spec is None:
        return queryset.none(), "", None
    department = department_for_user(user)
    if department is None or not _shadow_action_role_allowed(user, department, spec["role"]):
        return queryset.none(), attention, spec

    if attention == "needs_source":
        queryset = queryset.filter(department=department, status=FinanceShadowCycle.DRAFT).filter(
            Q(source_checksum="") | Q(source_schema_signature=""),
        )
    elif attention == "ready_to_prepare":
        queryset = queryset.filter(department=department, status=FinanceShadowCycle.DRAFT).exclude(
            Q(source_checksum="") | Q(source_schema_signature=""),
        )
    elif attention == "running":
        queryset = queryset.filter(department=department, status=FinanceShadowCycle.RUNNING)
    elif attention == "for_review":
        queryset = queryset.filter(
            department=department, status=FinanceShadowCycle.RECONCILIATION_REVIEW,
        ).exclude(submitted_by=user)
    elif attention == "my_defects":
        queryset = queryset.filter(defects__owner=user, defects__status=FinanceShadowDefect.OPEN)
    elif attention == "review_defects":
        actionable_defects = FinanceShadowDefect.objects.filter(
            status=FinanceShadowDefect.RESOLUTION_REVIEW,
        ).exclude(resolution_submitted_by=user)
        queryset = queryset.filter(
            department=department,
            pk__in=actionable_defects.values("cycle_id"),
        )
    elif attention == "my_exercises":
        queryset = queryset.filter(
            cutover_readiness_exercises__owner=user,
            cutover_readiness_exercises__status__in=(
                FinanceCutoverReadinessExercise.PLANNED,
                FinanceCutoverReadinessExercise.RETURNED,
            ),
        )
    elif attention == "witness_exercises":
        actionable_exercises = FinanceCutoverReadinessExercise.objects.filter(
            witness=user,
            status=FinanceCutoverReadinessExercise.SUBMITTED,
        ).exclude(
            Q(owner=user) | Q(submitted_by=user)
        )
        queryset = queryset.filter(pk__in=actionable_exercises.values("cycle_id"))
    elif attention == "my_acceptances":
        queryset = queryset.filter(
            status=FinanceShadowCycle.RECONCILED,
            stakeholder_acceptances__assigned_reviewer=user,
            stakeholder_acceptances__decision=FinanceStakeholderAcceptance.PENDING,
        )
    elif attention == "authorize_cutover":
        queryset = queryset.filter(
            department=department,
            cutover_decision__status=FinanceCutoverDecision.SUBMITTED,
        ).exclude(
            Q(cutover_decision__prepared_by=user) | Q(cutover_decision__submitted_by=user),
        )
    return queryset.distinct(), attention, spec

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
    queryset, *, user=None, status="", run_kind="", fiscal_year="", attention="", search="",
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

    if attention in SHADOW_ACTION_SPECS:
        if user is None:
            queryset = queryset.none()
        else:
            queryset, _selected, _spec = shadow_action_queryset(
                user, attention, queryset=queryset,
            )
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
