from __future__ import annotations

import hashlib
import json

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from .models import (
    FinanceAccountabilityPackage, FinanceAccountabilityPackageEvent,
    FinanceAccountabilityPackageProfile, FinanceAccountabilityPackageProfileEvent,
    FinanceAccountabilityPackageRequirement, FinanceAccountabilityPackageSelection,
    FinanceAccountabilityPackageSlot, FinanceStatementNoteSet, ReportReferenceComparison,
    ReportDefinition, ReportRun,
)
from .statement_services import comparison_snapshot, note_set_snapshot


def evidence_checksum(payload):
    serialized = json.dumps(
        payload, cls=DjangoJSONEncoder, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def profile_snapshot(profile):
    return {
        "schema_version": 1,
        "public_id": str(profile.public_id),
        "department_id": profile.department_id,
        "code": profile.code,
        "version": profile.version,
        "name": profile.name,
        "description": profile.description,
        "supersedes_public_id": str(profile.supersedes.public_id) if profile.supersedes_id else "",
        "authority_reference": profile.authority_reference,
        "local_acceptance_note": profile.local_acceptance_note,
        "requirements": [
            {
                "position": item.position,
                "code": item.code,
                "label": item.label,
                "evidence_kind": item.evidence_kind,
                "source_department_id": item.source_department_id,
                "source_department_label": item.source_department.name,
                "report_definition_id": item.report_definition_id,
                "report_definition_slug": item.report_definition.slug if item.report_definition_id else "",
                "report_definition_label": item.report_definition.name if item.report_definition_id else "",
                "tax_form_code": item.tax_form_code,
                "required": item.required,
                "instructions": item.instructions,
            }
            for item in profile.requirements.select_related(
                "source_department", "report_definition",
            ).order_by("position", "pk")
        ],
    }


def validate_profile(profile):
    errors = []
    requirements = list(profile.requirements.select_related("source_department", "report_definition"))
    if not requirements:
        errors.append("Add at least one plain-language evidence requirement before review.")
    if requirements and not any(item.required for item in requirements):
        errors.append("Mark at least one evidence requirement as required.")
    for item in requirements:
        try:
            item.full_clean()
        except ValidationError as exc:
            errors.extend(f"{item.label}: {message}" for message in exc.messages)
        if item.report_definition_id and not item.report_definition.is_active:
            errors.append(f"{item.label}: the selected report definition is inactive.")
    return {"valid": not errors, "errors": errors}


@transaction.atomic
def submit_profile(profile, actor):
    locked = FinanceAccountabilityPackageProfile.objects.select_for_update().get(pk=profile.pk)
    if not locked.is_editable:
        raise ValidationError("Only an editable package profile can be submitted.")
    validation = validate_profile(locked)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    snapshot = profile_snapshot(locked)
    locked.snapshot_checksum = evidence_checksum(snapshot)
    locked.status = FinanceAccountabilityPackageProfile.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.reviewed_by = None
    locked.reviewed_at = None
    locked.review_note = ""
    locked.save(update_fields=(
        "snapshot_checksum", "status", "submitted_by", "submitted_at", "reviewed_by", "reviewed_at",
        "review_note", "updated_at",
    ))
    FinanceAccountabilityPackageProfileEvent.objects.create(
        profile=locked, actor=actor, action="submitted", snapshot=snapshot,
    )
    return locked


@transaction.atomic
def review_profile(profile, actor, *, approve, note=""):
    locked = FinanceAccountabilityPackageProfile.objects.select_for_update().get(pk=profile.pk)
    if locked.status != FinanceAccountabilityPackageProfile.SUBMITTED:
        raise ValidationError("Only a submitted package profile can be reviewed.")
    if actor.pk in (locked.created_by_id, locked.submitted_by_id):
        raise ValidationError("The profile preparer or submitter cannot review the same profile.")
    note = (note or "").strip()
    if not approve:
        if not note:
            raise ValidationError("Explain the correction required before returning the profile.")
        locked.status = FinanceAccountabilityPackageProfile.RETURNED
        locked.reviewed_by = actor
        locked.reviewed_at = timezone.now()
        locked.review_note = note
        locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
        FinanceAccountabilityPackageProfileEvent.objects.create(
            profile=locked, actor=actor, action="returned", reason=note, snapshot=profile_snapshot(locked),
        )
        return locked

    validation = validate_profile(locked)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    if not locked.authority_reference.strip() or not locked.local_acceptance_note.strip():
        raise ValidationError("Record both the reviewed authority and local acceptance evidence before activation.")
    prior = FinanceAccountabilityPackageProfile.objects.select_for_update().filter(
        department=locked.department, code=locked.code,
        status=FinanceAccountabilityPackageProfile.ACTIVE,
    ).exclude(pk=locked.pk).first()
    locked.status = FinanceAccountabilityPackageProfile.ACTIVE
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.review_note = note
    snapshot = profile_snapshot(locked)
    if evidence_checksum(snapshot) != locked.snapshot_checksum:
        raise ValidationError("The submitted profile no longer matches its pinned evidence. Return and resubmit it.")
    if prior:
        prior.status = FinanceAccountabilityPackageProfile.SUPERSEDED
        prior.save(update_fields=("status", "updated_at"))
        FinanceAccountabilityPackageProfileEvent.objects.create(
            profile=prior, actor=actor, action="superseded",
            reason=f"Replaced by {locked.name} v{locked.version}.", snapshot=profile_snapshot(prior),
        )
    locked.full_clean()
    locked.save(update_fields=(
        "status", "reviewed_by", "reviewed_at", "review_note", "snapshot_checksum", "updated_at",
    ))
    FinanceAccountabilityPackageProfileEvent.objects.create(
        profile=locked, actor=actor, action="activated", reason=note, snapshot=snapshot,
    )
    return locked


@transaction.atomic
def create_profile_successor(profile, actor, *, reason):
    prior = FinanceAccountabilityPackageProfile.objects.select_for_update().get(pk=profile.pk)
    if prior.status != FinanceAccountabilityPackageProfile.ACTIVE:
        raise ValidationError("Only an active package profile can be modified through a successor.")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Explain why the accepted package recipe needs to change.")
    if prior.successor_profiles.filter(
        status__in=(
            FinanceAccountabilityPackageProfile.DRAFT,
            FinanceAccountabilityPackageProfile.RETURNED,
            FinanceAccountabilityPackageProfile.SUBMITTED,
        ),
    ).exists():
        raise ValidationError("This profile already has a successor in progress.")
    latest_version = FinanceAccountabilityPackageProfile.objects.filter(
        department=prior.department, code=prior.code,
    ).order_by("-version").values_list("version", flat=True).first() or prior.version
    successor = FinanceAccountabilityPackageProfile.objects.create(
        department=prior.department, code=prior.code, version=latest_version + 1,
        name=prior.name, description=prior.description, supersedes=prior,
        authority_reference=prior.authority_reference,
        local_acceptance_note=prior.local_acceptance_note, created_by=actor,
    )
    FinanceAccountabilityPackageRequirement.objects.bulk_create([
        FinanceAccountabilityPackageRequirement(
            profile=successor, position=item.position, code=item.code, label=item.label,
            evidence_kind=item.evidence_kind, source_department=item.source_department,
            report_definition=item.report_definition, tax_form_code=item.tax_form_code,
            required=item.required, instructions=item.instructions,
        )
        for item in prior.requirements.select_related("source_department", "report_definition")
    ])
    FinanceAccountabilityPackageProfileEvent.objects.create(
        profile=successor, actor=actor, action="successor_created", reason=reason,
        snapshot={
            "supersedes_public_id": str(prior.public_id),
            "supersedes_checksum": prior.snapshot_checksum,
        },
    )
    FinanceAccountabilityPackageProfileEvent.objects.create(
        profile=prior, actor=actor, action="modification_started", reason=reason,
        snapshot={"successor_public_id": str(successor.public_id)},
    )
    return successor


def _slot_snapshot(slot):
    return {
        "position": slot.position,
        "code": slot.code,
        "label": slot.label,
        "evidence_kind": slot.evidence_kind,
        "source_department_id": slot.source_department_id,
        "source_department_label": slot.source_department_label,
        "report_definition_id": slot.report_definition_id,
        "report_definition_slug": slot.report_definition.slug if slot.report_definition_id else "",
        "report_definition_label": slot.report_definition_label,
        "tax_form_code": slot.tax_form_code,
        "required": slot.required,
        "instructions": slot.instructions,
    }


@transaction.atomic
def create_package(*, profile, department, actor, title, period_start, period_end, preparation_note=""):
    locked_profile = FinanceAccountabilityPackageProfile.objects.select_for_update().get(pk=profile.pk)
    if locked_profile.department_id != department.pk:
        raise ValidationError("Choose an accountability profile owned by this Accounting office.")
    if locked_profile.status != FinanceAccountabilityPackageProfile.ACTIVE:
        raise ValidationError("Only an independently approved active profile can start a package.")
    snapshot = profile_snapshot(locked_profile)
    checksum = evidence_checksum(snapshot)
    if checksum != locked_profile.snapshot_checksum:
        raise ValidationError("The active profile no longer matches its approved checksum. Create and approve a successor profile.")
    latest = FinanceAccountabilityPackage.objects.select_for_update().filter(
        department=department, profile=locked_profile,
        period_start=period_start, period_end=period_end,
    ).order_by("-version").first()
    if latest:
        raise ValidationError(
            "A package already exists for this accepted profile and exact period. Open the existing draft, "
            "correct a returned package, or create a linked successor from the approved package."
        )
    package = FinanceAccountabilityPackage(
        department=department, profile=locked_profile, title=title,
        period_start=period_start, period_end=period_end,
        version=1,
        preparation_note=preparation_note, profile_snapshot=snapshot,
        profile_checksum=checksum, created_by=actor,
    )
    package.full_clean()
    package.save()
    FinanceAccountabilityPackageSlot.objects.bulk_create([
        FinanceAccountabilityPackageSlot(
            package=package, position=item["position"], code=item["code"], label=item["label"],
            evidence_kind=item["evidence_kind"], source_department_id=item["source_department_id"],
            source_department_label=item["source_department_label"],
            report_definition_id=item["report_definition_id"],
            report_definition_label=item["report_definition_label"], tax_form_code=item["tax_form_code"],
            required=item["required"], instructions=item["instructions"],
        )
        for item in snapshot["requirements"]
    ])
    FinanceAccountabilityPackageEvent.objects.create(
        package=package, actor=actor, action="created_from_profile",
        reason=f"Pinned active profile {locked_profile.code} v{locked_profile.version}.",
        snapshot={"profile_checksum": checksum, "slot_count": len(snapshot["requirements"])},
    )
    return package


def _run_snapshot(run):
    definition_snapshot = run.parameters.get("_definition_snapshot", {})
    return {
        "kind": FinanceAccountabilityPackageRequirement.REPORT_RUN,
        "public_id": str(run.public_id),
        "definition_id": run.definition_id,
        "definition_slug": definition_snapshot.get("slug", run.definition.slug),
        "definition_name": definition_snapshot.get("name", run.definition.name),
        "definition_applicability_status": definition_snapshot.get(
            "applicability_status", run.definition.applicability_status,
        ),
        "definition_authority_reference": definition_snapshot.get(
            "authority_reference", run.definition.authority_reference,
        ),
        "definition_local_acceptance_note": definition_snapshot.get(
            "local_acceptance_note", run.definition.local_acceptance_note,
        ),
        "department_id": run.definition.department_id,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat(),
        "accepted_workflow_status": ReportRun.APPROVED,
        "template_version": run.template_version.version,
        "template_official_ready": run.template_version.is_official_ready,
        "output_format": run.output_format,
        "output_checksum": run.checksum,
        "dataset_checksum": run.dataset_checksum,
        "control_checksum": run.control_checksum,
        "control_status": run.control_status,
        "control_gate_required": run.control_gate_required,
        "reproduction_key": run.reproduction_key,
        "approved_at": run.approved_at.isoformat() if run.approved_at else "",
    }


def _notes_snapshot(note_set):
    return {
        "kind": FinanceAccountabilityPackageRequirement.STATEMENT_NOTES,
        "public_id": str(note_set.public_id),
        "department_id": note_set.department_id,
        "title": note_set.title,
        "period_start": note_set.period_start.isoformat(),
        "period_end": note_set.period_end.isoformat(),
        "version": note_set.version,
        "accepted_workflow_status": FinanceStatementNoteSet.APPROVED,
        "applicability_status": note_set.applicability_status,
        "snapshot_checksum": note_set.snapshot_checksum,
        "snapshot": note_set_snapshot(note_set),
        "reviewed_at": note_set.reviewed_at.isoformat() if note_set.reviewed_at else "",
    }


def _comparison_evidence_snapshot(comparison):
    return {
        "kind": FinanceAccountabilityPackageRequirement.SIGNED_REFERENCE,
        "public_id": str(comparison.public_id),
        "department_id": comparison.department.pk,
        "run_public_id": str(comparison.run.public_id),
        "definition_id": comparison.run.definition_id,
        "definition_slug": comparison.run.definition.slug,
        "period_start": comparison.run.period_start.isoformat(),
        "period_end": comparison.run.period_end.isoformat(),
        "version": comparison.version,
        "accepted_workflow_status": ReportReferenceComparison.RECONCILED,
        "comparison_result": comparison.comparison_result,
        "snapshot_checksum": comparison.snapshot_checksum,
        "reference_file_checksum": comparison.reference_file_checksum,
        "snapshot": comparison_snapshot(comparison),
        "reviewed_at": comparison.reviewed_at.isoformat() if comparison.reviewed_at else "",
    }


def _tax_snapshot(evidence):
    return {
        "kind": FinanceAccountabilityPackageRequirement.TAX_FILING,
        "public_id": str(evidence.public_id),
        "finance_department_id": evidence.batch.finance_department_id,
        "treasury_department_id": evidence.batch.treasury_department_id,
        "batch_public_id": str(evidence.batch.public_id),
        "batch_reference": evidence.batch.reference_code,
        "version": evidence.version,
        "filing_type": evidence.filing_type,
        "return_form_code": evidence.return_form_code,
        "period_start": evidence.tax_period_start.isoformat(),
        "period_end": evidence.tax_period_end.isoformat(),
        "filing_date": evidence.filing_date.isoformat(),
        "filing_reference": evidence.filing_reference,
        "payment_confirmation_reference": evidence.payment_confirmation_reference,
        "source_mode": evidence.source_mode,
        "source_report_run_public_id": str(evidence.source_report_run_public_id or ""),
        "source_schedule_checksum": evidence.source_schedule_checksum,
        "evidence_schema_version": evidence.evidence_schema_version,
        "evidence_checksum": evidence.evidence_checksum,
        "accepted_workflow_status": evidence.VERIFIED,
        "reviewed_at": evidence.reviewed_at.isoformat() if evidence.reviewed_at else "",
    }


def eligible_sources(slot, *, allow_superseded=False):
    package = slot.package
    kind = slot.evidence_kind
    if kind == FinanceAccountabilityPackageRequirement.REPORT_RUN:
        queryset = ReportRun.objects.filter(
            definition_id=slot.report_definition_id, definition__department_id=slot.source_department_id,
            period_start=package.period_start, period_end=package.period_end,
            status__in=(
                (ReportRun.APPROVED, ReportRun.SUPERSEDED)
                if allow_superseded else (ReportRun.APPROVED,)
            ), approved_at__isnull=False,
            template_version__fidelity_status="official",
            template_version__fidelity_validated_at__isnull=False,
            template_version__approved_at__isnull=False,
        ).select_related("definition__department", "template_version")
        return [
            (item, _run_snapshot(item)) for item in queryset
            if (item.is_official_output or (allow_superseded and item.status == ReportRun.SUPERSEDED))
            and _run_snapshot(item)["definition_applicability_status"] != ReportDefinition.APPLICABILITY_CANDIDATE
            and (not item.control_gate_required or item.control_status == ReportRun.CONTROL_RECONCILED)
            and all(len(value or "") == 64 for value in (
                item.checksum, item.dataset_checksum, item.control_checksum, item.reproduction_key,
            ))
        ]
    if kind == FinanceAccountabilityPackageRequirement.STATEMENT_NOTES:
        queryset = FinanceStatementNoteSet.objects.filter(
            department_id=slot.source_department_id,
            period_start=package.period_start, period_end=package.period_end,
            status__in=(
                (FinanceStatementNoteSet.APPROVED, FinanceStatementNoteSet.SUPERSEDED)
                if allow_superseded else (FinanceStatementNoteSet.APPROVED,)
            ),
            applicability_status=FinanceStatementNoteSet.CONFIRMED,
        ).select_related("position_run__definition", "position_run__template_version",
                         "performance_run__definition", "performance_run__template_version")
        return [
            (item, _notes_snapshot(item)) for item in queryset
            if len(item.snapshot_checksum or "") == 64
            and evidence_checksum(note_set_snapshot(item)) == item.snapshot_checksum
        ]
    if kind == FinanceAccountabilityPackageRequirement.SIGNED_REFERENCE:
        queryset = ReportReferenceComparison.objects.filter(
            run__definition_id=slot.report_definition_id,
            run__definition__department_id=slot.source_department_id,
            run__period_start=package.period_start, run__period_end=package.period_end,
            status__in=(
                (ReportReferenceComparison.RECONCILED, ReportReferenceComparison.SUPERSEDED)
                if allow_superseded else (ReportReferenceComparison.RECONCILED,)
            ),
            comparison_result=ReportReferenceComparison.RESULT_RECONCILED,
            signed_copy=True, redaction_confirmed=True,
        ).select_related("run__definition__department", "run__template_version")
        return [
            (item, _comparison_evidence_snapshot(item)) for item in queryset
            if len(item.snapshot_checksum or "") == 64
            and len(item.reference_file_checksum or "") == 64
            and evidence_checksum(comparison_snapshot(item)) == item.snapshot_checksum
        ]
    if kind == FinanceAccountabilityPackageRequirement.TAX_FILING:
        from vouchers.models import TaxFilingEvidence

        queryset = TaxFilingEvidence.objects.filter(
            batch__finance_department_id=package.department_id,
            batch__treasury_department_id=slot.source_department_id,
            tax_period_start=package.period_start, tax_period_end=package.period_end,
            return_form_code__iexact=slot.tax_form_code,
            status__in=(
                (TaxFilingEvidence.VERIFIED, TaxFilingEvidence.SUPERSEDED)
                if allow_superseded else (TaxFilingEvidence.VERIFIED,)
            ),
        ).select_related("batch__treasury_department")
        return [
            (item, _tax_snapshot(item)) for item in queryset
            if len(item.evidence_checksum or "") == 64
        ]
    return []


def source_choices(slot):
    choices = []
    for item, snapshot in eligible_sources(slot):
        if slot.evidence_kind == FinanceAccountabilityPackageRequirement.REPORT_RUN:
            label = f"{item.definition.name} · {item.period_end:%Y-%m-%d} · {item.output_format.upper()} · {str(item.public_id)[:8]}"
        elif slot.evidence_kind == FinanceAccountabilityPackageRequirement.STATEMENT_NOTES:
            label = f"{item.title} · v{item.version} · {item.period_end:%Y-%m-%d} · {str(item.public_id)[:8]}"
        elif slot.evidence_kind == FinanceAccountabilityPackageRequirement.SIGNED_REFERENCE:
            label = f"{item.reference_label} · {item.run.definition.name} · v{item.version} · {str(item.public_id)[:8]}"
        else:
            label = f"{item.return_form_code} · {item.batch.reference_code} · filed {item.filing_date:%Y-%m-%d} · {str(item.public_id)[:8]}"
        choices.append((str(item.public_id), label, snapshot))
    return choices


@transaction.atomic
def select_source(slot, actor, *, source_public_id, reason=""):
    locked_slot = FinanceAccountabilityPackageSlot.objects.select_for_update().select_related(
        "package", "report_definition", "source_department",
    ).get(pk=slot.pk)
    if not locked_slot.package.is_editable:
        raise ValidationError("Locked packages cannot change evidence. Return the package or create a successor.")
    matched = [entry for entry in source_choices(locked_slot) if entry[0] == str(source_public_id)]
    if not matched:
        raise ValidationError("Choose currently eligible approved evidence for this exact slot and period.")
    source_id, label, snapshot = matched[0]
    current = locked_slot.selections.select_for_update().filter(
        status=FinanceAccountabilityPackageSelection.CURRENT,
    ).first()
    reason = (reason or "").strip()
    if current and not reason:
        raise ValidationError("Explain why the earlier evidence selection is being replaced.")
    if current and str(current.source_public_id) == source_id and current.source_snapshot == snapshot:
        raise ValidationError("This evidence is already the current selection.")
    if current:
        current.status = FinanceAccountabilityPackageSelection.SUPERSEDED
        current.save(update_fields=("status",))
    selection = FinanceAccountabilityPackageSelection.objects.create(
        slot=locked_slot, version=(current.version if current else 0) + 1,
        supersedes=current, source_public_id=source_id, source_label=label,
        source_snapshot=snapshot, source_checksum=evidence_checksum(snapshot),
        change_reason=reason, selected_by=actor,
    )
    FinanceAccountabilityPackageEvent.objects.create(
        package=locked_slot.package, actor=actor,
        action="evidence_replaced" if current else "evidence_selected",
        reason=reason,
        snapshot={
            "slot_code": locked_slot.code, "selection_version": selection.version,
            "source_public_id": source_id, "source_checksum": selection.source_checksum,
            "supersedes_selection_id": current.pk if current else None,
        },
    )
    return selection


def validate_package(package):
    errors = []
    historical = package.status in (
        FinanceAccountabilityPackage.APPROVED, FinanceAccountabilityPackage.SUPERSEDED,
    )
    slots = list(package.slots.select_related("report_definition", "source_department").prefetch_related("selections"))
    if not slots:
        errors.append("The pinned profile has no package requirements.")
    for slot in slots:
        selection = next((item for item in slot.selections.all() if item.status == item.CURRENT), None)
        if not selection:
            if slot.required:
                errors.append(f"{slot.label}: select required approved evidence.")
            continue
        matches = {
            str(item.public_id): snapshot for item, snapshot in eligible_sources(
                slot, allow_superseded=historical,
            )
        }
        current_snapshot = matches.get(str(selection.source_public_id))
        if current_snapshot is None:
            errors.append(f"{slot.label}: the selected evidence is no longer eligible or approved.")
        elif current_snapshot != selection.source_snapshot or evidence_checksum(current_snapshot) != selection.source_checksum:
            errors.append(f"{slot.label}: the selected evidence no longer matches its pinned checksum.")
    if package.profile.status != FinanceAccountabilityPackageProfile.ACTIVE and not historical:
        errors.append("The package profile is no longer active. Prepare a package from its accepted successor.")
    if historical:
        if evidence_checksum(package.profile_snapshot) != package.profile_checksum:
            errors.append("The retained package profile snapshot does not match its pinned checksum.")
    else:
        current_profile_snapshot = profile_snapshot(package.profile)
        if current_profile_snapshot != package.profile_snapshot or evidence_checksum(current_profile_snapshot) != package.profile_checksum:
            errors.append("The package profile does not match the approved snapshot pinned when this package was created.")
    return {"valid": not errors, "errors": errors}


def package_snapshot(package):
    return {
        "schema_version": 1,
        "public_id": str(package.public_id),
        "department_id": package.department_id,
        "profile_public_id": str(package.profile.public_id),
        "profile_code": package.profile.code,
        "profile_version": package.profile.version,
        "profile_checksum": package.profile_checksum,
        "title": package.title,
        "period_start": package.period_start.isoformat(),
        "period_end": package.period_end.isoformat(),
        "version": package.version,
        "supersedes_public_id": str(package.supersedes.public_id) if package.supersedes_id else "",
        "preparation_note": package.preparation_note,
        "slots": [
            {
                **_slot_snapshot(slot),
                "selection": (
                    {
                        "version": selection.version,
                        "source_public_id": str(selection.source_public_id),
                        "source_label": selection.source_label,
                        "source_snapshot": selection.source_snapshot,
                        "source_checksum": selection.source_checksum,
                        "change_reason": selection.change_reason,
                    }
                    if selection else None
                ),
            }
            for slot in package.slots.select_related(
                "source_department", "report_definition",
            ).prefetch_related("selections").order_by("position", "pk")
            for selection in [next((item for item in slot.selections.all() if item.status == item.CURRENT), None)]
        ],
    }


@transaction.atomic
def submit_package(package, actor):
    locked = FinanceAccountabilityPackage.objects.select_for_update().get(pk=package.pk)
    if not locked.is_editable:
        raise ValidationError("Only an editable accountability package can be submitted.")
    validation = validate_package(locked)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    snapshot = package_snapshot(locked)
    locked.package_snapshot = snapshot
    locked.package_checksum = evidence_checksum(snapshot)
    locked.status = FinanceAccountabilityPackage.SUBMITTED
    locked.submitted_by = actor
    locked.submitted_at = timezone.now()
    locked.reviewed_by = None
    locked.reviewed_at = None
    locked.review_note = ""
    locked.save(update_fields=(
        "package_snapshot", "package_checksum", "status", "submitted_by", "submitted_at",
        "reviewed_by", "reviewed_at", "review_note", "updated_at",
    ))
    FinanceAccountabilityPackageEvent.objects.create(
        package=locked, actor=actor, action="submitted", snapshot=snapshot,
    )
    return locked


@transaction.atomic
def review_package(package, actor, *, approve, note=""):
    locked = FinanceAccountabilityPackage.objects.select_for_update().get(pk=package.pk)
    if locked.status != FinanceAccountabilityPackage.SUBMITTED:
        raise ValidationError("Only a submitted accountability package can be reviewed.")
    if actor.pk in (locked.created_by_id, locked.submitted_by_id):
        raise ValidationError("The package preparer or submitter cannot review the same package.")
    note = (note or "").strip()
    if not approve:
        if not note:
            raise ValidationError("Explain the correction required before returning the package.")
        locked.status = FinanceAccountabilityPackage.RETURNED
        locked.reviewed_by = actor
        locked.reviewed_at = timezone.now()
        locked.review_note = note
        locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
        FinanceAccountabilityPackageEvent.objects.create(
            package=locked, actor=actor, action="returned", reason=note,
            snapshot={"package_checksum": locked.package_checksum},
        )
        return locked

    validation = validate_package(locked)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    snapshot = package_snapshot(locked)
    checksum = evidence_checksum(snapshot)
    if snapshot != locked.package_snapshot or checksum != locked.package_checksum:
        raise ValidationError("The submitted package no longer matches its pinned evidence. Return and resubmit it.")
    if locked.supersedes_id:
        prior = FinanceAccountabilityPackage.objects.select_for_update().get(pk=locked.supersedes_id)
        if prior.status != FinanceAccountabilityPackage.APPROVED:
            raise ValidationError("The package being corrected is no longer the approved predecessor.")
        prior.status = FinanceAccountabilityPackage.SUPERSEDED
        prior.save(update_fields=("status", "updated_at"))
        FinanceAccountabilityPackageEvent.objects.create(
            package=prior, actor=actor, action="superseded",
            reason=f"Replaced by approved package v{locked.version}.",
            snapshot={"successor_public_id": str(locked.public_id), "successor_checksum": checksum},
        )
    locked.status = FinanceAccountabilityPackage.APPROVED
    locked.reviewed_by = actor
    locked.reviewed_at = timezone.now()
    locked.review_note = note
    locked.full_clean()
    locked.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
    FinanceAccountabilityPackageEvent.objects.create(
        package=locked, actor=actor, action="approved", reason=note, snapshot=snapshot,
    )
    return locked


@transaction.atomic
def create_package_successor(package, actor, *, reason):
    prior = FinanceAccountabilityPackage.objects.select_for_update().select_related("profile").get(pk=package.pk)
    if prior.status != FinanceAccountabilityPackage.APPROVED:
        raise ValidationError("Only an approved package can be corrected through a successor.")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Explain why the approved package needs a successor.")
    if prior.successor_packages.exclude(status=FinanceAccountabilityPackage.SUPERSEDED).exists():
        raise ValidationError("This approved package already has a current successor in progress.")
    if prior.profile.status != FinanceAccountabilityPackageProfile.ACTIVE:
        raise ValidationError("The prior profile is no longer active. Start a new package from the accepted successor profile.")
    successor = FinanceAccountabilityPackage.objects.create(
        department=prior.department, profile=prior.profile, title=prior.title,
        period_start=prior.period_start, period_end=prior.period_end, version=prior.version + 1,
        supersedes=prior, preparation_note=f"Correction of v{prior.version}: {reason}",
        profile_snapshot=prior.profile_snapshot, profile_checksum=prior.profile_checksum,
        created_by=actor,
    )
    slot_map = {}
    for old_slot in prior.slots.select_related("source_department", "report_definition").order_by("position", "pk"):
        slot_map[old_slot.pk] = FinanceAccountabilityPackageSlot.objects.create(
            package=successor, position=old_slot.position, code=old_slot.code, label=old_slot.label,
            evidence_kind=old_slot.evidence_kind, source_department=old_slot.source_department,
            source_department_label=old_slot.source_department_label,
            report_definition=old_slot.report_definition,
            report_definition_label=old_slot.report_definition_label,
            tax_form_code=old_slot.tax_form_code, required=old_slot.required,
            instructions=old_slot.instructions,
        )
    for old_selection in FinanceAccountabilityPackageSelection.objects.filter(
        slot__package=prior, status=FinanceAccountabilityPackageSelection.CURRENT,
    ).select_related("slot"):
        FinanceAccountabilityPackageSelection.objects.create(
            slot=slot_map[old_selection.slot_id], version=1,
            source_public_id=old_selection.source_public_id, source_label=old_selection.source_label,
            source_snapshot=old_selection.source_snapshot, source_checksum=old_selection.source_checksum,
            change_reason=f"Copied from approved package v{prior.version}; review before resubmission.",
            selected_by=actor,
        )
    FinanceAccountabilityPackageEvent.objects.create(
        package=successor, actor=actor, action="successor_created", reason=reason,
        snapshot={
            "supersedes_public_id": str(prior.public_id),
            "supersedes_checksum": prior.package_checksum,
        },
    )
    FinanceAccountabilityPackageEvent.objects.create(
        package=prior, actor=actor, action="correction_started", reason=reason,
        snapshot={"successor_public_id": str(successor.public_id)},
    )
    return successor


def package_export_manifest(package):
    if package.status not in (
        FinanceAccountabilityPackage.APPROVED, FinanceAccountabilityPackage.SUPERSEDED,
    ):
        raise ValidationError("Only an approved or historically superseded accountability package can be exported.")
    validation = validate_package(package)
    if not validation["valid"]:
        raise ValidationError(validation["errors"])
    snapshot = package_snapshot(package)
    checksum = evidence_checksum(snapshot)
    if snapshot != package.package_snapshot or checksum != package.package_checksum:
        raise ValidationError("The approved package no longer matches its retained checksum.")
    return {
        "format": "GRAND Finance accountability package manifest",
        "schema_version": 1,
        "package": snapshot,
        "integrity": {
            "package_sha256": package.package_checksum,
            "profile_sha256": package.profile_checksum,
            "source_sha256": [
                item["selection"]["source_checksum"]
                for item in snapshot["slots"] if item["selection"]
            ],
        },
        "workflow": {
            "status": package.status,
            "prepared_by": package.created_by.username,
            "submitted_by": package.submitted_by.username if package.submitted_by_id else "",
            "submitted_at": package.submitted_at,
            "approved_by": package.reviewed_by.username if package.reviewed_by_id else "",
            "approved_at": package.reviewed_at,
            "review_note": package.review_note,
        },
        "portability_note": (
            "This manifest is archived under GRAND's department/user/category export root for TraceSync. "
            "Each source UUID and checksum identifies the separately retained governed output without changing it."
        ),
    }
