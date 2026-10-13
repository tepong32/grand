"""Identity and HR authority shared by authentication and account screens."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class EmployeeRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_employee(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

def is_employee(user):
    return bool(user and user.is_authenticated and user.is_active and getattr(user, "employeeprofile", None))


def can_manage_employee_accounts(user):
    from .services.query_service import can_access_users_directory

    return bool(can_access_users_directory(user) and user.has_perm("users.add_user"))


def can_manage_employee_profiles(user):
    from .services.query_service import can_access_users_directory

    return bool(can_access_users_directory(user) and user.has_perm("profiles.change_employeeprofile"))
