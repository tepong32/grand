from __future__ import annotations


def finance_operations_access(user, known_access=None):
    """Return existing Finance-area access without widening any domain boundary."""
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return {
            "budget": False, "vouchers": False, "accounting": False,
            "setup": False, "discovery": False, "field": False,
            "reporting": False, "allowed": False,
        }

    from accounting.access import can_view_accounting
    from budget.access import can_view as can_view_budget
    from reporting.access import can_view_reporting
    from vouchers.access import can_view_workbench

    from .access import (
        can_view_finance_discovery_workspace, can_view_finance_setup,
        can_view_shadow_workspace,
    )

    known_access = known_access or {}
    access = {
        "budget": known_access["budget"] if "budget" in known_access else can_view_budget(user),
        "vouchers": known_access["vouchers"] if "vouchers" in known_access else can_view_workbench(user),
        "accounting": known_access["accounting"] if "accounting" in known_access else can_view_accounting(user),
        "setup": known_access["setup"] if "setup" in known_access else can_view_finance_setup(user),
        "discovery": can_view_finance_discovery_workspace(user),
        "field": can_view_shadow_workspace(user),
        "reporting": known_access["reporting"] if "reporting" in known_access else can_view_reporting(user),
    }
    # Reporting is shared by non-Finance departments, so reporting permission
    # alone does not turn this into a Finance user. It appears as a destination
    # only after at least one Finance-domain access path is already present.
    access["allowed"] = any(access[key] for key in (
        "budget", "vouchers", "accounting", "setup", "discovery", "field",
    ))
    return access


def finance_operations_areas(user):
    access = finance_operations_access(user)
    if not access["allowed"]:
        return access, [], []

    work = []
    controls = []
    if access["budget"]:
        work.append({
            "title": "Budget and obligation control",
            "description": "Prepare or review annual budget authority, allotments, and the shared obligation registry.",
            "next_action": "Open the role-shaped Budget register and use its next-action filters.",
            "boundary": "Budget approval, appropriation authority, allotment, and obligation certification remain separate decisions.",
            "url_name": "budget:obligation_workspace", "action_label": "Open Budget", "icon": "fa-chart-pie",
        })
    if access["vouchers"]:
        from vouchers.roles import finance_workspace_profile

        profile = finance_workspace_profile(user)
        work.append({
            "title": profile["title"], "description": profile["description"],
            "next_action": "Continue the next case assigned to your role; the same case remains shared across offices.",
            "boundary": "A workflow task never implies budget, Accounting, signature, payment, or bank authority by itself.",
            "url_name": "vouchers:workspace", "action_label": "Open Finance queue", "icon": profile["icon"],
        })
    if access["accounting"]:
        work.append({
            "title": "Accounting and general ledger",
            "description": "Prepare and independently post balanced JEVs, reconcile controls, and close periods through governed routes.",
            "next_action": "Use the Accounting next-action filters; correct posted evidence only by reversal or another governed successor.",
            "boundary": "A balanced or posted JEV does not certify a statement, form, payment, or cutover.",
            "url_name": "accounting:workspace", "action_label": "Open Accounting", "icon": "fa-book",
        })
    if access["reporting"]:
        work.append({
            "title": "Reports and official outputs",
            "description": "Generate reproducible schedules, statements, and packages from approved sources and controlled templates.",
            "next_action": "Use the report-run next-action filters, then open the retained run and its detailed controls.",
            "boundary": "A generated output or register is not official until its separate review and local acceptance gates pass.",
            "url_name": "reporting:workspace", "action_label": "Open Reports", "icon": "fa-file-alt",
        })

    if access["discovery"]:
        controls.append({
            "title": "Decisions and evidence",
            "description": "Keep local process, form, authority, and exception questions scoped and independently reviewed.",
            "next_action": "Resolve only what retained evidence proves; leave unsupported scope visibly blocked.",
            "boundary": "Public COA, DBM, BIR, bank, or local references do not prove local applicability on their own.",
            "url_name": "finance:discovery_workspace", "action_label": "Open Decisions", "icon": "fa-book-open",
        })
    if access["setup"]:
        controls.append({
            "title": "Finance Setup Center",
            "description": "Govern master data, transaction rules, signatories, numbering, and editable workbook versions.",
            "next_action": "Prepare a versioned draft, obtain independent Accounting review, and activate only a ready release.",
            "boundary": "Configuration activation does not issue a voucher or make GRAND authoritative for production.",
            "url_name": "finance:workspace", "action_label": "Open Finance Setup", "icon": "fa-sliders-h",
        })
    if access["field"]:
        controls.append({
            "title": "Field acceptance and cutover",
            "description": "Coordinate source locks, exercises, field cycles, office decisions, recovery, and explicit cutover evidence.",
            "next_action": "Filter the visible cycle register, then use the ten-checkpoint board for the selected cycle.",
            "boundary": "Only a separate authorized cutover decision applies, and only to its exact recorded scope and date.",
            "url_name": "finance:shadow_workspace", "action_label": "Open Field operations", "icon": "fa-clipboard-check",
        })
    return access, work, controls
