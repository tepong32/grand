from __future__ import annotations

import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from src.export_archive import archive_export

from .access import (
    can_authorize_finance_cutover,
    can_manage_shadow_operation,
    can_review_shadow_reconciliation,
    can_view_shadow_cycle,
)
from .models import (
    FinanceAuditEvent,
    FinanceCutoverDecision,
    FinanceShadowCycle,
    FinanceStakeholderAcceptance,
)


REQUIRED_STAKEHOLDERS = {
    FinanceStakeholderAcceptance.REQUESTING_OFFICE,
    FinanceStakeholderAcceptance.BUDGET,
    FinanceStakeholderAcceptance.ACCOUNTING,
    FinanceStakeholderAcceptance.TREASURY,
    FinanceStakeholderAcceptance.IT,
    FinanceStakeholderAcceptance.MANAGEMENT,
    FinanceStakeholderAcceptance.AUDIT,
}


def _comparison_data(comparison):
    return {
        "level": comparison.comparison_level,
        "control_code": comparison.control_code,
        "label": comparison.label,
        "source_reference": comparison.source_reference,
        "grand_reference": comparison.grand_reference,
        "source_amount": comparison.source_amount,
        "grand_amount": comparison.grand_amount,
        "amount_difference": comparison.amount_difference,
        "source_count": comparison.source_count,
        "grand_count": comparison.grand_count,
        "count_difference": comparison.count_difference,
        "outcome": comparison.outcome,
        "explanation": comparison.explanation,
        "evidence_reference": comparison.evidence_reference,
        "defect_owner_id": comparison.defect_owner_id,
    }


def shadow_cycle_evidence(cycle):
    comparisons = [_comparison_data(item) for item in cycle.comparisons.order_by("comparison_level", "control_code", "pk")]
    payload = {
        "schema_version": 1,
        "cycle_public_id": str(cycle.public_id),
        "code": cycle.code,
        "title": cycle.title,
        "department_id": cycle.department_id,
        "fiscal_year": cycle.fiscal_year,
        "run_kind": cycle.run_kind,
        "enabled_scope": cycle.enabled_scope,
        "source_system_label": cycle.source_system_label,
        "source_extract_reference": cycle.source_extract_reference,
        "source_checksum": cycle.source_checksum,
        "source_schema_signature": cycle.source_schema_signature,
        "planned_start": cycle.planned_start,
        "planned_end": cycle.planned_end,
        "predecessor_public_id": str(cycle.predecessor.public_id) if cycle.predecessor_id else "",
        "comparisons": comparisons,
    }
    encoded = json.dumps(payload, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return payload, hashlib.sha256(encoded).hexdigest()


def _event(cycle, actor, action, reason="", snapshot=None):
    serializable_snapshot = json.loads(json.dumps(
        snapshot or {"cycle_public_id": str(cycle.public_id), "status": cycle.status},
        cls=DjangoJSONEncoder,
    ))
    return FinanceAuditEvent.objects.create(
        department=cycle.department,
        target_type="financeshadowcycle",
        target_id=str(cycle.pk),
        action=action,
        actor=actor,
        reason=reason,
        snapshot=serializable_snapshot,
    )


@transaction.atomic
def start_shadow_cycle(cycle, actor):
    cycle = FinanceShadowCycle.objects.select_for_update().get(pk=cycle.pk)
    if not can_manage_shadow_operation(actor, cycle.department):
        raise PermissionDenied
    if cycle.status != FinanceShadowCycle.DRAFT:
        raise ValidationError("Only a draft shadow-cycle plan can be started.")
    cycle.full_clean()
    cycle.status = FinanceShadowCycle.RUNNING
    cycle.save(update_fields=("status", "updated_at"))
    _event(cycle, actor, "shadow_cycle_started")
    return cycle


@transaction.atomic
def submit_shadow_cycle(cycle, actor):
    cycle = FinanceShadowCycle.objects.select_for_update().prefetch_related("comparisons").get(pk=cycle.pk)
    if not can_manage_shadow_operation(actor, cycle.department):
        raise PermissionDenied
    if cycle.status != FinanceShadowCycle.RUNNING:
        raise ValidationError("Only a running shadow cycle can be sent for independent reconciliation.")
    comparisons = list(cycle.comparisons.all())
    if not comparisons:
        raise ValidationError("Add at least one case, batch, period, register, ledger, or report comparison.")
    for comparison in comparisons:
        comparison.full_clean()
    open_defects = [item.control_code for item in comparisons if item.outcome == item.OPEN_DEFECT]
    if open_defects:
        raise ValidationError("Resolve or carry into a successor cycle every open defect before reconciliation review: " + ", ".join(open_defects))
    payload, checksum = shadow_cycle_evidence(cycle)
    cycle.status = FinanceShadowCycle.RECONCILIATION_REVIEW
    cycle.evidence_checksum = checksum
    cycle.submitted_by = actor
    cycle.submitted_at = timezone.now()
    cycle.save(update_fields=("status", "evidence_checksum", "submitted_by", "submitted_at", "updated_at"))
    payload["evidence_checksum"] = checksum
    _event(cycle, actor, "shadow_cycle_submitted", snapshot=payload)
    return cycle


@transaction.atomic
def review_shadow_cycle(cycle, actor, *, accept, reason):
    cycle = FinanceShadowCycle.objects.select_for_update().get(pk=cycle.pk)
    if not can_review_shadow_reconciliation(actor, cycle.department):
        raise PermissionDenied
    if cycle.status != FinanceShadowCycle.RECONCILIATION_REVIEW:
        raise ValidationError("This cycle is not awaiting reconciliation review.")
    if actor.pk == cycle.submitted_by_id:
        raise ValidationError("The shadow-cycle preparer cannot perform the independent reconciliation review.")
    if not reason.strip():
        raise ValidationError("Record the review basis or the specific return reason.")
    payload, checksum = shadow_cycle_evidence(cycle)
    if checksum != cycle.evidence_checksum:
        raise ValidationError("The comparison evidence changed after submission. Start a successor cycle rather than accepting altered evidence.")
    if accept:
        cycle.status = FinanceShadowCycle.RECONCILED
        cycle.reconciled_by = actor
        cycle.reconciled_at = timezone.now()
        action = "shadow_cycle_reconciled"
    else:
        cycle.status = FinanceShadowCycle.RETURNED
        action = "shadow_cycle_returned"
    cycle.save(update_fields=("status", "reconciled_by", "reconciled_at", "updated_at"))
    payload["evidence_checksum"] = checksum
    _event(cycle, actor, action, reason=reason, snapshot=payload)
    return cycle


@transaction.atomic
def decide_stakeholder_acceptance(acceptance, actor, *, decision, training_reference, uat_reference, reason=""):
    acceptance = FinanceStakeholderAcceptance.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=acceptance.pk)
    if acceptance.assigned_reviewer_id != actor.pk:
        raise PermissionDenied("Only the named stakeholder reviewer can record this decision.")
    if acceptance.cycle.status != FinanceShadowCycle.RECONCILED:
        raise ValidationError("Stakeholder acceptance opens only after independent shadow-cycle reconciliation.")
    if acceptance.decision != FinanceStakeholderAcceptance.PENDING:
        raise ValidationError("This stakeholder decision is already recorded and cannot be overwritten.")
    if decision not in {FinanceStakeholderAcceptance.ACCEPTED, FinanceStakeholderAcceptance.CONDITIONAL, FinanceStakeholderAcceptance.REJECTED}:
        raise ValidationError("Choose accepted, conditional, or not accepted.")
    if not training_reference.strip() or not uat_reference.strip():
        raise ValidationError("Reference both role-specific training evidence and the exact UAT scenarios reviewed.")
    if decision != FinanceStakeholderAcceptance.ACCEPTED and not reason.strip():
        raise ValidationError("State each condition or the reason the scope is not accepted.")
    acceptance.training_evidence_reference = training_reference.strip()
    acceptance.uat_evidence_reference = uat_reference.strip()
    acceptance.decision = decision
    acceptance.conditions_or_reason = reason.strip()
    acceptance.decided_by = actor
    acceptance.decided_at = timezone.now()
    acceptance.full_clean()
    acceptance.save(update_fields=(
        "training_evidence_reference", "uat_evidence_reference", "decision",
        "conditions_or_reason", "decided_by", "decided_at",
    ))
    _event(
        acceptance.cycle, actor, "stakeholder_acceptance_recorded", reason=reason,
        snapshot={
            "acceptance_id": acceptance.pk,
            "stakeholder_kind": acceptance.stakeholder_kind,
            "office_id": acceptance.office_id,
            "assigned_reviewer_id": acceptance.assigned_reviewer_id,
            "enabled_scope": acceptance.enabled_scope,
            "decision": acceptance.decision,
            "training_evidence_reference": acceptance.training_evidence_reference,
            "uat_evidence_reference": acceptance.uat_evidence_reference,
        },
    )
    return acceptance


def cutover_readiness(cycle):
    rows = list(cycle.stakeholder_acceptances.all())
    present = {row.stakeholder_kind for row in rows}
    missing = sorted(REQUIRED_STAKEHOLDERS - present)
    blocking = [
        row for row in rows
        if row.decision != FinanceStakeholderAcceptance.ACCEPTED
    ]
    checks = [
        {
            "code": "shadow_reconciled",
            "passed": cycle.status == FinanceShadowCycle.RECONCILED,
            "message": "The exact shadow-cycle evidence is independently reconciled.",
        },
        {
            "code": "stakeholders_present",
            "passed": not missing,
            "message": "All seven required stakeholder kinds have named acceptance rows." if not missing else "Missing stakeholder rows: " + ", ".join(missing),
        },
        {
            "code": "stakeholders_accepted",
            "passed": bool(rows) and not blocking,
            "message": "Every required stakeholder accepted the exact enabled scope." if rows and not blocking else "Pending, conditional, or rejected stakeholder decisions still block cutover.",
        },
    ]
    return {"ready": all(check["passed"] for check in checks), "checks": checks, "missing": missing, "blocking": blocking}


@transaction.atomic
def submit_cutover_decision(decision, actor):
    decision = FinanceCutoverDecision.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=decision.pk)
    if not can_manage_shadow_operation(actor, decision.cycle.department):
        raise PermissionDenied
    if decision.status != FinanceCutoverDecision.DRAFT:
        raise ValidationError("Only a draft cutover record can be submitted.")
    readiness = cutover_readiness(decision.cycle)
    if not readiness["ready"]:
        raise ValidationError("Cutover submission is blocked until shadow reconciliation and every required stakeholder acceptance pass.")
    decision.full_clean()
    decision.status = FinanceCutoverDecision.SUBMITTED
    decision.submitted_by = actor
    decision.submitted_at = timezone.now()
    decision.save(update_fields=("status", "submitted_by", "submitted_at"))
    _event(decision.cycle, actor, "cutover_decision_submitted", snapshot=_decision_data(decision))
    return decision


def _decision_data(decision):
    return {
        "decision_id": decision.pk,
        "status": decision.status,
        "authority_matrix_reference": decision.authority_matrix_reference,
        "enabled_scope": decision.enabled_scope,
        "cutover_at": decision.cutover_at,
        "opening_reconciliation_reference": decision.opening_reconciliation_reference,
        "rollback_criteria": decision.rollback_criteria,
        "legacy_read_only_retention_plan": decision.legacy_read_only_retention_plan,
        "backup_recovery_evidence": decision.backup_recovery_evidence,
        "prepared_by_id": decision.prepared_by_id,
        "submitted_by_id": decision.submitted_by_id,
        "decided_by_id": decision.decided_by_id,
        "decided_at": decision.decided_at,
        "decision_reason": decision.decision_reason,
    }


@transaction.atomic
def decide_cutover(decision, actor, *, authorize, reason):
    decision = FinanceCutoverDecision.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=decision.pk)
    if not can_authorize_finance_cutover(actor, decision.cycle.department):
        raise PermissionDenied
    if decision.status != FinanceCutoverDecision.SUBMITTED:
        raise ValidationError("This cutover record is not awaiting an authority decision.")
    if actor.pk in {decision.prepared_by_id, decision.submitted_by_id}:
        raise ValidationError("The preparer cannot authorize the same cutover record.")
    if not reason.strip():
        raise ValidationError("Record the authority's decision basis.")
    if authorize and not cutover_readiness(decision.cycle)["ready"]:
        raise ValidationError("The acceptance evidence no longer satisfies the cutover gate.")
    decision.status = FinanceCutoverDecision.AUTHORIZED if authorize else FinanceCutoverDecision.DECLINED
    decision.decided_by = actor
    decision.decided_at = timezone.now()
    decision.decision_reason = reason.strip()
    decision.save(update_fields=("status", "decided_by", "decided_at", "decision_reason"))
    _event(
        decision.cycle, actor,
        "finance_cutover_authorized" if authorize else "finance_cutover_declined",
        reason=reason, snapshot=_decision_data(decision),
    )
    return decision


@transaction.atomic
def record_cutover_rollback(decision, actor, *, reason):
    decision = FinanceCutoverDecision.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=decision.pk)
    if not can_authorize_finance_cutover(actor, decision.cycle.department):
        raise PermissionDenied
    if decision.status != FinanceCutoverDecision.AUTHORIZED:
        raise ValidationError("Rollback can be invoked only for an authorized cutover record.")
    if not reason.strip():
        raise ValidationError("Record the rollback criterion, incident, and immediate operating direction.")
    decision.status = FinanceCutoverDecision.ROLLED_BACK
    decision.decision_reason = f"{decision.decision_reason}\n\nROLLBACK: {reason.strip()}".strip()
    decision.save(update_fields=("status", "decision_reason"))
    _event(decision.cycle, actor, "finance_cutover_rolled_back", reason=reason, snapshot=_decision_data(decision))
    return decision


def build_cutover_evidence_package(cycle, actor):
    if not can_view_shadow_cycle(actor, cycle):
        raise PermissionDenied
    cycle_payload, computed_checksum = shadow_cycle_evidence(cycle)
    acceptances = [
        {
            "stakeholder_kind": row.stakeholder_kind,
            "office_id": row.office_id,
            "assigned_reviewer_id": row.assigned_reviewer_id,
            "enabled_scope": row.enabled_scope,
            "training_evidence_reference": row.training_evidence_reference,
            "uat_evidence_reference": row.uat_evidence_reference,
            "decision": row.decision,
            "conditions_or_reason": row.conditions_or_reason,
            "decided_by_id": row.decided_by_id,
            "decided_at": row.decided_at,
        }
        for row in cycle.stakeholder_acceptances.order_by("stakeholder_kind", "office_id", "pk")
    ]
    try:
        decision = cycle.cutover_decision
    except FinanceCutoverDecision.DoesNotExist:
        decision = None
    payload = {
        "format": "GRAND Finance shadow/cutover evidence",
        "schema_version": 1,
        "notice": "Portable evidence copy. Authority exists only when the included decision status is authorized for its exact scope and date.",
        "cycle": cycle_payload,
        "stored_cycle_evidence_checksum": cycle.evidence_checksum,
        "computed_cycle_evidence_checksum": computed_checksum,
        "stakeholder_acceptances": acceptances,
        "cutover_readiness": {key: value for key, value in cutover_readiness(cycle).items() if key != "blocking"},
        "cutover_decision": _decision_data(decision) if decision else None,
        "exported_at": timezone.now(),
        "exported_by_id": actor.pk,
    }
    content = json.dumps(payload, cls=DjangoJSONEncoder, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    filename = f"{cycle.code}-shadow-cutover-evidence.json"
    receipt = archive_export(
        content=content,
        department=cycle.department,
        user=actor,
        category="finance-shadow-cutover",
        filename=filename,
        metadata={
            "cycle_public_id": str(cycle.public_id),
            "cycle_status": cycle.status,
            "cutover_status": decision.status if decision else "not_prepared",
            "cycle_evidence_checksum": cycle.evidence_checksum,
        },
    )
    _event(cycle, actor, "shadow_cutover_evidence_exported", snapshot={
        "relative_path": receipt["relative_path"], "sha256": receipt["sha256"],
    })
    return content, filename, receipt
