from __future__ import annotations

import hashlib
import json
import re

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from finance.models import FinanceTemplateVersion

from .access import department_for_user
from .local_form_starters import DBM_BOM_URL, DBM_FORM_STARTERS_BY_KEY
from .models import (
    FinanceLocalFormAcceptance, FinanceLocalFormEvent, FinanceLocalFormSection,
    FinanceLocalFormTestAttempt, ReportTemplatePromotion,
)
from .template_services import template_snapshot


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@transaction.atomic
def create_local_form_from_starter(department, actor, *, starter_key):
    """Create one editable, non-authoritative F10 record from a built-in DBM starter."""
    starter = DBM_FORM_STARTERS_BY_KEY.get(starter_key)
    if starter is None:
        raise ValidationError("Choose a recognized DBM local-form starter.")
    if department is None or department_for_user(actor) != department:
        raise ValidationError("A DBM starter can be created only inside the actor's assigned department.")

    current_statuses = (
        FinanceLocalFormAcceptance.DRAFT,
        FinanceLocalFormAcceptance.RETURNED,
        FinanceLocalFormAcceptance.SUBMITTED,
        FinanceLocalFormAcceptance.ACCEPTED,
    )
    existing = FinanceLocalFormAcceptance.objects.select_for_update().filter(
        department=department,
        code=starter["key"],
        status__in=current_statuses,
    ).order_by("-version").first()
    if existing:
        raise ValidationError(
            f"{starter['form_number']} already has a current local-form record. "
            "Open that record and use its correction or successor action."
        )

    latest = FinanceLocalFormAcceptance.objects.select_for_update().filter(
        department=department,
        code=starter["key"],
    ).order_by("-version").first()
    item = FinanceLocalFormAcceptance(
        department=department,
        code=starter["key"],
        version=(latest.version if latest else 0) + 1,
        name=starter["title"],
        form_number=starter["form_number"],
        purpose=starter["purpose"],
        source_type=FinanceLocalFormAcceptance.SOURCE_UNMAPPED,
        authority_reference=(
            "Candidate official reference; local applicability and current issuance must still be confirmed: "
            "DBM Budget Operations Manual for LGUs, 2023 Edition, "
            f"manual pp. {starter['manual_pages']}, PDF pp. {starter['pdf_pages']}. {DBM_BOM_URL}"
        ),
        local_acceptance_note="",
        reference_kind="pdf",
        delivery_mode=FinanceLocalFormAcceptance.DELIVERY_UNCONFIRMED,
        signatory_instructions=(
            f"Candidate route to compare with the current local form: {starter['owner_note']} "
            "Record the actual order, delegation rule, and wet/digital signature treatment before testing."
        ),
        default_copy_count=1,
        recipient_instructions=(
            "Candidate — confirm locally which office receives each original, copy, or digital file and "
            "how receipt or acknowledgement is retained."
        ),
        deadline_instructions=(
            "Candidate — confirm the applicable preparation, submission, review, filing, and distribution "
            "dates from the current issuance and accepted local calendar."
        ),
        retention_instructions=(
            "Candidate — confirm the official records series, folder, custodian, retention period, access "
            "restriction, and signed-copy treatment."
        ),
        pagination_instructions=(
            "Candidate — compare page numbering, repeated headings, annexes, and continuation pages with "
            "the current blank or safely redacted local form."
        ),
        overflow_instructions=(
            "Candidate — confirm how extra rows, particulars, notes, and signature blocks continue without "
            "hiding data or shrinking text below a readable size."
        ),
        accessibility_instructions=(
            "Candidate — confirm readable field order, labels, downloadable format, scaling, keyboard use, "
            "and any locally required accessibility accommodation."
        ),
        created_by=actor,
    )
    item.full_clean()
    item.save()

    section_rows = []
    used_codes = set()
    for index, candidate in enumerate(starter["sections"], start=1):
        base_code = slugify(candidate["label"])[:70] or f"section-{index}"
        code = base_code
        suffix = 2
        while code in used_codes:
            code = f"{base_code[:74]}-{suffix}"
            suffix += 1
        used_codes.add(code)
        section_row = FinanceLocalFormSection(
            form=item,
            position=index * 10,
            code=code,
            label=candidate["label"],
            requirement_type=candidate["requirement_type"],
            field_instructions=candidate["field_instructions"],
            source_instructions=candidate["source_instructions"],
            control_instructions=candidate["control_instructions"],
            owner_instructions=candidate["owner_instructions"],
            print_instructions=candidate["print_instructions"],
            applicability_instructions=candidate["applicability_instructions"],
            row_instructions=candidate["row_instructions"],
            starter_reference=(
                f"DBM BOM 2023, manual pp. {starter['manual_pages']}; "
                f"PDF pp. {starter['pdf_pages']}"
            ),
            confirmation_status=FinanceLocalFormSection.STARTER_CANDIDATE,
        )
        section_row.full_clean()
        section_rows.append(section_row)
    FinanceLocalFormSection.objects.bulk_create(section_rows)
    FinanceLocalFormEvent.objects.create(
        form=item,
        actor=actor,
        action="candidate_starter_created",
        reason=(
            "Created an editable candidate from the DBM 2023 manual. Local applicability, exact fields, "
            "routing, source mapping, delivery, and practical acceptance remain unconfirmed."
        ),
        snapshot={
            "starter_key": starter["key"],
            "family": starter["family"],
            "manual_pages": starter["manual_pages"],
            "pdf_pages": starter["pdf_pages"],
            "section_count": len(section_rows),
            "status": FinanceLocalFormSection.STARTER_CANDIDATE,
            "source_type": FinanceLocalFormAcceptance.SOURCE_UNMAPPED,
            "delivery_mode": FinanceLocalFormAcceptance.DELIVERY_UNCONFIRMED,
            "tests_created": False,
        },
    )
    return item


def checksum(payload):
    serialized = json.dumps(
        payload, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def file_checksum(field):
    if not field:
        return ""
    digest = hashlib.sha256()
    field.open("rb")
    try:
        for chunk in iter(lambda: field.read(1024 * 1024), b""):
            digest.update(chunk)
    finally:
        field.close()
    return digest.hexdigest()


def _finance_template_snapshot(template):
    return {
        "kind": FinanceLocalFormAcceptance.SOURCE_FINANCE,
        "template_id": template.pk,
        "department_id": template.department_id,
        "release_id": template.release_id,
        "release_status": template.release.status,
        "document_type": template.document_type,
        "version": template.version,
        "title": template.title,
        "form_reference": template.form_reference,
        "form_status": template.form_status,
        "paper_size": template.paper_size,
        "orientation": template.orientation,
        "default_copy_count": template.default_copy_count,
        "controlled_print_required": template.controlled_print_required,
        "workbook_name": template.workbook.name,
        "workbook_checksum": template.workbook_checksum,
        "mapping_checksum": template.mapping_checksum,
        "preflight_result": template.preflight_result,
        "preflighted_at": template.preflighted_at.isoformat() if template.preflighted_at else "",
        "status": template.status,
        "effective_from": template.effective_from.isoformat(),
        "effective_to": template.effective_to.isoformat() if template.effective_to else "",
    }


def source_snapshot(form, *, require_current=True):
    if form.source_type == FinanceLocalFormAcceptance.SOURCE_REPORT:
        template = form.report_template
        promotion = getattr(template, "promotion_request", None)
        current_template_snapshot = template_snapshot(template)
        if require_current:
            if not template.is_active or not template.is_official_ready:
                raise ValidationError("The linked report template is not the current approved official-ready layout.")
            if not promotion or promotion.status != ReportTemplatePromotion.ACTIVATED:
                raise ValidationError("The linked report template must complete governed promotion and activation first.")
            if promotion.golden_result not in (
                ReportTemplatePromotion.GOLDEN_MATCHED,
                ReportTemplatePromotion.GOLDEN_REFERENCE,
            ):
                raise ValidationError("The linked report promotion has no accepted golden or first-reference result.")
            if template.definition.applicability_status == template.definition.APPLICABILITY_CANDIDATE:
                raise ValidationError("The linked report definition still awaits a local applicability decision.")
            if (
                current_template_snapshot != promotion.template_snapshot
                or checksum(current_template_snapshot) != promotion.template_checksum
            ):
                raise ValidationError("The linked report template no longer matches its activated promotion evidence.")
        return {
            "kind": form.source_type,
            "template": current_template_snapshot,
            "definition_id": template.definition_id,
            "definition_slug": template.definition.slug,
            "definition_applicability": template.definition.applicability_status,
            "promotion_public_id": str(promotion.public_id) if promotion else "",
            "promotion_status": promotion.status if promotion else "",
            "promotion_golden_result": promotion.golden_result if promotion else "",
            "promotion_template_checksum": promotion.template_checksum if promotion else "",
            "promotion_submission_checksum": promotion.submission_checksum if promotion else "",
        }
    if form.source_type == FinanceLocalFormAcceptance.SOURCE_FINANCE:
        template = form.finance_template
        if require_current:
            from finance.services import FinanceTemplateError, verify_template_evidence

            if template.form_status != FinanceTemplateVersion.LOCALLY_ACCEPTED:
                raise ValidationError("The linked Finance workbook still lacks locally accepted form evidence.")
            if not template.preflight_passed:
                raise ValidationError("The linked Finance workbook must pass macro-free mapping preflight.")
            if template.status != "active" or template.release.status != "active":
                raise ValidationError("The linked Finance workbook and configuration release must both be active.")
            if not SHA256_PATTERN.fullmatch((template.workbook_checksum or "").lower()):
                raise ValidationError("The linked Finance workbook has no valid retained SHA-256.")
            if not SHA256_PATTERN.fullmatch((template.mapping_checksum or "").lower()):
                raise ValidationError("The linked Finance workbook mapping has no valid retained SHA-256.")
            try:
                verify_template_evidence(template)
            except FinanceTemplateError as exc:
                raise ValidationError(str(exc)) from exc
        return _finance_template_snapshot(template)
    raise ValidationError(
        "This form is inventory-only. Link its exact governed report template or Finance workbook before submission."
    )


def latest_test_attempts(form):
    latest = {}
    for attempt in form.test_attempts.select_related("created_by", "reviewed_by").order_by(
        "category", "-attempt", "-pk",
    ):
        latest.setdefault(attempt.category, attempt)
    return latest


def _section_snapshot(item, *, include_candidate_mapping):
    snapshot = {
        "position": item.position,
        "code": item.code,
        "label": item.label,
        "requirement_type": item.requirement_type,
        "applicability_instructions": item.applicability_instructions,
        "row_instructions": item.row_instructions,
    }
    if include_candidate_mapping:
        snapshot.update({
            "field_instructions": item.field_instructions,
            "source_instructions": item.source_instructions,
            "control_instructions": item.control_instructions,
            "owner_instructions": item.owner_instructions,
            "print_instructions": item.print_instructions,
            "starter_reference": item.starter_reference,
            "confirmation_status": item.confirmation_status,
            "local_confirmation_reference": item.local_confirmation_reference,
        })
    return snapshot


def test_basis_snapshot(form, *, pinned_source=None, pinned_reference_checksum=None):
    """Return the exact editable form/source/reference contract one practical test exercised."""
    current_source = pinned_source if pinned_source is not None else source_snapshot(form, require_current=True)
    reference_hash = (
        pinned_reference_checksum
        if pinned_reference_checksum is not None
        else file_checksum(form.reference_file)
    )
    return {
        "schema_version": 2,
        "public_id": str(form.public_id),
        "department_id": form.department_id,
        "code": form.code,
        "version": form.version,
        "name": form.name,
        "form_number": form.form_number,
        "purpose": form.purpose,
        "source_type": form.source_type,
        "report_template_id": form.report_template_id,
        "finance_template_id": form.finance_template_id,
        "supersedes_public_id": str(form.supersedes.public_id) if form.supersedes_id else "",
        "authority_reference": form.authority_reference,
        "local_acceptance_note": form.local_acceptance_note,
        "reference_kind": form.reference_kind,
        "reference_name": form.reference_file.name,
        "reference_checksum": reference_hash,
        "delivery_mode": form.delivery_mode,
        "signatory_instructions": form.signatory_instructions,
        "default_copy_count": form.default_copy_count,
        "recipient_instructions": form.recipient_instructions,
        "deadline_instructions": form.deadline_instructions,
        "retention_instructions": form.retention_instructions,
        "paper_size": form.paper_size,
        "orientation": form.orientation,
        "form_stock": form.form_stock,
        "printer_instructions": form.printer_instructions,
        "pagination_instructions": form.pagination_instructions,
        "overflow_instructions": form.overflow_instructions,
        "accessibility_instructions": form.accessibility_instructions,
        "source_snapshot": current_source,
        "sections": [
            _section_snapshot(item, include_candidate_mapping=True)
            for item in form.sections.order_by("position", "pk")
        ],
    }


def _test_snapshot(attempt):
    return {
        "public_id": attempt.pk,
        "category": attempt.category,
        "category_label": attempt.get_category_display(),
        "attempt": attempt.attempt,
        "supersedes_attempt": attempt.supersedes.attempt if attempt.supersedes_id else None,
        "change_reason": attempt.change_reason,
        "test_steps": attempt.test_steps,
        "expected_result": attempt.expected_result,
        "observed_result": attempt.observed_result,
        "environment": attempt.environment,
        "evidence_reference": attempt.evidence_reference,
        "evidence_checksum": attempt.evidence_checksum,
        "basis_snapshot": attempt.basis_snapshot,
        "basis_checksum": attempt.basis_checksum,
        "status": attempt.status,
        "created_by": attempt.created_by.username,
        "created_at": attempt.created_at.isoformat(),
        "reviewed_by": attempt.reviewed_by.username if attempt.reviewed_by_id else "",
        "reviewed_at": attempt.reviewed_at.isoformat() if attempt.reviewed_at else "",
        "review_note": attempt.review_note,
    }


def form_snapshot(
    form, *, pinned_source=None, pinned_reference_checksum=None, schema_version=None,
):
    latest = latest_test_attempts(form)
    if schema_version is None:
        schema_version = int((form.submission_snapshot or {}).get("schema_version") or 2)
    return {
        "schema_version": schema_version,
        "public_id": str(form.public_id),
        "department_id": form.department_id,
        "code": form.code,
        "version": form.version,
        "name": form.name,
        "form_number": form.form_number,
        "purpose": form.purpose,
        "source_type": form.source_type,
        "report_template_id": form.report_template_id,
        "finance_template_id": form.finance_template_id,
        "supersedes_public_id": str(form.supersedes.public_id) if form.supersedes_id else "",
        "authority_reference": form.authority_reference,
        "local_acceptance_note": form.local_acceptance_note,
        "reference_kind": form.reference_kind,
        "reference_name": form.reference_file.name,
        "reference_checksum": pinned_reference_checksum or form.reference_checksum,
        "delivery_mode": form.delivery_mode,
        "signatory_instructions": form.signatory_instructions,
        "default_copy_count": form.default_copy_count,
        "recipient_instructions": form.recipient_instructions,
        "deadline_instructions": form.deadline_instructions,
        "retention_instructions": form.retention_instructions,
        "paper_size": form.paper_size,
        "orientation": form.orientation,
        "form_stock": form.form_stock,
        "printer_instructions": form.printer_instructions,
        "pagination_instructions": form.pagination_instructions,
        "overflow_instructions": form.overflow_instructions,
        "accessibility_instructions": form.accessibility_instructions,
        "source_snapshot": pinned_source if pinned_source is not None else form.source_snapshot,
        "sections": [
            _section_snapshot(item, include_candidate_mapping=schema_version >= 2)
            for item in form.sections.order_by("position", "pk")
        ],
        "latest_witnessed_tests": [
            _test_snapshot(latest[category])
            for category in FinanceLocalFormTestAttempt.REQUIRED_CATEGORIES
            if category in latest
        ],
    }


def validate_local_form(form):
    errors = []
    try:
        form.full_clean()
    except ValidationError as exc:
        errors.extend(exc.messages)

    required_text = (
        ("Authority", form.authority_reference),
        ("Local acceptance record", form.local_acceptance_note),
        ("Signatory route", form.signatory_instructions),
        ("Recipients/copies", form.recipient_instructions),
        ("Deadline basis", form.deadline_instructions),
        ("Retention/custody", form.retention_instructions),
        ("Pagination", form.pagination_instructions),
        ("Overflow handling", form.overflow_instructions),
        ("Accessibility/download", form.accessibility_instructions),
    )
    for label, value in required_text:
        if not (value or "").strip():
            errors.append(f"{label}: record the actual locally reviewed instruction or evidence.")
    if form.delivery_mode == FinanceLocalFormAcceptance.DELIVERY_UNCONFIRMED:
        errors.append("Delivery: confirm whether the current local form is digital, printed, or both.")
    if not form.reference_file:
        errors.append("Upload the exact blank or safely redacted local-form reference.")
        reference_hash = ""
    else:
        try:
            reference_hash = file_checksum(form.reference_file)
        except (OSError, ValueError):
            reference_hash = ""
            errors.append("The retained local-form reference cannot be read for checksum verification.")
    try:
        current_source = source_snapshot(form, require_current=True)
    except ValidationError as exc:
        current_source = None
        errors.extend(exc.messages)

    sections = list(form.sections.all())
    if not sections:
        errors.append("Add the form's required, optional, conditional, or repeating sections.")
    for section in sections:
        try:
            section.full_clean()
        except ValidationError as exc:
            errors.extend(f"{section.label}: {message}" for message in exc.messages)
        if section.confirmation_status == FinanceLocalFormSection.STARTER_CANDIDATE:
            errors.append(
                f"{section.label}: compare this candidate starter row with the current local form and record the outcome."
            )

    latest = latest_test_attempts(form)
    current_basis = None
    if current_source is not None and reference_hash:
        current_basis = test_basis_snapshot(
            form, pinned_source=current_source,
            pinned_reference_checksum=reference_hash,
        )
    for category, label in FinanceLocalFormTestAttempt.CATEGORY_CHOICES:
        attempt = latest.get(category)
        if not attempt:
            errors.append(f"{label}: record and independently witness a test attempt.")
            continue
        if attempt.status == FinanceLocalFormTestAttempt.SUBMITTED:
            errors.append(f"{label}: the latest attempt still awaits an independent witness.")
        elif attempt.status == FinanceLocalFormTestAttempt.FAILED:
            errors.append(f"{label}: the latest attempt failed; correct the form and record a successor attempt.")
        elif attempt.status == FinanceLocalFormTestAttempt.NOT_APPLICABLE and not (
            category == FinanceLocalFormTestAttempt.PRINTER_STOCK
            and form.delivery_mode == FinanceLocalFormAcceptance.DELIVERY_DIGITAL
        ):
            errors.append(f"{label}: not-applicable is allowed only for a digital-only printer/form-stock test.")
        if not SHA256_PATTERN.fullmatch((attempt.evidence_checksum or "").lower()):
            errors.append(f"{label}: enter the retained evidence file's 64-character SHA-256.")
        if (
            current_basis is not None
            and (
                attempt.basis_snapshot != current_basis
                or attempt.basis_checksum != checksum(current_basis)
            )
        ):
            errors.append(
                f"{label}: the form, governed source, reference, or section rules changed since this test; "
                "record and witness a successor attempt."
            )

    return {
        "valid": not errors,
        "errors": errors,
        "source_snapshot": current_source,
        "reference_checksum": reference_hash,
        "latest_tests": latest,
    }


@transaction.atomic
def record_test_attempt(
    form, actor, *, category, test_steps, expected_result, observed_result,
    environment, evidence_reference, evidence_checksum, change_reason="",
):
    locked = FinanceLocalFormAcceptance.objects.select_for_update().select_related(
        "department", "report_template__definition", "finance_template__release", "supersedes",
    ).get(pk=form.pk)
    if not locked.is_editable:
        raise ValidationError("Only an editable local-form record can receive a test attempt.")
    valid_categories = dict(FinanceLocalFormTestAttempt.CATEGORY_CHOICES)
    if category not in valid_categories:
        raise ValidationError("Choose a recognized local-form test category.")
    evidence_checksum = (evidence_checksum or "").strip().lower()
    if not SHA256_PATTERN.fullmatch(evidence_checksum):
        raise ValidationError("Enter the retained evidence file's 64-character SHA-256.")
    latest = locked.test_attempts.select_for_update().filter(category=category).order_by("-attempt").first()
    reason = (change_reason or "").strip()
    if latest and not reason:
        raise ValidationError("Explain why another attempt is required; the earlier result remains in history.")
    basis = test_basis_snapshot(locked)
    attempt = FinanceLocalFormTestAttempt(
        form=locked, category=category, attempt=(latest.attempt if latest else 0) + 1,
        supersedes=latest, change_reason=reason, test_steps=test_steps,
        expected_result=expected_result, observed_result=observed_result,
        environment=environment, evidence_reference=evidence_reference,
        evidence_checksum=evidence_checksum, basis_snapshot=basis,
        basis_checksum=checksum(basis), created_by=actor,
    )
    attempt.full_clean()
    attempt.save()
    FinanceLocalFormEvent.objects.create(
        form=locked, actor=actor, action="test_attempt_submitted", reason=reason,
        snapshot={
            "category": category, "attempt": attempt.attempt,
            "evidence_checksum": evidence_checksum,
            "basis_checksum": attempt.basis_checksum,
            "supersedes_attempt": latest.attempt if latest else None,
        },
    )
    return attempt


@transaction.atomic
def review_test_attempt(attempt, actor, *, action, note):
    locked = FinanceLocalFormTestAttempt.objects.select_for_update().select_related("form").get(pk=attempt.pk)
    if not locked.form.is_editable:
        raise ValidationError("Tests cannot be reviewed after the local-form record is submitted.")
    if locked.status != FinanceLocalFormTestAttempt.SUBMITTED:
        raise ValidationError("Only an unwitnessed test attempt can receive a decision.")
    if actor.pk == locked.created_by_id:
        raise ValidationError("The person who performed the test cannot witness the same attempt.")
    statuses = {
        "pass": FinanceLocalFormTestAttempt.PASSED,
        "fail": FinanceLocalFormTestAttempt.FAILED,
        "not-applicable": FinanceLocalFormTestAttempt.NOT_APPLICABLE,
    }
    if action not in statuses:
        raise ValidationError("Choose pass, fail, or not applicable.")
    note = (note or "").strip()
    if not note:
        raise ValidationError("Record what the independent witness checked and decided.")
    locked.status = statuses[action]
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.review_note = note
    locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note"))
    FinanceLocalFormEvent.objects.create(
        form=locked.form, actor=actor, action=f"test_{locked.status}", reason=note,
        snapshot={
            "category": locked.category, "attempt": locked.attempt,
            "evidence_checksum": locked.evidence_checksum,
        },
    )
    return locked


@transaction.atomic
def submit_local_form(form, actor):
    locked = FinanceLocalFormAcceptance.objects.select_for_update().select_related(
        "department", "report_template__definition", "finance_template__release", "supersedes",
    ).get(pk=form.pk)
    if not locked.is_editable:
        raise ValidationError("Only an editable local-form record can be submitted.")
    validation = validate_local_form(locked)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    locked.reference_checksum = validation["reference_checksum"]
    locked.source_snapshot = validation["source_snapshot"]
    locked.source_checksum = checksum(locked.source_snapshot)
    snapshot = form_snapshot(
        locked, pinned_source=locked.source_snapshot,
        pinned_reference_checksum=locked.reference_checksum, schema_version=2,
    )
    locked.submission_snapshot = snapshot
    locked.submission_checksum = checksum(snapshot)
    locked.status = FinanceLocalFormAcceptance.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.reviewed_by = None
    locked.reviewed_at = None
    locked.review_note = ""
    locked.save(update_fields=(
        "reference_checksum", "source_snapshot", "source_checksum",
        "submission_snapshot", "submission_checksum", "status", "submitted_by",
        "submitted_at", "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ))
    FinanceLocalFormEvent.objects.create(
        form=locked, actor=actor, action="submitted", snapshot=snapshot,
    )
    return locked


@transaction.atomic
def review_local_form(form, actor, *, approve, note):
    locked = FinanceLocalFormAcceptance.objects.select_for_update().select_related(
        "department", "report_template__definition", "finance_template__release", "supersedes",
    ).get(pk=form.pk)
    if locked.status != FinanceLocalFormAcceptance.SUBMITTED:
        raise ValidationError("Only a submitted local-form record can be reviewed.")
    if actor.pk in (locked.created_by_id, locked.submitted_by_id):
        raise ValidationError("The form preparer or submitter cannot accept the same form.")
    note = (note or "").strip()
    if not note:
        raise ValidationError("Record the independent acceptance or correction decision.")
    if not approve:
        locked.status = FinanceLocalFormAcceptance.RETURNED
        locked.reviewed_by = actor
        locked.reviewed_at = timezone.now()
        locked.review_note = note
        locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
        FinanceLocalFormEvent.objects.create(
            form=locked, actor=actor, action="returned", reason=note,
            snapshot={"submission_checksum": locked.submission_checksum},
        )
        return locked

    validation = validate_local_form(locked)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    if validation["reference_checksum"] != locked.reference_checksum:
        raise ValidationError("The retained blank/redacted form changed after submission. Return and resubmit it.")
    if validation["source_snapshot"] != locked.source_snapshot or checksum(validation["source_snapshot"]) != locked.source_checksum:
        raise ValidationError("The linked governed template changed after submission. Return and resubmit it.")
    snapshot = form_snapshot(locked)
    if snapshot != locked.submission_snapshot or checksum(snapshot) != locked.submission_checksum:
        raise ValidationError("The submitted local-form evidence no longer matches its pinned snapshot.")

    prior = FinanceLocalFormAcceptance.objects.select_for_update().filter(
        department=locked.department, code=locked.code, status=FinanceLocalFormAcceptance.ACCEPTED,
    ).exclude(pk=locked.pk).first()
    if prior:
        prior.status = FinanceLocalFormAcceptance.SUPERSEDED
        prior.save(update_fields=("status", "updated_at"))
        FinanceLocalFormEvent.objects.create(
            form=prior, actor=actor, action="superseded",
            reason=f"Replaced by accepted {locked.name} v{locked.version}.",
            snapshot={"successor_public_id": str(locked.public_id), "successor_checksum": locked.submission_checksum},
        )
    locked.status = FinanceLocalFormAcceptance.ACCEPTED
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.review_note = note
    locked.full_clean()
    locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
    FinanceLocalFormEvent.objects.create(
        form=locked, actor=actor, action="accepted", reason=note, snapshot=snapshot,
    )
    return locked


@transaction.atomic
def create_local_form_successor(form, actor, *, reason):
    prior = FinanceLocalFormAcceptance.objects.select_for_update().get(pk=form.pk)
    if prior.status != FinanceLocalFormAcceptance.ACCEPTED:
        raise ValidationError("Only an accepted local form can be changed through a successor.")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Explain why the accepted local form needs a successor.")
    if prior.successor_forms.filter(
        status__in=(FinanceLocalFormAcceptance.DRAFT, FinanceLocalFormAcceptance.RETURNED,
                    FinanceLocalFormAcceptance.SUBMITTED),
    ).exists():
        raise ValidationError("This local form already has a successor in progress.")
    latest_version = FinanceLocalFormAcceptance.objects.filter(
        department=prior.department, code=prior.code,
    ).order_by("-version").values_list("version", flat=True).first() or prior.version
    successor = FinanceLocalFormAcceptance.objects.create(
        department=prior.department, code=prior.code, version=latest_version + 1,
        name=prior.name, form_number=prior.form_number, purpose=prior.purpose,
        source_type=prior.source_type, report_template=prior.report_template,
        finance_template=prior.finance_template, supersedes=prior,
        authority_reference=prior.authority_reference,
        local_acceptance_note=prior.local_acceptance_note,
        reference_kind=prior.reference_kind, reference_file=prior.reference_file,
        delivery_mode=prior.delivery_mode, signatory_instructions=prior.signatory_instructions,
        default_copy_count=prior.default_copy_count,
        recipient_instructions=prior.recipient_instructions,
        deadline_instructions=prior.deadline_instructions,
        retention_instructions=prior.retention_instructions,
        paper_size=prior.paper_size, orientation=prior.orientation,
        form_stock=prior.form_stock, printer_instructions=prior.printer_instructions,
        pagination_instructions=prior.pagination_instructions,
        overflow_instructions=prior.overflow_instructions,
        accessibility_instructions=prior.accessibility_instructions,
        created_by=actor,
    )
    FinanceLocalFormSection.objects.bulk_create([
        FinanceLocalFormSection(
            form=successor, position=item.position, code=item.code, label=item.label,
            requirement_type=item.requirement_type,
            field_instructions=item.field_instructions,
            source_instructions=item.source_instructions,
            control_instructions=item.control_instructions,
            owner_instructions=item.owner_instructions,
            print_instructions=item.print_instructions,
            applicability_instructions=item.applicability_instructions,
            row_instructions=item.row_instructions,
            starter_reference=item.starter_reference,
            confirmation_status=item.confirmation_status,
            local_confirmation_reference=item.local_confirmation_reference,
        )
        for item in prior.sections.order_by("position", "pk")
    ])
    FinanceLocalFormEvent.objects.create(
        form=successor, actor=actor, action="successor_created", reason=reason,
        snapshot={
            "supersedes_public_id": str(prior.public_id),
            "supersedes_checksum": prior.submission_checksum,
            "tests_copied": False,
        },
    )
    FinanceLocalFormEvent.objects.create(
        form=prior, actor=actor, action="modification_started", reason=reason,
        snapshot={"successor_public_id": str(successor.public_id)},
    )
    return successor


def local_form_export_manifest(form):
    if form.status not in (FinanceLocalFormAcceptance.ACCEPTED, FinanceLocalFormAcceptance.SUPERSEDED):
        raise ValidationError("Only an accepted or historically superseded local-form record can be exported.")
    reference_hash = file_checksum(form.reference_file)
    if reference_hash != form.reference_checksum:
        raise ValidationError("The retained blank/redacted reference no longer matches its accepted checksum.")
    snapshot = form_snapshot(form)
    if snapshot != form.submission_snapshot or checksum(snapshot) != form.submission_checksum:
        raise ValidationError("The accepted local-form evidence no longer matches its retained checksum.")
    return {
        "format": "GRAND local Finance form acceptance packet",
        "schema_version": snapshot["schema_version"],
        "form": snapshot,
        "workflow": {
            "status": form.status,
            "prepared_by": form.created_by.username,
            "submitted_by": form.submitted_by.username if form.submitted_by_id else "",
            "submitted_at": form.submitted_at,
            "accepted_by": form.reviewed_by.username if form.reviewed_by_id else "",
            "accepted_at": form.reviewed_at,
            "review_note": form.review_note,
        },
        "integrity": {
            "reference_sha256": form.reference_checksum,
            "source_sha256": form.source_checksum,
            "submission_sha256": form.submission_checksum,
        },
        "test_history": [
            _test_snapshot(item)
            for item in form.test_attempts.select_related(
                "created_by", "reviewed_by", "supersedes",
            ).order_by("category", "attempt", "pk")
        ],
        "audit_events": [
            {
                "action": item.action,
                "actor": item.actor.username,
                "reason": item.reason,
                "snapshot": item.snapshot,
                "created_at": item.created_at,
            }
            for item in form.events.exclude(
                action="acceptance_packet_exported",
            ).select_related("actor").order_by("created_at", "pk")
        ],
        "portability_note": (
            "Archive this packet with the separately retained blank/redacted reference, test files, "
            "template-promotion evidence, and generated outputs under GRAND_EXPORT_ROOT."
        ),
    }
