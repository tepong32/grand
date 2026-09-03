import csv
import hashlib
import io
import json
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from reporting.models import ReportDefinition, ReportRun, ReportTemplateVersion
from reporting.template_services import template_snapshot
from src.export_archive import archive_export

from .access import department_for_user, has_explicit_permission
from .models import RemittanceEvent, TaxFilingEvidence, TreasuryRemittanceBatch, TreasuryRemittanceLine


class TaxFilingWorkflowError(ValidationError):
    pass


TAX_RETURN_SUMMARY_DATASET = "finance_governed_tax_return_summary"


def _require(actor, permission):
    if not has_explicit_permission(actor, permission):
        raise PermissionDenied


def _require_treasury_scope(actor, batch):
    department = department_for_user(actor)
    if department is None or batch.treasury_department_id != department.pk:
        raise PermissionDenied("Tax-remittance preparation is limited to the owning Treasury office.")


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def tax_scope(batch):
    lines = list(batch.lines.filter(status=TreasuryRemittanceLine.ACTIVE).order_by("pk"))
    if not lines:
        raise TaxFilingWorkflowError("The remittance has no active allocation lines.")
    if any(not line.tax_rule_checksum or not line.tax_rule_snapshot for line in lines):
        raise TaxFilingWorkflowError(
            "This remittance mixes or lacks governed tax-rule evidence. Use the generic remittance register."
        )
    forms = {str(line.tax_rule_snapshot.get("return_form_code") or "").strip().upper() for line in lines}
    if len(forms) != 1 or not next(iter(forms)):
        raise TaxFilingWorkflowError("One filing evidence package must use one governed return/remittance form.")
    rules = {}
    for line in lines:
        rules[line.tax_rule_checksum] = {
            key: line.tax_rule_snapshot.get(key, "")
            for key in (
                "tax_family", "atc", "rate_percent", "tax_base_label", "return_form_code",
                "certificate_form_code", "rounding_mode", "authority_reference",
                "local_applicability_note", "tax_rule_checksum",
            )
        }
    snapshot = {
        "schema_version": 1,
        "remittance_public_id": str(batch.public_id),
        "remittance_reference": batch.reference_code,
        "remittance_date": batch.remittance_date.isoformat(),
        "recipient_code": batch.recipient_party.code,
        "recipient_name": batch.recipient_party.display_name,
        "fund_code": batch.fund_code,
        "total_amount": str(batch.total_amount),
        "release_reference": batch.release_reference,
        "acknowledgement_reference": batch.acknowledgement_reference,
        "return_form_code": next(iter(forms)),
        "rules": [rules[key] for key in sorted(rules)],
        "allocation_evidence": [
            {
                "line_id": line.pk, "deduction_code": line.deduction_code,
                "reference_key": line.reference_key, "amount": str(line.amount),
                "source_checksum": line.source_checksum, "tax_rule_checksum": line.tax_rule_checksum,
            }
            for line in lines
        ],
    }
    return snapshot, _digest(snapshot)


def eligible_source_runs(batch):
    """Official, reconciled GRAND tax summaries offered to ordinary preparers."""
    mapping_ready = (
        Q(template_version__render_mode=ReportTemplateVersion.RENDER_NATIVE)
        | Q(
            template_version__mapping_checksum__regex=r"^[0-9a-fA-F]{64}$",
            template_version__mapping_validated_at__isnull=False,
        )
    )
    return ReportRun.objects.filter(mapping_ready,
        definition__department_id=batch.finance_department_id,
        definition__dataset_key=TAX_RETURN_SUMMARY_DATASET,
        definition__applicability_status=ReportDefinition.APPLICABILITY_CONFIRMED,
        status=ReportRun.APPROVED, control_status=ReportRun.CONTROL_RECONCILED,
        control_gate_required=True, approved_at__isnull=False,
        checksum__regex=r"^[0-9a-fA-F]{64}$",
        dataset_checksum__regex=r"^[0-9a-fA-F]{64}$",
        control_checksum__regex=r"^[0-9a-fA-F]{64}$",
        reproduction_key__regex=r"^[0-9a-fA-F]{64}$",
        template_version__fidelity_status=ReportTemplateVersion.OFFICIAL,
        template_version__approved_at__isnull=False,
        template_version__fidelity_validated_at__isnull=False,
    ).select_related("definition", "template_version").order_by("-period_end", "-created_at")


def _validated_report_source(*, run, batch, period_start, period_end, return_form_code):
    current = eligible_source_runs(batch).filter(pk=run.pk).first() if run else None
    if current is None:
        raise TaxFilingWorkflowError(
            "Select an approved, control-reconciled GRAND tax return/remittance summary using a department-validated official template."
        )
    if not current.template_version.is_official_ready:
        raise TaxFilingWorkflowError("The selected GRAND report's template is no longer complete official evidence.")
    if not current.definition.authority_reference.strip() or not current.definition.local_acceptance_note.strip():
        raise TaxFilingWorkflowError("The selected GRAND report is missing its locally reviewed authority or acceptance basis.")
    if current.period_start != period_start or current.period_end != period_end:
        raise TaxFilingWorkflowError("The selected GRAND report must use the exact tax period recorded in this filing evidence.")
    rows = (current.dataset_snapshot or {}).get("rows") or []
    forms = {str(row.get("return_form_code") or "").strip().upper() for row in rows}
    if forms != {return_form_code}:
        raise TaxFilingWorkflowError(
            f"Generate and approve a {return_form_code}-only tax return/remittance summary for this exact period."
        )
    try:
        reported_total = sum((Decimal(str(row.get("tax_withheld") or "0")) for row in rows), Decimal("0.00"))
    except (ArithmeticError, ValueError):
        raise TaxFilingWorkflowError("The selected GRAND tax report has an unreadable withholding control total.")
    if reported_total != batch.total_amount:
        raise TaxFilingWorkflowError(
            f"The selected report total {reported_total:,.2f} must equal this remittance total {batch.total_amount:,.2f}."
        )
    template = template_snapshot(current.template_version)
    snapshot = {
        "schema_version": 1, "run_public_id": str(current.public_id),
        "definition_slug": current.definition.slug, "definition_name": current.definition.name,
        "dataset_key": current.definition.dataset_key,
        "definition_applicability": current.definition.applicability_status,
        "period_start": current.period_start.isoformat(), "period_end": current.period_end.isoformat(),
        "output_format": current.output_format, "output_checksum": current.checksum,
        "dataset_checksum": current.dataset_checksum, "control_checksum": current.control_checksum,
        "control_status": current.control_status, "control_totals": current.control_totals,
        "control_message": current.control_message,
        "control_gate_required": current.control_gate_required,
        "reproduction_key": current.reproduction_key,
        "row_count": current.row_count, "source_record_count": current.source_record_count,
        "reported_tax_withheld": str(reported_total),
        "template_version": current.template_version.version,
        "template_snapshot": template, "template_checksum": _digest(template),
        "approved_at": current.approved_at.isoformat() if current.approved_at else "",
    }
    return current, snapshot


def _evidence_payload(item):
    payload = {
        "schema_version": item.evidence_schema_version,
        "batch_public_id": str(item.batch.public_id),
        "version": item.version, "supersedes": str(item.supersedes.public_id) if item.supersedes_id else "",
        "filing_type": item.filing_type, "return_form_code": item.return_form_code,
        "tax_period_start": item.tax_period_start.isoformat(),
        "tax_period_end": item.tax_period_end.isoformat(), "filing_date": item.filing_date.isoformat(),
        "submission_channel": item.submission_channel, "filing_reference": item.filing_reference,
        "payment_confirmation_reference": item.payment_confirmation_reference,
        "source_schedule_reference": item.source_schedule_reference,
        "source_schedule_checksum": item.source_schedule_checksum,
        "evidence_reference": item.evidence_reference, "tax_scope_snapshot": item.tax_scope_snapshot,
    }
    if item.evidence_schema_version >= item.CURRENT_EVIDENCE_SCHEMA:
        payload.update({
            "source_mode": item.source_mode,
            "source_report_run_public_id": (
                str(item.source_report_run_public_id) if item.source_report_run_public_id else ""
            ),
            "source_report_snapshot": item.source_report_snapshot,
            "external_source_basis": item.external_source_basis,
        })
    return payload


def _refresh_checksum(item):
    item.evidence_checksum = _digest(_evidence_payload(item))


def _event(item, actor, action, previous, reason=""):
    return RemittanceEvent.objects.create(
        batch=item.batch, action=action, actor=actor, actor_department=department_for_user(actor),
        from_status=previous, to_status=item.status, reason=reason.strip(),
        metadata={"tax_filing_evidence": str(item.public_id), "version": item.version,
                  "evidence_schema_version": item.evidence_schema_version,
                  "evidence_checksum": item.evidence_checksum, "source_mode": item.source_mode,
                  "source_report_run": str(item.source_report_run_public_id or "")},
        state_version=item.batch.state_version,
    )


@transaction.atomic
def save_draft(*, batch, actor, evidence=None, **values):
    _require(actor, "vouchers.prepare_remittances")
    locked_batch = TreasuryRemittanceBatch.objects.select_for_update().select_related("recipient_party").get(pk=batch.pk)
    _require_treasury_scope(actor, locked_batch)
    if locked_batch.status not in {locked_batch.ACCOUNTING_POSTING, locked_batch.COMPLETED}:
        raise TaxFilingWorkflowError("Record the actual remittance release before preparing filing evidence.")
    scope, _scope_checksum = tax_scope(locked_batch)
    if evidence is None:
        if locked_batch.tax_filing_evidence.exclude(status=TaxFilingEvidence.SUPERSEDED).exists():
            raise TaxFilingWorkflowError("This remittance already has current filing evidence.")
        evidence = TaxFilingEvidence(
            batch=locked_batch, version=1, filing_type=TaxFilingEvidence.ORIGINAL,
            created_by=actor,
        )
        previous = ""
    else:
        evidence = TaxFilingEvidence.objects.select_for_update().get(pk=evidence.pk)
        if evidence.status not in {evidence.DRAFT, evidence.RETURNED}:
            raise TaxFilingWorkflowError("Only draft or returned filing evidence can be modified.")
        previous = evidence.status
    source_report_run = values.pop("source_report_run", None)
    for field, value in values.items():
        setattr(evidence, field, value.strip() if isinstance(value, str) else value)
    evidence.return_form_code = evidence.return_form_code.strip().upper()
    if evidence.return_form_code != scope["return_form_code"]:
        raise TaxFilingWorkflowError(
            f"Use the governed return/remittance form {scope['return_form_code']} for this remittance."
        )
    evidence.tax_scope_snapshot = scope
    if evidence.source_mode == evidence.GRAND_REPORT:
        run, report_snapshot = _validated_report_source(
            run=source_report_run, batch=locked_batch,
            period_start=evidence.tax_period_start, period_end=evidence.tax_period_end,
            return_form_code=evidence.return_form_code,
        )
        evidence.source_report_run_public_id = run.public_id
        evidence.source_report_snapshot = report_snapshot
        evidence.source_schedule_reference = f"GRAND {run.definition.slug} · {run.public_id}"
        evidence.source_schedule_checksum = run.checksum.lower()
        evidence.external_source_basis = ""
    elif evidence.source_mode == evidence.EXTERNAL_SCHEDULE:
        evidence.source_report_run_public_id = None
        evidence.source_report_snapshot = {}
    else:
        raise TaxFilingWorkflowError("Choose the approved GRAND report or advanced external-schedule source path.")
    evidence.evidence_schema_version = evidence.CURRENT_EVIDENCE_SCHEMA
    evidence.status = evidence.DRAFT
    evidence.review_reason = ""
    evidence.reviewed_by = None
    evidence.reviewed_at = None
    evidence.state_version += 1
    _refresh_checksum(evidence)
    evidence.full_clean(); evidence.save()
    _event(evidence, actor, "tax_filing_evidence_saved", previous)
    return evidence


@transaction.atomic
def submit_evidence(*, evidence, actor):
    _require(actor, "vouchers.prepare_remittances")
    item = TaxFilingEvidence.objects.select_for_update().select_related("batch").get(pk=evidence.pk)
    _require_treasury_scope(actor, item.batch)
    if item.status not in {item.DRAFT, item.RETURNED}:
        raise TaxFilingWorkflowError("Only draft or returned filing evidence can be submitted.")
    scope, _checksum = tax_scope(item.batch)
    if item.source_mode == item.GRAND_REPORT:
        run = ReportRun.objects.filter(public_id=item.source_report_run_public_id).first()
        _run, current_report_snapshot = _validated_report_source(
            run=run, batch=item.batch, period_start=item.tax_period_start,
            period_end=item.tax_period_end, return_form_code=item.return_form_code,
        )
        if current_report_snapshot != item.source_report_snapshot:
            raise TaxFilingWorkflowError("The selected GRAND tax report evidence changed. Save this draft again.")
    if scope != item.tax_scope_snapshot or _digest(_evidence_payload(item)) != item.evidence_checksum:
        raise TaxFilingWorkflowError("The filing evidence or its pinned tax/remittance scope changed. Save it again.")
    previous = item.status
    item.status = item.FOR_REVIEW; item.submitted_by = actor; item.submitted_at = timezone.now()
    item.state_version += 1; item.save()
    _event(item, actor, "tax_filing_evidence_submitted", previous)
    return item


@transaction.atomic
def review_evidence(*, evidence, actor, approve, reason):
    _require(actor, "vouchers.approve_remittances")
    item = TaxFilingEvidence.objects.select_for_update().get(pk=evidence.pk)
    if item.status != item.FOR_REVIEW:
        raise TaxFilingWorkflowError("Only submitted filing evidence is awaiting review.")
    if item.created_by_id == actor.pk or item.submitted_by_id == actor.pk:
        raise TaxFilingWorkflowError("Maker-checker control: the preparer cannot verify the same filing evidence.")
    if not reason.strip():
        raise TaxFilingWorkflowError("Record the verification basis or correction instruction.")
    previous = item.status
    item.status = item.VERIFIED if approve else item.RETURNED
    item.reviewed_by = actor; item.reviewed_at = timezone.now(); item.review_reason = reason.strip()
    item.state_version += 1; item.save()
    _event(item, actor, "tax_filing_evidence_verified" if approve else "tax_filing_evidence_returned", previous, reason)
    return item


@transaction.atomic
def create_amendment(*, evidence, actor, reason):
    _require(actor, "vouchers.prepare_remittances")
    prior = TaxFilingEvidence.objects.select_for_update().select_related("batch").get(pk=evidence.pk)
    _require_treasury_scope(actor, prior.batch)
    if prior.status != prior.VERIFIED:
        raise TaxFilingWorkflowError("Only verified evidence can start an amended successor.")
    if not reason.strip():
        raise TaxFilingWorkflowError("Explain why an amended filing-evidence version is required.")
    version = prior.batch.tax_filing_evidence.aggregate(value=Max("version"))["value"] + 1
    prior.status = prior.SUPERSEDED; prior.state_version += 1; prior.save()
    successor = TaxFilingEvidence(
        batch=prior.batch, version=version, supersedes=prior, filing_type=TaxFilingEvidence.AMENDED,
        return_form_code=prior.return_form_code, tax_period_start=prior.tax_period_start,
        tax_period_end=prior.tax_period_end, filing_date=prior.filing_date,
        submission_channel=prior.submission_channel, filing_reference=prior.filing_reference,
        payment_confirmation_reference=prior.payment_confirmation_reference,
        source_mode=prior.source_mode, source_report_run_public_id=prior.source_report_run_public_id,
        source_report_snapshot=prior.source_report_snapshot,
        source_schedule_reference=prior.source_schedule_reference,
        source_schedule_checksum=prior.source_schedule_checksum,
        external_source_basis=prior.external_source_basis, evidence_reference=prior.evidence_reference,
        tax_scope_snapshot=prior.tax_scope_snapshot,
        evidence_schema_version=TaxFilingEvidence.CURRENT_EVIDENCE_SCHEMA,
        status=TaxFilingEvidence.DRAFT,
        state_version=1, created_by=actor,
    )
    _refresh_checksum(successor); successor.full_clean(); successor.save()
    _event(successor, actor, "tax_filing_amendment_started", prior.VERIFIED, reason)
    return successor


def export_evidence_csv(*, evidence, actor):
    _require(actor, "vouchers.view_remittance_workbench")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "remittance_reference", "evidence_version", "status", "filing_type", "return_form_code",
        "period_start", "period_end", "filing_date", "submission_channel", "filing_reference",
        "payment_confirmation_reference", "source_schedule_reference", "source_schedule_sha256",
        "source_mode", "grand_report_run", "grand_definition", "grand_template_version",
        "external_source_basis", "evidence_schema_version",
        "remittance_total", "evidence_sha256",
    ])
    writer.writerow([
        evidence.batch.reference_code, evidence.version, evidence.get_status_display(),
        evidence.get_filing_type_display(), evidence.return_form_code,
        evidence.tax_period_start.isoformat(), evidence.tax_period_end.isoformat(),
        evidence.filing_date.isoformat(), evidence.submission_channel, evidence.filing_reference,
        evidence.payment_confirmation_reference, evidence.source_schedule_reference,
        evidence.source_schedule_checksum, evidence.get_source_mode_display(),
        str(evidence.source_report_run_public_id or ""),
        evidence.source_report_snapshot.get("definition_slug", ""),
        evidence.source_report_snapshot.get("template_version", ""),
        evidence.external_source_basis, evidence.evidence_schema_version,
        str(evidence.batch.total_amount), evidence.evidence_checksum,
    ])
    content = output.getvalue().encode("utf-8-sig")
    return content, archive_export(
        content=content, department=evidence.batch.treasury_department, user=actor,
        category="finance-tax-filings",
        filename=f"{evidence.batch.reference_code}-tax-filing-v{evidence.version}.csv",
        metadata={"tax_filing_public_id": str(evidence.public_id), "status": evidence.status,
                  "evidence_checksum": evidence.evidence_checksum},
    )
