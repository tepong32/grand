from __future__ import annotations

import csv
import hashlib
import io
import json
import re

from django.core.files.base import ContentFile
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
    FinanceShadowSourceVersion,
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

SHADOW_SOURCE_MAX_BYTES = 5 * 1024 * 1024
SENSITIVE_HEADER_TERMS = {
    "account_number", "address", "bank_account", "birth_date", "contact_number", "email",
    "employee_name", "full_name", "mobile_number", "payee_name", "phone_number", "tin",
}


def _normalized_header(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _source_version_data(item):
    return {
        "version": item.version,
        "intake_kind": item.intake_kind,
        "original_filename": item.original_filename,
        "file_size": item.file_size,
        "source_checksum": item.source_checksum,
        "normalized_headers": item.normalized_headers,
        "row_count": item.row_count,
        "schema_signature": item.schema_signature,
        "predecessor_schema_signature": item.predecessor_schema_signature,
        "schema_comparison": item.schema_comparison,
        "sensitive_header_warnings": item.sensitive_header_warnings,
        "redaction_confirmed": item.redaction_confirmed,
        "redaction_note": item.redaction_note,
        "change_reason": item.change_reason,
        "is_current": item.is_current,
        "review_status": item.review_status,
        "review_note": item.review_note,
        "staged_by_id": item.staged_by_id,
        "staged_at": item.staged_at,
        "reviewed_by_id": item.reviewed_by_id,
        "reviewed_at": item.reviewed_at,
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
    source_versions = [
        _source_version_data(item) for item in cycle.source_versions.order_by("version", "pk")
    ]
    payload = {
        "schema_version": 2,
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
        "source_versions": source_versions,
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


def _schema_comparison(cycle, schema_signature, current=None):
    reference = cycle.predecessor.source_schema_signature if cycle.predecessor_id else ""
    if not reference and current:
        reference = current.schema_signature
    if not reference:
        return FinanceShadowSourceVersion.BASELINE, ""
    if reference == schema_signature:
        return FinanceShadowSourceVersion.MATCHED, reference
    return FinanceShadowSourceVersion.DRIFT, reference


def _next_source_version(cycle):
    current = cycle.source_versions.filter(is_current=True).order_by("-version").first()
    return current, (cycle.source_versions.order_by("-version").values_list("version", flat=True).first() or 0) + 1


def _validate_replacement_reason(current, change_reason):
    if current and not str(change_reason or "").strip():
        raise ValidationError("Explain why the previously staged source is being replaced.")


@transaction.atomic
def stage_shadow_source_csv(cycle, actor, uploaded_file, *, redaction_confirmed, redaction_note, change_reason=""):
    cycle = FinanceShadowCycle.objects.select_for_update().select_related("department", "predecessor").get(pk=cycle.pk)
    if not can_manage_shadow_operation(actor, cycle.department):
        raise PermissionDenied
    if cycle.status != FinanceShadowCycle.DRAFT:
        raise ValidationError("A source can be staged only while the shadow cycle is still a draft.")
    if not redaction_confirmed or not str(redaction_note or "").strip():
        raise ValidationError("Confirm redaction and describe what was removed, masked, or intentionally retained.")
    filename = str(getattr(uploaded_file, "name", "shadow-source.csv"))
    if not filename.lower().endswith(".csv"):
        raise ValidationError("Choose a CSV file. GRAND does not execute spreadsheet or database files here.")
    raw = uploaded_file.read(SHADOW_SOURCE_MAX_BYTES + 1)
    if len(raw) > SHADOW_SOURCE_MAX_BYTES:
        raise ValidationError("The redacted source CSV exceeds the 5 MB staging limit.")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("Save the redacted source as a UTF-8 CSV file.") from exc
    if "\x00" in decoded:
        raise ValidationError("The CSV contains binary/null content. Export a plain UTF-8 CSV comparison copy.")
    rows = csv.reader(io.StringIO(decoded, newline=""))
    try:
        raw_headers = next(rows)
    except StopIteration as exc:
        raise ValidationError("The CSV is empty. Include a header row and at least one redacted data row.") from exc
    headers = [_normalized_header(value) for value in raw_headers]
    if not headers or any(not value for value in headers):
        raise ValidationError("Every CSV column needs a readable heading.")
    if len(headers) != len(set(headers)):
        raise ValidationError("CSV column headings must remain unique after spacing and punctuation are normalized.")
    row_count = 0
    for row_number, row in enumerate(rows, start=2):
        if not any(str(value or "").strip() for value in row):
            continue
        if len(row) != len(headers):
            raise ValidationError(f"Row {row_number} has {len(row)} columns; the header defines {len(headers)}.")
        row_count += 1
    if not row_count:
        raise ValidationError("The CSV contains no redacted data rows.")
    schema_signature = hashlib.sha256(
        json.dumps(headers, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    checksum = hashlib.sha256(raw).hexdigest()
    current, version = _next_source_version(cycle)
    _validate_replacement_reason(current, change_reason)
    comparison, predecessor_signature = _schema_comparison(cycle, schema_signature, current)
    warnings = sorted({
        header for header in headers
        if any(term in header for term in SENSITIVE_HEADER_TERMS)
    })
    if current:
        current.is_current = False
        current.save(update_fields=("is_current",))
    item = FinanceShadowSourceVersion(
        cycle=cycle,
        version=version,
        intake_kind=FinanceShadowSourceVersion.UPLOADED_CSV,
        original_filename=filename[:255],
        file_size=len(raw),
        source_checksum=checksum,
        normalized_headers=headers,
        row_count=row_count,
        schema_signature=schema_signature,
        predecessor_schema_signature=predecessor_signature,
        schema_comparison=comparison,
        sensitive_header_warnings=warnings,
        redaction_confirmed=True,
        redaction_note=str(redaction_note).strip(),
        change_reason=str(change_reason or "").strip(),
        review_status=(
            FinanceShadowSourceVersion.PENDING
            if comparison == FinanceShadowSourceVersion.DRIFT
            else FinanceShadowSourceVersion.NOT_REQUIRED
        ),
        staged_by=actor,
    )
    item.source_file = ContentFile(raw, name=filename.split("/")[-1].split("\\")[-1])
    item.save()
    cycle.source_checksum = checksum
    cycle.source_schema_signature = schema_signature
    cycle.save(update_fields=("source_checksum", "source_schema_signature", "updated_at"))
    _event(cycle, actor, "shadow_source_staged", reason=item.change_reason, snapshot=_source_version_data(item))
    return item


@transaction.atomic
def stage_shadow_external_lock(cycle, actor, *, source_checksum, schema_signature, redaction_confirmed, redaction_note, change_reason=""):
    cycle = FinanceShadowCycle.objects.select_for_update().select_related("department", "predecessor").get(pk=cycle.pk)
    if not can_manage_shadow_operation(actor, cycle.department):
        raise PermissionDenied
    if cycle.status != FinanceShadowCycle.DRAFT:
        raise ValidationError("A source lock can be recorded only while the shadow cycle is still a draft.")
    current, version = _next_source_version(cycle)
    _validate_replacement_reason(current, change_reason)
    checksum = str(source_checksum or "").strip().lower()
    signature = str(schema_signature or "").strip().lower()
    comparison, predecessor_signature = _schema_comparison(cycle, signature, current)
    if current:
        current.is_current = False
        current.save(update_fields=("is_current",))
    item = FinanceShadowSourceVersion(
        cycle=cycle, version=version, intake_kind=FinanceShadowSourceVersion.EXTERNAL_LOCK,
        source_checksum=checksum, schema_signature=signature,
        predecessor_schema_signature=predecessor_signature, schema_comparison=comparison,
        redaction_confirmed=bool(redaction_confirmed), redaction_note=str(redaction_note or "").strip(),
        change_reason=str(change_reason or "").strip(),
        review_status=(FinanceShadowSourceVersion.PENDING if comparison == FinanceShadowSourceVersion.DRIFT else FinanceShadowSourceVersion.NOT_REQUIRED),
        staged_by=actor,
    )
    item.save()
    cycle.source_checksum = checksum
    cycle.source_schema_signature = signature
    cycle.save(update_fields=("source_checksum", "source_schema_signature", "updated_at"))
    _event(cycle, actor, "shadow_external_source_lock_recorded", reason=item.change_reason, snapshot=_source_version_data(item))
    return item


@transaction.atomic
def review_shadow_source_drift(source_version, actor, *, accept, reason):
    item = FinanceShadowSourceVersion.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=source_version.pk)
    if not can_review_shadow_reconciliation(actor, item.cycle.department):
        raise PermissionDenied
    if item.cycle.status != FinanceShadowCycle.DRAFT or not item.is_current:
        raise ValidationError("Only the current draft source version can receive a schema-drift decision.")
    if item.schema_comparison != FinanceShadowSourceVersion.DRIFT or item.review_status != FinanceShadowSourceVersion.PENDING:
        raise ValidationError("This source version is not awaiting schema-drift review.")
    if actor.pk == item.staged_by_id:
        raise ValidationError("The person who staged the source cannot review its schema drift.")
    if not str(reason or "").strip():
        raise ValidationError("Explain what columns changed and why the mapping remains safe, or why it is rejected.")
    item.review_status = FinanceShadowSourceVersion.ACCEPTED if accept else FinanceShadowSourceVersion.REJECTED
    item.review_note = str(reason).strip()
    item.reviewed_by = actor
    item.reviewed_at = timezone.now()
    item.save(update_fields=("review_status", "review_note", "reviewed_by", "reviewed_at"))
    _event(
        item.cycle, actor,
        "shadow_source_drift_accepted" if accept else "shadow_source_drift_rejected",
        reason=item.review_note, snapshot=_source_version_data(item),
    )
    return item


@transaction.atomic
def start_shadow_cycle(cycle, actor):
    cycle = FinanceShadowCycle.objects.select_for_update().get(pk=cycle.pk)
    if not can_manage_shadow_operation(actor, cycle.department):
        raise PermissionDenied
    if cycle.status != FinanceShadowCycle.DRAFT:
        raise ValidationError("Only a draft shadow-cycle plan can be started.")
    if not cycle.source_checksum or not cycle.source_schema_signature:
        raise ValidationError("Stage a redacted CSV or record an external source lock before starting.")
    current = cycle.source_versions.filter(is_current=True).first()
    if current:
        if current.source_checksum != cycle.source_checksum or current.schema_signature != cycle.source_schema_signature:
            raise ValidationError("The cycle source lock no longer matches its current retained source version.")
        if current.review_status == FinanceShadowSourceVersion.PENDING:
            raise ValidationError("Obtain an independent review of the changed column layout before starting.")
        if current.review_status == FinanceShadowSourceVersion.REJECTED:
            raise ValidationError("The current source layout was rejected. Stage a corrected version before starting.")
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
        "schema_version": 2,
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
