from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

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
    attention = finance_work_attention(request.user)
    attention.update(finance_work_tasks(request.user))
    return render(request, "finance/my_work.html", attention)
