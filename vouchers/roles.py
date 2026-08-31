from __future__ import annotations

from copy import deepcopy


FINANCE_UAT_VIEWER_GROUP = "Finance UAT Viewer"


FINANCE_ROLE_PERMISSIONS = {
    FINANCE_UAT_VIEWER_GROUP: (
        "finance.view_finance_setup",
        "vouchers.view_voucher_workbench",
        "vouchers.view_voucher_audit",
        "vouchers.view_remittance_workbench",
        "vouchers.view_remittance_audit",
        "vouchers.view_cash_position",
        "vouchers.view_bank_advice",
        "accounting.view_accounting_workspace",
        "accounting.view_general_ledger",
        "accounting.view_bank_reconciliation",
        "budget.view_budget_workspace",
        "budget.view_allotment_control",
        "budget.view_obligation_registry",
        "reporting.view_reporting_workspace",
        "reporting.view_department_reports",
    ),
    "Budget Voucher Officer": (
        "budget.view_budget_workspace",
        "budget.prepare_budget_calls",
        "budget.prepare_budget_proposals",
        "budget.view_obligation_registry",
        "budget.certify_obligations",
        "vouchers.view_voucher_workbench",
        "vouchers.initiate_budget_case",
        "vouchers.initiate_payable_case",
        "vouchers.certify_budget_obligation",
        "vouchers.return_voucher_case",
        "vouchers.view_voucher_audit",
        "reporting.view_reporting_workspace",
        "reporting.generate_reports",
        "reporting.download_reports",
    ),
    "Budget Review and Consolidation Officer": (
        "budget.view_budget_workspace",
        "budget.approve_budget_calls",
        "budget.review_budget_proposals",
        "budget.view_budget_audit",
        "budget.view_allotment_control",
        "budget.prepare_allotment_releases",
        "budget.view_obligation_registry",
        "reporting.view_reporting_workspace",
        "reporting.manage_report_definitions",
        "reporting.manage_report_templates",
        "reporting.prepare_template_promotions",
        "reporting.activate_template_promotions",
        "reporting.schedule_reports",
        "reporting.generate_reports",
        "reporting.review_reports",
        "reporting.download_reports",
        "reporting.view_department_reports",
    ),
    "Budget Appropriation Authorizer": (
        "budget.view_budget_workspace",
        "budget.authorize_appropriations",
        "budget.view_budget_audit",
        "budget.view_allotment_control",
        "budget.approve_allotment_releases",
        "budget.view_obligation_registry",
        "reporting.view_reporting_workspace",
        "reporting.approve_reports",
        "reporting.approve_template_promotions",
        "reporting.download_reports",
        "reporting.view_department_reports",
    ),
    "Requesting Office Obligation Preparer": (
        "budget.view_budget_workspace",
        "budget.initiate_obligation_requests",
        "vouchers.view_voucher_workbench",
        "vouchers.initiate_payable_case",
        "vouchers.view_voucher_audit",
    ),
    "Accounting DV Preparer": (
        "finance.view_finance_setup",
        "vouchers.view_voucher_workbench",
        "vouchers.review_payable_intake",
        "vouchers.prepare_disbursement_voucher",
        "vouchers.control_dv_printing",
        "vouchers.track_wet_signatures",
        "vouchers.link_tracepoint_custody",
        "vouchers.amend_nonfinancial_voucher",
        "vouchers.return_voucher_case",
        "vouchers.view_voucher_audit",
        "vouchers.view_remittance_workbench",
        "vouchers.view_bank_advice",
        "vouchers.prepare_bank_advice",
        "vouchers.submit_bank_advice",
        "vouchers.export_bank_advice",
        "accounting.view_accounting_workspace",
        "accounting.prepare_journal_entries",
        "accounting.prepare_opening_balances",
        "accounting.view_bank_reconciliation",
        "accounting.prepare_bank_reconciliation",
        "accounting.export_bank_reconciliation",
        "accounting.prepare_period_close",
        "accounting.export_period_close",
        "tracepoint.view_tracepoint_workspace",
        "tracepoint.prepare_tracked_packets",
        "tracepoint.print_packet_labels",
        "reporting.view_reporting_workspace",
        "reporting.generate_reports",
        "reporting.download_reports",
        "reporting.prepare_statement_notes",
        "reporting.prepare_reference_comparisons",
        "reporting.export_statement_packages",
        "reporting.prepare_accountability_packages",
        "reporting.export_accountability_packages",
    ),
    "Accounting Reviewer": (
        "finance.view_finance_setup",
        "vouchers.view_voucher_workbench",
        "vouchers.validate_accounting_voucher",
        "vouchers.finalize_bank_advice",
        "vouchers.view_bank_advice",
        "vouchers.approve_bank_advice",
        "vouchers.acknowledge_bank_advice",
        "vouchers.review_returned_instruments",
        "vouchers.export_bank_advice",
        "vouchers.approve_control_overrides",
        "vouchers.return_voucher_case",
        "vouchers.view_voucher_audit",
        "vouchers.view_remittance_workbench",
        "vouchers.approve_remittances",
        "vouchers.view_remittance_audit",
        "vouchers.view_cash_position",
        "vouchers.approve_cash_position",
        "vouchers.export_cash_position",
        "accounting.view_accounting_workspace",
        "accounting.post_journal_entries",
        "accounting.post_opening_balances",
        "accounting.view_general_ledger",
        "accounting.reconcile_control_accounts",
        "accounting.view_bank_reconciliation",
        "accounting.approve_bank_reconciliation",
        "accounting.export_bank_reconciliation",
        "accounting.approve_period_close",
        "accounting.reopen_period",
        "accounting.export_period_close",
        "reporting.view_reporting_workspace",
        "reporting.review_reports",
        "reporting.approve_reports",
        "reporting.download_reports",
        "reporting.view_department_reports",
        "reporting.review_statement_notes",
        "reporting.review_reference_comparisons",
        "reporting.export_statement_packages",
        "reporting.review_accountability_packages",
        "reporting.export_accountability_packages",
    ),
    "Treasury Disbursement Officer": (
        "vouchers.view_voucher_workbench",
        "vouchers.issue_payment_instruments",
        "vouchers.release_payment_instruments",
        "vouchers.manage_payment_exceptions",
        "vouchers.view_bank_advice",
        "vouchers.submit_bank_advice",
        "vouchers.export_bank_advice",
        "vouchers.return_voucher_case",
        "vouchers.view_voucher_audit",
        "vouchers.view_remittance_workbench",
        "vouchers.prepare_remittances",
        "vouchers.release_remittances",
        "vouchers.view_remittance_audit",
        "vouchers.view_cash_position",
        "vouchers.prepare_cash_position",
        "vouchers.export_cash_position",
        "reporting.view_reporting_workspace",
        "reporting.generate_reports",
        "reporting.download_reports",
    ),
    "Finance Configuration Manager": (
        "finance.view_finance_setup",
        "finance.manage_finance_configuration",
        "finance.manage_finance_templates",
        "finance.manage_finance_providers",
        "finance.manage_shadow_operation",
        "accounting.view_accounting_workspace",
        "accounting.manage_accounting_setup",
        "accounting.prepare_opening_balances",
        "accounting.manage_period_close_policies",
        "reporting.view_reporting_workspace",
        "reporting.manage_report_definitions",
        "reporting.manage_report_templates",
        "reporting.prepare_template_promotions",
        "reporting.activate_template_promotions",
        "reporting.schedule_reports",
        "reporting.generate_reports",
        "reporting.download_reports",
        "reporting.prepare_reference_comparisons",
        "reporting.export_statement_packages",
        "reporting.manage_accountability_package_profiles",
    ),
    "Finance Configuration Approver": (
        "finance.view_finance_setup",
        "finance.approve_finance_configuration",
        "finance.review_shadow_reconciliation",
        "finance.authorize_finance_cutover",
        "accounting.view_accounting_workspace",
        "accounting.approve_fiscal_readiness",
        "accounting.approve_opening_balances",
        "accounting.approve_period_close_policies",
        "reporting.view_reporting_workspace",
        "reporting.review_reports",
        "reporting.approve_reports",
        "reporting.approve_template_promotions",
        "reporting.download_reports",
        "reporting.view_department_reports",
        "reporting.review_reference_comparisons",
        "reporting.export_statement_packages",
        "reporting.approve_accountability_package_profiles",
    ),
}


ROLE_PROFILES = {
    "requesting": {
        "eyebrow": "Requesting Office",
        "title": "Payable preparation workspace",
        "description": "Complete transaction-specific evidence against the certified obligation before Accounting review.",
        "queue_title": "Payables ready for your office",
        "empty_message": "No payable intake is waiting for this requesting office.",
        "stages": ("payable_preparation",),
        "icon": "fa-file-invoice-dollar",
    },
    "budget": {
        "eyebrow": "Budget Office",
        "title": "Budget voucher workspace",
        "description": "Review authoritative obligation lineage carried into shared payable and voucher cases.",
        "queue_title": "Budget cases ready for review",
        "empty_message": "No Budget voucher case is waiting for action.",
        "stages": ("budget_draft",),
        "icon": "fa-file-signature",
    },
    "accounting": {
        "eyebrow": "Accounting Office",
        "title": "Accounting disbursement workspace",
        "description": "Prepare and validate DVs, track wet signatures, post JEVs, and govern bank-advice and returned-item evidence from one shared case.",
        "queue_title": "Accounting cases ready for review",
        "empty_message": "No voucher case is waiting for Accounting action.",
        "stages": (
            "payable_review", "accounting_preparation", "awaiting_signatures", "accounting_validation",
            "accounting_posting", "accounting_event_posting", "accounting_bank_advice", "accounting_returned_item",
        ),
        "icon": "fa-balance-scale",
    },
    "treasury": {
        "eyebrow": "Treasury Office",
        "title": "Treasury disbursement workspace",
        "description": "Maintain reviewed cash positions, register or replace physical checks, monitor ageing, submit approved advice, and release only bank-acknowledged instruments.",
        "queue_title": "Treasury cases ready for review",
        "empty_message": "No voucher case is waiting for Treasury action.",
        "stages": ("treasury_check_preparation", "treasury_release", "accounting_returned_item"),
        "icon": "fa-money-check-alt",
    },
    "oversight": {
        "eyebrow": "Finance oversight",
        "title": "Voucher and disbursement overview",
        "description": "Review the shared Budget–Accounting–Treasury route without receiving transaction authority.",
        "queue_title": "Open finance cases",
        "empty_message": "No finance case is currently open.",
        "stages": (
            "budget_draft", "payable_preparation", "payable_review", "accounting_preparation", "awaiting_signatures", "accounting_validation",
            "accounting_posting", "accounting_event_posting", "accounting_returned_item", "treasury_check_preparation", "accounting_bank_advice", "treasury_release",
        ),
        "icon": "fa-route",
    },
}


STAGE_NEXT_ACTION = {
    "budget_draft": "Complete shadow OBR compatibility step",
    "payable_preparation": "Complete the transaction-specific payable checklist",
    "payable_review": "Review payable readiness or return specific corrections",
    "accounting_preparation": "Prepare the disbursement voucher",
    "awaiting_signatures": "Prepare the controlled signing copy, link its packet, and record returned wet signatures",
    "accounting_validation": "Validate the voucher and request a JEV",
    "accounting_posting": "Create, submit, and independently post the GRAND JEV",
    "accounting_event_posting": "Post the governed payment-event JEV, then resume the recorded Treasury step",
    "accounting_returned_item": "Review bank-return evidence and record the governed Accounting treatment",
    "treasury_check_preparation": "Confirm cash position, then register or replace checks",
    "accounting_bank_advice": "Prepare, review, submit, and record bank response to the advice",
    "treasury_release": "Release bank-acknowledged checks",
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
    if user.user_permissions.filter(content_type__app_label="vouchers", codename="initiate_payable_case").exists() or user.groups.filter(
        permissions__content_type__app_label="vouchers", permissions__codename="initiate_payable_case",
    ).exists():
        return "requesting"
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

