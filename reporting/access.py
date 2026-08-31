from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def department_for_user(user):
    profile = getattr(user, "employeeprofile", None)
    return getattr(profile, "assigned_department", None)


def department_head(user, department=None):
    department = department or department_for_user(user)
    return bool(department and department.deptHead_or_oic_id == getattr(user, "pk", None))


def _authorized(user, permission, department=None):
    if not getattr(user, "is_authenticated", False):
        return False
    department = department or department_for_user(user)
    if not department:
        return False
    return bool(user.is_superuser or department_head(user, department) or user.has_perm(permission))


def can_view_reporting(user, department=None):
    return _authorized(user, "reporting.view_reporting_workspace", department)


def can_manage_definitions(user, department=None):
    return _authorized(user, "reporting.manage_report_definitions", department)


def can_manage_templates(user, department=None):
    return _authorized(user, "reporting.manage_report_templates", department)


def can_schedule_reports(user, department=None):
    return _authorized(user, "reporting.schedule_reports", department)


def can_generate_reports(user, department=None):
    return _authorized(user, "reporting.generate_reports", department)


def can_review_reports(user, department=None):
    return _authorized(user, "reporting.review_reports", department)


def can_approve_reports(user, department=None):
    return _authorized(user, "reporting.approve_reports", department)


def can_download_reports(user, department=None):
    return _authorized(user, "reporting.download_reports", department)


def can_view_department_reports(user, department=None):
    return bool(
        _authorized(user, "reporting.view_department_reports", department)
        or can_review_reports(user, department)
        or can_approve_reports(user, department)
    )


def can_prepare_statement_notes(user, department=None):
    return _authorized(user, "reporting.prepare_statement_notes", department)


def can_review_statement_notes(user, department=None):
    return _authorized(user, "reporting.review_statement_notes", department)


def can_prepare_reference_comparisons(user, department=None):
    return _authorized(user, "reporting.prepare_reference_comparisons", department)


def can_review_reference_comparisons(user, department=None):
    return _authorized(user, "reporting.review_reference_comparisons", department)


def can_export_statement_packages(user, department=None):
    return _authorized(user, "reporting.export_statement_packages", department)


def can_prepare_template_promotions(user, department=None):
    return _authorized(user, "reporting.prepare_template_promotions", department)


def can_approve_template_promotions(user, department=None):
    return _authorized(user, "reporting.approve_template_promotions", department)


def can_activate_template_promotions(user, department=None):
    return _authorized(user, "reporting.activate_template_promotions", department)


def reporting_access_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_view_reporting(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def reporting_permission_required(check):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not check(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
