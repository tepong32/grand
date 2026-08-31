from __future__ import annotations

import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from .mappers import preflight_template
from .models import (
    ReportDefinition, ReportRun, ReportSchedule, ReportTemplatePromotion,
    ReportTemplatePromotionEvent, ReportTemplateVersion,
)
from .services import create_manual_run


def _safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, sort_keys=True))


def _checksum(value):
    payload = json.dumps(_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_checksum(field):
    if not field:
        return ""
    field.open("rb")
    try:
        digest = hashlib.sha256()
        for chunk in iter(lambda: field.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        field.close()


def template_snapshot(template):
    mappings = [
        {
            "source_key": item.source_key,
            "page_number": item.page_number,
            "x_mm": str(item.x_mm),
            "y_mm": str(item.y_mm),
            "width_mm": str(item.width_mm),
            "font_size": str(item.font_size),
            "alignment": item.alignment,
            "repeat_for_rows": item.repeat_for_rows,
            "row_height_mm": str(item.row_height_mm),
            "max_rows": item.max_rows,
            "display_order": item.display_order,
        }
        for item in template.overlay_fields.order_by("display_order", "pk")
    ]
    return {
        "template_id": template.pk,
        "definition_id": template.definition_id,
        "version": template.version,
        "title": template.title,
        "header_text": template.header_text,
        "certification_text": template.certification_text,
        "footer_text": template.footer_text,
        "document_control_prefix": template.document_control_prefix,
        "signatories": list(template.signatories or []),
        "layout_config": dict(template.layout_config or {}),
        "reference_kind": template.reference_kind,
        "reference_name": template.reference_file.name if template.reference_file else "",
        "reference_checksum": _file_checksum(template.reference_file),
        "render_mode": template.render_mode,
        "mapping_checksum": template.mapping_checksum,
        "mapping_summary": dict(template.mapping_summary or {}),
        "page_size": template.page_size,
        "orientation": template.orientation,
        "margin_mm": template.margin_mm,
        "page_border": template.page_border,
        "repeat_header": template.repeat_header,
        "show_footer": template.show_footer,
        "show_page_numbers": template.show_page_numbers,
        "show_document_control": template.show_document_control,
        "primary_logo_name": template.primary_logo.name if template.primary_logo else "",
        "primary_logo_checksum": _file_checksum(template.primary_logo),
        "secondary_logo_name": template.secondary_logo.name if template.secondary_logo else "",
        "secondary_logo_checksum": _file_checksum(template.secondary_logo),
        "mappings": mappings,
    }


def template_diff(before, after):
    before = before or {}
    changes = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changes.append({"field": key, "before": before.get(key), "after": after.get(key)})
    return changes


def _run_evidence(run):
    return {
        "public_id": str(run.public_id),
        "template_version": run.template_version.version,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat(),
        "output_format": run.output_format,
        "status": run.status,
        "row_count": run.row_count,
        "source_record_count": run.source_record_count,
        "output_checksum": run.checksum,
        "dataset_checksum": run.dataset_checksum,
        "control_checksum": run.control_checksum,
        "control_status": run.control_status,
        "reproduction_key": run.reproduction_key,
    }


def _impact_snapshot(candidate, baseline):
    schedules = ReportSchedule.objects.filter(
        definition=candidate.definition, is_active=True,
    )
    if baseline:
        schedules = schedules.filter(template_version=baseline)
    eligible = [item.pk for item in schedules if candidate.supports_format(item.output_format)]
    incompatible = [item.pk for item in schedules if not candidate.supports_format(item.output_format)]
    return {
        "active_schedule_count": schedules.count(),
        "compatible_schedule_ids": eligible,
        "incompatible_schedule_ids": incompatible,
        "prior_template_version": baseline.version if baseline else None,
        "candidate_template_version": candidate.version,
        "render_mode_changed": bool(baseline and baseline.render_mode != candidate.render_mode),
        "supported_formats_before": list(baseline.supported_formats) if baseline else [],
        "supported_formats_after": list(candidate.supported_formats),
        "approved_historical_output_count": ReportRun.objects.filter(
            definition=candidate.definition, status=ReportRun.APPROVED,
        ).count(),
        "historical_outputs_remain_pinned": True,
    }


def active_official_template(definition, exclude_template=None):
    queryset = definition.template_versions.filter(
        is_active=True,
        approved_at__isnull=False,
        fidelity_status=ReportTemplateVersion.OFFICIAL,
        fidelity_validated_at__isnull=False,
    )
    if exclude_template:
        queryset = queryset.exclude(pk=exclude_template.pk)
    return queryset.order_by("-version").first()


def _golden_snapshot(preview, baseline_run):
    result = {
        "preview": _run_evidence(preview),
        "baseline": _run_evidence(baseline_run) if baseline_run else None,
    }
    if baseline_run:
        checks = {
            "dataset_checksum": preview.dataset_checksum == baseline_run.dataset_checksum,
            "control_checksum": preview.control_checksum == baseline_run.control_checksum,
            "row_count": preview.row_count == baseline_run.row_count,
            "source_record_count": preview.source_record_count == baseline_run.source_record_count,
            "control_status": preview.control_status == baseline_run.control_status,
        }
        result["checks"] = checks
        result["all_checks_passed"] = all(checks.values())
    else:
        result["checks"] = {"reference_review_required": True}
        result["all_checks_passed"] = None
    return result


@transaction.atomic
def create_template_promotion(
    template, actor, period_start, period_end, output_format, change_reason,
    comparison_note, baseline_run=None, update_compatible_schedules=False,
):
    if hasattr(template, "promotion_request"):
        raise ValueError("This template version already has a promotion request.")
    if not template.approved_at:
        raise ValueError("Approve the candidate for controlled preview generation first.")
    if template.render_mode != template.RENDER_NATIVE:
        preflight_template(template, actor)
        template.refresh_from_db()
    if not template.is_mapping_ready:
        raise ValueError("The candidate template must pass preflight before comparison.")
    if not template.supports_format(output_format):
        raise ValueError("Choose an output format supported by this candidate template.")
    active_baseline = active_official_template(template.definition, exclude_template=template)
    baseline = baseline_run.template_version if baseline_run else active_baseline
    if baseline_run:
        if baseline_run.definition_id != template.definition_id or not baseline_run.is_official_output:
            raise ValueError("Choose an approved official run from the same report as the golden comparison.")
        if not active_baseline or baseline_run.template_version_id != active_baseline.pk:
            raise ValueError("Choose an accepted run from the current active official template.")
        if (baseline_run.period_start, baseline_run.period_end, baseline_run.output_format) != (
            period_start, period_end, output_format,
        ):
            raise ValueError("The golden run must cover the same period and output format as the preview.")
    elif baseline:
        raise ValueError("Choose an approved run from the current official template for the golden comparison.")
    elif not template.reference_file:
        raise ValueError("A first official layout requires a retained blank or redacted reference form.")
    if not change_reason.strip() or not comparison_note.strip():
        raise ValueError("Record both the reason for change and the plain-language comparison evidence.")

    preview = create_manual_run(
        template.definition, template, output_format, period_start, period_end,
        {"_template_promotion_preview": True}, actor,
    )
    candidate_snapshot = template_snapshot(template)
    baseline_snapshot = template_snapshot(baseline) if baseline else {}
    golden = _golden_snapshot(preview, baseline_run)
    if baseline_run:
        golden_result = (
            ReportTemplatePromotion.GOLDEN_MATCHED
            if golden["all_checks_passed"]
            else ReportTemplatePromotion.GOLDEN_EXCEPTION
        )
    else:
        golden_result = ReportTemplatePromotion.GOLDEN_REFERENCE
    promotion = ReportTemplatePromotion(
        candidate_template=template,
        baseline_template=baseline,
        preview_run=preview,
        baseline_run=baseline_run,
        change_reason=change_reason.strip(),
        comparison_note=comparison_note.strip(),
        update_compatible_schedules=update_compatible_schedules,
        template_snapshot=candidate_snapshot,
        template_checksum=_checksum(candidate_snapshot),
        mapping_diff=template_diff(baseline_snapshot, candidate_snapshot),
        impact_snapshot=_impact_snapshot(template, baseline),
        golden_result=golden_result,
        golden_snapshot=golden,
        created_by=actor,
    )
    promotion.full_clean()
    promotion.save()
    ReportTemplatePromotionEvent.objects.create(
        promotion=promotion, actor=actor, action="preview_created",
        reason=promotion.change_reason,
        snapshot={
            "template_checksum": promotion.template_checksum,
            "golden_result": promotion.golden_result,
            "preview_run": str(preview.public_id),
        },
    )
    return promotion


def _current_submission_snapshot(promotion):
    return {
        "candidate_template_id": promotion.candidate_template_id,
        "baseline_template_id": promotion.baseline_template_id,
        "preview_run": _run_evidence(promotion.preview_run),
        "baseline_run": _run_evidence(promotion.baseline_run) if promotion.baseline_run_id else None,
        "change_reason": promotion.change_reason,
        "comparison_note": promotion.comparison_note,
        "update_compatible_schedules": promotion.update_compatible_schedules,
        "template_snapshot": promotion.template_snapshot,
        "template_checksum": promotion.template_checksum,
        "mapping_diff": promotion.mapping_diff,
        "impact_snapshot": promotion.impact_snapshot,
        "golden_result": promotion.golden_result,
        "golden_snapshot": promotion.golden_snapshot,
    }


def assert_template_evidence_current(promotion):
    current = template_snapshot(promotion.candidate_template)
    if _checksum(current) != promotion.template_checksum or current != promotion.template_snapshot:
        raise ValueError("The candidate template changed after preview. Create a new version and comparison.")
    preview = promotion.preview_run
    expected = promotion.golden_snapshot.get("preview", {})
    if _run_evidence(preview) != expected:
        raise ValueError("The retained preview evidence no longer matches this request.")


@transaction.atomic
def submit_template_promotion(promotion, actor):
    if promotion.status not in (promotion.DRAFT, promotion.RETURNED):
        raise ValueError("Only an editable promotion request can be submitted.")
    if promotion.candidate_template.definition.applicability_status == ReportDefinition.APPLICABILITY_CANDIDATE:
        raise ValueError("Confirm the report's local applicability before submitting an official template promotion.")
    assert_template_evidence_current(promotion)
    if promotion.golden_result == promotion.GOLDEN_EXCEPTION:
        raise ValueError("The golden comparison has differences. Correct the source or create a new template version.")
    if promotion.impact_snapshot.get("incompatible_schedule_ids") and promotion.update_compatible_schedules:
        raise ValueError("One or more active schedules use a format this candidate cannot produce.")
    now = timezone.now()
    promotion.status = promotion.SUBMITTED
    promotion.submitted_by = actor
    promotion.submitted_at = now
    promotion.submission_checksum = _checksum(_current_submission_snapshot(promotion))
    promotion.full_clean()
    promotion.save(update_fields=(
        "status", "submitted_by", "submitted_at", "submission_checksum", "updated_at",
    ))
    ReportTemplatePromotionEvent.objects.create(
        promotion=promotion, actor=actor, action="submitted",
        snapshot={"submission_checksum": promotion.submission_checksum},
    )
    return promotion


@transaction.atomic
def review_template_promotion(promotion, actor, action, note):
    if promotion.status != promotion.SUBMITTED:
        raise ValueError("Only a submitted promotion request can be reviewed.")
    if actor.pk in (promotion.created_by_id, promotion.submitted_by_id):
        raise ValueError("The preparer or submitter cannot review the same template promotion.")
    if not note.strip():
        raise ValueError("Record the approval or return reason.")
    assert_template_evidence_current(promotion)
    now = timezone.now()
    promotion.reviewed_by = actor
    promotion.reviewed_at = now
    promotion.review_note = note.strip()
    if action == "return":
        promotion.status = promotion.RETURNED
    elif action == "approve":
        promotion.status = promotion.APPROVED
        template = promotion.candidate_template
        template.fidelity_status = template.OFFICIAL
        template.fidelity_notes = f"{promotion.comparison_note}\n\nIndependent approval: {promotion.review_note}"
        template.fidelity_validated_by = actor
        template.fidelity_validated_at = now
        template.is_active = False
        template.full_clean()
        template.save(update_fields=(
            "fidelity_status", "fidelity_notes", "fidelity_validated_by",
            "fidelity_validated_at", "is_active",
        ))
    else:
        raise ValueError("Choose approve or return.")
    promotion.full_clean()
    promotion.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_note", "updated_at"))
    ReportTemplatePromotionEvent.objects.create(
        promotion=promotion, actor=actor, action=action, reason=promotion.review_note,
        snapshot={"submission_checksum": promotion.submission_checksum},
    )
    return promotion


@transaction.atomic
def activate_template_promotion(promotion, actor):
    if promotion.status != promotion.APPROVED:
        raise ValueError("Only an independently approved promotion can be activated.")
    assert_template_evidence_current(promotion)
    candidate = promotion.candidate_template
    if not candidate.is_official_ready:
        raise ValueError("The candidate no longer satisfies official-template controls.")
    ReportTemplateVersion.objects.filter(
        definition=candidate.definition, is_active=True,
    ).exclude(pk=candidate.pk).update(is_active=False)
    candidate.is_active = True
    candidate.save(update_fields=("is_active",))
    updated_schedule_ids = []
    if promotion.update_compatible_schedules and promotion.baseline_template_id:
        schedules = ReportSchedule.objects.filter(
            definition=candidate.definition,
            template_version=promotion.baseline_template,
            is_active=True,
        )
        for schedule in schedules:
            if not candidate.supports_format(schedule.output_format):
                raise ValueError("An active schedule uses an output format this candidate cannot produce.")
            schedule.template_version = candidate
            schedule.full_clean()
            schedule.save(update_fields=("template_version", "updated_at"))
            updated_schedule_ids.append(schedule.pk)
    promotion.status = promotion.ACTIVATED
    promotion.activated_by = actor
    promotion.activated_at = timezone.now()
    promotion.full_clean()
    promotion.save(update_fields=("status", "activated_by", "activated_at", "updated_at"))
    ReportTemplatePromotionEvent.objects.create(
        promotion=promotion, actor=actor, action="activated",
        reason="Approved layout activated without a software deployment.",
        snapshot={"active_template_id": candidate.pk, "updated_schedule_ids": updated_schedule_ids},
    )
    return promotion


@transaction.atomic
def rollback_template_promotion(promotion, actor, reason):
    if promotion.status != promotion.ACTIVATED:
        raise ValueError("Only the active promoted template can be rolled back.")
    if not promotion.baseline_template_id:
        raise ValueError("This is the first official template, so there is no prior version to restore.")
    if not reason.strip():
        raise ValueError("Record why the active layout is being rolled back.")
    candidate = promotion.candidate_template
    baseline = promotion.baseline_template
    if not baseline.is_official_ready:
        raise ValueError("The prior template is not eligible to return to official service.")
    candidate.is_active = False
    candidate.save(update_fields=("is_active",))
    baseline.is_active = True
    baseline.save(update_fields=("is_active",))
    updated_schedule_ids = []
    for schedule in ReportSchedule.objects.filter(
        definition=candidate.definition, template_version=candidate, is_active=True,
    ):
        if baseline.supports_format(schedule.output_format):
            schedule.template_version = baseline
            schedule.full_clean()
            schedule.save(update_fields=("template_version", "updated_at"))
            updated_schedule_ids.append(schedule.pk)
    promotion.status = promotion.ROLLED_BACK
    promotion.rolled_back_by = actor
    promotion.rolled_back_at = timezone.now()
    promotion.rollback_reason = reason.strip()
    promotion.full_clean()
    promotion.save(update_fields=(
        "status", "rolled_back_by", "rolled_back_at", "rollback_reason", "updated_at",
    ))
    ReportTemplatePromotionEvent.objects.create(
        promotion=promotion, actor=actor, action="rolled_back", reason=promotion.rollback_reason,
        snapshot={"restored_template_id": baseline.pk, "updated_schedule_ids": updated_schedule_ids},
    )
    return promotion


def promotion_receipt(promotion):
    return {
        "promotion_public_id": str(promotion.public_id),
        "report": promotion.candidate_template.definition.name,
        "department": promotion.department.name,
        "status": promotion.status,
        "candidate_template_version": promotion.candidate_template.version,
        "baseline_template_version": promotion.baseline_template.version if promotion.baseline_template_id else None,
        "change_reason": promotion.change_reason,
        "comparison_note": promotion.comparison_note,
        "template_checksum": promotion.template_checksum,
        "submission_checksum": promotion.submission_checksum,
        "mapping_diff": promotion.mapping_diff,
        "impact_snapshot": promotion.impact_snapshot,
        "golden_result": promotion.golden_result,
        "golden_snapshot": promotion.golden_snapshot,
        "review_note": promotion.review_note,
        "rollback_reason": promotion.rollback_reason,
        "events": [
            {
                "action": item.action,
                "actor": item.actor.get_full_name() or item.actor.username,
                "reason": item.reason,
                "snapshot": item.snapshot,
                "created_at": item.created_at.isoformat(),
            }
            for item in promotion.events.select_related("actor").order_by("created_at", "pk")
        ],
    }
