from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


ACCOUNTING_PERMISSIONS = (
    "accounting.view_accounting_workspace",
    "accounting.manage_accounting_setup",
    "accounting.approve_fiscal_readiness",
    "accounting.prepare_opening_balances",
    "accounting.approve_opening_balances",
    "accounting.post_opening_balances",
    "accounting.prepare_journal_entries",
    "accounting.post_journal_entries",
    "accounting.view_general_ledger",
    "accounting.reconcile_control_accounts",
    "accounting.view_bank_reconciliation",
    "accounting.prepare_bank_reconciliation",
    "accounting.approve_bank_reconciliation",
    "accounting.export_bank_reconciliation",
)


def department_for_user(user):
    profile = getattr(user, "employeeprofile", None)
    return getattr(profile, "assigned_department", None)


def has_explicit_permission(user, permission):
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    if department_for_user(user) is None:
        return False
    app_label, codename = permission.split(".", 1)
    return bool(
        user.user_permissions.filter(content_type__app_label=app_label, codename=codename).exists()
        or user.groups.filter(permissions__content_type__app_label=app_label, permissions__codename=codename).exists()
    )


def can_view_accounting(user):
    from vouchers.roles import is_finance_uat_viewer

    viewer = is_finance_uat_viewer(user) and department_for_user(user) is not None
    return viewer or any(
        has_explicit_permission(user, permission) for permission in ACCOUNTING_PERMISSIONS
    )


def can_manage_setup(user):
    return has_explicit_permission(user, "accounting.manage_accounting_setup")


def can_approve_fiscal_readiness(user):
    return has_explicit_permission(user, "accounting.approve_fiscal_readiness")


def can_govern_setup(user):
    return can_manage_setup(user) or can_approve_fiscal_readiness(user)


def can_prepare_opening_balances(user):
    return has_explicit_permission(user, "accounting.prepare_opening_balances")


def can_approve_opening_balances(user):
    return has_explicit_permission(user, "accounting.approve_opening_balances")


def can_post_opening_balances(user):
    return has_explicit_permission(user, "accounting.post_opening_balances")


def can_prepare_journals(user):
    return has_explicit_permission(user, "accounting.prepare_journal_entries")


def can_post_journals(user):
    return has_explicit_permission(user, "accounting.post_journal_entries")


def can_view_ledger(user):
    return has_explicit_permission(user, "accounting.view_general_ledger")


def can_reconcile_controls(user):
    return has_explicit_permission(user, "accounting.reconcile_control_accounts")


def can_view_bank_reconciliation(user):
    return has_explicit_permission(user, "accounting.view_bank_reconciliation")


def can_prepare_bank_reconciliation(user):
    return has_explicit_permission(user, "accounting.prepare_bank_reconciliation")


def can_approve_bank_reconciliation(user):
    return has_explicit_permission(user, "accounting.approve_bank_reconciliation")


def can_export_bank_reconciliation(user):
    return has_explicit_permission(user, "accounting.export_bank_reconciliation")


def accounting_access_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_view_accounting(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def accounting_permission_required(check):
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
