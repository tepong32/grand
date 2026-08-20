from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def department_for_user(user):
    profile = getattr(user, "employeeprofile", None)
    return getattr(profile, "assigned_department", None)


def _explicit_permission(user, codename):
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    app_label, code = codename.split(".", 1)
    return bool(
        user.user_permissions.filter(content_type__app_label=app_label, codename=code).exists()
        or user.groups.filter(permissions__content_type__app_label=app_label, permissions__codename=code).exists()
    )


def _in_department(user, department=None):
    assigned = department_for_user(user)
    return bool(assigned and (department is None or assigned == department))


def can_view_finance_setup(user, department=None):
    if not _in_department(user, department):
        return False
    return any(_explicit_permission(user, permission) for permission in (
        "finance.view_finance_setup", "finance.manage_finance_configuration",
        "finance.approve_finance_configuration", "finance.manage_finance_templates",
        "finance.manage_finance_providers",
    ))


def can_manage_finance_configuration(user, department=None):
    return _in_department(user, department) and _explicit_permission(user, "finance.manage_finance_configuration")


def can_approve_finance_configuration(user, department=None):
    return _in_department(user, department) and _explicit_permission(user, "finance.approve_finance_configuration")


def can_manage_finance_templates(user, department=None):
    return _in_department(user, department) and _explicit_permission(user, "finance.manage_finance_templates")


def finance_access_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_view_finance_setup(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def finance_permission_required(check):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
