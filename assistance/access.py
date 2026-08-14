from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from social_welfare.access import employee_department, is_mswd_employee


def _is_mswd_head(user):
    department = employee_department(user)
    return bool(department and department.deptHead_or_oic_id == user.pk)


def can_access_citizen_reviews(user):
    if not is_mswd_employee(user):
        return False
    return bool(
        user.is_superuser
        or _is_mswd_head(user)
        or user.has_perm("assistance.view_citizen_review_workspace")
    )


def can_review_citizen_profiles(user):
    if not is_mswd_employee(user):
        return False
    return bool(
        user.is_superuser
        or _is_mswd_head(user)
        or user.has_perm("assistance.review_citizen_profiles")
    )


def can_view_citizen_pii(user):
    if not is_mswd_employee(user):
        return False
    return bool(
        user.is_superuser
        or _is_mswd_head(user)
        or user.has_perm("assistance.view_citizen_profile_pii")
    )


def citizen_review_access_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_access_citizen_reviews(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper
