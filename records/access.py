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
    assigned_department = department_for_user(user)
    if department and getattr(department, "pk", None) != getattr(assigned_department, "pk", None):
        return False
    department = department or assigned_department
    return bool(department and (user.is_superuser or department_head(user, department) or user.has_perm(permission)))


def can_view_records(user, department=None):
    return _authorized(user, "records.view_records_workspace", department)


def can_manage_records(user, department=None):
    return _authorized(user, "records.manage_department_records", department)


def can_review_records(user, department=None):
    return _authorized(user, "records.review_department_records", department)


def can_approve_records(user, department=None):
    return _authorized(user, "records.approve_department_records", department)


def can_download_records(user, department=None):
    return _authorized(user, "records.download_department_records", department)


def can_manage_retention(user, department=None):
    return _authorized(user, "records.manage_record_retention", department)


def can_view_restricted_records(user, department=None):
    return _authorized(user, "records.view_restricted_records", department)


def record_is_visible(user, record):
    department = department_for_user(user)
    if not department or record.department_id != department.id or not can_view_records(user, department):
        return False
    return record.confidentiality == record.CONFIDENTIALITY_INTERNAL or can_view_restricted_records(user, department)


def records_access_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_view_records(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def records_permission_required(check):
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
