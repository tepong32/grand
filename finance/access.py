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
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user):
        return _in_department(user, department)
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


def can_manage_shadow_operation(user, department=None):
    return _in_department(user, department) and _explicit_permission(user, "finance.manage_shadow_operation")


def can_review_shadow_reconciliation(user, department=None):
    return _in_department(user, department) and _explicit_permission(user, "finance.review_shadow_reconciliation")


def can_authorize_finance_cutover(user, department=None):
    return _in_department(user, department) and _explicit_permission(user, "finance.authorize_finance_cutover")


def can_view_shadow_cycle(user, cycle):
    from vouchers.roles import is_finance_uat_viewer

    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if cycle.stakeholder_acceptances.filter(assigned_reviewer=user).exists():
        return True
    if cycle.defects.filter(owner=user).exists():
        return True
    if cycle.cutover_readiness_exercises.filter(owner=user).exists():
        return True
    if cycle.cutover_readiness_exercises.filter(witness=user).exists():
        return True
    if not _in_department(user, cycle.department):
        return False
    return bool(
        is_finance_uat_viewer(user)
        or can_view_finance_setup(user, cycle.department)
        or can_manage_shadow_operation(user, cycle.department)
        or can_review_shadow_reconciliation(user, cycle.department)
        or can_authorize_finance_cutover(user, cycle.department)
    )


def can_view_shadow_workspace(user):
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if user.assigned_finance_shadow_acceptances.exists():
        return True
    if user.owned_finance_cutover_readiness_exercises.exists():
        return True
    if user.witnessed_finance_cutover_readiness_exercises.exists():
        return True
    department = department_for_user(user)
    return bool(department and any((
        can_view_finance_setup(user, department),
        can_manage_shadow_operation(user, department),
        can_review_shadow_reconciliation(user, department),
        can_authorize_finance_cutover(user, department),
    )))


def shadow_access_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_view_shadow_workspace(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


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
