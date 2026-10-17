"""Navigation to GRAND's existing registry; no duplicate filing authority."""
from django.apps import apps
from django.urls import NoReverseMatch, reverse

from .access import _is_gso_department, department_for_user


def workspace_url(actor):
    if not (getattr(actor, "is_authenticated", False) and getattr(actor, "is_active", False)):
        return None
    if not apps.is_installed("records") or not _is_gso_department(department_for_user(actor)):
        return None
    from records.access import can_view_records
    if not can_view_records(actor):
        return None
    try:
        return reverse("records:workspace")
    except NoReverseMatch:
        # An installed app without its routes is not an available workspace.
        return None
