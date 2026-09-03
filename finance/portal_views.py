from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from .operations import finance_operations_areas


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
    })
