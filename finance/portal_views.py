from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

from .operations import finance_operations_access, finance_operations_areas
from .work_attention import finance_work_attention
from .work_tasks import finance_work_tasks
from .work_exports import WORK_EXPORT_LIMIT, build_work_export, can_export_work


@login_required
def overview(request):
    access, work_areas, control_areas = finance_operations_areas(request.user)
    if not access["allowed"]:
        raise PermissionDenied
    department = getattr(getattr(request.user, "employeeprofile", None), "assigned_department", None)
    return render(request, "finance/operations_overview.html", {
        "department": department,
        "work_areas": work_areas,
        "control_areas": control_areas,
        "can_search_cases": access["vouchers"],
    })


@login_required
def my_work(request):
    access = finance_operations_access(request.user)
    if not access["allowed"]:
        raise PermissionDenied
    selected_view, planned_days = _work_view_parameters(request)
    attention = finance_work_attention(request.user)
    attention.update(finance_work_tasks(request.user, view=selected_view, planned_days=planned_days))
    attention["can_export_work"] = can_export_work(request.user)
    attention["export_row_limit"] = WORK_EXPORT_LIMIT
    attention["planned_days"] = planned_days
    attention["planned_windows"] = (7, 14, 30)
    attention["selected_view"] = selected_view
    attention["work_views"] = (("ready", "Ready for me"), ("waiting", "Waiting"), ("returned", "Returned"), ("upcoming", "Upcoming dates"), ("past_dates", "Past dates"), ("completed", "Completed by me"))
    return render(request, "finance/my_work.html", attention)


def _work_view_parameters(request):
    selected_view = request.GET.get("view", "ready")
    if selected_view not in ("ready", "waiting", "returned", "upcoming", "past_dates", "completed"):
        raise Http404("Unknown work view.")
    raw_days = request.GET.get("days", "7")
    if raw_days not in ("7", "14", "30"):
        raise Http404("Unknown calendar window.")
    return selected_view, int(raw_days)


@login_required
@require_GET
def my_work_export(request):
    if not can_export_work(request.user):
        raise PermissionDenied
    selected_view, planned_days = _work_view_parameters(request)
    content, filename, receipt, metadata = build_work_export(request.user, view=selected_view, planned_days=planned_days)
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-GRAND-Export-Archived"] = "true"
    response["X-GRAND-Export-SHA256"] = receipt["sha256"]
    response["X-GRAND-Export-Row-Count"] = str(metadata["row_count"])
    response["X-GRAND-Export-Eligible-Count"] = str(metadata["eligible_count"])
    response["X-GRAND-Export-Truncated"] = str(metadata["truncated"]).lower()
    return response
