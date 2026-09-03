from __future__ import annotations

import csv
import io
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils.text import slugify

from src.export_archive import archive_export

from .access import (
    can_approve_reports, can_download_reports, can_generate_reports,
    can_review_reports, can_view_department_reports, department_for_user,
)
from .models import ReportDefinition, ReportRun, ReportRunEvent


ATTENTION_CHOICES = (
    ("generation_failed", "Generation failed"),
    ("control_blocked", "Control evidence blocks review"),
    ("needs_review", "Ready for independent review"),
    ("needs_approval", "Reviewed; needs approval decision"),
    ("approved", "Approved output"),
    ("superseded", "Superseded evidence"),
)

RUN_ACTION_SPECS = {
    "generation": {
        "title": "Draft reports ready to generate",
        "definition": "Visible draft report runs awaiting generation from their pinned definition and template.",
        "next_action": "Generate the report from its governed sources and retain its exact output and control evidence.",
        "permission": "generate",
    },
    "generation_failed": {
        "title": "Failed reports to correct and rerun",
        "definition": "Visible failed report runs awaiting a source/setup correction and controlled rerun.",
        "next_action": "Read the retained error, correct the governed source or setup, then rerun this report.",
        "permission": "generate",
    },
    "control_blocked": {
        "title": "Generated reports blocked by controls",
        "definition": "Generated reports whose required control evidence is unavailable or does not reconcile exactly.",
        "next_action": "Resolve the stated source or mapping difference and generate a successor report; do not alter this evidence.",
        "permission": "generate",
    },
    "needs_review": {
        "title": "Reports ready for independent review",
        "definition": "Generated reports with satisfied control gates awaiting a reviewer other than the creator.",
        "next_action": "Independently verify the retained output, dataset, source, control, and reproduction checksums before review.",
        "permission": "review",
    },
    "needs_approval": {
        "title": "Reviewed reports awaiting approval",
        "definition": "Reviewed reports awaiting an approver other than the report creator.",
        "next_action": "Confirm local applicability, official-template readiness, exact controls, and retained checksums before approval.",
        "permission": "approve",
    },
}


def visible_report_runs(user, queryset=None):
    department = department_for_user(user)
    base = queryset if queryset is not None else ReportRun.objects.all()
    if department is None:
        return base.none()
    base = base.filter(definition__department_id=department.pk)
    if not can_view_department_reports(user):
        base = base.filter(created_by=user)
    return base


def report_action_choices_for_user(user):
    allowed = {
        "generate": can_generate_reports(user),
        "review": can_review_reports(user),
        "approve": can_approve_reports(user),
    }
    return tuple(
        (key, spec["title"])
        for key, spec in RUN_ACTION_SPECS.items()
        if allowed[spec["permission"]]
    )


def report_action_queryset(user, action, queryset=None):
    base = visible_report_runs(user, queryset)
    spec = RUN_ACTION_SPECS.get(action)
    allowed = {
        "generate": can_generate_reports(user),
        "review": can_review_reports(user),
        "approve": can_approve_reports(user),
    }
    if spec is None or not allowed[spec["permission"]]:
        return base.none(), action if spec else "", spec
    if action == "generation":
        base = base.filter(status=ReportRun.DRAFT)
    elif action == "generation_failed":
        base = base.filter(status=ReportRun.FAILED)
    elif action == "control_blocked":
        base = base.filter(
            status=ReportRun.GENERATED, control_gate_required=True,
        ).exclude(control_status=ReportRun.CONTROL_RECONCILED)
    elif action == "needs_review":
        base = base.filter(status=ReportRun.GENERATED).filter(
            Q(control_gate_required=False) | Q(control_status=ReportRun.CONTROL_RECONCILED),
        ).exclude(created_by=user)
    elif action == "needs_approval":
        base = base.filter(status=ReportRun.REVIEWED).exclude(created_by=user)
    return base.distinct(), action, spec

RUN_REGISTER_COLUMNS = (
    "run_public_id", "report_name", "definition_slug", "dataset_key",
    "definition_applicability", "authority_reference", "template_title", "template_version",
    "template_render_mode", "template_fidelity", "template_mapping_checksum",
    "current_template_official_ready", "period_start", "period_end", "output_format", "status",
    "next_action", "row_count", "source_record_count", "source_freshness_at",
    "control_gate_required", "control_status", "control_message", "control_totals",
    "output_checksum", "dataset_checksum", "control_checksum", "reproduction_key",
    "run_source", "schedule_name", "runtime_parameters", "created_by", "created_at",
    "generated_at", "reviewed_by", "reviewed_at", "approved_by", "approved_at",
    "last_event", "last_event_note", "last_event_at", "error_message",
)


def apply_report_run_filters(
    queryset, *, status="", definition="", output_format="", control_status="",
    period_year="", attention="", search="",
):
    available_definition_ids = set(queryset.values_list("definition_id", flat=True))
    if status in dict(ReportRun.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    elif status:
        queryset = queryset.none()
    else:
        status = ""

    if definition:
        if definition.isdigit() and int(definition) in available_definition_ids:
            queryset = queryset.filter(definition_id=definition)
        else:
            queryset = queryset.none()

    if output_format in dict(ReportDefinition.FORMAT_CHOICES):
        queryset = queryset.filter(output_format=output_format)
    elif output_format:
        queryset = queryset.none()
    else:
        output_format = ""

    if control_status in dict(ReportRun.CONTROL_STATUS_CHOICES):
        queryset = queryset.filter(control_status=control_status)
    elif control_status:
        queryset = queryset.none()
    else:
        control_status = ""

    available_years = {str(value.year) for value in queryset.values_list("period_end", flat=True)}
    if period_year:
        if period_year in available_years:
            queryset = queryset.filter(period_end__year=period_year)
        else:
            queryset = queryset.none()

    if attention == "generation_failed":
        queryset = queryset.filter(status=ReportRun.FAILED)
    elif attention == "control_blocked":
        queryset = queryset.filter(
            status=ReportRun.GENERATED, control_gate_required=True,
        ).exclude(control_status=ReportRun.CONTROL_RECONCILED)
    elif attention == "needs_review":
        queryset = queryset.filter(status=ReportRun.GENERATED).filter(
            Q(control_gate_required=False) | Q(control_status=ReportRun.CONTROL_RECONCILED),
        )
    elif attention == "needs_approval":
        queryset = queryset.filter(status=ReportRun.REVIEWED)
    elif attention == "approved":
        queryset = queryset.filter(status=ReportRun.APPROVED)
    elif attention == "superseded":
        queryset = queryset.filter(status=ReportRun.SUPERSEDED)
    elif attention:
        queryset = queryset.none()
    else:
        attention = ""

    search = (search or "").strip()[:160]
    if search:
        queryset = queryset.filter(
            Q(definition__name__icontains=search) | Q(definition__slug__icontains=search)
            | Q(idempotency_key__icontains=search) | Q(control_message__icontains=search)
            | Q(error_message__icontains=search),
        )
    return (
        queryset, status, definition, output_format, control_status,
        period_year, attention, search,
    )


def next_report_action(run):
    definition_snapshot = run.parameters.get("_definition_snapshot", {})
    if run.status == ReportRun.DRAFT:
        return "Generate the report from its governed source and retain the resulting evidence"
    if run.status == ReportRun.FAILED:
        return "Read the generation error, correct the source or setup, and run it again"
    if run.status == ReportRun.GENERATED:
        if run.control_gate_required and run.control_status != ReportRun.CONTROL_RECONCILED:
            return "Correct the governed source or mapping, then generate a successor report"
        return "A different authorized reviewer checks controls, source evidence, and layout"
    if run.status == ReportRun.REVIEWED:
        if definition_snapshot.get("applicability_status") == ReportDefinition.APPLICABILITY_CANDIDATE:
            return "Confirm local applicability, then generate a successor under the accepted definition"
        if not run.template_version.is_official_ready:
            return "Complete independent template promotion and fidelity validation before approval"
        return "An authorized approver decides whether this exact retained output is official"
    if run.status == ReportRun.APPROVED:
        if run.is_official_output:
            return "Retain, distribute through the approved route, or select it for an accountability package"
        return "Retain this earlier approval and generate a successor with the validated current template"
    return "Retain as superseded evidence and use the approved successor for current reporting"


def _csv_safe(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def _actor_label(actor):
    return actor.get_full_name() or actor.username if actor else ""


def _iso(value):
    return value.isoformat() if value else ""


def build_report_run_register(
    *, actor, queryset, status="", definition="", output_format="", control_status="",
    period_year="", attention="", search="",
):
    department = department_for_user(actor)
    if department is None or not can_download_reports(actor):
        raise PermissionDenied
    if queryset.exclude(definition__department_id=department.pk).exists():
        raise ValidationError("The report-run register may contain only the acting user's department.")
    if not can_view_department_reports(actor) and queryset.exclude(created_by=actor).exists():
        raise ValidationError("The report-run register may contain only reports visible to this user.")

    runs = list(queryset.select_related(
        "definition", "template_version", "schedule", "created_by", "reviewed_by", "approved_by",
    ).prefetch_related("events"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(RUN_REGISTER_COLUMNS)
    for run in runs:
        definition_snapshot = run.parameters.get("_definition_snapshot", {})
        template_snapshot = run.parameters.get("_template_snapshot", {})
        runtime_parameters = {
            key: value for key, value in run.parameters.items() if not key.startswith("_")
        }
        events = list(run.events.all())
        last_event = events[0] if events else None
        writer.writerow(tuple(_csv_safe(value) for value in (
            run.public_id, definition_snapshot.get("name", run.definition.name),
            definition_snapshot.get("slug", run.definition.slug),
            definition_snapshot.get("dataset_key", run.definition.dataset_key),
            definition_snapshot.get("applicability_status", run.definition.applicability_status),
            definition_snapshot.get("authority_reference", ""),
            template_snapshot.get("title", run.template_version.title),
            template_snapshot.get("version", run.template_version.version),
            template_snapshot.get("render_mode", run.template_version.render_mode),
            template_snapshot.get("fidelity_status", run.template_version.fidelity_status),
            template_snapshot.get("mapping_checksum", run.template_version.mapping_checksum),
            run.template_version.is_official_ready, run.period_start, run.period_end,
            run.output_format, run.get_status_display(), next_report_action(run), run.row_count,
            run.source_record_count, _iso(run.source_freshness_at), run.control_gate_required,
            run.get_control_status_display(), run.control_message,
            json.dumps(run.control_totals, sort_keys=True, ensure_ascii=False), run.checksum,
            run.dataset_checksum, run.control_checksum, run.reproduction_key,
            "Scheduled" if run.schedule_id else "Manual", run.schedule.name if run.schedule_id else "",
            json.dumps(runtime_parameters, sort_keys=True, ensure_ascii=False), _actor_label(run.created_by),
            _iso(run.created_at), _iso(run.generated_at), _actor_label(run.reviewed_by),
            _iso(run.reviewed_at), _actor_label(run.approved_by), _iso(run.approved_at),
            last_event.action if last_event else "", last_event.note if last_event else "",
            _iso(last_event.created_at) if last_event else "", run.error_message,
        )))

    content = "\ufeff".encode("utf-8") + stream.getvalue().encode("utf-8")
    suffix = "-".join(slugify(value) for value in (
        attention, status, f"definition-{definition}" if definition else "", output_format,
        control_status, f"year-{period_year}" if period_year else "", search,
    ) if value) or "all-visible"
    filename = f"finance-report-run-register-{suffix}.csv"
    metadata = {
        "kind": "finance_report_run_register", "status_filter": status or "all",
        "definition_filter": definition or "all", "output_format_filter": output_format or "all",
        "control_status_filter": control_status or "all", "period_year_filter": period_year or "all",
        "attention_filter": attention or "all", "search_filter": search, "run_count": len(runs),
        "visibility_scope": "department" if can_view_department_reports(actor) else "own_runs",
        "authority_boundary": (
            "Operational report-ledger evidence only. This register is not an approved report, signed form, "
            "filing acknowledgement, or proof of COA, DBM, BIR, or local-form acceptance."
        ),
    }
    receipt = archive_export(
        content=content, department=department, user=actor,
        category="finance-report-run-register", filename=filename, metadata=metadata,
    )
    if runs:
        ReportRunEvent.objects.bulk_create([
            ReportRunEvent(
                run=run, actor=actor, action="register_exported",
                from_status=run.status, to_status=run.status,
                note=f"Archived {receipt['relative_path']} with SHA-256 {receipt['sha256']}.",
            )
            for run in runs
        ])
    return content, filename, receipt
