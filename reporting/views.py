import csv
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from src.export_archive import archive_export

from .access import (
    can_approve_reports, can_download_reports, can_generate_reports, can_manage_definitions,
    can_manage_templates, can_review_reports, can_schedule_reports, department_for_user,
    can_view_department_reports, can_prepare_reference_comparisons, can_prepare_statement_notes,
    can_review_reference_comparisons, can_review_statement_notes, can_export_statement_packages,
    reporting_access_required, reporting_permission_required,
)
from .forms import (
    FinanceStatementLineForm, FinanceStatementMappingForm, FinanceStatementNoteForm,
    FinanceStatementNoteSetForm, ManualReportForm, ReportDefinitionForm,
    ReportReferenceComparisonForm, ReportScheduleForm, ReportTemplateMappingFieldForm,
    ReportTemplateVersionForm,
)
from .mappers import TemplateMappingError, preflight_template
from .models import (
    FinanceStatementLine, FinanceStatementMapping, FinanceStatementNote,
    FinanceStatementNoteEvent, FinanceStatementNoteSet, ReportDefinition,
    ReportReferenceComparison, ReportReferenceComparisonEvent, ReportRun, ReportRunEvent,
    ReportSchedule, ReportTemplateMappingField, ReportTemplateVersion,
)
from .services import create_manual_run, transition_run
from .statement_services import (
    comparison_controls, comparison_snapshot, mapping_coverage, note_set_snapshot,
    review_note_set, review_reference_comparison, review_statement_mapping,
    submit_note_set, submit_reference_comparison, submit_statement_mapping,
    validate_note_set,
)


def _department_object(queryset, user, **lookup):
    return get_object_or_404(queryset, department=department_for_user(user), **lookup)


def _statement_department(user):
    from django.core.exceptions import PermissionDenied
    department = department_for_user(user)
    if not ReportDefinition.objects.filter(
        department=department,
        dataset_key__in=("finance_statement_position", "finance_statement_performance"),
    ).exists():
        raise PermissionDenied("Statement mappings are available only to the configured Accounting reporting office.")
    return department


def _runs_visible_to(user):
    queryset = ReportRun.objects.filter(definition__department=department_for_user(user))
    if not can_view_department_reports(user):
        queryset = queryset.filter(created_by=user)
    return queryset


def _explained_finance_measures(runs):
    configured = {
        "finance_statement_position": (
            ("assets", "Assets"), ("liabilities", "Liabilities"),
            ("equity", "Equity"), ("unclosed_operating_result", "Unclosed operating result"),
            ("equation_difference", "Equation difference"),
        ),
        "finance_statement_performance": (
            ("revenue", "Revenue"), ("expense", "Expense"),
            ("operating_result", "Surplus / (deficit)"),
        ),
    }
    measures = []
    seen = set()
    for run in runs.filter(generated_at__isnull=False).select_related("definition").order_by("-generated_at"):
        dataset_key = run.parameters.get("_definition_snapshot", {}).get("dataset_key", run.definition.dataset_key)
        if dataset_key in seen or dataset_key not in configured:
            continue
        seen.add(dataset_key)
        for key, label in configured[dataset_key]:
            if key not in run.control_totals:
                continue
            measures.append({
                "label": label, "value": run.control_totals[key], "run": run,
                "definition": run.definition, "period_start": run.period_start,
                "period_end": run.period_end, "freshness_at": run.source_freshness_at,
                "control_status": run.get_control_status_display(),
                "control_ok": run.control_status == ReportRun.CONTROL_RECONCILED,
            })
    return measures


@reporting_access_required
def workspace(request):
    department = department_for_user(request.user)
    definitions = ReportDefinition.objects.filter(department=department, is_active=True).annotate(run_total=Count("runs"))
    visible_runs = _runs_visible_to(request.user)
    runs = visible_runs.select_related("definition", "template_version", "created_by")[:12]
    schedules = ReportSchedule.objects.filter(definition__department=department, is_active=True).select_related("definition")[:8]
    now = timezone.now()
    statement_mappings_enabled = definitions.filter(
        dataset_key__in=("finance_statement_position", "finance_statement_performance"),
    ).exists()
    return render(request, "reporting/workspace.html", {
        "department": department, "definitions": definitions, "recent_runs": runs, "schedules": schedules,
        "failed_count": visible_runs.filter(status=ReportRun.FAILED).count(),
        "awaiting_review_count": visible_runs.filter(status=ReportRun.GENERATED).count(),
        "overdue_count": ReportSchedule.objects.filter(definition__department=department, is_active=True, next_run_at__lt=now).count(),
        "recent_approved": visible_runs.filter(status=ReportRun.APPROVED, template_version__fidelity_status=ReportTemplateVersion.OFFICIAL, template_version__fidelity_validated_at__isnull=False).select_related("definition")[:5],
        "can_manage_definitions": can_manage_definitions(request.user), "can_schedule_reports": can_schedule_reports(request.user),
        "can_download": can_download_reports(request.user),
        "can_prepare_statement_notes": can_prepare_statement_notes(request.user),
        "can_prepare_reference_comparisons": can_prepare_reference_comparisons(request.user),
        "statement_note_sets": FinanceStatementNoteSet.objects.filter(department=department).select_related(
            "created_by", "reviewed_by",
        )[:5],
        "reference_comparisons": ReportReferenceComparison.objects.filter(
            run__definition__department=department,
        ).select_related("run__definition", "created_by", "reviewed_by")[:5],
        "explained_measures": _explained_finance_measures(visible_runs),
        "statement_mappings_enabled": statement_mappings_enabled,
    })


@reporting_access_required
def statement_mapping_list(request):
    department = _statement_department(request.user)
    mappings = FinanceStatementMapping.objects.filter(department=department).select_related(
        "created_by", "reviewed_by",
    ).prefetch_related("lines")
    return render(request, "reporting/statement_mapping_list.html", {
        "mappings": mappings, "department": department,
        "can_manage": can_manage_definitions(request.user),
    })


@reporting_permission_required(can_manage_definitions)
@require_http_methods(["GET", "POST"])
def statement_mapping_create(request):
    department = _statement_department(request.user)
    form = FinanceStatementMappingForm(
        request.POST or None, department=department, user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        mapping = form.save()
        messages.success(request, "Editable statement mapping created. Add its governed account lines, then submit it for independent review.")
        return redirect(mapping)
    return render(request, "reporting/statement_mapping_form.html", {"form": form, "mode": "Create"})


@reporting_access_required
def statement_mapping_detail(request, public_id):
    _statement_department(request.user)
    mapping = _department_object(
        FinanceStatementMapping.objects.select_related(
            "created_by", "submitted_by", "reviewed_by", "supersedes",
        ).prefetch_related("lines", "events__actor"), request.user, public_id=public_id,
    )
    return render(request, "reporting/statement_mapping_detail.html", {
        "mapping": mapping, "coverage": mapping_coverage(mapping),
        "can_manage": can_manage_definitions(request.user),
        "can_approve": can_approve_reports(request.user),
    })


@reporting_permission_required(can_manage_definitions)
@require_http_methods(["GET", "POST"])
def statement_mapping_update(request, public_id):
    _statement_department(request.user)
    mapping = _department_object(FinanceStatementMapping.objects.all(), request.user, public_id=public_id)
    if not mapping.is_editable:
        messages.error(request, "Locked mappings are immutable. Create a successor version instead.")
        return redirect(mapping)
    form = FinanceStatementMappingForm(
        request.POST or None, instance=mapping, department=mapping.department, user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Statement mapping details saved.")
        return redirect(mapping)
    return render(request, "reporting/statement_mapping_form.html", {"form": form, "mode": "Update", "mapping": mapping})


@reporting_permission_required(can_manage_definitions)
@require_http_methods(["GET", "POST"])
def statement_line_create(request, public_id):
    _statement_department(request.user)
    mapping = _department_object(FinanceStatementMapping.objects.all(), request.user, public_id=public_id)
    if not mapping.is_editable:
        messages.error(request, "Locked mapping lines cannot be changed. Create a successor version instead.")
        return redirect(mapping)
    form = FinanceStatementLineForm(request.POST or None, mapping=mapping)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Statement line added. The coverage check has been refreshed.")
        return redirect(mapping)
    return render(request, "reporting/statement_line_form.html", {"form": form, "mapping": mapping})


@reporting_permission_required(can_manage_definitions)
@require_http_methods(["GET", "POST"])
def statement_line_update(request, public_id, pk):
    _statement_department(request.user)
    mapping = _department_object(FinanceStatementMapping.objects.all(), request.user, public_id=public_id)
    line = get_object_or_404(FinanceStatementLine, pk=pk, mapping=mapping)
    if not mapping.is_editable:
        messages.error(request, "Locked mapping lines cannot be changed. Create a successor version instead.")
        return redirect(mapping)
    form = FinanceStatementLineForm(request.POST or None, instance=line, mapping=mapping)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Statement line updated. The coverage check has been refreshed.")
        return redirect(mapping)
    return render(request, "reporting/statement_line_form.html", {"form": form, "mapping": mapping, "line": line})


@reporting_permission_required(can_manage_definitions)
@require_POST
def statement_line_delete(request, public_id, pk):
    _statement_department(request.user)
    mapping = _department_object(FinanceStatementMapping.objects.all(), request.user, public_id=public_id)
    line = get_object_or_404(FinanceStatementLine, pk=pk, mapping=mapping)
    try:
        line.delete()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Statement line removed.")
    return redirect(mapping)


@reporting_permission_required(can_manage_definitions)
@require_POST
def statement_mapping_submit(request, public_id):
    _statement_department(request.user)
    mapping = _department_object(FinanceStatementMapping.objects.all(), request.user, public_id=public_id)
    try:
        submit_statement_mapping(mapping, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Statement mapping submitted for independent review.")
    return redirect(mapping)


@reporting_permission_required(can_approve_reports)
@require_POST
def statement_mapping_review(request, public_id, action):
    _statement_department(request.user)
    if action not in ("approve", "return"):
        from django.http import Http404
        raise Http404
    mapping = _department_object(FinanceStatementMapping.objects.all(), request.user, public_id=public_id)
    try:
        review_statement_mapping(
            mapping, request.user, approve=action == "approve", note=request.POST.get("review_note", ""),
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Statement mapping activated." if action == "approve" else "Statement mapping returned for correction.")
    return redirect(mapping)


def _note_set_for_user(user, public_id):
    return get_object_or_404(
        FinanceStatementNoteSet.objects.filter(department=department_for_user(user)).select_related(
            "department", "position_run__definition", "position_run__template_version",
            "performance_run__definition", "performance_run__template_version", "created_by",
            "submitted_by", "reviewed_by", "supersedes",
        ).prefetch_related("notes", "events__actor"),
        public_id=public_id,
    )


def _comparison_for_user(user, public_id):
    return get_object_or_404(
        ReportReferenceComparison.objects.filter(
            run__definition__department=department_for_user(user),
        ).select_related(
            "run__definition__department", "run__template_version", "created_by",
            "submitted_by", "reviewed_by",
        ).prefetch_related("events__actor"),
        public_id=public_id,
    )


@reporting_access_required
def statement_note_set_list(request):
    department = _statement_department(request.user)
    note_sets = FinanceStatementNoteSet.objects.filter(department=department).select_related(
        "position_run", "performance_run", "created_by", "reviewed_by",
    )
    return render(request, "reporting/statement_note_set_list.html", {
        "department": department,
        "note_sets": note_sets,
        "can_prepare": can_prepare_statement_notes(request.user),
    })


@reporting_permission_required(can_prepare_statement_notes)
@require_http_methods(["GET", "POST"])
def statement_note_set_create(request):
    department = _statement_department(request.user)
    form = FinanceStatementNoteSetForm(
        request.POST or None, department=department, user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        note_set = form.save()
        messages.success(
            request,
            "Editable candidate note topics created. Complete each applicable disclosure or record why it does not apply.",
        )
        return redirect(note_set)
    return render(request, "reporting/statement_note_set_form.html", {
        "form": form, "mode": "Create",
    })


@reporting_access_required
def statement_note_set_detail(request, public_id):
    _statement_department(request.user)
    note_set = _note_set_for_user(request.user, public_id)
    validation = validate_note_set(note_set)
    return render(request, "reporting/statement_note_set_detail.html", {
        "note_set": note_set,
        "validation": validation,
        "can_prepare": can_prepare_statement_notes(request.user),
        "can_review": can_review_statement_notes(request.user),
        "can_export": can_export_statement_packages(request.user),
    })


@reporting_permission_required(can_prepare_statement_notes)
@require_http_methods(["GET", "POST"])
def statement_note_set_update(request, public_id):
    _statement_department(request.user)
    note_set = _note_set_for_user(request.user, public_id)
    if not note_set.is_editable:
        messages.error(request, "Locked notes are immutable. Create a successor package instead.")
        return redirect(note_set)
    form = FinanceStatementNoteSetForm(
        request.POST or None, instance=note_set, department=note_set.department, user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Statement-note package details saved.")
        return redirect(note_set)
    return render(request, "reporting/statement_note_set_form.html", {
        "form": form, "mode": "Update", "note_set": note_set,
    })


@reporting_permission_required(can_prepare_statement_notes)
@require_http_methods(["GET", "POST"])
def statement_note_create(request, public_id):
    _statement_department(request.user)
    note_set = _note_set_for_user(request.user, public_id)
    if not note_set.is_editable:
        messages.error(request, "Locked note topics cannot be changed. Create a successor package.")
        return redirect(note_set)
    form = FinanceStatementNoteForm(request.POST or None, note_set=note_set)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Statement-note topic added.")
        return redirect(note_set)
    return render(request, "reporting/statement_note_form.html", {
        "form": form, "note_set": note_set, "mode": "Add",
    })


@reporting_permission_required(can_prepare_statement_notes)
@require_http_methods(["GET", "POST"])
def statement_note_update(request, public_id, pk):
    _statement_department(request.user)
    note_set = _note_set_for_user(request.user, public_id)
    item = get_object_or_404(FinanceStatementNote, note_set=note_set, pk=pk)
    if not note_set.is_editable:
        messages.error(request, "Locked note topics cannot be changed. Create a successor package.")
        return redirect(note_set)
    form = FinanceStatementNoteForm(
        request.POST or None, instance=item, note_set=note_set,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Statement-note topic saved.")
        return redirect(note_set)
    return render(request, "reporting/statement_note_form.html", {
        "form": form, "note_set": note_set, "item": item, "mode": "Update",
    })


@reporting_permission_required(can_prepare_statement_notes)
@require_POST
def statement_note_delete(request, public_id, pk):
    _statement_department(request.user)
    note_set = _note_set_for_user(request.user, public_id)
    item = get_object_or_404(FinanceStatementNote, note_set=note_set, pk=pk)
    try:
        item.delete()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Statement-note topic removed.")
    return redirect(note_set)


@reporting_permission_required(can_prepare_statement_notes)
@require_POST
def statement_note_set_submit(request, public_id):
    _statement_department(request.user)
    note_set = _note_set_for_user(request.user, public_id)
    try:
        submit_note_set(note_set, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Statement notes submitted with pinned report evidence.")
    return redirect(note_set)


@reporting_permission_required(can_review_statement_notes)
@require_POST
def statement_note_set_review(request, public_id, action):
    _statement_department(request.user)
    if action not in ("accept_working", "approve", "return"):
        from django.http import Http404
        raise Http404
    note_set = _note_set_for_user(request.user, public_id)
    try:
        review_note_set(
            note_set, request.user, action=action, note=request.POST.get("review_note", ""),
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        label = {
            "accept_working": "Controlled working notes accepted.",
            "approve": "Locally accepted statement notes approved.",
            "return": "Statement notes returned for correction.",
        }[action]
        messages.success(request, label)
    return redirect(note_set)


@reporting_permission_required(can_export_statement_packages)
def statement_note_set_export(request, public_id):
    _statement_department(request.user)
    note_set = _note_set_for_user(request.user, public_id)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow((
        "record_kind", "note_set_public_id", "period_start", "period_end", "version",
        "applicability_status", "workflow_status", "snapshot_checksum", "position_run",
        "performance_run", "package_authority_reference", "package_local_acceptance_note",
        "position", "topic_code", "title", "related_statement",
        "related_line_codes", "disclosure_text", "source_reference", "authority_basis",
        "not_applicable", "not_applicable_reason",
    ))
    writer.writerow((
        "note_package", note_set.public_id, note_set.period_start, note_set.period_end,
        note_set.version, note_set.applicability_status, note_set.status,
        note_set.snapshot_checksum, note_set.position_run.public_id,
        note_set.performance_run.public_id, note_set.authority_reference,
        note_set.local_acceptance_note, "", "", note_set.title, "", "", "", "", "", "", "",
    ))
    for item in note_set.notes.all():
        writer.writerow((
            "note_topic", note_set.public_id, note_set.period_start, note_set.period_end,
            note_set.version, note_set.applicability_status, note_set.status,
            note_set.snapshot_checksum, note_set.position_run.public_id,
            note_set.performance_run.public_id, note_set.authority_reference,
            note_set.local_acceptance_note, item.position, item.topic_code, item.title,
            item.related_statement, " | ".join(item.related_line_codes or []),
            item.disclosure_text, item.source_reference, item.authority_basis,
            item.is_not_applicable, item.not_applicable_reason,
        ))
    filename = f"statement-notes_{note_set.period_end}_{str(note_set.public_id)[:8]}.csv"
    archived = archive_export(
        content=response.content, department=note_set.department, user=request.user,
        category="finance-statement-notes", filename=filename,
        metadata={
            "kind": "finance_statement_notes", "note_set_public_id": str(note_set.public_id),
            "period_start": note_set.period_start, "period_end": note_set.period_end,
            "version": note_set.version, "status": note_set.status,
            "snapshot_checksum": note_set.snapshot_checksum,
        },
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    FinanceStatementNoteEvent.objects.create(
        note_set=note_set, actor=request.user, action="exported",
        reason=f"Archived {archived['relative_path']} with SHA-256 {archived['sha256']}.",
        snapshot={"relative_path": archived["relative_path"], "sha256": archived["sha256"]},
    )
    return response


@reporting_permission_required(can_prepare_reference_comparisons)
@require_http_methods(["GET", "POST"])
def reference_comparison_create(request, run_public_id):
    _statement_department(request.user)
    run = get_object_or_404(_runs_visible_to(request.user).select_related(
        "definition__department", "template_version",
    ), public_id=run_public_id)
    if not comparison_controls(run):
        from django.http import Http404
        raise Http404
    form = ReportReferenceComparisonForm(
        request.POST or None, request.FILES or None, run=run, user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        comparison = form.save()
        messages.success(request, "Editable signed-reference comparison saved. Submit it to pin and calculate exact controls.")
        return redirect(comparison)
    return render(request, "reporting/reference_comparison_form.html", {
        "form": form, "run": run, "mode": "Create",
    })


@reporting_access_required
def reference_comparison_detail(request, public_id):
    _statement_department(request.user)
    comparison = _comparison_for_user(request.user, public_id)
    labels = dict(comparison_controls(comparison.run))
    rows = [
        {
            "key": key, "label": label,
            "reference": comparison.reference_values.get(key, ""),
            "generated": comparison.generated_values_snapshot.get(key, ""),
            "difference": comparison.differences.get(key, ""),
        }
        for key, label in labels.items()
    ]
    return render(request, "reporting/reference_comparison_detail.html", {
        "comparison": comparison,
        "comparison_rows": rows,
        "can_prepare": can_prepare_reference_comparisons(request.user),
        "can_review": can_review_reference_comparisons(request.user),
        "can_export": can_export_statement_packages(request.user),
    })


@reporting_permission_required(can_prepare_reference_comparisons)
@require_http_methods(["GET", "POST"])
def reference_comparison_update(request, public_id):
    _statement_department(request.user)
    comparison = _comparison_for_user(request.user, public_id)
    if not comparison.is_editable:
        messages.error(request, "Submitted comparison evidence is immutable. Return it or create a successor.")
        return redirect(comparison)
    form = ReportReferenceComparisonForm(
        request.POST or None, request.FILES or None, instance=comparison,
        run=comparison.run, user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Signed-reference comparison saved.")
        return redirect(comparison)
    return render(request, "reporting/reference_comparison_form.html", {
        "form": form, "run": comparison.run, "comparison": comparison, "mode": "Update",
    })


@reporting_permission_required(can_prepare_reference_comparisons)
@require_POST
def reference_comparison_submit(request, public_id):
    _statement_department(request.user)
    comparison = _comparison_for_user(request.user, public_id)
    try:
        submit_reference_comparison(comparison, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Reference values, file checksum, and report evidence pinned for independent review.")
    return redirect(comparison)


@reporting_permission_required(can_review_reference_comparisons)
@require_POST
def reference_comparison_review(request, public_id, action):
    _statement_department(request.user)
    if action not in ("reconcile", "return"):
        from django.http import Http404
        raise Http404
    comparison = _comparison_for_user(request.user, public_id)
    try:
        review_reference_comparison(
            comparison, request.user, approve=action == "reconcile",
            note=request.POST.get("review_note", ""),
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Comparison independently reconciled." if action == "reconcile" else "Comparison returned for correction.")
    return redirect(comparison)


@reporting_access_required
def reference_comparison_download(request, public_id):
    _statement_department(request.user)
    if not can_export_statement_packages(request.user):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    comparison = _comparison_for_user(request.user, public_id)
    filename = comparison.reference_file.name.rsplit("/", 1)[-1]
    ReportReferenceComparisonEvent.objects.create(
        comparison=comparison, actor=request.user, action="reference_downloaded",
        reason="Permission-checked access to the retained redacted comparison copy.",
        snapshot={"reference_file_checksum": comparison.reference_file_checksum},
    )
    return FileResponse(comparison.reference_file.open("rb"), as_attachment=True, filename=filename)


@reporting_permission_required(can_export_statement_packages)
def reference_comparison_export(request, public_id):
    _statement_department(request.user)
    comparison = _comparison_for_user(request.user, public_id)
    evidence = {
        "format": "GRAND signed-reference comparison evidence",
        "version": 1,
        "comparison": comparison_snapshot(comparison),
        "integrity": {
            "comparison_sha256": comparison.snapshot_checksum,
            "reference_file_sha256": comparison.reference_file_checksum,
            "report_reproduction_key": comparison.run.reproduction_key,
        },
        "workflow_status": comparison.status,
        "reviewed_by": comparison.reviewed_by.username if comparison.reviewed_by_id else "",
        "reviewed_at": comparison.reviewed_at,
        "review_note": comparison.review_note,
    }
    content = json.dumps(
        evidence, cls=DjangoJSONEncoder, indent=2, sort_keys=True, ensure_ascii=False,
    ).encode("utf-8") + b"\n"
    filename = f"statement-reference-comparison_{str(comparison.public_id)[:8]}.json"
    archived = archive_export(
        content=content, department=comparison.department, user=request.user,
        category="finance-statement-reference-comparisons", filename=filename,
        metadata={
            "kind": "finance_statement_reference_comparison",
            "comparison_public_id": str(comparison.public_id),
            "run_public_id": str(comparison.run.public_id),
            "result": comparison.comparison_result,
            "snapshot_checksum": comparison.snapshot_checksum,
            "reference_file_checksum": comparison.reference_file_checksum,
        },
    )
    response = HttpResponse(content, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    ReportReferenceComparisonEvent.objects.create(
        comparison=comparison, actor=request.user, action="evidence_exported",
        reason=f"Archived {archived['relative_path']} with SHA-256 {archived['sha256']}.",
        snapshot={"relative_path": archived["relative_path"], "sha256": archived["sha256"]},
    )
    return response


@reporting_access_required
@require_http_methods(["GET", "POST"])
def definition_detail(request, pk):
    definition = _department_object(ReportDefinition.objects.all(), request.user, pk=pk)
    form = ManualReportForm(request.POST or None, definition=definition)
    if request.method == "POST":
        if not can_generate_reports(request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        if form.is_valid():
            try:
                run = create_manual_run(definition, form.cleaned_data["template_version"], form.cleaned_data["output_format"], form.cleaned_data["period_start"], form.cleaned_data["period_end"], {}, request.user)
            except Exception:
                messages.error(request, "The report run failed. Its error was recorded and can be safely retried.")
            else:
                scope = "official-layout candidate" if run.template_version.is_official_ready else "pilot comparison"
                messages.success(request, f"Report generated as a {scope}. Review is required before further use.")
                return redirect(run)
    runs = _runs_visible_to(request.user).filter(definition=definition).select_related("created_by")[:15]
    return render(request, "reporting/definition_detail.html", {"definition": definition, "form": form, "runs": runs, "templates": definition.template_versions.all(), "can_generate": can_generate_reports(request.user), "can_manage_templates": can_manage_templates(request.user), "can_manage_definitions": can_manage_definitions(request.user), "can_approve_templates": can_approve_reports(request.user)})


@reporting_permission_required(can_manage_definitions)
@require_http_methods(["GET", "POST"])
def definition_create(request):
    department = department_for_user(request.user)
    form = ReportDefinitionForm(request.POST or None, department=department, user=request.user)
    if request.method == "POST" and form.is_valid():
        definition = form.save()
        messages.success(request, "Report definition created. Add and approve an official template before generating outputs.")
        return redirect(definition)
    return render(request, "reporting/definition_form.html", {"form": form, "mode": "Create"})


@reporting_permission_required(can_manage_definitions)
@require_http_methods(["GET", "POST"])
def definition_update(request, pk):
    department = department_for_user(request.user)
    definition = _department_object(ReportDefinition.objects.all(), request.user, pk=pk)
    form = ReportDefinitionForm(request.POST or None, instance=definition, department=department, user=request.user)
    if request.method == "POST" and form.is_valid():
        definition = form.save()
        messages.success(request, "Report definition updated. Existing generated reports retain their original parameters and template versions.")
        return redirect(definition)
    return render(request, "reporting/definition_form.html", {"form": form, "mode": "Update", "definition": definition})


@reporting_permission_required(can_manage_templates)
@require_http_methods(["GET", "POST"])
def template_create(request, pk):
    definition = _department_object(ReportDefinition.objects.all(), request.user, pk=pk)
    form = ReportTemplateVersionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        template = form.save(commit=False)
        template.definition = definition
        template.version = (definition.template_versions.order_by("-version").values_list("version", flat=True).first() or 0) + 1
        template.created_by = request.user
        template.full_clean()
        template.save()
        messages.success(request, f"Template version {template.version} saved for controlled review.")
        if template.render_mode != ReportTemplateVersion.RENDER_NATIVE:
            return redirect("reporting:template_mapping", pk=template.pk)
        return redirect(definition)
    return render(request, "reporting/template_form.html", {"form": form, "definition": definition})


@reporting_permission_required(can_approve_reports)
@require_POST
def template_approve(request, pk):
    template = get_object_or_404(ReportTemplateVersion, pk=pk, definition__department=department_for_user(request.user))
    if not template.is_mapping_ready:
        messages.error(request, "Run template preflight successfully before approval.")
        return redirect("reporting:template_mapping", pk=template.pk)
    if template.render_mode != ReportTemplateVersion.RENDER_NATIVE:
        try:
            preflight_template(template, request.user)
        except TemplateMappingError as exc:
            messages.error(request, f"Approval blocked because preflight no longer passes: {exc}")
            return redirect("reporting:template_mapping", pk=template.pk)
        template.refresh_from_db()
    template.approved_by = request.user
    template.approved_at = timezone.now()
    template.full_clean()
    template.save(update_fields=("approved_by", "approved_at"))
    messages.success(request, f"Template version {template.version} is approved for controlled pilot generation. Department fidelity validation is still required before official use.")
    return redirect(template.definition)


@reporting_permission_required(can_manage_templates)
@require_http_methods(["GET", "POST"])
def template_mapping(request, pk):
    template = get_object_or_404(ReportTemplateVersion, pk=pk, definition__department=department_for_user(request.user))
    if template.render_mode == ReportTemplateVersion.RENDER_NATIVE:
        messages.info(request, "Native layouts do not require a mapper.")
        return redirect(template.definition)
    if template.approved_at and request.method == "POST":
        messages.error(request, "Approved template mappings are immutable. Create a new version instead.")
        return redirect("reporting:template_mapping", pk=template.pk)
    form = None
    if template.render_mode == ReportTemplateVersion.RENDER_PDF_OVERLAY:
        form = ReportTemplateMappingFieldForm(request.POST or None, template_version=template)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Coordinate mapping saved. Run preflight again before approval.")
            return redirect("reporting:template_mapping", pk=template.pk)
    return render(request, "reporting/template_mapping.html", {"template": template, "form": form, "mappings": template.overlay_fields.all()})


@reporting_permission_required(can_manage_templates)
@require_POST
def template_mapping_delete(request, pk, mapping_pk):
    template = get_object_or_404(ReportTemplateVersion, pk=pk, definition__department=department_for_user(request.user))
    mapping = get_object_or_404(ReportTemplateMappingField, pk=mapping_pk, template_version=template)
    try:
        mapping.delete()
    except Exception as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Coordinate mapping removed. Run preflight again before approval.")
    return redirect("reporting:template_mapping", pk=template.pk)


@reporting_permission_required(can_manage_templates)
@require_POST
def template_preflight(request, pk):
    template = get_object_or_404(ReportTemplateVersion, pk=pk, definition__department=department_for_user(request.user))
    if template.approved_at:
        messages.info(request, "This approved mapping is immutable and already validated.")
        return redirect("reporting:template_mapping", pk=template.pk)
    try:
        summary = preflight_template(template, request.user)
    except TemplateMappingError as exc:
        messages.error(request, f"Preflight failed: {exc}")
    else:
        messages.success(request, f"Preflight passed. The reference checksum and {summary.get('mapping_count', summary.get('row_capacity', 0))} mapped area(s) were recorded.")
    return redirect("reporting:template_mapping", pk=template.pk)


@reporting_permission_required(can_manage_templates)
def template_reference_download(request, pk):
    template = get_object_or_404(ReportTemplateVersion, pk=pk, definition__department=department_for_user(request.user))
    if not template.reference_file:
        from django.http import Http404
        raise Http404
    return FileResponse(template.reference_file.open("rb"), as_attachment=True, filename=template.reference_file.name.rsplit("/", 1)[-1])


@reporting_permission_required(can_approve_reports)
@require_POST
def template_validate_fidelity(request, pk):
    template = get_object_or_404(ReportTemplateVersion, pk=pk, definition__department=department_for_user(request.user))
    if template.is_official_ready:
        messages.info(request, "This template version already has immutable department fidelity validation.")
        return redirect(template.definition)
    if not template.approved_at:
        messages.error(request, "Approve the controlled template before recording department fidelity validation.")
        return redirect(template.definition)
    note = request.POST.get("fidelity_notes", "").strip()
    if not note:
        messages.error(request, "Record what departmental form and comparison were used for validation.")
        return redirect(template.definition)
    template.fidelity_status = ReportTemplateVersion.OFFICIAL
    template.fidelity_notes = note
    template.fidelity_validated_by = request.user
    template.fidelity_validated_at = timezone.now()
    template.full_clean()
    template.save(update_fields=("fidelity_status", "fidelity_notes", "fidelity_validated_by", "fidelity_validated_at"))
    messages.success(request, f"Template version {template.version} is department-validated for official outputs.")
    return redirect(template.definition)


@reporting_access_required
def run_detail(request, public_id):
    run = get_object_or_404(_runs_visible_to(request.user).select_related("definition__department", "template_version", "created_by", "reviewed_by", "approved_by"), public_id=public_id)
    can_download = can_download_reports(request.user)
    official_record = None
    if run.is_official_output:
        from django.contrib.contenttypes.models import ContentType
        from records.models import RecordAssociation

        content_type = ContentType.objects.get_for_model(run)
        association = RecordAssociation.objects.filter(
            content_type=content_type, object_id=run.pk, role="official_source"
        ).select_related("record").first()
        official_record = association.record if association else None
    return render(request, "reporting/run_detail.html", {
        "run": run, "can_review": can_review_reports(request.user),
        "can_approve": can_approve_reports(request.user), "can_download": can_download,
        "can_print": can_download and run.is_printable, "official_record": official_record,
        "source_records": run.source_records.all()[:100],
        "statement_comparison_controls": comparison_controls(run),
        "reference_comparisons": run.reference_comparisons.select_related("created_by", "reviewed_by").all(),
        "can_prepare_reference_comparisons": can_prepare_reference_comparisons(request.user),
        "definition_applicability_snapshot": run.parameters.get("_definition_snapshot", {}).get("applicability_status", "departmental"),
    })


@reporting_access_required
@require_POST
def run_transition(request, public_id, action):
    run = get_object_or_404(_runs_visible_to(request.user), public_id=public_id)
    allowed = (action == "review" and can_review_reports(request.user)) or (action in ("approve", "supersede") and can_approve_reports(request.user))
    if not allowed:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    try:
        transition_run(run, action, request.user, request.POST.get("note", ""))
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Report marked as {run.get_status_display().lower()}.")
    return redirect(run)


@reporting_access_required
def run_download(request, public_id):
    if not can_download_reports(request.user):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    run = get_object_or_404(_runs_visible_to(request.user), public_id=public_id)
    if not run.output_file:
        from django.http import Http404
        raise Http404
    filename = run.output_file.name.rsplit("/", 1)[-1]
    with run.output_file.open("rb") as source:
        archived = archive_export(
            content=source.read(),
            department=run.definition.department,
            user=request.user,
            category="reports",
            filename=filename,
            metadata={
                "kind": "report_run_export",
                "run_public_id": str(run.public_id),
                "definition": run.definition.slug,
                "period_start": run.period_start,
                "period_end": run.period_end,
                "parameters": run.parameters,
                "status": run.status,
                "output_checksum": run.checksum,
                "dataset_checksum": run.dataset_checksum,
                "control_checksum": run.control_checksum,
                "reproduction_key": run.reproduction_key,
                "official_output": run.is_official_output,
            },
        )
    response = FileResponse(run.output_file.open("rb"), as_attachment=True, filename=filename)
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    ReportRunEvent.objects.create(
        run=run,
        actor=request.user,
        action="exported",
        from_status=run.status,
        to_status=run.status,
        note=f"Archived {archived['relative_path']} with SHA-256 {archived['sha256']}.",
    )
    return response


def _require_downloadable_run(request, public_id):
    if not can_download_reports(request.user):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    return get_object_or_404(_runs_visible_to(request.user), public_id=public_id)


@reporting_access_required
def run_control_export(request, public_id):
    run = _require_downloadable_run(request, public_id)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    writer = csv.writer(response)
    writer.writerow((
        "record_kind", "run_public_id", "definition", "period_start", "period_end",
        "control_status", "dataset_checksum", "control_checksum", "reproduction_key",
        "source_app", "source_model", "source_pk", "source_public_id", "source_reference",
        "source_date", "control_group", "amount", "source_checksum", "source_url", "source_snapshot",
    ))
    writer.writerow((
        "report_control", run.public_id, run.definition.slug, run.period_start, run.period_end,
        run.control_status, run.dataset_checksum, run.control_checksum, run.reproduction_key,
        "", "", "", "", "", "", "", "", "", "", "", json.dumps(run.control_totals, sort_keys=True),
    ))
    for source in run.source_records.all():
        writer.writerow((
            "source_record", run.public_id, run.definition.slug, run.period_start, run.period_end,
            run.control_status, run.dataset_checksum, run.control_checksum, run.reproduction_key,
            source.source_app, source.source_model, source.source_pk, source.source_public_id,
            source.source_reference, source.source_date, source.control_group, source.amount,
            source.source_checksum, source.source_url, json.dumps(source.snapshot, sort_keys=True),
        ))
    filename = f"{run.definition.slug}_{str(run.public_id)[:8]}_control-evidence.csv"
    archived = archive_export(
        content=response.content, department=run.definition.department, user=request.user,
        category="finance-report-evidence", filename=filename,
        metadata={
            "kind": "report_control_evidence", "run_public_id": str(run.public_id),
            "dataset_checksum": run.dataset_checksum, "control_checksum": run.control_checksum,
            "reproduction_key": run.reproduction_key, "source_record_count": run.source_record_count,
        },
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    ReportRunEvent.objects.create(
        run=run, actor=request.user, action="control_evidence_exported",
        from_status=run.status, to_status=run.status,
        note=f"Archived {archived['relative_path']} with SHA-256 {archived['sha256']}.",
    )
    return response


@reporting_access_required
def run_reproduction_receipt(request, public_id):
    run = _require_downloadable_run(request, public_id)
    receipt = {
        "format": "GRAND report reproduction receipt",
        "version": 1,
        "run_public_id": str(run.public_id),
        "definition": run.parameters.get("_definition_snapshot", {}),
        "template": run.parameters.get("_template_snapshot", {}),
        "period_start": run.period_start,
        "period_end": run.period_end,
        "output_format": run.output_format,
        "status": run.status,
        "row_count": run.row_count,
        "source_record_count": run.source_record_count,
        "source_freshness_at": run.source_freshness_at,
        "dataset_snapshot": run.dataset_snapshot,
        "control_totals": run.control_totals,
        "control_status": run.control_status,
        "control_message": run.control_message,
        "checksums": {
            "output_sha256": run.checksum,
            "dataset_sha256": run.dataset_checksum,
            "control_sha256": run.control_checksum,
            "reproduction_key": run.reproduction_key,
        },
        "sources": [
            {
                "app": source.source_app, "model": source.source_model,
                "pk": source.source_pk, "public_id": source.source_public_id,
                "reference": source.source_reference, "date": source.source_date,
                "control_group": source.control_group, "amount": source.amount,
                "source_checksum": source.source_checksum, "source_url": source.source_url,
                "snapshot": source.snapshot,
            }
            for source in run.source_records.all()
        ],
    }
    content = json.dumps(
        receipt, cls=DjangoJSONEncoder, indent=2, sort_keys=True, ensure_ascii=False,
    ).encode("utf-8") + b"\n"
    filename = f"{run.definition.slug}_{str(run.public_id)[:8]}_reproduction-receipt.json"
    archived = archive_export(
        content=content, department=run.definition.department, user=request.user,
        category="finance-report-evidence", filename=filename,
        metadata={
            "kind": "report_reproduction_receipt", "run_public_id": str(run.public_id),
            "output_checksum": run.checksum, "dataset_checksum": run.dataset_checksum,
            "control_checksum": run.control_checksum, "reproduction_key": run.reproduction_key,
        },
    )
    response = HttpResponse(content, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = archived["sha256"]
    ReportRunEvent.objects.create(
        run=run, actor=request.user, action="reproduction_receipt_exported",
        from_status=run.status, to_status=run.status,
        note=f"Archived {archived['relative_path']} with SHA-256 {archived['sha256']}.",
    )
    return response


@reporting_access_required
def run_print_preview(request, public_id):
    if not can_download_reports(request.user):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    run = get_object_or_404(_runs_visible_to(request.user), public_id=public_id, output_format=ReportDefinition.FORMAT_PDF)
    if not run.output_file:
        from django.http import Http404
        raise Http404
    return FileResponse(run.output_file.open("rb"), as_attachment=False, filename=run.output_file.name.rsplit("/", 1)[-1], content_type="application/pdf")


@reporting_permission_required(can_schedule_reports)
@require_http_methods(["GET", "POST"])
def schedule_create(request):
    department = department_for_user(request.user)
    form = ReportScheduleForm(request.POST or None, department=department, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Recurring report schedule created. Duplicate scheduled outputs are prevented by the run ledger.")
        return redirect("reporting:workspace")
    return render(request, "reporting/schedule_form.html", {"form": form})
