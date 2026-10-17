"""GSO scope and action checks; dashboard visibility is never authorization."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


GSO_NAMES = {"gso", "general services", "general services office"}
GSO_SLUGS = {"gso", "general-services", "general-services-office"}


def department_for_user(user):
    """Support Grand's EmployeeProfile and the prototype's local User model."""
    if hasattr(user, "employeeprofile"):
        return getattr(user.employeeprofile, "assigned_department", None)
    return getattr(user, "department", None)


def department_model():
    from django.apps import apps

    for label in ("departments.Department", "user.Department"):
        try:
            return apps.get_model(label)
        except LookupError:
            continue
    return None


def _is_gso_department(department):
    if not department:
        return False
    slug = (getattr(department, "slug", "") or "").strip().lower()
    name = (getattr(department, "name", "") or "").strip().lower()
    return slug in GSO_SLUGS or name in GSO_NAMES


def gso_department_for_user(user):
    department = department_for_user(user)
    if _is_gso_department(department):
        return department
    if getattr(user, "is_superuser", False):
        # Grand and this concept repo use different app labels for Department.
        from django.apps import apps

        for label in ("departments.Department", "user.Department"):
            try:
                model = apps.get_model(label)
            except LookupError:
                continue
            fields = {field.name for field in model._meta.get_fields()}
            if "slug" in fields:
                found = model.objects.filter(slug__iexact="gso").first()
                if found:
                    return found
            if "name" in fields:
                found = model.objects.filter(name__iexact="General Services").first()
                if found:
                    return found
    return None


def in_gso_scope(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and (getattr(user, "is_superuser", False) or gso_department_for_user(user))
    )


def has_inventory_permission(user, codename, *, mutation=False):
    """Use GRAND's explicit grants; its UAT role never authorizes writes."""
    from django.apps import apps
    permission = f"inventory.{codename}"
    if apps.is_installed("vouchers"):
        from vouchers.access import has_explicit_permission
        from vouchers.roles import is_finance_uat_viewer
        return bool(not (mutation and is_finance_uat_viewer(user))
                    and has_explicit_permission(user, permission))
    return bool(user.has_perm(permission))


def can(user, action):
    if action not in ("view", "add", "change", "delete", "export"):
        return False
    codename = "export_asset_register" if action == "export" else f"{action}_asset"
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    department = department_for_user(user)
    if action != "view" and not (getattr(user, "is_superuser", False) or _is_gso_department(department)):
        return False
    valid_department = bool(
        department and (getattr(department, "name", "") or "").strip() != "---select one---"
    )
    if action == "view" and not (getattr(user, "is_superuser", False) or valid_department):
        return False
    return has_inventory_permission(user, codename, mutation=action not in ("view", "export"))


def can_view_audit(user):
    return bool(in_gso_scope(user) and has_inventory_permission(user, "view_asset_audit"))


def can_transfer_asset(user, *, read_only=False):
    return bool(in_gso_scope(user) and has_inventory_permission(user, "transfer_asset", mutation=not read_only))


def can_acknowledge_asset_transfer(user, transfer=None, *, read_only=False):
    if transfer is not None and transfer.kind == transfer.RETURN:
        return False
    if not can(user, "view") or not has_inventory_permission(user, "acknowledge_asset_transfer", mutation=not read_only):
        return False
    department = department_for_user(user)
    if transfer is not None and transfer.destination_custodian_user_id:
        if transfer.destination_custodian_user_id != user.pk or transfer.requested_by_id == user.pk:
            return False
        from django.apps import apps
        if not apps.is_installed("vouchers"):
            return False
        from vouchers.access import has_explicit_permission
        from vouchers.roles import is_finance_uat_viewer
        if is_finance_uat_viewer(user) or not has_explicit_permission(user, "inventory.acknowledge_asset_transfer"):
            return False
    return bool(department and (transfer is None or transfer.destination_department_id == department.pk))


def can_request_asset_disposal(user, asset=None, *, read_only=False):
    return bool(
        can(user, "view")
        and (has_inventory_permission(user, "request_asset_disposal", mutation=not read_only)
             or can_review_asset_disposal(user, read_only=read_only))
        and (asset is None or asset_in_scope(user, asset))
    )


def can_review_asset_disposal(user, *, read_only=False):
    return bool(in_gso_scope(user) and has_inventory_permission(user, "review_asset_disposal", mutation=not read_only))


def can_manage_asset_verification(user, action="view", *, read_only=False):
    permission = {
        "start": "start_asset_verification",
        "record": "record_asset_verification",
        "close": "close_asset_verification",
        "import": "import_asset_accounting_snapshot",
    }.get(action)
    return bool(permission and in_gso_scope(user) and has_inventory_permission(user, permission, mutation=not read_only))


def can_stock(user, action):
    """GSO controls stock; department users may see only their own issue history."""
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    department = department_for_user(user)
    gso = getattr(user, "is_superuser", False) or _is_gso_department(department)
    permission = {
        "view": "view_consumableitem",
        "add": "add_consumableitem",
        "change": "change_consumableitem",
        "receive": "receive_stock",
        "issue": "issue_stock",
        "adjust": "adjust_stock",
        "export": "export_stock_register",
    }.get(action)
    if not permission:
        return False
    from django.apps import apps
    if apps.is_installed("vouchers"):
        from vouchers.access import has_explicit_permission
        from vouchers.roles import is_finance_uat_viewer
        if action not in ("view", "export") and is_finance_uat_viewer(user):
            return False
        if not has_explicit_permission(user, f"inventory.{permission}"):
            return False
    if action == "view" and department and not gso:
        return bool(user.has_perm(f"inventory.{permission}"))
    return bool(gso and user.has_perm(f"inventory.{permission}"))


def asset_in_scope(user, asset):
    if getattr(user, "is_superuser", False):
        return True
    department = gso_department_for_user(user)
    if department:
        return asset.department_id == department.pk
    assigned = department_for_user(user)
    return bool(assigned and asset.assigned_department_id == assigned.pk)


def asset_access_required(permission):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not can(request.user, permission):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapped
    return decorate
