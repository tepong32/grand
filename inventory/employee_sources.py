"""Minimal read-only GRAND employee identity for explicit custody selection.

Account activation is not employment or clearance status. Numeric identities are
local to the GRAND installation and require an explicit map during imports.
"""
import hashlib
import json

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .access import in_gso_scope


def resolve_employee_custodian(*, actor, user_id):
    require_employee_custody_manager(actor)
    return _employee_snapshot(actor, user_id)


def require_employee_custody_manager(actor):
    _require_grand()
    from vouchers.access import has_explicit_permission
    from vouchers.roles import is_finance_uat_viewer
    if (not in_gso_scope(actor) or is_finance_uat_viewer(actor)
            or not has_explicit_permission(actor, "inventory.transfer_asset")):
        raise PermissionDenied


def can_manage_employee_custody(actor):
    try:
        require_employee_custody_manager(actor)
    except (PermissionDenied, ValidationError):
        return False
    return True


def resolve_own_custodian(*, actor):
    """Recipients may revalidate only their own identity for acknowledgment."""
    _require_grand()
    from users.access import is_employee
    from vouchers.access import has_explicit_permission
    from vouchers.roles import is_finance_uat_viewer
    if (not is_employee(actor) or is_finance_uat_viewer(actor)
            or not has_explicit_permission(actor, "inventory.acknowledge_asset_transfer")):
        raise PermissionDenied
    return _employee_snapshot(actor, actor.pk)


def _require_grand():
    if not all(apps.is_installed(label) for label in ("profiles", "departments", "vouchers")):
        raise ValidationError("Employee custody lookup is available only after GRAND integration.")


def _employee_snapshot(actor, user_id):
    from profiles.models import EmployeeProfile
    from profiles.services.profile_service import can_view_profile
    from departments.models import Department
    try:
        if isinstance(user_id, bool) or str(int(user_id)) != str(user_id) or not 0 < int(user_id) <= 9223372036854775807:
            raise ValueError
        user_id = int(user_id)
    except (TypeError, ValueError, OverflowError):
        raise ValidationError("Select a valid employee account.")

    with transaction.atomic(using="default"):
        # A later custody write must call this inside its own outer transaction
        # and compare the reviewed fingerprint before persisting the relationship.
        target = get_user_model().objects.using("default").select_for_update().only(
            "pk", "username", "first_name", "middle_name", "last_name", "ext_name", "is_active").filter(pk=user_id).first()
        if target is None or not target.is_active:
            raise PermissionDenied
        profile = EmployeeProfile.objects.using("default").select_for_update().only(
            "pk", "user_id", "assigned_department_id").filter(user=target).first()
        if profile is None:
            raise PermissionDenied
        target.employeeprofile = profile
        if not can_view_profile(actor, target):
            raise PermissionDenied
        department = Department.objects.using("default").select_for_update().only(
            "pk", "name").filter(pk=profile.assigned_department_id).first()
        if department is None or not department.name.strip() or department.name.strip() == "---select one---":
            raise ValidationError("The employee needs an assigned department before new custody can be recorded.")
        payload = {
            "schema": "gso-grand-employee-custodian-v1",
            "user_local_id": target.pk,
            "employee_profile_local_id": profile.pk,
            "username": target.username,
            "display_name": target.get_full_name(),
            "department_local_id": department.pk,
            "department_label": department.name,
            "account_active": target.is_active,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        return {"source": payload, "sha256": hashlib.sha256(encoded).hexdigest()}
