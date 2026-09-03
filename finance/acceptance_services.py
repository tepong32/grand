from __future__ import annotations

import csv
import io

from django.utils import timezone

from src.export_archive import archive_export

from .cutover_services import cutover_readiness
from .models import (
    FinanceAuditEvent,
    FinanceCutoverDecision,
    FinanceCutoverReadinessExercise,
    FinanceCutoverReadinessPlan,
    FinanceDiscoveryDecision,
    FinanceShadowReconciliationPlan,
    FinanceShadowSourceVersion,
)


def _check_map(readiness):
    return {item["code"]: item for item in readiness["checks"]}


def _all_pass(checks, *codes):
    return all(checks.get(code, {}).get("passed", False) for code in codes)


def _state(*, passed, started):
    if passed:
        return "accepted", "Evidence accepted"
    if started:
        return "action", "Action needed"
    return "not_started", "Not started"


def _milestone(code, title, purpose, *, passed, started, evidence, next_action):
    state, state_label = _state(passed=passed, started=started)
    return {
        "code": code,
        "title": title,
        "purpose": purpose,
        "passed": passed,
        "state": state,
        "state_label": state_label,
        "evidence": evidence,
        "next_action": next_action,
    }


def build_field_acceptance_board(cycle):
    """Summarize existing governed evidence without creating a parallel approval record."""
    readiness = cutover_readiness(cycle)
    checks = _check_map(readiness)
    current_source = cycle.source_versions.filter(is_current=True).order_by("-version", "-pk").first()
    source_review_ok = bool(
        current_source
        and current_source.review_status
        in {FinanceShadowSourceVersion.NOT_REQUIRED, FinanceShadowSourceVersion.ACCEPTED}
        and current_source.source_checksum == cycle.source_checksum
        and current_source.schema_signature == cycle.source_schema_signature
    )
    reconciliation_plan = FinanceShadowReconciliationPlan.objects.filter(cycle=cycle).first()
    readiness_plan = FinanceCutoverReadinessPlan.objects.filter(cycle=cycle).first()
    exercises = list(cycle.cutover_readiness_exercises.all())
    role_exercises = [
        item for item in exercises if item.kind == FinanceCutoverReadinessExercise.ROLE_TRAINING
    ]
    nonfunctional_exercises = [
        item for item in exercises if item.kind != FinanceCutoverReadinessExercise.ROLE_TRAINING
    ]
    recovery_exercises = [
        item for item in exercises if item.kind == FinanceCutoverReadinessExercise.BACKUP_RESTORE
    ]
    qualification_plan = getattr(cycle, "cutover_qualification_plan", None)
    qualification_rows = list(qualification_plan.cycle_evidence.all()) if qualification_plan else []
    stakeholders = list(cycle.stakeholder_acceptances.all())
    decision = FinanceCutoverDecision.objects.filter(cycle=cycle).first()
    discovery_decisions = cycle.discovery_decisions.exclude(
        status="superseded",
    )
    discovery_decision_count = discovery_decisions.count()
    discovery_blocking_count = discovery_decisions.filter(
        blocks_affected_scope=True,
    ).count()
    coverage_labels = dict(FinanceDiscoveryDecision.COVERAGE_KIND_CHOICES)

    plans_passed = bool(
        reconciliation_plan
        and reconciliation_plan.status == FinanceShadowReconciliationPlan.APPROVED
        and _all_pass(checks, "readiness_plan_approved")
    )
    source_evidence = (
        f"Current source v{current_source.version}; {current_source.get_review_status_display()}; "
        f"file and layout locks match the cycle."
        if source_review_ok
        else (
            "A current source version exists, but its lock or independent layout-drift decision is incomplete."
            if current_source
            else "No governed current source version is retained for this cycle."
        )
    )
    milestones = [
        _milestone(
            "source_layout",
            "1. Redacted source and layout",
            "Lock the actual comparison source and confirm any changed headings before field use.",
            passed=source_review_ok,
            started=bool(current_source or cycle.source_checksum),
            evidence=source_evidence,
            next_action="Stage the current redacted CSV or external lock, then obtain independent drift review when headings changed.",
        ),
        _milestone(
            "local_plans",
            "2. Local cadence, procedures, and support",
            "Approve the office's actual comparison cadence, defect escalation, curriculum, quick guide, and support route.",
            passed=plans_passed,
            started=bool(reconciliation_plan or readiness_plan),
            evidence=(
                f"Reconciliation plan: {reconciliation_plan.get_status_display() if reconciliation_plan else 'missing'}; "
                f"readiness/support plan: {readiness_plan.get_status_display() if readiness_plan else 'missing'}."
            ),
            next_action="Complete both editable plans and send each to a different authorized reviewer.",
        ),
        _milestone(
            "role_exercises",
            "3. Department role exercises",
            "Give every named stakeholder a real, independently witnessed exercise for the exact enabled scope.",
            passed=_all_pass(checks, "role_exercises_passed"),
            started=bool(role_exercises or stakeholders),
            evidence=(
                "Every named stakeholder has a witnessed passing role exercise."
                if _all_pass(checks, "role_exercises_passed")
                else f"{len(role_exercises)} role exercise(s) recorded; {len(readiness['role_training_missing'])} stakeholder(s) still lack a pass."
            ),
            next_action="Assign missing stakeholders, schedule their role exercise, record the observable result, and have the different witness decide it.",
        ),
        _milestone(
            "nonfunctional_exercises",
            "4. Practical operating exercises",
            "Test security, privacy, accessibility, performance, printing, continuity, incident support, and recovery under local conditions.",
            passed=_all_pass(checks, "nonfunctional_exercises_passed", "all_exercises_closed"),
            started=bool(nonfunctional_exercises),
            evidence=(
                "All required practical exercises have a final witnessed pass."
                if _all_pass(checks, "nonfunctional_exercises_passed", "all_exercises_closed")
                else "Missing passed kinds: " + (", ".join(readiness["missing_exercises"]) or "none; one or more scheduled exercises is still open")
            ),
            next_action="Use locally accepted devices, volume, paper, timings, and pass conditions; rerun every returned or unfinished exercise.",
        ),
        _milestone(
            "recovery_rehearsal",
            "5. Two-store backup and restore rehearsal",
            "Prove an off-host backup can restore both GRAND stores and their linked Finance evidence in an isolated environment.",
            passed=FinanceCutoverReadinessExercise.BACKUP_RESTORE not in readiness["missing_exercises"],
            started=bool(recovery_exercises),
            evidence=(
                "A structured recovery rehearsal has an independent witnessed pass."
                if FinanceCutoverReadinessExercise.BACKUP_RESTORE not in readiness["missing_exercises"]
                else f"{len(recovery_exercises)} recovery exercise record(s); no qualifying witnessed pass yet."
            ),
            next_action="Bind the exact backup set, hashes, RPO/RTO, restored stores, reconciled controls, cross-store case, runtime checks, exceptions, and disposal evidence.",
        ),
        _milestone(
            "accepted_forms",
            "6. Exact accepted local forms",
            "Pin every applicable current F10.2 form version used by the field-cycle qualification plan.",
            passed=_all_pass(checks, "qualification_plan_approved", "accepted_local_forms_current"),
            started=bool(qualification_plan),
            evidence=(
                f"{len(readiness['qualification_form_ids'])} current accepted form version(s) are pinned to the approved plan."
                if _all_pass(checks, "qualification_plan_approved", "accepted_local_forms_current")
                else "The qualification plan is missing, unapproved, or does not pin a complete current accepted-form set."
            ),
            next_action="Accept the actual local form versions in F10.2, select every applicable one here, explain its use, and obtain independent plan approval.",
        ),
        _milestone(
            "field_cycles",
            "7. Consecutive field-cycle qualification",
            "Run the locally approved number of uninterrupted field cycles, including a parallel cycle when required.",
            passed=_all_pass(
                checks,
                "qualification_forms_match",
                "consecutive_field_cycles_accepted",
                "parallel_field_cycle_accepted",
            ),
            started=bool(qualification_rows),
            evidence=(
                f"{len(readiness['accepted_qualification_cycle_ids'])} field cycle(s) are independently accepted in the current chain."
            ),
            next_action="Record each real reconciled cycle from oldest to newest and have a different reviewer accept the field packet and exact form set.",
        ),
        _milestone(
            "cycle_reconciliation",
            "8. Final cycle reconciliation",
            "Close every comparison and defect, then independently reconcile the exact candidate cycle.",
            passed=_all_pass(checks, "shadow_reconciled"),
            started=bool(cycle.comparisons.exists() or cycle.status != cycle.DRAFT),
            evidence=checks["shadow_reconciled"]["message"],
            next_action="Resolve owned differences, finish scheduled reconciliation runs, submit the locked cycle, and obtain independent reconciliation.",
        ),
        _milestone(
            "stakeholder_decisions",
            "9. Named-office decisions",
            "Collect separate, attributable decisions from requesting offices, Budget, Accounting, Treasury, IT, management, and audit.",
            passed=_all_pass(
                checks,
                "stakeholders_present",
                "stakeholders_accepted",
                "stakeholder_decisions_retained",
            ),
            started=bool(stakeholders),
            evidence=(
                f"{len(stakeholders)} stakeholder row(s); {len(readiness['missing'])} required kind(s) missing; "
                f"{len(readiness['unsigned_stakeholder_ids'])} accepted decision(s) lack retained record locks."
            ),
            next_action="Each named reviewer records their own exact-scope decision and the reference plus SHA-256 of the retained attributable record.",
        ),
        _milestone(
            "cutover_authority",
            "10. Cutover authority and rollback",
            "Record go/no-go only after every gate passes; preserve the exact scope, date, authority, recovery evidence, and rollback criteria.",
            passed=bool(decision and decision.status == FinanceCutoverDecision.AUTHORIZED),
            started=bool(decision),
            evidence=(
                f"Cutover decision: {decision.get_status_display()}."
                if decision else "No cutover decision record exists. GRAND remains in shadow/UAT mode."
            ),
            next_action="Prepare the authority record last; a different authorized official decides it. Invoke the retained rollback route if a recorded criterion occurs.",
        ),
    ]
    accepted_count = sum(item["passed"] for item in milestones)
    return {
        "cycle": cycle,
        "milestones": milestones,
        "accepted_count": accepted_count,
        "total_count": len(milestones),
        "percent": round(100 * accepted_count / len(milestones)),
        "cutover_ready": readiness["ready"],
        "authorized": bool(decision and decision.status == FinanceCutoverDecision.AUTHORIZED),
        "decision": decision,
        "decision_status": decision.status if decision else "not_prepared",
        "discovery_decision_count": discovery_decision_count,
        "discovery_blocking_count": discovery_blocking_count,
        "discovery_scope_accepted": _all_pass(checks, "discovery_scope_accepted"),
        "discovery_dimensions_accepted": _all_pass(checks, "discovery_dimensions_accepted"),
        "missing_discovery_kinds": readiness["missing_discovery_kinds"],
        "missing_discovery_labels": [
            coverage_labels[kind] for kind in readiness["missing_discovery_kinds"]
        ],
    }


def export_field_acceptance_board(cycle, actor):
    board = build_field_acceptance_board(cycle)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "cycle_code",
            "fiscal_year",
            "enabled_scope",
            "checkpoint_code",
            "checkpoint",
            "evidence_state",
            "gate_passed",
            "current_evidence",
            "next_action",
            "grand_authorized",
            "linked_discovery_decisions",
            "linked_scope_blockers",
            "missing_discovery_coverage",
        )
    )
    for milestone in board["milestones"]:
        writer.writerow(
            (
                cycle.code,
                cycle.fiscal_year,
                cycle.enabled_scope,
                milestone["code"],
                milestone["title"],
                milestone["state_label"],
                "yes" if milestone["passed"] else "no",
                milestone["evidence"],
                milestone["next_action"],
                "yes" if board["authorized"] else "no",
                board["discovery_decision_count"],
                board["discovery_blocking_count"],
                ", ".join(board["missing_discovery_labels"]),
            )
        )
    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    filename = f"{cycle.code}-field-acceptance-board.csv"
    receipt = archive_export(
        content=content,
        department=cycle.department,
        user=actor,
        category="finance-field-acceptance",
        filename=filename,
        metadata={
            "cycle_public_id": str(cycle.public_id),
            "cycle_status": cycle.status,
            "accepted_checkpoints": board["accepted_count"],
            "total_checkpoints": board["total_count"],
            "grand_authorized": board["authorized"],
            "linked_discovery_decisions": board["discovery_decision_count"],
            "linked_scope_blockers": board["discovery_blocking_count"],
            "missing_discovery_coverage": board["missing_discovery_kinds"],
        },
    )
    FinanceAuditEvent.objects.create(
        department=cycle.department,
        target_type="financeshadowcycle",
        target_id=str(cycle.pk),
        action="field_acceptance_board_exported",
        actor=actor,
        snapshot={
            "relative_path": receipt["relative_path"],
            "sha256": receipt["sha256"],
            "accepted_checkpoints": board["accepted_count"],
            "total_checkpoints": board["total_count"],
            "grand_authorized": board["authorized"],
            "exported_at": timezone.now().isoformat(),
        },
    )
    return content, filename, receipt
