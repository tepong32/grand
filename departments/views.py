from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_http_methods

from .models import Department
from .services.query_service import get_department_by_slug
from .services.internal_howtos import set_step_completion


@require_http_methods(["GET"])
@login_required
def department_index(request):
    """
    Lightweight department index endpoint used by internal tools and admins.
    Keeps app behavior minimal while providing a stable place for future extensions.
    """
    departments = Department.objects.all().order_by("name")
    return render(request, "home/authed/dashboards/generic.html", {"department_rows": departments})


def department_detail(request, slug: str):
    """
    Lightweight public-safe department detail helper to avoid duplicated query logic.
    """
    department = get_department_by_slug(slug)
    if not department:
        raise PermissionDenied("Department not found.")

    context = {"department": department}
    return render(request, "home/authed/dashboards/generic.html", context)


@require_POST
@login_required
def internal_howto_step_completion(request, step_id):
    completed = request.POST.get("completed", "true").lower() in {"1", "true", "yes", "on"}
    _completion, is_completed = set_step_completion(user=request.user, step_id=step_id, completed=completed)
    return JsonResponse({"step_id": step_id, "completed": is_completed})
