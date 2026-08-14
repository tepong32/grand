from __future__ import annotations

from copy import deepcopy

from django.db.models import QuerySet

from profiles.models import EmployeeProfile
from leave_mgt.models import LeaveRequest

from ..models import Department

DEFAULT_DASHBOARD_TEMPLATE = "home/authed/dashboards/generic.html"


# These presets describe the work an office dashboard should grow into. They
# intentionally contain no fake totals: live figures come from the database,
# while unfinished modules are clearly labelled as planned.
DEFAULT_WORKSPACE_SECTIONS = (
    {
        "icon": "fa-inbox",
        "title": "Office work queue",
        "description": "Track incoming requests, assignments, and work awaiting action.",
        "status": "Planned",
    },
    {
        "icon": "fa-folder-open",
        "title": "Records and documents",
        "description": "Keep frequently used files, forms, and office records together.",
        "status": "Planned",
    },
    {
        "icon": "fa-chart-line",
        "title": "Reports and performance",
        "description": "Review service volume, turnaround time, and office targets.",
        "status": "Planned",
    },
)

DEPARTMENT_WORKSPACE_PRESETS = {
    "mswd": (
        {
            "icon": "fa-hands-helping",
            "title": "Assistance Requests",
            "description": "Review citizen assistance applications, supporting documents, and request progress.",
            "status": "Available",
            "url_name": "assistance:mswd_dashboard",
            "action_label": "Open Assistance Processing",
        },
        {
            "icon": "fa-people-carry",
            "title": "Social Welfare Programs",
            "description": "Coordinate feeding, outreach, orientation, distribution, and intervention programs.",
            "status": "Planned",
        },
        {
            "icon": "fa-calendar-day",
            "title": "Activities and Events",
            "description": "Schedule seminars, community activities, program sessions, and field operations.",
            "status": "Planned",
        },
        {
            "icon": "fa-user-friends",
            "title": "Beneficiaries and Citizens",
            "description": "Connect reusable citizen records with the services and programs they receive.",
            "status": "Planned",
        },
        {
            "icon": "fa-folder-open",
            "title": "Records and Documents",
            "description": "Maintain program records, supporting documents, and official office files.",
            "status": "Planned",
        },
        {
            "icon": "fa-chart-line",
            "title": "Reports and Statistics",
            "description": "Prepare service-volume, accomplishment, participation, and performance reports.",
            "status": "Planned",
        },
    ),
    "hr": (
        {
            "icon": "fa-users",
            "title": "Employee records",
            "description": "Review employee profiles, appointments, and department assignments.",
            "status": "Available",
            "url": "/users/",
        },
        {
            "icon": "fa-calendar-check",
            "title": "Leave administration",
            "description": "Review pending leave applications and monitor employee leave activity.",
            "status": "Available",
            "url": "/leave-mgt/",
        },
        {
            "icon": "fa-id-badge",
            "title": "Plantilla and recruitment",
            "description": "Monitor filled positions, vacancies, onboarding, and recruitment activity.",
            "status": "Planned",
        },
        {
            "icon": "fa-chart-bar",
            "title": "Workforce reports",
            "description": "Summarize headcount, movements, attendance, and staffing needs.",
            "status": "Planned",
        },
    ),
    "gso": (
        {
            "icon": "fa-boxes",
            "title": "Inventory register",
            "description": "Monitor accountable property, stock levels, and reorder points.",
            "status": "Planned",
        },
        {
            "icon": "fa-hand-holding",
            "title": "Property issuance",
            "description": "Track issued equipment, custodians, returns, and transfers.",
            "status": "Planned",
        },
        {
            "icon": "fa-truck",
            "title": "Suppliers and procurement",
            "description": "Follow purchase requests, supplier records, and expected deliveries.",
            "status": "Planned",
        },
        {
            "icon": "fa-tools",
            "title": "Maintenance requests",
            "description": "Coordinate facility, vehicle, and equipment maintenance work.",
            "status": "Planned",
        },
    ),
    "acctg": (
        {
            "icon": "fa-file-invoice-dollar",
            "title": "Disbursement queue",
            "description": "Track vouchers and supporting documents awaiting accounting action.",
            "status": "Planned",
        },
        {
            "icon": "fa-book",
            "title": "Ledgers and journals",
            "description": "Provide a working view of posting batches and reconciliation status.",
            "status": "Planned",
        },
        {
            "icon": "fa-money-check-alt",
            "title": "Payroll coordination",
            "description": "Monitor payroll preparation, deductions, and release readiness.",
            "status": "Planned",
        },
        {
            "icon": "fa-balance-scale",
            "title": "Compliance and audit",
            "description": "Surface reporting deadlines, audit findings, and required follow-ups.",
            "status": "Planned",
        },
    ),
}


def _query_employees() -> QuerySet[EmployeeProfile]:
    return EmployeeProfile.objects.select_related(
        "user", "assigned_department", "plantilla"
    )


def _department_employees(department: Department) -> QuerySet[EmployeeProfile]:
    return _query_employees().filter(assigned_department=department).order_by(
        "user__last_name", "user__first_name", "user__username"
    )


def _workspace_sections(department: Department) -> list[dict]:
    slug = (department.slug or "").strip().lower()
    sections = DEPARTMENT_WORKSPACE_PRESETS.get(slug, DEFAULT_WORKSPACE_SECTIONS)
    result = deepcopy(list(sections))
    if slug == "mswd":
        from assistance.models import AssistanceRequest

        active_requests = AssistanceRequest.objects.filter(is_active=True)
        result[0]["summary_items"] = (
            {"label": "Active", "value": active_requests.count()},
            {
                "label": "Awaiting action",
                "value": active_requests.filter(status__in=("submitted", "pending")).count(),
            },
            {"label": "Under review", "value": active_requests.filter(status="review").count()},
        )
    return result


def _metric_cards(department: Department, employees: QuerySet[EmployeeProfile]) -> list[dict]:
    employee_count = employees.count()
    plantilla_count = department.plantilla_set.count()
    filled_plantilla_count = employees.exclude(plantilla=None).count()
    pending_leave_count = LeaveRequest.objects.filter(
        employee__employee__assigned_department=department,
        status="PENDING",
    ).count()

    return [
        {
            "label": "Team members",
            "value": employee_count,
            "icon": "fa-users",
            "color": "info",
        },
        {
            "label": "Plantilla positions",
            "value": plantilla_count,
            "icon": "fa-id-card",
            "color": "primary",
        },
        {
            "label": "Unfilled positions",
            "value": max(plantilla_count - filled_plantilla_count, 0),
            "icon": "fa-user-plus",
            "color": "secondary",
        },
        {
            "label": "Pending leave",
            "value": pending_leave_count,
            "icon": "fa-calendar-alt",
            "color": "warning",
        },
    ]


def get_department_dashboard_context(department: Department, user) -> dict:
    """Build the live and suggested content for any department dashboard."""
    if not department:
        return {}

    employees = _department_employees(department)
    context = {
        "dashboard_metrics": _metric_cards(department, employees),
        "dashboard_sections": _workspace_sections(department),
        "team_members": employees[:6],
        "team_member_count": employees.count(),
        "is_department_head": department.deptHead_or_oic_id == getattr(user, "pk", None),
    }

    if (department.slug or "").strip().lower() == "hr":
        context.update(
            {
                "employees": _query_employees().all(),
                "leave_requests": LeaveRequest.objects.select_related(
                    "employee__employee__user"
                ).order_by("-date_filed")[:10],
            }
        )

    return context


def get_department_home_context(department: Department, user) -> dict:
    """Return the complete context contract consumed by dashboard templates."""
    if not department:
        return {}

    from home.models import Announcement

    base = {
        "department": department,
        "recent_announcements": Announcement.objects.filter(
            announcement_type=Announcement.INTERNAL,
            published=True,
        ).select_related("user").order_by("-is_pinned", "-created_at")[:5],
    }
    base.update(get_department_dashboard_context(department, user))
    return base
