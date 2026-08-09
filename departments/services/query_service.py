from __future__ import annotations

from typing import Optional

from ..models import Department


def get_department_by_slug(slug: str) -> Optional[Department]:
    """
    Return a department by slug, normalized to a lowercase match.

    Args:
        slug: Potential slug input from URL, code or stored value.
    """
    if not slug:
        return None
    return Department.objects.filter(slug__iexact=slug.strip()).first()


def get_department_for_user(user) -> Optional[Department]:
    """
    Return the department assigned to a user's employee profile if present.
    """
    profile = getattr(user, "employeeprofile", None)
    if not profile:
        return None
    return getattr(profile, "assigned_department", None)


def get_dashboard_template(department: Optional[Department], fallback: str) -> str:
    """
    Resolve dashboard template path for a department with a safe fallback.
    """
    template = getattr(department, "dashboard_template", None) if department else None
    template = (template or "").strip()
    return template if template else fallback
