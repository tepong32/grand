from __future__ import annotations

from copy import deepcopy


FINANCE_UAT_VIEWER_GROUP = "Finance UAT Viewer"


FINANCE_ROLE_PERMISSIONS = {
    FINANCE_UAT_VIEWER_GROUP: (
        "finance.view_finance_setup",
        "vouchers.view_voucher_workbench",
        "vouchers.view_voucher_audit",
        "accounting.view_accounting_workspace",
        "accounting.view_general_ledger",
    ),
    "Budget Voucher Officer": (
        "vouchers.view_voucher_workbench",
        "vouchers.initiate_budget_case",
        "vouchers.certify_budget_obligation",
        "vouchers.return_voucher_case",
        "vouchers.view_voucher_audit",
    ),
    "Accounting DV Preparer": (
        "finance.view_finance_setup",
        "vouchers.view_voucher_workbench",
        "vouchers.prepare_disbursement_voucher",
        "vouchers.track_wet_signatures",
        "vouchers.link_tracepoint_custody",
        "vouchers.amend_nonfinancial_voucher",
        "vouchers.return_voucher_case",
        "vouchers.view_voucher_audit",
        "accounting.view_accounting_workspace",
        "accounting.prepare_journal_entries",
    ),
    "Accounting Reviewer": (
        "finance.view_finance_setup",
        "vouchers.view_voucher_workbench",
        "vouchers.validate_accounting_voucher",
        "vouchers.finalize_bank_advice",
        "vouchers.approve_control_overrides",
        "vouchers.return_voucher_case",
        "vouchers.view_voucher_audit",
        "accounting.view_accounting_workspace",
        "accounting.post_journal_entries",
        "accounting.view_general_ledger",
    ),
    "Treasury Disbursement Officer": (
        "vouchers.view_voucher_workbench",
        "vouchers.issue_payment_instruments",
        "vouchers.release_payment_instruments",
        "vouchers.manage_payment_exceptions",
        "vouchers.return_voucher_case",
        "vouchers.view_voucher_audit",
    ),
    "Finance Configuration Manager": (
        "finance.view_finance_setup",
        "finance.manage_finance_configuration",
        "finance.manage_finance_templates",
        "finance.manage_finance_providers",
        "accounting.view_accounting_workspace",
        "accounting.manage_accounting_setup",
    ),
    "Finance Configuration Approver": (
        "finance.view_finance_setup",
        "finance.approve_finance_configuration",
        "accounting.view_accounting_workspace",
        "accounting.approve_fiscal_readiness",
    ),
}


ROLE_PROFILES = {
    "budget": {
        "eyebrow": "Budget Office",
        "title": "Budget voucher workspace",
        "description": "Open governed cases, certify OBR allocations, and follow vouchers already forwarded to Accounting.",
        "queue_title": "Budget cases ready for review",
        "empty_message": "No Budget voucher case is waiting for action.",
        "stages": ("budget_draft",),
        "icon": "fa-file-signature",
    },
    "accounting": {
        "eyebrow": "Accounting Office",
        "title": "Accounting disbursement workspace",
        "description": "Prepare and validate DVs, track wet signatures, post JEVs, and finalize bank advice from one shared case.",
        "queue_title": "Accounting cases ready for review",
        "empty_message": "No voucher case is waiting for Accounting action.",
        "stages": (
            "accounting_preparation", "awaiting_signatures", "accounting_validation",
            "accounting_posting", "accounting_bank_advice",
        ),
        "icon": "fa-balance-scale",
    },
    "treasury": {
        "eyebrow": "Treasury Office",
        "title": "Treasury disbursement workspace",
        "description": "Register or replace physical checks and release only checks covered by finalized bank advice.",
        "queue_title": "Treasury cases ready for review",
        "empty_message": "No voucher case is waiting for Treasury action.",
        "stages": ("treasury_check_preparation", "treasury_release"),
        "icon": "fa-money-check-alt",
    },
    "oversight": {
        "eyebrow": "Finance oversight",
        "title": "Voucher and disbursement overview",
        "description": "Review the shared Budget–Accounting–Treasury route without receiving transaction authority.",
        "queue_title": "Open finance cases",
        "empty_message": "No finance case is currently open.",
        "stages": (
            "budget_draft", "accounting_preparation", "awaiting_signatures", "accounting_validation",
            "accounting_posting", "treasury_check_preparation", "accounting_bank_advice", "treasury_release",
        ),
        "icon": "fa-route",
    },
}


STAGE_NEXT_ACTION = {
    "budget_draft": "Certify OBR allocation",
    "accounting_preparation": "Prepare the disbursement voucher",
    "awaiting_signatures": "Record returned wet signatures",
    "accounting_validation": "Validate the voucher and request a JEV",
    "accounting_posting": "Create, submit, and independently post the GRAND JEV",
    "treasury_check_preparation": "Register or replace checks",
    "accounting_bank_advice": "Finalize bank advice",
    "treasury_release": "Release advised checks",
    "completed": "Completed",
    "cancelled": "Cancelled",
}


def is_finance_uat_viewer(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and user.groups.filter(name=FINANCE_UAT_VIEWER_GROUP).exists()
    )


def department_workspace_role(user) -> str:
    profile = getattr(user, "employeeprofile", None)
    department = getattr(profile, "assigned_department", None)
    if not department:
        return "oversight"
    identity = f"{department.slug or ''} {department.name or ''}".lower()
    if "budget" in identity:
        return "budget"
    if "account" in identity or "acctg" in identity:
        return "accounting"
    if "treasur" in identity:
        return "treasury"
    return "oversight"


def finance_workspace_profile(user, requested_role: str | None = None) -> dict:
    actual_role = department_workspace_role(user)
    viewer = is_finance_uat_viewer(user)
    selected_role = requested_role if viewer and requested_role in ROLE_PROFILES else actual_role
    result = deepcopy(ROLE_PROFILES[selected_role])
    result.update({
        "role": selected_role,
        "actual_role": actual_role,
        "is_uat_viewer": viewer,
        "is_preview": viewer and selected_role != actual_role,
        "preview_roles": tuple(ROLE_PROFILES),
    })
    return result

