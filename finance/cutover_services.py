from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import timedelta

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
    FinanceCutoverQualificationForm,
    FinanceCutoverQualificationEvidence,
    FinanceCutoverQualificationPlan,
    FinanceRecoveryRehearsalEvidence,
    FinanceCutoverReadinessExercise,
    FinanceCutoverReadinessPlan,
    FinanceDiscoveryDecision,
    FinanceShadowComparison,
    FinanceShadowCycle,
    FinanceShadowDefect,
    FinanceShadowReconciliationPlan,
    FinanceShadowReconciliationRun,
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

REQUIRED_NONFUNCTIONAL_EXERCISES = {
    FinanceCutoverReadinessExercise.SECURITY_ACCESS,
    FinanceCutoverReadinessExercise.PRIVACY,
    FinanceCutoverReadinessExercise.ACCESSIBILITY,
    FinanceCutoverReadinessExercise.PERFORMANCE,
    FinanceCutoverReadinessExercise.PRINTING,
    FinanceCutoverReadinessExercise.BACKUP_RESTORE,
    FinanceCutoverReadinessExercise.BUSINESS_CONTINUITY,
    FinanceCutoverReadinessExercise.INCIDENT_RESPONSE,
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


def _plan_data(plan):
    return {
        "plan_id": plan.pk,
        "cadence": plan.cadence,
        "first_due_at": plan.first_due_at,
        "grace_minutes": plan.grace_minutes,
        "minimum_reviewed_runs": plan.minimum_reviewed_runs,
        "enabled_transaction_types": plan.enabled_transaction_types,
        "local_authority_reference": plan.local_authority_reference,
        "local_acceptance_note": plan.local_acceptance_note,
        "severity_rules": {
            severity: {
                "resolution_hours": getattr(plan, f"{severity}_resolution_hours"),
                "escalation_route": getattr(plan, f"{severity}_escalation_route"),
            }
            for severity in ("critical", "high", "medium", "low")
        },
        "status": plan.status,
        "evidence_checksum": plan.evidence_checksum,
        "created_by_id": plan.created_by_id,
        "submitted_by_id": plan.submitted_by_id,
        "submitted_at": plan.submitted_at,
        "approved_by_id": plan.approved_by_id,
        "approved_at": plan.approved_at,
        "review_note": plan.review_note,
    }


def _defect_data(item):
    return {
        "defect_id": item.pk,
        "code": item.code,
        "comparison_id": item.comparison_id,
        "severity": item.severity,
        "summary": item.summary,
        "impact": item.impact,
        "owner_id": item.owner_id,
        "correction_due_at": item.correction_due_at,
        "escalation_route_snapshot": item.escalation_route_snapshot,
        "status": item.status,
        "resolution_note": item.resolution_note,
        "resolution_evidence_reference": item.resolution_evidence_reference,
        "resolution_submitted_by_id": item.resolution_submitted_by_id,
        "resolution_submitted_at": item.resolution_submitted_at,
        "resolved_by_id": item.resolved_by_id,
        "resolved_at": item.resolved_at,
        "last_escalation_note": item.last_escalation_note,
        "last_escalation_at": item.last_escalation_at,
        "last_escalated_by_id": item.last_escalated_by_id,
        "escalation_count": item.escalation_count,
    }


def _run_data(item):
    return {
        "run_id": item.pk,
        "sequence": item.sequence,
        "scheduled_for": item.scheduled_for,
        "due_at": item.due_at,
        "status": item.status,
        "comparison_snapshot": item.comparison_snapshot,
        "defect_snapshot": item.defect_snapshot,
        "comparison_count": item.comparison_count,
        "matched_count": item.matched_count,
        "explained_count": item.explained_count,
        "open_defect_count": item.open_defect_count,
        "evidence_checksum": item.evidence_checksum,
        "prepared_by_id": item.prepared_by_id,
        "submitted_by_id": item.submitted_by_id,
        "submitted_at": item.submitted_at,
        "reviewed_by_id": item.reviewed_by_id,
        "reviewed_at": item.reviewed_at,
        "review_note": item.review_note,
    }


def _readiness_plan_data(plan):
    return {
        "plan_id": plan.pk,
        "curriculum_register_reference": plan.curriculum_register_reference,
        "quick_guides_reference": plan.quick_guides_reference,
        "supervisor_runbook_reference": plan.supervisor_runbook_reference,
        "support_owner_id": plan.support_owner_id,
        "support_channels_and_hours": plan.support_channels_and_hours,
        "support_escalation_procedure": plan.support_escalation_procedure,
        "local_acceptance_note": plan.local_acceptance_note,
        "learning_privacy_notice": plan.learning_privacy_notice,
        "status": plan.status,
        "evidence_checksum": plan.evidence_checksum,
        "created_by_id": plan.created_by_id,
        "submitted_by_id": plan.submitted_by_id,
        "submitted_at": plan.submitted_at,
        "approved_by_id": plan.approved_by_id,
        "approved_at": plan.approved_at,
        "review_note": plan.review_note,
    }


def _recovery_rehearsal_data(item):
    return {
        "backup_id": item.backup_id,
        "manifest_sha256": item.manifest_sha256,
        "default_artifact_sha256": item.default_artifact_sha256,
        "finance_artifact_sha256": item.finance_artifact_sha256,
        "off_host_copy_reference": item.off_host_copy_reference,
        "off_host_copy_verified": item.off_host_copy_verified,
        "preflight_receipt_reference": item.preflight_receipt_reference,
        "preflight_receipt_checksum": item.preflight_receipt_checksum,
        "preflight_passed": item.preflight_passed,
        "policy_reference": item.policy_reference,
        "isolated_environment_reference": item.isolated_environment_reference,
        "release_reference": item.release_reference,
        "database_versions": item.database_versions,
        "restore_log_reference": item.restore_log_reference,
        "recovery_point_at": item.recovery_point_at,
        "simulated_interruption_at": item.simulated_interruption_at,
        "restored_at": item.restored_at,
        "approved_rpo_minutes": item.approved_rpo_minutes,
        "approved_rto_minutes": item.approved_rto_minutes,
        "actual_rpo_minutes": item.actual_rpo_minutes,
        "actual_rto_minutes": item.actual_rto_minutes,
        "default_store_restored": item.default_store_restored,
        "finance_store_restored": item.finance_store_restored,
        "default_migrations_current": item.default_migrations_current,
        "finance_migrations_current": item.finance_migrations_current,
        "control_totals_reconciled": item.control_totals_reconciled,
        "control_reconciliation_reference": item.control_reconciliation_reference,
        "control_reconciliation_checksum": item.control_reconciliation_checksum,
        "cross_store_case_verified": item.cross_store_case_verified,
        "cross_store_verification_reference": item.cross_store_verification_reference,
        "cross_store_verification_checksum": item.cross_store_verification_checksum,
        "runtime_files_checked": item.runtime_files_checked,
        "runtime_files_verification_reference": item.runtime_files_verification_reference,
        "secure_disposal_completed": item.secure_disposal_completed,
        "secure_disposal_reference": item.secure_disposal_reference,
        "unresolved_exceptions": item.unresolved_exceptions,
        "exceptions_and_resolution": item.exceptions_and_resolution,
        "meets_control_objectives": item.meets_control_objectives,
        "prepared_by_id": item.prepared_by_id,
    }


def _recovery_rehearsal_for_exercise(item):
    try:
        return item.recovery_rehearsal
    except FinanceRecoveryRehearsalEvidence.DoesNotExist:
        return None


def _readiness_exercise_data(item):
    recovery = _recovery_rehearsal_for_exercise(item)
    return {
        "exercise_id": item.pk,
        "kind": item.kind,
        "code": item.code,
        "title": item.title,
        "stakeholder_acceptance_id": item.stakeholder_acceptance_id,
        "enabled_scope": item.enabled_scope,
        "procedure": item.procedure,
        "expected_result": item.expected_result,
        "owner_id": item.owner_id,
        "witness_id": item.witness_id,
        "support_route_snapshot": item.support_route_snapshot,
        "scheduled_for": item.scheduled_for,
        "due_at": item.due_at,
        "status": item.status,
        "actual_result": item.actual_result,
        "evidence_reference": item.evidence_reference,
        "evidence_checksum": item.evidence_checksum,
        "submitted_by_id": item.submitted_by_id,
        "submitted_at": item.submitted_at,
        "reviewed_by_id": item.reviewed_by_id,
        "reviewed_at": item.reviewed_at,
        "review_note": item.review_note,
        "created_by_id": item.created_by_id,
        "recovery_rehearsal": (
            {
                **_recovery_rehearsal_data(recovery),
                "evidence_checksum": recovery.evidence_checksum,
            }
            if recovery else None
        ),
    }


def _qualification_plan_data(plan):
    return {
        "plan_id": plan.pk,
        "minimum_consecutive_cycles": plan.minimum_consecutive_cycles,
        "require_parallel_cycle": plan.require_parallel_cycle,
        "local_authority_reference": plan.local_authority_reference,
        "accepted_rules_forms_reference": plan.accepted_rules_forms_reference,
        "field_evidence_basis": plan.field_evidence_basis,
        "accepted_forms": [
            _qualification_form_data(item)
            for item in plan.accepted_forms.select_related(
                "local_form", "local_form__department", "local_form__reviewed_by",
            ).order_by("position", "pk")
        ],
        "status": plan.status,
        "evidence_checksum": plan.evidence_checksum,
        "created_by_id": plan.created_by_id,
        "submitted_by_id": plan.submitted_by_id,
        "submitted_at": plan.submitted_at,
        "approved_by_id": plan.approved_by_id,
        "approved_at": plan.approved_at,
        "review_note": plan.review_note,
    }


def _qualification_form_data(item):
    form = item.local_form
    return {
        "lineage_id": item.pk,
        "position": item.position,
        "use_instructions": item.use_instructions,
        "form_public_id": str(form.public_id),
        "department_id": form.department_id,
        "department_name": form.department.name,
        "code": form.code,
        "version": form.version,
        "name": form.name,
        "form_number": form.form_number,
        "source_type": form.source_type,
        "report_template_id": form.report_template_id,
        "finance_template_id": form.finance_template_id,
        "submission_checksum": item.form_submission_checksum,
        "reference_checksum": item.form_reference_checksum,
        "source_checksum": item.form_source_checksum,
        "accepted_by_id": form.reviewed_by_id,
        "accepted_at": form.reviewed_at.isoformat() if form.reviewed_at else "",
        "accepted_form_snapshot": item.form_snapshot,
    }


def _validated_qualification_forms(plan, *, pin=False):
    from reporting.form_acceptance_services import local_form_export_manifest
    from reporting.models import FinanceLocalFormAcceptance

    rows = list(plan.accepted_forms.select_related(
        "local_form", "local_form__department", "local_form__reviewed_by",
    ).order_by("position", "pk"))
    if not rows:
        raise ValidationError(
            "Select at least one currently accepted local form before submitting the field-qualification plan."
        )
    for row in rows:
        form = row.local_form
        if form.status != FinanceLocalFormAcceptance.ACCEPTED:
            raise ValidationError(
                f"{form.name} v{form.version} is no longer the current accepted form. Use a successor qualification cycle."
            )
        try:
            manifest = local_form_export_manifest(form)
        except (OSError, ValueError, ValidationError) as exc:
            raise ValidationError(
                f"The accepted evidence for {form.name} v{form.version} is unavailable or no longer verifies: {exc}"
            ) from exc
        expected = {
            "form_snapshot": manifest["form"],
            "form_submission_checksum": form.submission_checksum,
            "form_reference_checksum": form.reference_checksum,
            "form_source_checksum": form.source_checksum,
        }
        if pin:
            for field, value in expected.items():
                setattr(row, field, value)
            row.save(update_fields=(*expected.keys(), "updated_at"))
        elif any(getattr(row, field) != value for field, value in expected.items()):
            raise ValidationError(
                f"The accepted evidence for {form.name} v{form.version} no longer matches the plan's pinned lineage."
            )
    return rows


def _qualification_evidence_data(item):
    return {
        "evidence_id": item.pk,
        "cycle_id": item.cycle_id,
        "cycle_code": item.cycle.code,
        "cycle_run_kind": item.cycle.run_kind,
        "sequence": item.sequence,
        "field_execution_reference": item.field_execution_reference,
        "rules_forms_reference": item.rules_forms_reference,
        "accepted_forms_snapshot": item.accepted_forms_snapshot,
        "accepted_forms_checksum": item.accepted_forms_checksum,
        "status": item.status,
        "evidence_checksum": item.evidence_checksum,
        "prepared_by_id": item.prepared_by_id,
        "submitted_by_id": item.submitted_by_id,
        "submitted_at": item.submitted_at,
        "reviewed_by_id": item.reviewed_by_id,
        "reviewed_at": item.reviewed_at,
        "review_note": item.review_note,
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
    plan = FinanceShadowReconciliationPlan.objects.filter(cycle=cycle).first()
    runs = [_run_data(item) for item in cycle.reconciliation_runs.order_by("sequence", "pk")]
    defects = [_defect_data(item) for item in cycle.defects.order_by("created_at", "pk")]
    payload = {
        "schema_version": 3,
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
        "reconciliation_plan": _plan_data(plan) if plan else None,
        "reconciliation_runs": runs,
        "defects": defects,
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


def _checksum_payload(payload):
    encoded = json.dumps(payload, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


RECOVERY_REHEARSAL_FIELDS = (
    "backup_id", "manifest_sha256", "default_artifact_sha256", "finance_artifact_sha256",
    "off_host_copy_reference", "off_host_copy_verified",
    "preflight_receipt_reference", "preflight_receipt_checksum", "preflight_passed",
    "policy_reference", "isolated_environment_reference", "release_reference",
    "database_versions", "restore_log_reference", "recovery_point_at",
    "simulated_interruption_at", "restored_at", "approved_rpo_minutes", "approved_rto_minutes",
    "default_store_restored", "finance_store_restored", "default_migrations_current",
    "finance_migrations_current", "control_totals_reconciled",
    "control_reconciliation_reference", "control_reconciliation_checksum",
    "cross_store_case_verified", "cross_store_verification_reference",
    "cross_store_verification_checksum", "runtime_files_checked",
    "runtime_files_verification_reference", "secure_disposal_completed",
    "secure_disposal_reference", "unresolved_exceptions", "exceptions_and_resolution",
)
RECOVERY_HASH_FIELDS = {
    "manifest_sha256", "default_artifact_sha256", "finance_artifact_sha256",
    "preflight_receipt_checksum", "control_reconciliation_checksum",
    "cross_store_verification_checksum",
}
RECOVERY_TEXT_FIELDS = {
    "backup_id", "off_host_copy_reference", "preflight_receipt_reference", "policy_reference",
    "isolated_environment_reference", "release_reference", "database_versions",
    "restore_log_reference", "control_reconciliation_reference",
    "cross_store_verification_reference", "runtime_files_verification_reference",
    "secure_disposal_reference", "exceptions_and_resolution",
}


def _serializable_payload(payload):
    return json.loads(json.dumps(payload, cls=DjangoJSONEncoder))


def _record_recovery_rehearsal(exercise, actor, values):
    item = FinanceRecoveryRehearsalEvidence.objects.select_for_update().filter(
        exercise=exercise,
    ).first()
    if item is None:
        item = FinanceRecoveryRehearsalEvidence(exercise=exercise, prepared_by=actor)
    for field in RECOVERY_REHEARSAL_FIELDS:
        value = values.get(field)
        if field in RECOVERY_HASH_FIELDS:
            value = str(value or "").strip().lower()
        elif field in RECOVERY_TEXT_FIELDS:
            value = str(value or "").strip()
        setattr(item, field, value)
    item.prepared_by = actor
    item.evidence_snapshot = {}
    item.evidence_checksum = ""
    item.full_clean()
    # Persist and reload first so timezone-aware values are normalized exactly as
    # they will be read during witness review and later evidence-package checks.
    item.save()
    item.refresh_from_db()
    snapshot = _recovery_rehearsal_data(item)
    item.evidence_snapshot = _serializable_payload(snapshot)
    item.evidence_checksum = _checksum_payload(snapshot)
    item.save(update_fields=("evidence_snapshot", "evidence_checksum", "updated_at"))
    exercise.recovery_rehearsal = item
    return item


def _validated_recovery_rehearsal(exercise, *, require_objectives=False):
    item = _recovery_rehearsal_for_exercise(exercise)
    if item is None:
        raise ValidationError(
            "A backup and restore exercise requires the structured two-store recovery rehearsal record."
        )
    snapshot = _recovery_rehearsal_data(item)
    if item.evidence_snapshot != _serializable_payload(snapshot):
        raise ValidationError("The structured recovery rehearsal changed after its checksum snapshot.")
    if not item.evidence_checksum or _checksum_payload(snapshot) != item.evidence_checksum:
        raise ValidationError("The structured recovery rehearsal checksum is invalid.")
    if require_objectives and not item.meets_control_objectives:
        failures = []
        if item.actual_rpo_minutes > item.approved_rpo_minutes:
            failures.append("actual RPO exceeded the approved target")
        if item.actual_rto_minutes > item.approved_rto_minutes:
            failures.append("actual RTO exceeded the approved target")
        if item.unresolved_exceptions:
            failures.append("recovery exceptions remain unresolved")
        if not all((
            item.off_host_copy_verified, item.preflight_passed,
            item.default_store_restored, item.finance_store_restored,
            item.default_migrations_current, item.finance_migrations_current,
            item.control_totals_reconciled, item.cross_store_case_verified,
            item.runtime_files_checked, item.secure_disposal_completed,
        )):
            failures.append("one or more required two-store recovery controls is not confirmed")
        raise ValidationError(
            "The recovery exercise cannot pass: " + "; ".join(failures or ["control objectives are incomplete"])
        )
    return item


def _recovery_rehearsal_pass_ready(exercise):
    try:
        _validated_recovery_rehearsal(exercise, require_objectives=True)
    except ValidationError:
        return False
    return True


@transaction.atomic
def submit_reconciliation_plan(plan, actor):
    plan = FinanceShadowReconciliationPlan.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=plan.pk)
    if not can_manage_shadow_operation(actor, plan.cycle.department):
        raise PermissionDenied
    if plan.status not in {FinanceShadowReconciliationPlan.DRAFT, FinanceShadowReconciliationPlan.RETURNED}:
        raise ValidationError("Only a draft or returned reconciliation plan can be submitted.")
    plan.status = FinanceShadowReconciliationPlan.DRAFT
    plan.evidence_checksum = ""
    plan.submitted_by = None
    plan.submitted_at = None
    plan.approved_by = None
    plan.approved_at = None
    plan.review_note = ""
    plan.full_clean()
    snapshot = _plan_data(plan)
    snapshot.pop("evidence_checksum", None)
    plan.evidence_checksum = _checksum_payload(snapshot)
    plan.status = FinanceShadowReconciliationPlan.SUBMITTED
    plan.submitted_by = actor
    plan.submitted_at = timezone.now()
    plan.approved_by = None
    plan.approved_at = None
    plan.review_note = ""
    plan.save(update_fields=(
        "status", "evidence_checksum", "submitted_by", "submitted_at",
        "approved_by", "approved_at", "review_note", "updated_at",
    ))
    _event(plan.cycle, actor, "shadow_reconciliation_plan_submitted", snapshot=_plan_data(plan))
    return plan


@transaction.atomic
def review_reconciliation_plan(plan, actor, *, approve, reason):
    plan = FinanceShadowReconciliationPlan.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=plan.pk)
    if not can_review_shadow_reconciliation(actor, plan.cycle.department):
        raise PermissionDenied
    if plan.status != FinanceShadowReconciliationPlan.SUBMITTED:
        raise ValidationError("This reconciliation plan is not awaiting review.")
    if actor.pk == plan.submitted_by_id or actor.pk == plan.created_by_id:
        raise ValidationError("The plan preparer or submitter cannot approve the same local plan.")
    if not str(reason or "").strip():
        raise ValidationError("Record the local review basis or the exact correction required.")
    snapshot = _plan_data(plan)
    stored = snapshot.pop("evidence_checksum", "")
    snapshot["status"] = FinanceShadowReconciliationPlan.DRAFT
    snapshot["submitted_by_id"] = None
    snapshot["submitted_at"] = None
    snapshot["approved_by_id"] = None
    snapshot["approved_at"] = None
    snapshot["review_note"] = ""
    if _checksum_payload(snapshot) != stored:
        raise ValidationError("The local plan changed after submission. Return it rather than approving altered controls.")
    plan.status = FinanceShadowReconciliationPlan.APPROVED if approve else FinanceShadowReconciliationPlan.RETURNED
    plan.review_note = str(reason).strip()
    if approve:
        plan.approved_by = actor
        plan.approved_at = timezone.now()
    else:
        plan.evidence_checksum = ""
        plan.approved_by = None
        plan.approved_at = None
    plan.save(update_fields=("status", "review_note", "evidence_checksum", "approved_by", "approved_at", "updated_at"))
    _event(
        plan.cycle, actor,
        "shadow_reconciliation_plan_approved" if approve else "shadow_reconciliation_plan_returned",
        reason=reason, snapshot=_plan_data(plan),
    )
    return plan


@transaction.atomic
def submit_cutover_readiness_plan(plan, actor):
    plan = FinanceCutoverReadinessPlan.objects.select_for_update().select_related(
        "cycle", "cycle__department",
    ).get(pk=plan.pk)
    if not can_manage_shadow_operation(actor, plan.cycle.department):
        raise PermissionDenied
    if plan.status not in {FinanceCutoverReadinessPlan.DRAFT, FinanceCutoverReadinessPlan.RETURNED}:
        raise ValidationError("Only a draft or returned cutover readiness plan can be submitted.")
    plan.status = FinanceCutoverReadinessPlan.DRAFT
    plan.evidence_checksum = ""
    plan.submitted_by = None
    plan.submitted_at = None
    plan.approved_by = None
    plan.approved_at = None
    plan.review_note = ""
    plan.full_clean()
    snapshot = _readiness_plan_data(plan)
    snapshot.pop("evidence_checksum", None)
    plan.evidence_checksum = _checksum_payload(snapshot)
    plan.status = FinanceCutoverReadinessPlan.SUBMITTED
    plan.submitted_by = actor
    plan.submitted_at = timezone.now()
    plan.save(update_fields=(
        "status", "evidence_checksum", "submitted_by", "submitted_at",
        "approved_by", "approved_at", "review_note", "updated_at",
    ))
    _event(plan.cycle, actor, "cutover_readiness_plan_submitted", snapshot=_readiness_plan_data(plan))
    return plan


@transaction.atomic
def review_cutover_readiness_plan(plan, actor, *, approve, reason):
    plan = FinanceCutoverReadinessPlan.objects.select_for_update().select_related(
        "cycle", "cycle__department",
    ).get(pk=plan.pk)
    if not can_review_shadow_reconciliation(actor, plan.cycle.department):
        raise PermissionDenied
    if plan.status != FinanceCutoverReadinessPlan.SUBMITTED:
        raise ValidationError("This cutover readiness plan is not awaiting review.")
    if actor.pk in {plan.created_by_id, plan.submitted_by_id}:
        raise ValidationError("The readiness-plan preparer or submitter cannot approve the same plan.")
    if not str(reason or "").strip():
        raise ValidationError("Record the local review basis or the exact correction required.")
    snapshot = _readiness_plan_data(plan)
    stored = snapshot.pop("evidence_checksum", "")
    snapshot["status"] = FinanceCutoverReadinessPlan.DRAFT
    snapshot["submitted_by_id"] = None
    snapshot["submitted_at"] = None
    snapshot["approved_by_id"] = None
    snapshot["approved_at"] = None
    snapshot["review_note"] = ""
    if _checksum_payload(snapshot) != stored:
        raise ValidationError("The readiness plan changed after submission. Return it rather than approving altered controls.")
    plan.status = FinanceCutoverReadinessPlan.APPROVED if approve else FinanceCutoverReadinessPlan.RETURNED
    plan.review_note = str(reason).strip()
    if approve:
        plan.approved_by = actor
        plan.approved_at = timezone.now()
    else:
        plan.evidence_checksum = ""
        plan.approved_by = None
        plan.approved_at = None
    plan.save(update_fields=(
        "status", "review_note", "evidence_checksum", "approved_by", "approved_at", "updated_at",
    ))
    _event(
        plan.cycle, actor,
        "cutover_readiness_plan_approved" if approve else "cutover_readiness_plan_returned",
        reason=reason, snapshot=_readiness_plan_data(plan),
    )
    return plan


@transaction.atomic
def submit_cutover_qualification_plan(plan, actor):
    plan = FinanceCutoverQualificationPlan.objects.select_for_update().select_related(
        "cycle", "cycle__department",
    ).get(pk=plan.pk)
    if not can_manage_shadow_operation(actor, plan.cycle.department):
        raise PermissionDenied
    if plan.status not in {FinanceCutoverQualificationPlan.DRAFT, FinanceCutoverQualificationPlan.RETURNED}:
        raise ValidationError("Only a draft or returned field-qualification plan can be submitted.")
    plan.status = FinanceCutoverQualificationPlan.DRAFT
    plan.evidence_checksum = ""
    plan.submitted_by = None
    plan.submitted_at = None
    plan.approved_by = None
    plan.approved_at = None
    plan.review_note = ""
    plan.full_clean()
    _validated_qualification_forms(plan, pin=True)
    snapshot = _qualification_plan_data(plan)
    snapshot.pop("evidence_checksum", None)
    plan.evidence_checksum = _checksum_payload(snapshot)
    plan.status = FinanceCutoverQualificationPlan.SUBMITTED
    plan.submitted_by = actor
    plan.submitted_at = timezone.now()
    plan.save(update_fields=(
        "status", "evidence_checksum", "submitted_by", "submitted_at",
        "approved_by", "approved_at", "review_note", "updated_at",
    ))
    _event(plan.cycle, actor, "cutover_qualification_plan_submitted", snapshot=_qualification_plan_data(plan))
    return plan


@transaction.atomic
def review_cutover_qualification_plan(plan, actor, *, approve, reason):
    plan = FinanceCutoverQualificationPlan.objects.select_for_update().select_related(
        "cycle", "cycle__department",
    ).get(pk=plan.pk)
    if not can_review_shadow_reconciliation(actor, plan.cycle.department):
        raise PermissionDenied
    if plan.status != FinanceCutoverQualificationPlan.SUBMITTED:
        raise ValidationError("This field-qualification plan is not awaiting review.")
    if actor.pk in {plan.created_by_id, plan.submitted_by_id}:
        raise ValidationError("The qualification-plan preparer or submitter cannot approve the same plan.")
    if not str(reason or "").strip():
        raise ValidationError("Record the local review basis or the exact correction required.")
    if approve:
        _validated_qualification_forms(plan)
    snapshot = _qualification_plan_data(plan)
    stored = snapshot.pop("evidence_checksum", "")
    snapshot.update({
        "status": FinanceCutoverQualificationPlan.DRAFT,
        "submitted_by_id": None,
        "submitted_at": None,
        "approved_by_id": None,
        "approved_at": None,
        "review_note": "",
    })
    if _checksum_payload(snapshot) != stored:
        raise ValidationError("The qualification plan changed after submission. Return it rather than approving altered controls.")
    plan.status = FinanceCutoverQualificationPlan.APPROVED if approve else FinanceCutoverQualificationPlan.RETURNED
    plan.review_note = str(reason).strip()
    if approve:
        plan.approved_by = actor
        plan.approved_at = timezone.now()
    else:
        plan.evidence_checksum = ""
        plan.approved_by = None
        plan.approved_at = None
    plan.save(update_fields=(
        "status", "review_note", "evidence_checksum", "approved_by", "approved_at", "updated_at",
    ))
    _event(
        plan.cycle, actor,
        "cutover_qualification_plan_approved" if approve else "cutover_qualification_plan_returned",
        reason=reason, snapshot=_qualification_plan_data(plan),
    )
    return plan


@transaction.atomic
def submit_cutover_qualification_evidence(item, actor):
    item = FinanceCutoverQualificationEvidence.objects.select_for_update().select_related(
        "plan", "plan__cycle", "plan__cycle__department", "cycle",
    ).get(pk=item.pk)
    if not can_manage_shadow_operation(actor, item.plan.cycle.department):
        raise PermissionDenied
    if item.status not in {FinanceCutoverQualificationEvidence.DRAFT, FinanceCutoverQualificationEvidence.RETURNED}:
        raise ValidationError("Only draft or returned field-cycle evidence can be submitted.")
    item.status = FinanceCutoverQualificationEvidence.DRAFT
    item.evidence_checksum = ""
    item.submitted_by = None
    item.submitted_at = None
    item.reviewed_by = None
    item.reviewed_at = None
    item.review_note = ""
    rows = _validated_qualification_forms(item.plan)
    item.accepted_forms_snapshot = [_qualification_form_data(row) for row in rows]
    item.accepted_forms_checksum = _checksum_payload(item.accepted_forms_snapshot)
    item.full_clean()
    snapshot = _qualification_evidence_data(item)
    snapshot.pop("evidence_checksum", None)
    item.evidence_checksum = _checksum_payload(snapshot)
    item.status = FinanceCutoverQualificationEvidence.SUBMITTED
    item.submitted_by = actor
    item.submitted_at = timezone.now()
    item.save(update_fields=(
        "status", "accepted_forms_snapshot", "accepted_forms_checksum", "evidence_checksum", "submitted_by", "submitted_at",
        "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ))
    _event(item.plan.cycle, actor, "cutover_qualification_evidence_submitted", snapshot=_qualification_evidence_data(item))
    return item


@transaction.atomic
def review_cutover_qualification_evidence(item, actor, *, accept, reason):
    item = FinanceCutoverQualificationEvidence.objects.select_for_update().select_related(
        "plan", "plan__cycle", "plan__cycle__department", "cycle",
    ).get(pk=item.pk)
    if not can_review_shadow_reconciliation(actor, item.plan.cycle.department):
        raise PermissionDenied
    if item.status != FinanceCutoverQualificationEvidence.SUBMITTED:
        raise ValidationError("This field-cycle evidence is not awaiting review.")
    if actor.pk in {item.prepared_by_id, item.submitted_by_id}:
        raise ValidationError("The evidence preparer or submitter cannot accept the same field cycle.")
    if not str(reason or "").strip():
        raise ValidationError("Record the independent review basis or the exact correction/rerun required.")
    if accept:
        rows = _validated_qualification_forms(item.plan)
        current_forms = [_qualification_form_data(row) for row in rows]
        if (
            item.accepted_forms_snapshot != current_forms
            or item.accepted_forms_checksum != _checksum_payload(current_forms)
        ):
            raise ValidationError(
                "The exact accepted-form set changed after this field cycle was submitted. Return it and use a successor cycle."
            )
    snapshot = _qualification_evidence_data(item)
    stored = snapshot.pop("evidence_checksum", "")
    snapshot.update({
        "status": FinanceCutoverQualificationEvidence.DRAFT,
        "submitted_by_id": None,
        "submitted_at": None,
        "reviewed_by_id": None,
        "reviewed_at": None,
        "review_note": "",
    })
    if _checksum_payload(snapshot) != stored:
        raise ValidationError("The field-cycle evidence changed after submission. Return it instead of accepting altered evidence.")
    item.status = FinanceCutoverQualificationEvidence.ACCEPTED if accept else FinanceCutoverQualificationEvidence.RETURNED
    item.review_note = str(reason).strip()
    if accept:
        item.reviewed_by = actor
        item.reviewed_at = timezone.now()
    else:
        item.evidence_checksum = ""
        item.reviewed_by = None
        item.reviewed_at = None
    item.save(update_fields=(
        "status", "review_note", "evidence_checksum", "reviewed_by", "reviewed_at", "updated_at",
    ))
    _event(
        item.plan.cycle, actor,
        "cutover_qualification_evidence_accepted" if accept else "cutover_qualification_evidence_returned",
        reason=reason, snapshot=_qualification_evidence_data(item),
    )
    return item


@transaction.atomic
def schedule_cutover_readiness_exercise(
    cycle, actor, *, kind, code, title, enabled_scope, procedure, expected_result,
    owner, witness, scheduled_for, due_at, stakeholder_acceptance=None,
):
    cycle = FinanceShadowCycle.objects.select_for_update().select_related("department").get(pk=cycle.pk)
    if not can_manage_shadow_operation(actor, cycle.department):
        raise PermissionDenied
    try:
        cutover_status = cycle.cutover_decision.status
    except FinanceCutoverDecision.DoesNotExist:
        cutover_status = ""
    if cutover_status and cutover_status != FinanceCutoverDecision.DRAFT:
        raise ValidationError("Readiness exercises are locked after the cutover record is submitted.")
    plan = FinanceCutoverReadinessPlan.objects.filter(cycle=cycle).first()
    if not plan:
        raise ValidationError("Approve a cutover readiness plan before scheduling exercises.")
    if plan.status != FinanceCutoverReadinessPlan.APPROVED:
        raise ValidationError("The cutover readiness plan is not independently approved.")
    item = FinanceCutoverReadinessExercise(
        cycle=cycle, plan=plan, stakeholder_acceptance=stakeholder_acceptance,
        kind=kind, code=code, title=title, enabled_scope=enabled_scope,
        procedure=procedure, expected_result=expected_result, owner=owner, witness=witness,
        support_route_snapshot=(
            f"{plan.support_channels_and_hours}\nEscalation: {plan.support_escalation_procedure}"
        ).strip(),
        scheduled_for=scheduled_for, due_at=due_at, created_by=actor,
    )
    item.save()
    _event(cycle, actor, "cutover_readiness_exercise_scheduled", snapshot=_readiness_exercise_data(item))
    return item


@transaction.atomic
def submit_cutover_readiness_exercise(
    exercise, actor, *, actual_result, evidence_reference, recovery_evidence=None,
):
    exercise = FinanceCutoverReadinessExercise.objects.select_for_update().select_related(
        "cycle", "cycle__department",
    ).get(pk=exercise.pk)
    if actor.pk != exercise.owner_id:
        raise PermissionDenied("Only the assigned exercise owner can submit its result.")
    if exercise.status not in {FinanceCutoverReadinessExercise.PLANNED, FinanceCutoverReadinessExercise.RETURNED}:
        raise ValidationError("Only a planned or returned readiness exercise can be submitted.")
    if not str(actual_result or "").strip() or not str(evidence_reference or "").strip():
        raise ValidationError("Record the actual result and retained evidence reference.")
    if exercise.kind == FinanceCutoverReadinessExercise.BACKUP_RESTORE:
        if recovery_evidence is None:
            raise ValidationError(
                "Record the structured two-store recovery rehearsal before submitting this exercise."
            )
        _record_recovery_rehearsal(exercise, actor, recovery_evidence)
    elif recovery_evidence is not None:
        raise ValidationError("Structured recovery evidence belongs only to a backup and restore exercise.")
    exercise.status = FinanceCutoverReadinessExercise.PLANNED
    exercise.actual_result = str(actual_result).strip()
    exercise.evidence_reference = str(evidence_reference).strip()
    exercise.evidence_checksum = ""
    exercise.submitted_by = None
    exercise.submitted_at = None
    exercise.reviewed_by = None
    exercise.reviewed_at = None
    exercise.review_note = ""
    exercise.full_clean()
    snapshot = _readiness_exercise_data(exercise)
    snapshot["evidence_checksum"] = ""
    exercise.evidence_checksum = _checksum_payload(snapshot)
    exercise.status = FinanceCutoverReadinessExercise.SUBMITTED
    exercise.submitted_by = actor
    exercise.submitted_at = timezone.now()
    exercise.save(update_fields=(
        "status", "actual_result", "evidence_reference", "evidence_checksum", "submitted_by",
        "submitted_at", "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ))
    _event(exercise.cycle, actor, "cutover_readiness_exercise_submitted", snapshot=_readiness_exercise_data(exercise))
    return exercise


@transaction.atomic
def review_cutover_readiness_exercise(exercise, actor, *, accept, reason):
    exercise = FinanceCutoverReadinessExercise.objects.select_for_update().select_related(
        "cycle", "cycle__department", "recovery_rehearsal",
    ).get(pk=exercise.pk)
    if actor.pk != exercise.witness_id:
        raise PermissionDenied("Only the assigned witness can review this exercise.")
    if exercise.status != FinanceCutoverReadinessExercise.SUBMITTED:
        raise ValidationError("This readiness exercise is not awaiting witness review.")
    if actor.pk == exercise.submitted_by_id:
        raise ValidationError("The evidence submitter cannot independently witness the same exercise.")
    if not str(reason or "").strip():
        raise ValidationError("Record the witness basis or the exact correction/rerun required.")
    if accept and exercise.kind == FinanceCutoverReadinessExercise.BACKUP_RESTORE:
        _validated_recovery_rehearsal(exercise, require_objectives=True)
    snapshot = _readiness_exercise_data(exercise)
    stored = snapshot["evidence_checksum"]
    snapshot["status"] = FinanceCutoverReadinessExercise.PLANNED
    snapshot["evidence_checksum"] = ""
    snapshot["submitted_by_id"] = None
    snapshot["submitted_at"] = None
    snapshot["reviewed_by_id"] = None
    snapshot["reviewed_at"] = None
    snapshot["review_note"] = ""
    if _checksum_payload(snapshot) != stored:
        raise ValidationError("The exercise evidence changed after submission. Return it rather than accepting altered evidence.")
    exercise.review_note = str(reason).strip()
    if accept:
        exercise.status = FinanceCutoverReadinessExercise.PASSED
        exercise.reviewed_by = actor
        exercise.reviewed_at = timezone.now()
    else:
        exercise.status = FinanceCutoverReadinessExercise.RETURNED
        exercise.reviewed_by = None
        exercise.reviewed_at = None
    exercise.save(update_fields=(
        "status", "evidence_checksum", "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ))
    _event(
        exercise.cycle, actor,
        "cutover_readiness_exercise_passed" if accept else "cutover_readiness_exercise_returned",
        reason=reason, snapshot=_readiness_exercise_data(exercise),
    )
    return exercise


def _next_scheduled_for(plan, prior=None):
    scheduled = plan.first_due_at if prior is None else prior.scheduled_for + timedelta(days=1)
    if plan.cadence == FinanceShadowReconciliationPlan.BUSINESS_DAILY:
        while timezone.localtime(scheduled).weekday() >= 5:
            scheduled += timedelta(days=1)
    return scheduled


@transaction.atomic
def open_next_reconciliation_run(cycle, actor):
    cycle = FinanceShadowCycle.objects.select_for_update().select_related("department").get(pk=cycle.pk)
    if not can_manage_shadow_operation(actor, cycle.department):
        raise PermissionDenied
    if cycle.status != FinanceShadowCycle.RUNNING:
        raise ValidationError("Scheduled reconciliation runs open only while the shadow cycle is running.")
    try:
        plan = cycle.reconciliation_plan
    except FinanceShadowReconciliationPlan.DoesNotExist as exc:
        raise ValidationError("Approve a local reconciliation plan before opening runs.") from exc
    if plan.status != FinanceShadowReconciliationPlan.APPROVED:
        raise ValidationError("The local reconciliation plan is not independently approved.")
    prior = cycle.reconciliation_runs.order_by("-sequence").first()
    if prior and prior.status in {FinanceShadowReconciliationRun.OPEN, FinanceShadowReconciliationRun.RETURNED, FinanceShadowReconciliationRun.SUBMITTED}:
        raise ValidationError("Finish or independently review the current scheduled run before opening the next one.")
    scheduled_for = _next_scheduled_for(plan, prior)
    if timezone.localtime(scheduled_for).date() > cycle.planned_end:
        raise ValidationError("The next scheduled run falls after the cycle's planned end date.")
    run = FinanceShadowReconciliationRun.objects.create(
        cycle=cycle, plan=plan, sequence=(prior.sequence + 1 if prior else 1),
        scheduled_for=scheduled_for, due_at=scheduled_for + timedelta(minutes=plan.grace_minutes),
        prepared_by=actor,
    )
    _event(cycle, actor, "shadow_reconciliation_run_opened", snapshot=_run_data(run))
    return run


@transaction.atomic
def register_shadow_defect(comparison, actor, *, code, severity, summary, impact, owner):
    comparison = FinanceShadowComparison.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=comparison.pk)
    cycle = comparison.cycle
    if not can_manage_shadow_operation(actor, cycle.department):
        raise PermissionDenied
    if cycle.status != FinanceShadowCycle.RUNNING or comparison.outcome != FinanceShadowComparison.OPEN_DEFECT:
        raise ValidationError("Register triage only for an open difference in a running shadow cycle.")
    if comparison.defects.exclude(status=FinanceShadowDefect.RESOLVED).exists():
        raise ValidationError("This comparison already has an unresolved defect record.")
    try:
        plan = cycle.reconciliation_plan
    except FinanceShadowReconciliationPlan.DoesNotExist as exc:
        raise ValidationError("Approve the local reconciliation plan before triaging defects.") from exc
    if plan.status != FinanceShadowReconciliationPlan.APPROVED:
        raise ValidationError("The local reconciliation plan is not independently approved.")
    if severity not in dict(FinanceShadowDefect.SEVERITY_CHOICES):
        raise ValidationError("Choose Critical, High, Medium, or Low using the approved local plan.")
    if comparison.defect_owner_id and comparison.defect_owner_id != owner.pk:
        raise ValidationError("Use the owner already assigned on the comparison or correct that comparison first.")
    hours = getattr(plan, f"{severity}_resolution_hours")
    route = getattr(plan, f"{severity}_escalation_route")
    latest_run = cycle.reconciliation_runs.order_by("-sequence").first()
    defect = FinanceShadowDefect.objects.create(
        cycle=cycle, first_seen_run=latest_run, comparison=comparison, code=code,
        severity=severity, summary=summary, impact=impact, owner=owner,
        correction_due_at=timezone.now() + timedelta(hours=hours),
        escalation_route_snapshot=route, created_by=actor,
    )
    _event(cycle, actor, "shadow_defect_registered", snapshot=_defect_data(defect))
    return defect


@transaction.atomic
def submit_shadow_defect_resolution(defect, actor, *, note, evidence_reference):
    defect = FinanceShadowDefect.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=defect.pk)
    if actor.pk != defect.owner_id and not can_manage_shadow_operation(actor, defect.cycle.department):
        raise PermissionDenied
    if defect.cycle.status != FinanceShadowCycle.RUNNING or defect.status != FinanceShadowDefect.OPEN:
        raise ValidationError("Only an open defect in a running cycle can be submitted as corrected.")
    if not str(note or "").strip() or not str(evidence_reference or "").strip():
        raise ValidationError("Describe the correction and reference the retained verification evidence.")
    defect.status = FinanceShadowDefect.RESOLUTION_REVIEW
    defect.resolution_note = str(note).strip()
    defect.resolution_evidence_reference = str(evidence_reference).strip()
    defect.resolution_submitted_by = actor
    defect.resolution_submitted_at = timezone.now()
    defect.save(update_fields=(
        "status", "resolution_note", "resolution_evidence_reference", "resolution_submitted_by",
        "resolution_submitted_at", "updated_at",
    ))
    _event(defect.cycle, actor, "shadow_defect_resolution_submitted", snapshot=_defect_data(defect))
    return defect


@transaction.atomic
def review_shadow_defect_resolution(defect, actor, *, accept, reason):
    defect = FinanceShadowDefect.objects.select_for_update().select_related(
        "cycle", "cycle__department", "comparison",
    ).get(pk=defect.pk)
    if not can_review_shadow_reconciliation(actor, defect.cycle.department):
        raise PermissionDenied
    if defect.status != FinanceShadowDefect.RESOLUTION_REVIEW:
        raise ValidationError("This defect resolution is not awaiting independent review.")
    if actor.pk == defect.resolution_submitted_by_id:
        raise ValidationError("The resolution submitter cannot independently accept the same correction.")
    if not str(reason or "").strip():
        raise ValidationError("Record the verification basis or the exact reason for reopening the defect.")
    if accept:
        defect.status = FinanceShadowDefect.RESOLVED
        defect.resolved_by = actor
        defect.resolved_at = timezone.now()
        comparison = defect.comparison
        comparison.outcome = FinanceShadowComparison.EXPLAINED
        comparison.explanation = (
            f"{comparison.explanation.strip()}\n\nResolved defect {defect.code}: {defect.resolution_note}"
        ).strip()
        comparison.save(update_fields=("outcome", "explanation", "amount_difference", "count_difference"))
    else:
        defect.status = FinanceShadowDefect.OPEN
        defect.resolved_by = None
        defect.resolved_at = None
    defect.save(update_fields=("status", "resolved_by", "resolved_at", "updated_at"))
    _event(
        defect.cycle, actor,
        "shadow_defect_resolution_accepted" if accept else "shadow_defect_resolution_returned",
        reason=reason, snapshot=_defect_data(defect),
    )
    return defect


@transaction.atomic
def record_shadow_defect_escalation(defect, actor, *, note):
    defect = FinanceShadowDefect.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=defect.pk)
    if not can_manage_shadow_operation(actor, defect.cycle.department):
        raise PermissionDenied
    if defect.status == FinanceShadowDefect.RESOLVED:
        raise ValidationError("A resolved defect does not accept a new escalation.")
    if not str(note or "").strip():
        raise ValidationError("Record who was notified, when, and the requested action.")
    defect.last_escalation_note = str(note).strip()
    defect.last_escalation_at = timezone.now()
    defect.last_escalated_by = actor
    defect.escalation_count += 1
    defect.save(update_fields=(
        "last_escalation_note", "last_escalation_at", "last_escalated_by", "escalation_count", "updated_at",
    ))
    _event(defect.cycle, actor, "shadow_defect_escalated", reason=note, snapshot=_defect_data(defect))
    return defect


@transaction.atomic
def submit_reconciliation_run(run, actor):
    run = FinanceShadowReconciliationRun.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=run.pk)
    if not can_manage_shadow_operation(actor, run.cycle.department):
        raise PermissionDenied
    if run.status not in {FinanceShadowReconciliationRun.OPEN, FinanceShadowReconciliationRun.RETURNED}:
        raise ValidationError("Only an open or returned scheduled run can be submitted.")
    comparisons = list(run.cycle.comparisons.select_related("defect_owner").order_by("comparison_level", "control_code", "pk"))
    if not comparisons:
        raise ValidationError("Add the current case, batch, period, register, ledger, or report controls before submitting this run.")
    for comparison in comparisons:
        comparison.full_clean()
        if comparison.outcome == FinanceShadowComparison.OPEN_DEFECT and not comparison.defects.exclude(status=FinanceShadowDefect.RESOLVED).exists():
            raise ValidationError(f"Register severity, owner, due time, and escalation route for open control {comparison.control_code}.")
    defects = list(run.cycle.defects.select_related("owner").order_by("created_at", "pk"))
    comparison_snapshot = json.loads(json.dumps(
        [_comparison_data(item) for item in comparisons], cls=DjangoJSONEncoder,
    ))
    defect_snapshot = json.loads(json.dumps(
        [_defect_data(item) for item in defects], cls=DjangoJSONEncoder,
    ))
    open_defect_count = sum(item.status != FinanceShadowDefect.RESOLVED for item in defects)
    run.comparison_snapshot = comparison_snapshot
    run.defect_snapshot = defect_snapshot
    run.comparison_count = len(comparisons)
    run.matched_count = sum(item.outcome == FinanceShadowComparison.MATCHED for item in comparisons)
    run.explained_count = sum(item.outcome == FinanceShadowComparison.EXPLAINED for item in comparisons)
    run.open_defect_count = open_defect_count
    run.submitted_by = None
    run.submitted_at = None
    run.reviewed_by = None
    run.reviewed_at = None
    run.review_note = ""
    payload = _run_data(run)
    payload["status"] = FinanceShadowReconciliationRun.OPEN
    payload["evidence_checksum"] = ""
    run.evidence_checksum = _checksum_payload(payload)
    run.status = FinanceShadowReconciliationRun.SUBMITTED
    run.submitted_by = actor
    run.submitted_at = timezone.now()
    run.reviewed_by = None
    run.reviewed_at = None
    run.review_note = ""
    run.save(update_fields=(
        "comparison_snapshot", "defect_snapshot", "comparison_count", "matched_count",
        "explained_count", "open_defect_count", "evidence_checksum", "status", "submitted_by",
        "submitted_at", "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ))
    _event(run.cycle, actor, "shadow_reconciliation_run_submitted", snapshot=_run_data(run))
    return run


@transaction.atomic
def review_reconciliation_run(run, actor, *, accept, reason):
    run = FinanceShadowReconciliationRun.objects.select_for_update().select_related("cycle", "cycle__department").get(pk=run.pk)
    if not can_review_shadow_reconciliation(actor, run.cycle.department):
        raise PermissionDenied
    if run.status != FinanceShadowReconciliationRun.SUBMITTED:
        raise ValidationError("This scheduled run is not awaiting review.")
    if actor.pk == run.submitted_by_id:
        raise ValidationError("The run submitter cannot independently review the same evidence.")
    if not str(reason or "").strip():
        raise ValidationError("Record the exact comparison review basis or correction required.")
    payload = _run_data(run)
    stored = payload["evidence_checksum"]
    payload["status"] = FinanceShadowReconciliationRun.OPEN
    payload["evidence_checksum"] = ""
    payload["submitted_by_id"] = None
    payload["submitted_at"] = None
    payload["reviewed_by_id"] = None
    payload["reviewed_at"] = None
    payload["review_note"] = ""
    if _checksum_payload(payload) != stored:
        raise ValidationError("The scheduled-run evidence changed after submission. Return it rather than accepting altered evidence.")
    if accept:
        run.status = (
            FinanceShadowReconciliationRun.REVIEWED_WITH_EXCEPTIONS
            if run.open_defect_count else FinanceShadowReconciliationRun.RECONCILED
        )
        run.reviewed_by = actor
        run.reviewed_at = timezone.now()
    else:
        run.status = FinanceShadowReconciliationRun.RETURNED
        run.reviewed_by = None
        run.reviewed_at = None
    run.review_note = str(reason).strip()
    run.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
    _event(
        run.cycle, actor,
        "shadow_reconciliation_run_reviewed" if accept else "shadow_reconciliation_run_returned",
        reason=reason, snapshot=_run_data(run),
    )
    return run


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
    try:
        plan = cycle.reconciliation_plan
    except FinanceShadowReconciliationPlan.DoesNotExist as exc:
        raise ValidationError("Prepare and independently approve the local reconciliation cadence and escalation plan before starting.") from exc
    if plan.status != FinanceShadowReconciliationPlan.APPROVED:
        raise ValidationError("The local reconciliation cadence and escalation plan is not independently approved.")
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
    try:
        plan = cycle.reconciliation_plan
    except FinanceShadowReconciliationPlan.DoesNotExist as exc:
        raise ValidationError("The cycle has no approved reconciliation plan.") from exc
    reviewed_statuses = {
        FinanceShadowReconciliationRun.RECONCILED,
        FinanceShadowReconciliationRun.REVIEWED_WITH_EXCEPTIONS,
    }
    runs = list(cycle.reconciliation_runs.all())
    if len([item for item in runs if item.status in reviewed_statuses]) < plan.minimum_reviewed_runs:
        raise ValidationError(f"Complete at least {plan.minimum_reviewed_runs} independently reviewed scheduled reconciliation run(s).")
    if any(item.status not in reviewed_statuses for item in runs):
        raise ValidationError("Finish or independently review every opened scheduled reconciliation run before cycle submission.")
    if cycle.defects.exclude(status=FinanceShadowDefect.RESOLVED).exists():
        raise ValidationError("Independently resolve every registered defect before final cycle reconciliation review.")
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
def decide_stakeholder_acceptance(
    acceptance, actor, *, decision, training_reference, uat_reference,
    signed_decision_reference, signed_decision_checksum, reason="",
):
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
    if not str(signed_decision_reference or "").strip():
        raise ValidationError("Reference the retained signed or attributable stakeholder decision record.")
    checksum = str(signed_decision_checksum or "").strip().lower()
    if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
        raise ValidationError("Enter the 64-character SHA-256 of the retained stakeholder decision copy.")
    if decision == FinanceStakeholderAcceptance.ACCEPTED:
        readiness_plan = FinanceCutoverReadinessPlan.objects.filter(cycle=acceptance.cycle).first()
        if not readiness_plan:
            raise ValidationError("Approve the local curriculum and support plan before accepting this scope.")
        if readiness_plan.status != FinanceCutoverReadinessPlan.APPROVED:
            raise ValidationError("The local curriculum and support plan is not independently approved.")
        if not acceptance.training_exercises.filter(
            kind=FinanceCutoverReadinessExercise.ROLE_TRAINING,
            status=FinanceCutoverReadinessExercise.PASSED,
        ).exists():
            raise ValidationError(
                "Complete and independently witness the named stakeholder's role exercise before acceptance. "
                "Private Internal How-To progress is not acceptance evidence."
            )
    if decision != FinanceStakeholderAcceptance.ACCEPTED and not reason.strip():
        raise ValidationError("State each condition or the reason the scope is not accepted.")
    acceptance.training_evidence_reference = training_reference.strip()
    acceptance.uat_evidence_reference = uat_reference.strip()
    acceptance.signed_decision_reference = str(signed_decision_reference).strip()
    acceptance.signed_decision_checksum = checksum
    acceptance.decision = decision
    acceptance.conditions_or_reason = reason.strip()
    acceptance.decided_by = actor
    acceptance.decided_at = timezone.now()
    acceptance.full_clean()
    acceptance.save(update_fields=(
        "training_evidence_reference", "uat_evidence_reference", "signed_decision_reference",
        "signed_decision_checksum", "decision",
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
            "signed_decision_reference": acceptance.signed_decision_reference,
            "signed_decision_checksum": acceptance.signed_decision_checksum,
        },
    )
    return acceptance


def cutover_readiness(cycle):
    discovery_decisions = list(cycle.discovery_decisions.order_by("phase", "code", "version"))
    current_discovery_decisions = [
        item for item in discovery_decisions
        if item.status != FinanceDiscoveryDecision.SUPERSEDED
    ]
    discovery_blockers = [
        item for item in current_discovery_decisions if item.blocks_affected_scope
    ]
    discovery_coverage = [
        item for item in current_discovery_decisions
        if item.status == FinanceDiscoveryDecision.RECORDED
        and item.phase == "F0"
        and item.coverage_kind == FinanceDiscoveryDecision.SCOPE_ACCEPTANCE
        and item.evidence_label == FinanceDiscoveryDecision.LGU_CONFIRMED
        and not item.blocks_affected_scope
        and item.acceptance_example_reference.strip()
        and item.affected_scope.strip() == cycle.enabled_scope.strip()
    ]
    accepted_discovery_kinds = {
        item.coverage_kind for item in current_discovery_decisions
        if item.status == FinanceDiscoveryDecision.RECORDED
        and item.phase == "F0"
        and item.coverage_kind in FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS
        and item.evidence_label == FinanceDiscoveryDecision.LGU_CONFIRMED
        and not item.blocks_affected_scope
        and item.acceptance_example_reference.strip()
    }
    missing_discovery_kinds = sorted(
        FinanceDiscoveryDecision.REQUIRED_COVERAGE_KINDS - accepted_discovery_kinds
    )
    coverage_labels = dict(FinanceDiscoveryDecision.COVERAGE_KIND_CHOICES)
    rows = list(cycle.stakeholder_acceptances.all())
    present = {row.stakeholder_kind for row in rows}
    missing = sorted(REQUIRED_STAKEHOLDERS - present)
    blocking = [
        row for row in rows
        if row.decision != FinanceStakeholderAcceptance.ACCEPTED
    ]
    readiness_plan = FinanceCutoverReadinessPlan.objects.filter(cycle=cycle).first()
    exercises = list(cycle.cutover_readiness_exercises.select_related("recovery_rehearsal"))
    passed_nonfunctional = {
        item.kind for item in exercises
        if item.status == FinanceCutoverReadinessExercise.PASSED
        and item.kind in REQUIRED_NONFUNCTIONAL_EXERCISES
        and (
            item.kind != FinanceCutoverReadinessExercise.BACKUP_RESTORE
            or _recovery_rehearsal_pass_ready(item)
        )
    }
    missing_exercises = sorted(REQUIRED_NONFUNCTIONAL_EXERCISES - passed_nonfunctional)
    role_training_missing = [
        row.pk for row in rows
        if not any(
            item.kind == FinanceCutoverReadinessExercise.ROLE_TRAINING
            and item.stakeholder_acceptance_id == row.pk
            and item.status == FinanceCutoverReadinessExercise.PASSED
            for item in exercises
        )
    ]
    unfinished_exercises = [
        item for item in exercises if item.status != FinanceCutoverReadinessExercise.PASSED
    ]
    qualification_plan = FinanceCutoverQualificationPlan.objects.filter(cycle=cycle).first()
    qualification_forms_current = False
    qualification_form_ids = []
    qualification_form_error = "The qualification plan has no exact current accepted-form lineage."
    current_qualification_forms = []
    if qualification_plan and qualification_plan.status == FinanceCutoverQualificationPlan.APPROVED:
        try:
            current_qualification_rows = _validated_qualification_forms(qualification_plan)
        except ValidationError as exc:
            qualification_form_error = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
        else:
            current_qualification_forms = [
                _qualification_form_data(item) for item in current_qualification_rows
            ]
            qualification_form_ids = [item.local_form_id for item in current_qualification_rows]
            qualification_forms_current = True
    qualification_evidence = list(
        qualification_plan.cycle_evidence.select_related("cycle").order_by("sequence", "pk")
    ) if qualification_plan else []
    accepted_qualification = [
        item for item in qualification_evidence
        if item.status == FinanceCutoverQualificationEvidence.ACCEPTED
    ]
    expected_sequences = list(range(1, len(accepted_qualification) + 1))
    actual_sequences = [item.sequence for item in accepted_qualification]
    qualification_chain_valid = bool(accepted_qualification) and actual_sequences == expected_sequences
    if qualification_chain_valid:
        qualification_chain_valid = accepted_qualification[-1].cycle_id == cycle.pk
    if qualification_chain_valid:
        qualification_chain_valid = all(
            current.cycle.predecessor_id == prior.cycle_id
            for prior, current in zip(accepted_qualification, accepted_qualification[1:])
        )
    minimum_cycles_met = bool(
        qualification_plan
        and len(accepted_qualification) >= qualification_plan.minimum_consecutive_cycles
    )
    parallel_cycle_met = bool(
        qualification_plan
        and (
            not qualification_plan.require_parallel_cycle
            or any(item.cycle.run_kind == FinanceShadowCycle.PARALLEL for item in accepted_qualification)
        )
    )
    unfinished_qualification = [
        item for item in qualification_evidence
        if item.status != FinanceCutoverQualificationEvidence.ACCEPTED
    ]
    qualification_evidence_forms_match = bool(accepted_qualification) and all(
        item.accepted_forms_snapshot == current_qualification_forms
        and item.accepted_forms_checksum == _checksum_payload(current_qualification_forms)
        for item in accepted_qualification
    )
    unsigned_stakeholders = [
        row.pk for row in rows
        if row.decision == FinanceStakeholderAcceptance.ACCEPTED
        and (not row.signed_decision_reference.strip() or len(row.signed_decision_checksum) != 64)
    ]
    checks = [
        {
            "code": "discovery_scope_accepted",
            "passed": bool(discovery_coverage) and not discovery_blockers,
            "message": (
                "An independently recorded LGU-confirmed F0 decision covers this exact enabled scope, and no linked discovery finding blocks it."
                if discovery_coverage and not discovery_blockers
                else (
                    "One or more current linked discovery findings still blocks its named scope."
                    if discovery_blockers
                    else "Record an independently reviewed, LGU-confirmed F0 decision for this exact enabled scope; absence of a finding is not acceptance evidence."
                )
            ),
        },
        {
            "code": "discovery_dimensions_accepted",
            "passed": not missing_discovery_kinds,
            "message": (
                "LGU-confirmed acceptance examples cover every required discovery area for this cycle."
                if not missing_discovery_kinds
                else "Missing LGU-confirmed discovery coverage: " + ", ".join(
                    coverage_labels[kind] for kind in missing_discovery_kinds
                )
            ),
        },
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
        {
            "code": "stakeholder_decisions_retained",
            "passed": bool(rows) and not unsigned_stakeholders,
            "message": (
                "Every accepted stakeholder decision has a retained signed/attributable record reference and SHA-256."
                if rows and not unsigned_stakeholders
                else "One or more accepted stakeholder decisions lacks a retained decision reference or SHA-256."
            ),
        },
        {
            "code": "qualification_plan_approved",
            "passed": bool(
                qualification_plan
                and qualification_plan.status == FinanceCutoverQualificationPlan.APPROVED
            ),
            "message": (
                "The locally editable field-cycle qualification plan is independently approved."
                if qualification_plan and qualification_plan.status == FinanceCutoverQualificationPlan.APPROVED
                else "The field-cycle qualification plan is missing or not independently approved."
            ),
        },
        {
            "code": "accepted_local_forms_current",
            "passed": qualification_forms_current,
            "message": (
                "Every qualifying cycle is governed by exact, checksum-pinned, currently accepted local form versions."
                if qualification_forms_current
                else qualification_form_error
            ),
        },
        {
            "code": "qualification_forms_match",
            "passed": qualification_evidence_forms_match,
            "message": (
                "Every accepted qualifying cycle used the plan's exact accepted-form set."
                if qualification_evidence_forms_match
                else "One or more accepted field cycles does not preserve the plan's current exact accepted-form set."
            ),
        },
        {
            "code": "consecutive_field_cycles_accepted",
            "passed": bool(minimum_cycles_met and qualification_chain_valid and not unfinished_qualification),
            "message": (
                "The required consecutive predecessor chain ends at this candidate cycle, and every recorded field cycle is independently accepted."
                if minimum_cycles_met and qualification_chain_valid and not unfinished_qualification
                else "The accepted field evidence does not yet meet the local minimum, form one uninterrupted predecessor chain ending here, or still has open rows."
            ),
        },
        {
            "code": "parallel_field_cycle_accepted",
            "passed": parallel_cycle_met,
            "message": (
                "The local parallel-run requirement is satisfied."
                if parallel_cycle_met
                else "The approved plan requires at least one accepted controlled parallel cycle."
            ),
        },
        {
            "code": "readiness_plan_approved",
            "passed": bool(readiness_plan and readiness_plan.status == FinanceCutoverReadinessPlan.APPROVED),
            "message": (
                "The local curriculum, quick-guide, supervisor-runbook, and support plan is independently approved."
                if readiness_plan and readiness_plan.status == FinanceCutoverReadinessPlan.APPROVED
                else "The local curriculum and support plan is missing or not independently approved."
            ),
        },
        {
            "code": "role_exercises_passed",
            "passed": bool(rows) and not role_training_missing,
            "message": (
                "Every named stakeholder has a passed, independently witnessed role exercise."
                if rows and not role_training_missing
                else "One or more named stakeholders still lack a passed role exercise. Private tutorial progress does not satisfy this gate."
            ),
        },
        {
            "code": "nonfunctional_exercises_passed",
            "passed": not missing_exercises,
            "message": (
                "Security, privacy, accessibility, performance, printing, recovery, continuity, and incident exercises all passed."
                if not missing_exercises
                else "Missing passed nonfunctional exercise kinds: " + ", ".join(missing_exercises)
            ),
        },
        {
            "code": "all_exercises_closed",
            "passed": bool(exercises) and not unfinished_exercises,
            "message": (
                "Every scheduled readiness exercise has a final passed result."
                if exercises and not unfinished_exercises
                else "Planned, submitted, or returned readiness exercises still block cutover."
            ),
        },
    ]
    return {
        "ready": all(check["passed"] for check in checks),
        "checks": checks,
        "missing": missing,
        "blocking": blocking,
        "missing_exercises": missing_exercises,
        "role_training_missing": role_training_missing,
        "unfinished_exercise_ids": [item.pk for item in unfinished_exercises],
        "unsigned_stakeholder_ids": unsigned_stakeholders,
        "qualification_plan_status": qualification_plan.status if qualification_plan else "missing",
        "qualification_form_ids": qualification_form_ids,
        "qualification_forms_current": qualification_forms_current,
        "qualification_evidence_forms_match": qualification_evidence_forms_match,
        "accepted_qualification_cycle_ids": [item.cycle_id for item in accepted_qualification],
        "unfinished_qualification_evidence_ids": [item.pk for item in unfinished_qualification],
        "discovery_decision_ids": [item.pk for item in discovery_decisions],
        "discovery_blocking_ids": [item.pk for item in discovery_blockers],
        "discovery_coverage_ids": [item.pk for item in discovery_coverage],
        "accepted_discovery_kinds": sorted(accepted_discovery_kinds),
        "missing_discovery_kinds": missing_discovery_kinds,
    }


@transaction.atomic
def submit_cutover_decision(decision, actor):
    decision = FinanceCutoverDecision.objects.select_for_update().select_related(
        "cycle", "cycle__department", "recovery_rehearsal", "recovery_rehearsal__exercise",
    ).get(pk=decision.pk)
    if not can_manage_shadow_operation(actor, decision.cycle.department):
        raise PermissionDenied
    if decision.status != FinanceCutoverDecision.DRAFT:
        raise ValidationError("Only a draft cutover record can be submitted.")
    if not decision.signed_authority_reference.strip() or not decision.signature_custody_reference.strip():
        raise ValidationError("Reference the retained signed authority record and its local custodian before submission.")
    if len(decision.signed_authority_checksum) != 64:
        raise ValidationError("Enter the 64-character SHA-256 of the retained signed authority record before submission.")
    readiness = cutover_readiness(decision.cycle)
    if not readiness["ready"]:
        raise ValidationError(
            "Cutover submission is blocked until discovery coverage, field-cycle qualification, "
            "readiness exercises, shadow reconciliation, and every required stakeholder acceptance pass."
        )
    if not decision.recovery_rehearsal_id:
        raise ValidationError("Bind the cutover record to its independently passed structured recovery rehearsal.")
    if decision.recovery_rehearsal.exercise.cycle_id != decision.cycle_id:
        raise ValidationError("The bound recovery rehearsal belongs to a different cutover cycle.")
    _validated_recovery_rehearsal(
        decision.recovery_rehearsal.exercise, require_objectives=True,
    )
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
        "recovery_rehearsal_id": decision.recovery_rehearsal_id,
        "recovery_backup_id": (
            decision.recovery_rehearsal.backup_id if decision.recovery_rehearsal_id else ""
        ),
        "recovery_evidence_checksum": (
            decision.recovery_rehearsal.evidence_checksum if decision.recovery_rehearsal_id else ""
        ),
        "signed_authority_reference": decision.signed_authority_reference,
        "signed_authority_checksum": decision.signed_authority_checksum,
        "signature_custody_reference": decision.signature_custody_reference,
        "prepared_by_id": decision.prepared_by_id,
        "submitted_by_id": decision.submitted_by_id,
        "decided_by_id": decision.decided_by_id,
        "decided_at": decision.decided_at,
        "decision_reason": decision.decision_reason,
    }


@transaction.atomic
def decide_cutover(decision, actor, *, authorize, reason):
    decision = FinanceCutoverDecision.objects.select_for_update().select_related(
        "cycle", "cycle__department", "recovery_rehearsal", "recovery_rehearsal__exercise",
    ).get(pk=decision.pk)
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
    if authorize:
        if not decision.recovery_rehearsal_id:
            raise ValidationError("Authorization requires a bound structured recovery rehearsal.")
        _validated_recovery_rehearsal(
            decision.recovery_rehearsal.exercise, require_objectives=True,
        )
    if authorize and (
        not decision.signed_authority_reference.strip()
        or not decision.signature_custody_reference.strip()
        or len(decision.signed_authority_checksum) != 64
    ):
        raise ValidationError("Authorization requires a retained signed authority reference, custody location, and SHA-256.")
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
            "signed_decision_reference": row.signed_decision_reference,
            "signed_decision_checksum": row.signed_decision_checksum,
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
    readiness_plan = FinanceCutoverReadinessPlan.objects.filter(cycle=cycle).first()
    readiness_exercises = [
        _readiness_exercise_data(item)
        for item in cycle.cutover_readiness_exercises.select_related(
            "recovery_rehearsal",
        ).order_by("kind", "scheduled_for", "code")
    ]
    qualification_plan = FinanceCutoverQualificationPlan.objects.filter(cycle=cycle).first()
    qualification_evidence = [
        _qualification_evidence_data(item)
        for item in (
            qualification_plan.cycle_evidence.select_related("cycle").order_by("sequence", "pk")
            if qualification_plan else []
        )
    ]
    discovery_decisions = [
        {
            "public_id": str(item.public_id),
            "code": item.code,
            "version": item.version,
            "phase": item.phase,
            "coverage_kind": item.coverage_kind,
            "status": item.status,
            "question": item.question,
            "proposed_outcome": item.proposed_outcome,
            "affected_scope": item.affected_scope,
            "evidence_label": item.evidence_label,
            "authority_evidence_reference": item.authority_evidence_reference,
            "evidence_needed": item.evidence_needed,
            "evidence_custody_reference": item.evidence_custody_reference,
            "acceptance_example_reference": item.acceptance_example_reference,
            "blocks_affected_scope": item.blocks_affected_scope,
            "owner_id": item.owner_id,
            "reviewer_id": item.reviewer_id,
            "due_date": item.due_date,
            "predecessor_id": item.predecessor_id,
            "change_reason": item.change_reason,
            "evidence_snapshot": item.evidence_snapshot,
            "evidence_checksum": item.evidence_checksum,
            "submitted_by_id": item.submitted_by_id,
            "submitted_at": item.submitted_at,
            "reviewed_by_id": item.reviewed_by_id,
            "reviewed_at": item.reviewed_at,
            "review_note": item.review_note,
        }
        for item in cycle.discovery_decisions.order_by("phase", "code", "version")
    ]
    payload = {
        "format": "GRAND Finance shadow/cutover evidence",
        "schema_version": 9,
        "notice": "Portable evidence copy. Authority exists only when the included decision status is authorized for its exact scope and date.",
        "cycle": cycle_payload,
        "stored_cycle_evidence_checksum": cycle.evidence_checksum,
        "computed_cycle_evidence_checksum": computed_checksum,
        "stakeholder_acceptances": acceptances,
        "cutover_readiness_plan": _readiness_plan_data(readiness_plan) if readiness_plan else None,
        "cutover_readiness_exercises": readiness_exercises,
        "cutover_qualification_plan": _qualification_plan_data(qualification_plan) if qualification_plan else None,
        "cutover_qualification_evidence": qualification_evidence,
        "discovery_decisions": discovery_decisions,
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
            "discovery_decision_count": len(discovery_decisions),
        },
    )
    _event(cycle, actor, "shadow_cutover_evidence_exported", snapshot={
        "relative_path": receipt["relative_path"], "sha256": receipt["sha256"],
    })
    return content, filename, receipt
