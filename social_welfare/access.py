from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from departments.models import Department


def employee_department(user):
    profile = getattr(user, "employeeprofile", None)
    return getattr(profile, "assigned_department", None)


def is_mswd_employee(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    department = employee_department(user)
    return bool(department and (department.slug or "").strip().lower() == "mswd")


def mswd_department_for_user(user):
    department = employee_department(user)
    if department and (department.slug or "").strip().lower() == "mswd":
        return department
    if getattr(user, "is_superuser", False):
        return Department.objects.filter(slug__iexact="mswd").first()
    return None


def can_manage_social_welfare(user):
    if not is_mswd_employee(user):
        return False
    if user.is_superuser or user.has_perm("social_welfare.manage_social_welfare_programs"):
        return True
    department = employee_department(user)
    return bool(department and department.deptHead_or_oic_id == user.pk)


def mswd_programs_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_mswd_employee(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


def social_welfare_manager_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_manage_social_welfare(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
