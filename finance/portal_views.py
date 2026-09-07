from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.http import Http404

from .operations import finance_operations_access, finance_operations_areas
from .work_attention import finance_work_attention
from .work_tasks import finance_work_tasks


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
    selected_view = request.GET.get("view", "ready")
    if selected_view not in ("ready", "waiting", "returned", "upcoming", "past_dates"):
        raise Http404("Unknown work view.")
    raw_days = request.GET.get("days", "7")
    if raw_days not in ("7", "14", "30"):
        raise Http404("Unknown calendar window.")
    planned_days = int(raw_days)
    attention = finance_work_attention(request.user)
    attention.update(finance_work_tasks(request.user, view=selected_view, planned_days=planned_days))
    attention["planned_days"] = planned_days
    attention["planned_windows"] = (7, 14, 30)
    attention["selected_view"] = selected_view
    attention["work_views"] = (("ready", "Ready for me"), ("waiting", "Waiting"), ("returned", "Returned"), ("upcoming", "Upcoming dates"), ("past_dates", "Past dates"))
    return render(request, "finance/my_work.html", attention)
