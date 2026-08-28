from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def department_for_user(user):
    return getattr(getattr(user, "employeeprofile", None), "assigned_department", None)


def has_budget_permission(user, codename):
    department = department_for_user(user)
    if not department or not getattr(user, "is_active", False):
        return False
    return bool(
        user.user_permissions.filter(content_type__app_label="budget", codename=codename).exists()
        or user.groups.filter(permissions__content_type__app_label="budget", permissions__codename=codename).exists()
    )


def can_view(user):
    from vouchers.roles import is_finance_uat_viewer
    return bool(department_for_user(user)) and (
        is_finance_uat_viewer(user)
        or any(has_budget_permission(user, code) for code in (
            "view_budget_workspace", "prepare_budget_calls", "approve_budget_calls",
            "prepare_budget_proposals", "review_budget_proposals", "authorize_appropriations",
        ))
    )


def budget_access_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_view(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def budget_permission_required(codename):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not has_budget_permission(request.user, codename):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator

