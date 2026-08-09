from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db.models import Q

from departments.models import Department
from profiles.models import EmployeeProfile

User = get_user_model()


def can_access_users_directory(user):
    if not user or not user.is_authenticated:
        return False

    if user.is_staff or user.is_superuser:
        return True

    profile = getattr(user, 'employeeprofile', None)
    department = getattr(profile, 'assigned_department', None)
    return bool(department and department.slug == 'hr')


def get_department_list():
    return Department.objects.order_by('name')


def get_department_user_map(departments=None):
    if departments is None:
        departments = get_department_list()

    return {
        dept: EmployeeProfile.objects.filter(assigned_department=dept).select_related(
            'user', 'plantilla'
        ).order_by('user__last_name', 'user__first_name')
        for dept in departments
    }


def users_directory_context(request_user):
    if not can_access_users_directory(request_user):
        raise PermissionDenied("Access denied.")

    departments = get_department_list()
    department_users = get_department_user_map(departments)

    return {
        'users': User.objects.all().order_by('last_name', 'first_name'),
        'profiles': EmployeeProfile.objects.all().select_related('user', 'assigned_department', 'plantilla'),
        'userCount': User.objects.count(),
        'department_users': department_users,
    }


def search_users_by_query(search_query):
    search_query = (search_query or '').strip()
    if not search_query:
        return []

    results = User.objects.filter(
        Q(username__icontains=search_query)
        | Q(email__icontains=search_query)
        | Q(first_name__icontains=search_query)
        | Q(last_name__icontains=search_query)
    ).distinct()

    return [(account, False) for account in results]


def get_department_search_options():
    return Department.objects.values_list('slug', 'name').order_by('name')
