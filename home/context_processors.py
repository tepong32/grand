from assistance.access import (
    can_access_citizen_reviews,
    can_review_citizen_profiles,
    can_view_citizen_pii,
)
from reporting.access import can_view_reporting
from records.access import can_manage_records, can_view_records
from tracepoint.access import can_prepare_packets, can_view_workspace

from .models import ServiceShortcut, SiteConfiguration


def site_ui(request):
    configuration = SiteConfiguration.objects.first() or SiteConfiguration()
    profile = getattr(request.user, "employeeprofile", None) if request.user.is_authenticated else None
    department = getattr(profile, "assigned_department", None)
    is_hr = bool(department and (department.slug or "").strip().lower() == "hr")
    context = {
        "site_configuration": configuration,
        "public_service_shortcuts": ServiceShortcut.objects.filter(
            audience=ServiceShortcut.PUBLIC,
            is_active=True,
        ),
        "employee_service_shortcuts": ServiceShortcut.objects.filter(
            audience=ServiceShortcut.EMPLOYEE,
            is_active=True,
        ) if request.user.is_authenticated else ServiceShortcut.objects.none(),
        "employee_department": department,
        "can_view_user_directory": bool(request.user.is_authenticated and (request.user.is_superuser or is_hr)),
        "can_access_citizen_reviews": can_access_citizen_reviews(request.user),
        "can_review_citizen_profiles": can_review_citizen_profiles(request.user),
        "can_view_citizen_pii": can_view_citizen_pii(request.user),
        "can_access_reporting": can_view_reporting(request.user),
        "can_access_records": can_view_records(request.user),
        "can_manage_records": can_manage_records(request.user),
        "can_access_tracepoint": can_view_workspace(request.user),
        "can_prepare_tracepoint": can_prepare_packets(request.user),
    }
    if getattr(request, "user", None) and request.user.is_authenticated:
        from finance.access import can_view_finance_setup
        from vouchers.access import can_view_workbench
        context["can_access_finance_setup"] = can_view_finance_setup(request.user)
        context["can_access_vouchers"] = can_view_workbench(request.user)
    else:
        context["can_access_finance_setup"] = False
        context["can_access_vouchers"] = False
    return context
