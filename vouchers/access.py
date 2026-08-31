from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .roles import is_finance_uat_viewer


ACTION_PERMISSIONS = (
    "vouchers.initiate_budget_case",
    "vouchers.initiate_payable_case",
    "vouchers.review_payable_intake",
    "vouchers.certify_budget_obligation",
    "vouchers.prepare_disbursement_voucher",
    "vouchers.track_wet_signatures",
    "vouchers.link_tracepoint_custody",
    "vouchers.validate_accounting_voucher",
    "vouchers.issue_payment_instruments",
    "vouchers.finalize_bank_advice",
    "vouchers.view_bank_advice",
    "vouchers.prepare_bank_advice",
    "vouchers.approve_bank_advice",
    "vouchers.submit_bank_advice",
    "vouchers.acknowledge_bank_advice",
    "vouchers.review_returned_instruments",
    "vouchers.export_bank_advice",
    "vouchers.release_payment_instruments",
    "vouchers.manage_payment_exceptions",
    "vouchers.return_voucher_case",
    "vouchers.amend_nonfinancial_voucher",
    "vouchers.approve_control_overrides",
    "vouchers.prepare_remittances",
    "vouchers.approve_remittances",
    "vouchers.release_remittances",
    "vouchers.prepare_cash_position",
    "vouchers.approve_cash_position",
    "vouchers.export_cash_position",
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


def can_view_workbench(user):
    viewer = is_finance_uat_viewer(user) and department_for_user(user) is not None
    return viewer or has_explicit_permission(user, "vouchers.view_voucher_workbench") or any(
        has_explicit_permission(user, permission) for permission in ACTION_PERMISSIONS
    )


def voucher_access_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_view_workbench(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
