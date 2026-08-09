from __future__ import annotations

from django.db.models import QuerySet

from profiles.models import EmployeeProfile
from leave_mgt.models import LeaveRequest
from assistance.models import AssistanceRequest

from ..models import Department

DEFAULT_DASHBOARD_TEMPLATE = "home/authed/dashboards/generic.html"


def _query_employees() -> QuerySet[EmployeeProfile]:
    return EmployeeProfile.objects.select_related("user", "assigned_department")


def get_department_dashboard_context(department: Department, user) -> dict:
    """
    Build compact dashboard context by department slug.
    """
    if not department:
        return {}

    match (department.slug or "").strip().lower():
        case "hr":
            return {
                "employees": _query_employees().all(),
                "leave_requests": LeaveRequest.objects.select_related("employee__user").order_by("-submitted_at")[:10],
            }
        case "gso":
            return {}
        case "acctg":
            return {}
        case "mswd":
            assistance_qs = AssistanceRequest.objects.order_by("-submitted_at")
            return {
                "recent_requests": assistance_qs[:10],
                "request_count": assistance_qs.count(),
                "pending_count": AssistanceRequest.objects.filter(status="pending").count(),
                "review_count": AssistanceRequest.objects.filter(status="review").count(),
                "approved_count": AssistanceRequest.objects.filter(status="approved").count(),
                "denied_count": AssistanceRequest.objects.filter(status="denied").count(),
            }
        case _:
            return {}


def get_department_home_context(department: Department, user) -> dict:
    """
    Extend the context with common department-specific values.
    """
    base = {"department": department}
    base.update(get_department_dashboard_context(department, user))
    return base
