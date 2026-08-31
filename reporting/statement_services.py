from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from accounting.models import LedgerAccount

from .models import (
    FinanceStatementLine, FinanceStatementMapping, FinanceStatementMappingEvent,
    FinanceStatementNote, FinanceStatementNoteEvent, FinanceStatementNoteSet,
    ReportReferenceComparison, ReportReferenceComparisonEvent, ReportRun,
)


STARTER_LINES = {
    FinanceStatementMapping.POSITION: (
        (10, "assets", "Assets", "assets", "Assets", "asset"),
        (20, "liabilities", "Liabilities", "liabilities", "Liabilities", "liability"),
        (30, "equity", "Equity", "equity", "Equity", "equity"),
    ),
    FinanceStatementMapping.PERFORMANCE: (
        (10, "revenue", "Revenue", "revenue", "Revenue", "revenue"),
        (20, "expenses", "Expenses", "expenses", "Expenses", "expense"),
    ),
}


def statement_mapping_snapshot(mapping):
    return {
        "public_id": str(mapping.public_id),
        "department_id": mapping.department_id,
        "statement_type": mapping.statement_type,
        "version": mapping.version,
        "title": mapping.title,
        "description": mapping.description,
        "status": mapping.status,
        "authority_reference": mapping.authority_reference,
        "local_acceptance_note": mapping.local_acceptance_note,
        "lines": [
            {
                "position": line.position,
                "section_code": line.section_code,
                "section_title": line.section_title,
                "line_code": line.line_code,
                "line_title": line.line_title,
                "selector_type": line.selector_type,
                "account_type": line.account_type,
                "account_codes": list(line.account_codes or []),
            }
            for line in mapping.lines.order_by("position", "pk")
        ],
    }


def snapshot_checksum(snapshot):
    payload = json.dumps(
        snapshot, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def current_statement_mapping(department, statement_type):
    mappings = FinanceStatementMapping.objects.filter(
        department=department, statement_type=statement_type,
    )
    return mappings.filter(status=FinanceStatementMapping.ACTIVE).first() or mappings.filter(
        status=FinanceStatementMapping.STARTER,
    ).first()


def mapping_coverage(mapping):
    allowed_types = (
        {"asset", "liability", "equity"}
        if mapping.statement_type == FinanceStatementMapping.POSITION
        else {"revenue", "expense"}
    )
    accounts = list(LedgerAccount.objects.filter(
        department_id=mapping.department_id, allow_posting=True, is_active=True,
        account_type__in=allowed_types,
    ).order_by("code"))
    by_code = {account.code: account for account in accounts}
    assignments = {}
    errors = []
    for line in mapping.lines.order_by("position", "pk"):
        if line.selector_type == FinanceStatementLine.ACCOUNT_TYPE:
            selected = [account.code for account in accounts if account.account_type == line.account_type]
        else:
            selected = list(line.account_codes or [])
            for code in selected:
                account = by_code.get(code)
                if not account:
                    errors.append(f"{line.line_title}: {code} is not an active posting account for this statement.")
        for code in selected:
            if code in assignments:
                errors.append(f"{code} is assigned to both {assignments[code]} and {line.line_title}.")
            else:
                assignments[code] = line.line_title
    unmapped = [account.code for account in accounts if account.code not in assignments]
    if unmapped:
        errors.append("Unmapped active posting accounts: " + ", ".join(unmapped))
    if not mapping.lines.exists():
        errors.append("Add at least one statement line before review.")
    return {
        "valid": not errors,
        "errors": errors,
        "active_account_count": len(accounts),
        "mapped_account_count": len(assignments),
        "unmapped_account_codes": unmapped,
    }


def seed_statement_starters(department, actor):
    created = []
    for statement_type, starter_lines in STARTER_LINES.items():
        if FinanceStatementMapping.objects.filter(
            department=department, statement_type=statement_type,
        ).exists():
            continue
        mapping = FinanceStatementMapping.objects.create(
            department=department, statement_type=statement_type, version=1,
            title=dict(FinanceStatementMapping.STATEMENT_CHOICES)[statement_type],
            description=(
                "Broad, human-editable management starter. Adopt an independently reviewed successor "
                "after the municipality confirms its current COA mapping and signed reference statements."
            ),
            status=FinanceStatementMapping.DRAFT, created_by=actor,
        )
        for position, section_code, section_title, line_code, line_title, account_type in starter_lines:
            FinanceStatementLine.objects.create(
                mapping=mapping, position=position, section_code=section_code,
                section_title=section_title, line_code=line_code, line_title=line_title,
                selector_type=FinanceStatementLine.ACCOUNT_TYPE, account_type=account_type,
            )
        mapping.status = FinanceStatementMapping.STARTER
        snapshot = statement_mapping_snapshot(mapping)
        mapping.snapshot_checksum = snapshot_checksum(snapshot)
        mapping.save(update_fields=("snapshot_checksum", "status", "updated_at"))
        FinanceStatementMappingEvent.objects.create(
            mapping=mapping, actor=actor, action="starter_seeded",
            reason="Controlled broad starter; local signed-statement comparison remains pending.",
            snapshot=snapshot,
        )
        created.append(mapping)
    return created


def submit_statement_mapping(mapping, actor):
    if not mapping.is_editable:
        raise ValidationError("Only an editable draft can be submitted.")
    coverage = mapping_coverage(mapping)
    if not coverage["valid"]:
        raise ValidationError(coverage["errors"])
    mapping.status = FinanceStatementMapping.SUBMITTED
    mapping.submitted_by = actor
    mapping.submitted_at = timezone.now()
    mapping.review_note = ""
    mapping.save(update_fields=("status", "submitted_by", "submitted_at", "review_note", "updated_at"))
    FinanceStatementMappingEvent.objects.create(
        mapping=mapping, actor=actor, action="submitted", snapshot=statement_mapping_snapshot(mapping),
    )
    return mapping


@transaction.atomic
def review_statement_mapping(mapping, actor, *, approve, note=""):
    if mapping.status != FinanceStatementMapping.SUBMITTED:
        raise ValidationError("Only a submitted mapping can be independently reviewed.")
    if mapping.created_by_id == actor.pk or mapping.submitted_by_id == actor.pk:
        raise ValidationError("The preparer or submitter cannot approve or return the same mapping.")
    note = (note or "").strip()
    if not approve:
        if not note:
            raise ValidationError("Explain the correction required before returning the mapping.")
        mapping.status = FinanceStatementMapping.RETURNED
        mapping.reviewed_by = actor
        mapping.reviewed_at = timezone.now()
        mapping.review_note = note
        mapping.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
        FinanceStatementMappingEvent.objects.create(
            mapping=mapping, actor=actor, action="returned", reason=note,
            snapshot=statement_mapping_snapshot(mapping),
        )
        return mapping

    coverage = mapping_coverage(mapping)
    if not coverage["valid"]:
        raise ValidationError(coverage["errors"])
    if not mapping.authority_reference.strip() or not mapping.local_acceptance_note.strip():
        raise ValidationError("Record both the reviewed authority and local acceptance evidence before activation.")
    prior = FinanceStatementMapping.objects.select_for_update().filter(
        department=mapping.department, statement_type=mapping.statement_type,
        status=FinanceStatementMapping.ACTIVE,
    ).first()
    mapping.reviewed_by = actor
    mapping.reviewed_at = timezone.now()
    mapping.review_note = note
    mapping.status = FinanceStatementMapping.ACTIVE
    snapshot = statement_mapping_snapshot(mapping)
    mapping.snapshot_checksum = snapshot_checksum(snapshot)
    if prior:
        prior.status = FinanceStatementMapping.SUPERSEDED
        prior.save(update_fields=("status", "updated_at"))
        FinanceStatementMappingEvent.objects.create(
            mapping=prior, actor=actor, action="superseded", reason=f"Replaced by version {mapping.version}.",
            snapshot=statement_mapping_snapshot(prior),
        )
    mapping.full_clean()
    mapping.save(update_fields=(
        "status", "reviewed_by", "reviewed_at", "review_note", "snapshot_checksum", "updated_at",
    ))
    FinanceStatementMappingEvent.objects.create(
        mapping=mapping, actor=actor, action="activated", reason=note, snapshot=snapshot,
    )
    return mapping


NOTE_STARTER_TOPICS = (
    (10, "reporting-entity", "Reporting entity and scope", FinanceStatementNote.GENERAL),
    (20, "basis-of-preparation", "Basis of preparation and measurement", FinanceStatementNote.GENERAL),
    (30, "significant-accounting-policies", "Significant accounting policies", FinanceStatementNote.GENERAL),
    (40, "cash-and-cash-equivalents", "Cash and cash equivalents", FinanceStatementNote.POSITION),
    (50, "receivables", "Receivables and allowances", FinanceStatementNote.POSITION),
    (60, "property-plant-and-equipment", "Property, plant and equipment", FinanceStatementNote.POSITION),
    (70, "payables-and-withholdings", "Payables, deductions, and withholding liabilities", FinanceStatementNote.POSITION),
    (80, "revenue", "Revenue and other receipts", FinanceStatementNote.PERFORMANCE),
    (90, "expenses", "Expenses", FinanceStatementNote.PERFORMANCE),
    (100, "commitments-and-contingencies", "Commitments, contingencies, and other required disclosures", FinanceStatementNote.BOTH),
    (110, "events-after-reporting-date", "Events after the reporting date", FinanceStatementNote.GENERAL),
)

STATEMENT_COMPARISON_CONTROLS = {
    "finance_statement_position": (
        ("assets", "Assets"),
        ("liabilities", "Liabilities"),
        ("equity", "Equity"),
        ("unclosed_operating_result", "Unclosed operating result"),
        ("equation_difference", "Equation difference"),
    ),
    "finance_statement_performance": (
        ("revenue", "Revenue"),
        ("expense", "Expense"),
        ("operating_result", "Surplus / (deficit)"),
    ),
}


def _run_dataset_key(run):
    return run.parameters.get("_definition_snapshot", {}).get(
        "dataset_key", run.definition.dataset_key,
    )


def _run_evidence(run):
    return {
        "public_id": str(run.public_id),
        "definition": run.definition.slug,
        "dataset_key": _run_dataset_key(run),
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat(),
        "status": run.status,
        "official_output": run.is_official_output,
        "control_status": run.control_status,
        "output_checksum": run.checksum,
        "dataset_checksum": run.dataset_checksum,
        "control_checksum": run.control_checksum,
        "reproduction_key": run.reproduction_key,
        "statement_mapping": run.parameters.get("_statement_mapping_snapshot", {}),
    }


def note_set_source_snapshot(note_set):
    return {
        "position_run": _run_evidence(note_set.position_run),
        "performance_run": _run_evidence(note_set.performance_run),
    }


def note_set_snapshot(note_set, *, source_snapshot=None):
    return {
        "public_id": str(note_set.public_id),
        "department_id": note_set.department_id,
        "title": note_set.title,
        "period_start": note_set.period_start.isoformat(),
        "period_end": note_set.period_end.isoformat(),
        "version": note_set.version,
        "applicability_status": note_set.applicability_status,
        "supersedes_public_id": str(note_set.supersedes.public_id) if note_set.supersedes_id else "",
        "preparation_note": note_set.preparation_note,
        "authority_reference": note_set.authority_reference,
        "local_acceptance_note": note_set.local_acceptance_note,
        "source_snapshot": source_snapshot if source_snapshot is not None else note_set.source_snapshot,
        "notes": [
            {
                "position": item.position,
                "topic_code": item.topic_code,
                "title": item.title,
                "related_statement": item.related_statement,
                "related_line_codes": list(item.related_line_codes or []),
                "disclosure_text": item.disclosure_text,
                "source_reference": item.source_reference,
                "authority_basis": item.authority_basis,
                "is_not_applicable": item.is_not_applicable,
                "not_applicable_reason": item.not_applicable_reason,
            }
            for item in note_set.notes.order_by("position", "pk")
        ],
    }


def _statement_line_codes(run):
    snapshot = run.parameters.get("_statement_mapping_snapshot", {})
    return {item.get("line_code") for item in snapshot.get("lines", []) if item.get("line_code")}


def validate_note_set(note_set, *, require_official=False):
    errors = []
    try:
        note_set.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)
    if require_official:
        if note_set.applicability_status != FinanceStatementNoteSet.CONFIRMED:
            errors.append("Mark the package locally confirmed only after authority and acceptance evidence are retained.")
        if not note_set.authority_reference.strip() or not note_set.local_acceptance_note.strip():
            errors.append("Official notes require both reviewed authority and local acceptance evidence.")
        if not note_set.position_run.is_official_output or not note_set.performance_run.is_official_output:
            errors.append("Official notes require approved official position and performance statement runs.")
    notes = list(note_set.notes.order_by("position", "pk"))
    if not notes:
        errors.append("Add at least one note topic before review.")
    line_codes = {
        FinanceStatementNote.POSITION: _statement_line_codes(note_set.position_run),
        FinanceStatementNote.PERFORMANCE: _statement_line_codes(note_set.performance_run),
    }
    line_codes[FinanceStatementNote.BOTH] = line_codes[FinanceStatementNote.POSITION] | line_codes[FinanceStatementNote.PERFORMANCE]
    line_codes[FinanceStatementNote.GENERAL] = line_codes[FinanceStatementNote.BOTH]
    for item in notes:
        try:
            item.full_clean()
        except ValidationError as exc:
            errors.extend(f"{item.title}: {message}" for message in exc.messages)
        unknown = sorted(set(item.related_line_codes or []) - line_codes[item.related_statement])
        if unknown:
            errors.append(f"{item.title}: unknown pinned statement line codes: {', '.join(unknown)}.")
    current_source = note_set_source_snapshot(note_set)
    if note_set.source_snapshot and note_set.source_snapshot != current_source:
        errors.append("The pinned statement evidence differs from the selected runs. Create or resubmit a successor package.")
    return {"valid": not errors, "errors": errors, "source_snapshot": current_source}


@transaction.atomic
def create_note_set(*, department, position_run, performance_run, actor, data):
    period_start, period_end = position_run.period_start, position_run.period_end
    latest = FinanceStatementNoteSet.objects.select_for_update().filter(
        department=department, period_start=period_start, period_end=period_end,
    ).order_by("-version").first()
    note_set = FinanceStatementNoteSet(
        department=department,
        title=data.get("title") or "Notes to the financial statements",
        period_start=period_start,
        period_end=period_end,
        version=(latest.version if latest else 0) + 1,
        applicability_status=data.get("applicability_status") or FinanceStatementNoteSet.CANDIDATE,
        position_run=position_run,
        performance_run=performance_run,
        supersedes=latest if latest and latest.status in (
            FinanceStatementNoteSet.REVIEWED, FinanceStatementNoteSet.APPROVED,
        ) else None,
        preparation_note=data.get("preparation_note", ""),
        authority_reference=data.get("authority_reference", ""),
        local_acceptance_note=data.get("local_acceptance_note", ""),
        created_by=actor,
    )
    note_set.full_clean()
    note_set.save()
    FinanceStatementNote.objects.bulk_create([
        FinanceStatementNote(
            note_set=note_set, position=position, topic_code=code, title=title,
            related_statement=related,
        )
        for position, code, title, related in NOTE_STARTER_TOPICS
    ])
    FinanceStatementNoteEvent.objects.create(
        note_set=note_set, actor=actor, action="candidate_topics_seeded",
        reason=(
            "Plain-language candidate topics informed by general financial-statement disclosure practice; "
            "the current COA requirements and local applicability must be reviewed topic by topic."
        ),
        snapshot=note_set_snapshot(note_set),
    )
    return note_set


@transaction.atomic
def submit_note_set(note_set, actor):
    locked = FinanceStatementNoteSet.objects.select_for_update().select_related(
        "position_run__definition", "position_run__template_version",
        "performance_run__definition", "performance_run__template_version",
    ).get(pk=note_set.pk)
    if not locked.is_editable:
        raise ValidationError("Only an editable note package can be submitted.")
    validation = validate_note_set(locked)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    locked.source_snapshot = validation["source_snapshot"]
    locked.snapshot_checksum = snapshot_checksum(
        note_set_snapshot(locked, source_snapshot=validation["source_snapshot"]),
    )
    locked.status = FinanceStatementNoteSet.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.reviewed_by = None
    locked.reviewed_at = None
    locked.review_note = ""
    locked.save(update_fields=(
        "source_snapshot", "snapshot_checksum", "status", "submitted_by", "submitted_at",
        "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ))
    FinanceStatementNoteEvent.objects.create(
        note_set=locked, actor=actor, action="submitted", snapshot=note_set_snapshot(locked),
    )
    return locked


@transaction.atomic
def review_note_set(note_set, actor, *, action, note=""):
    locked = FinanceStatementNoteSet.objects.select_for_update().select_related(
        "position_run__definition", "position_run__template_version",
        "performance_run__definition", "performance_run__template_version",
    ).get(pk=note_set.pk)
    if locked.status != FinanceStatementNoteSet.SUBMITTED:
        raise ValidationError("Only submitted statement notes can be independently reviewed.")
    if locked.created_by_id == actor.pk or locked.submitted_by_id == actor.pk:
        raise ValidationError("The note preparer or submitter cannot review the same package.")
    note = (note or "").strip()
    if action == "return":
        if not note:
            raise ValidationError("Explain the correction required before returning the notes.")
        locked.status = FinanceStatementNoteSet.RETURNED
        locked.reviewed_by = actor
        locked.reviewed_at = timezone.now()
        locked.review_note = note
        locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
        FinanceStatementNoteEvent.objects.create(
            note_set=locked, actor=actor, action="returned", reason=note,
            snapshot=note_set_snapshot(locked),
        )
        return locked
    if action not in ("accept_working", "approve"):
        raise ValidationError("Choose a supported note-review decision.")
    validation = validate_note_set(locked, require_official=action == "approve")
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    current_checksum = snapshot_checksum(
        note_set_snapshot(locked, source_snapshot=validation["source_snapshot"]),
    )
    if current_checksum != locked.snapshot_checksum:
        raise ValidationError("Statement-note evidence changed after submission. Return and resubmit it.")
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.review_note = note
    locked.status = (
        FinanceStatementNoteSet.APPROVED if action == "approve" else FinanceStatementNoteSet.REVIEWED
    )
    if action == "approve":
        prior = FinanceStatementNoteSet.objects.select_for_update().filter(
            department=locked.department, period_start=locked.period_start,
            period_end=locked.period_end, status=FinanceStatementNoteSet.APPROVED,
        ).exclude(pk=locked.pk).first()
        if prior:
            prior.status = FinanceStatementNoteSet.SUPERSEDED
            prior.save(update_fields=("status", "updated_at"))
            FinanceStatementNoteEvent.objects.create(
                note_set=prior, actor=actor, action="superseded",
                reason=f"Replaced by note package version {locked.version}.",
                snapshot=note_set_snapshot(prior),
            )
    locked.full_clean()
    locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
    FinanceStatementNoteEvent.objects.create(
        note_set=locked, actor=actor, action=("approved" if action == "approve" else "working_notes_accepted"),
        reason=note, snapshot=note_set_snapshot(locked),
    )
    return locked


def comparison_controls(run):
    return STATEMENT_COMPARISON_CONTROLS.get(_run_dataset_key(run), ())


def _decimal_text(value):
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"{value!r} is not a valid comparison amount.")


def comparison_snapshot(comparison):
    return {
        "public_id": str(comparison.public_id),
        "run_public_id": str(comparison.run.public_id),
        "version": comparison.version,
        "reference_label": comparison.reference_label,
        "reference_kind": comparison.reference_kind,
        "reference_file_name": comparison.reference_file.name,
        "signed_copy": comparison.signed_copy,
        "redaction_confirmed": comparison.redaction_confirmed,
        "authority_reference": comparison.authority_reference,
        "local_acceptance_note": comparison.local_acceptance_note,
        "reference_values": comparison.reference_values,
        "generated_values_snapshot": comparison.generated_values_snapshot,
        "differences": comparison.differences,
        "comparison_result": comparison.comparison_result,
        "run_evidence_snapshot": comparison.run_evidence_snapshot,
        "reference_file_checksum": comparison.reference_file_checksum,
    }


def _reference_file_checksum(comparison):
    digest = hashlib.sha256()
    comparison.reference_file.open("rb")
    try:
        for chunk in iter(lambda: comparison.reference_file.read(1024 * 1024), b""):
            digest.update(chunk)
    finally:
        comparison.reference_file.close()
    return digest.hexdigest()


@transaction.atomic
def submit_reference_comparison(comparison, actor):
    locked = ReportReferenceComparison.objects.select_for_update().select_related(
        "run__definition", "run__template_version",
    ).get(pk=comparison.pk)
    if not locked.is_editable:
        raise ValidationError("Only an editable reference comparison can be submitted.")
    locked.full_clean()
    if locked.run.status not in (ReportRun.GENERATED, ReportRun.REVIEWED, ReportRun.APPROVED):
        raise ValidationError("Generate a controlled statement run before comparing a reference copy.")
    if locked.run.control_status != ReportRun.CONTROL_RECONCILED:
        raise ValidationError("Resolve statement control exceptions before signed-reference comparison.")
    if not locked.signed_copy:
        raise ValidationError("Confirm that the retained reference is the signed comparison copy.")
    if not locked.redaction_confirmed:
        raise ValidationError("Confirm that sensitive information was redacted before upload.")
    if not locked.authority_reference.strip() or not locked.local_acceptance_note.strip():
        raise ValidationError("Record the authority and local acceptance evidence for the comparison.")
    controls = comparison_controls(locked.run)
    if not controls:
        raise ValidationError("This report does not have a governed statement comparison profile.")
    missing = [label for key, label in controls if key not in locked.reference_values]
    if missing:
        raise ValidationError("Enter every required reference control: " + ", ".join(missing) + ".")
    generated = {key: _decimal_text(locked.run.control_totals.get(key)) for key, _label in controls}
    reference = {key: _decimal_text(locked.reference_values[key]) for key, _label in controls}
    differences = {
        key: _decimal_text(Decimal(reference[key]) - Decimal(generated[key])) for key, _label in controls
    }
    locked.reference_values = reference
    locked.generated_values_snapshot = generated
    locked.differences = differences
    locked.comparison_result = (
        ReportReferenceComparison.RESULT_RECONCILED
        if all(Decimal(value) == 0 for value in differences.values())
        else ReportReferenceComparison.RESULT_EXCEPTION
    )
    locked.run_evidence_snapshot = _run_evidence(locked.run)
    locked.reference_file_checksum = _reference_file_checksum(locked)
    locked.snapshot_checksum = snapshot_checksum(comparison_snapshot(locked))
    locked.status = ReportReferenceComparison.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.reviewed_by = None
    locked.reviewed_at = None
    locked.review_note = ""
    locked.save(update_fields=(
        "reference_values", "generated_values_snapshot", "differences", "comparison_result",
        "run_evidence_snapshot", "reference_file_checksum", "snapshot_checksum", "status",
        "submitted_by", "submitted_at", "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ))
    ReportReferenceComparisonEvent.objects.create(
        comparison=locked, actor=actor, action="submitted", snapshot=comparison_snapshot(locked),
    )
    return locked


@transaction.atomic
def review_reference_comparison(comparison, actor, *, approve, note=""):
    locked = ReportReferenceComparison.objects.select_for_update().select_related(
        "run__definition", "run__template_version",
    ).get(pk=comparison.pk)
    if locked.status != ReportReferenceComparison.SUBMITTED:
        raise ValidationError("Only a submitted comparison can be independently reviewed.")
    if locked.created_by_id == actor.pk or locked.submitted_by_id == actor.pk:
        raise ValidationError("The comparison preparer or submitter cannot review the same evidence.")
    note = (note or "").strip()
    if not approve:
        if not note:
            raise ValidationError("Explain the correction or unresolved difference before returning the comparison.")
        locked.status = ReportReferenceComparison.RETURNED
        locked.reviewed_by = actor
        locked.reviewed_at = timezone.now()
        locked.review_note = note
        locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
        ReportReferenceComparisonEvent.objects.create(
            comparison=locked, actor=actor, action="returned", reason=note,
            snapshot=comparison_snapshot(locked),
        )
        return locked
    if locked.comparison_result != ReportReferenceComparison.RESULT_RECONCILED:
        raise ValidationError("An exact zero-difference comparison is required before reconciliation.")
    if _run_evidence(locked.run) != locked.run_evidence_snapshot:
        raise ValidationError("The report evidence differs from the submitted comparison. Create a successor comparison.")
    if _reference_file_checksum(locked) != locked.reference_file_checksum:
        raise ValidationError("The uploaded reference differs from the submitted file checksum.")
    if snapshot_checksum(comparison_snapshot(locked)) != locked.snapshot_checksum:
        raise ValidationError("The comparison evidence changed after submission. Return and resubmit it.")
    priors = list(ReportReferenceComparison.objects.select_for_update().filter(
        run=locked.run, status=ReportReferenceComparison.RECONCILED,
    ).exclude(pk=locked.pk))
    for prior in priors:
        prior.status = ReportReferenceComparison.SUPERSEDED
        prior.save(update_fields=("status", "updated_at"))
        ReportReferenceComparisonEvent.objects.create(
            comparison=prior, actor=actor, action="superseded",
            reason=f"Replaced by comparison version {locked.version}.",
            snapshot=comparison_snapshot(prior),
        )
    locked.status = ReportReferenceComparison.RECONCILED
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.review_note = note
    locked.full_clean()
    locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
    ReportReferenceComparisonEvent.objects.create(
        comparison=locked, actor=actor, action="reconciled", reason=note,
        snapshot=comparison_snapshot(locked),
    )
    return locked
