from django.contrib import messages
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .access import (
    can_approve_reports, can_download_reports, can_generate_reports, can_manage_definitions,
    can_manage_templates, can_review_reports, can_schedule_reports, department_for_user,
    can_view_department_reports, reporting_access_required, reporting_permission_required,
)
from .forms import ManualReportForm, ReportDefinitionForm, ReportScheduleForm, ReportTemplateVersionForm
from .models import ReportDefinition, ReportRun, ReportSchedule, ReportTemplateVersion
from .services import create_manual_run, transition_run


def _department_object(queryset, user, **lookup):
    return get_object_or_404(queryset, department=department_for_user(user), **lookup)


def _runs_visible_to(user):
    queryset = ReportRun.objects.filter(definition__department=department_for_user(user))
    if not can_view_department_reports(user):
        queryset = queryset.filter(created_by=user)
    return queryset


@reporting_access_required
def workspace(request):
    department = department_for_user(request.user)
    definitions = ReportDefinition.objects.filter(department=department, is_active=True).annotate(run_total=Count("runs"))
    visible_runs = _runs_visible_to(request.user)
    runs = visible_runs.select_related("definition", "template_version", "created_by")[:12]
    schedules = ReportSchedule.objects.filter(definition__department=department, is_active=True).select_related("definition")[:8]
    now = timezone.now()
    return render(request, "reporting/workspace.html", {
        "department": department, "definitions": definitions, "recent_runs": runs, "schedules": schedules,
        "failed_count": visible_runs.filter(status=ReportRun.FAILED).count(),
        "awaiting_review_count": visible_runs.filter(status=ReportRun.GENERATED).count(),
        "overdue_count": ReportSchedule.objects.filter(definition__department=department, is_active=True, next_run_at__lt=now).count(),
        "recent_approved": visible_runs.filter(status=ReportRun.APPROVED).select_related("definition")[:5],
        "can_manage_definitions": can_manage_definitions(request.user), "can_schedule_reports": can_schedule_reports(request.user),
    })


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
                messages.success(request, "Report generated as a draft output. Review and approval are still required before official use.")
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
        return redirect(definition)
    return render(request, "reporting/template_form.html", {"form": form, "definition": definition})


@reporting_permission_required(can_approve_reports)
@require_POST
def template_approve(request, pk):
    template = get_object_or_404(ReportTemplateVersion, pk=pk, definition__department=department_for_user(request.user))
    template.approved_by = request.user
    template.approved_at = timezone.now()
    template.save(update_fields=("approved_by", "approved_at"))
    messages.success(request, f"Template version {template.version} is approved for official generation.")
    return redirect(template.definition)


@reporting_access_required
def run_detail(request, public_id):
    run = get_object_or_404(_runs_visible_to(request.user).select_related("definition__department", "template_version", "created_by", "reviewed_by", "approved_by"), public_id=public_id)
    return render(request, "reporting/run_detail.html", {"run": run, "can_review": can_review_reports(request.user), "can_approve": can_approve_reports(request.user), "can_download": can_download_reports(request.user)})


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
    return FileResponse(run.output_file.open("rb"), as_attachment=True, filename=run.output_file.name.rsplit("/", 1)[-1])


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
