from __future__ import annotations

from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


def _queue_url(name, **filters):
    query = urlencode({key: value for key, value in filters.items() if value})
    return f"{reverse(name)}?{query}" if query else reverse(name)


def _group(*, key, area, title, count, url, definition, scope):
    return {
        "key": key, "area": area, "title": title, "count": count, "url": url,
        "definition": definition, "scope": scope,
    }


def _setup_groups(user, department):
    from finance.setup_register import (
        setup_attention_choices_for_user, setup_attention_queryset,
    )

    keys = {
        "needs_preparation": "setup-release-preparation",
        "awaiting_review": "setup-release-review",
        "ready_to_schedule": "setup-release-scheduling",
        "ready_to_activate": "setup-release-activation",
    }
    groups = []
    for attention, _label in setup_attention_choices_for_user(user, department):
        queryset, selected_attention, spec = setup_attention_queryset(user, attention)
        groups.append(_group(
            key=keys[attention], area="Finance setup", title=spec["title"],
            count=queryset.count(),
            url=_queue_url("finance:workspace", attention=selected_attention),
            definition=spec["definition"], scope=department.name,
        ))
    return groups


def _discovery_groups(user, department):
    from finance.access import can_manage_finance_discovery
    from finance.discovery_register import (
        discovery_action_choices_for_user, discovery_action_queryset,
    )

    keys = {
        "needs_preparation": "discovery-preparation",
        "my_reviews": "discovery-review",
    }
    groups = []
    for attention, _label in discovery_action_choices_for_user(user):
        queryset, selected_attention, spec = discovery_action_queryset(user, attention)
        scope = (
            (
                f"Rows naming you as owner plus managed department: {department.name}"
                if can_manage_finance_discovery(user, department)
                else "Rows naming you as owner"
            )
            if attention == "needs_preparation"
            else "Rows naming you as independent reviewer"
        )
        groups.append(_group(
            key=keys[attention], area="Finance decisions", title=spec["title"],
            count=queryset.count(),
            url=_queue_url("finance:discovery_workspace", attention=selected_attention),
            definition=spec["definition"], scope=scope,
        ))
    return groups


def _field_operation_groups(user, department):
    from finance.shadow_register_exports import (
        shadow_action_choices_for_user, shadow_action_queryset, visible_shadow_cycles,
    )

    keys = {
        "needs_source": "field-source-lock",
        "ready_to_prepare": "field-cycle-preparation",
        "running": "field-cycle-execution",
        "for_review": "field-cycle-review",
        "my_defects": "field-defect-correction",
        "review_defects": "field-defect-review",
        "my_exercises": "field-exercise-completion",
        "witness_exercises": "field-exercise-witness",
        "my_acceptances": "field-stakeholder-decision",
        "authorize_cutover": "field-cutover-authority",
    }
    named_roles = {
        "my_defects": "Open defects naming you as correction owner",
        "my_exercises": "Readiness exercises naming you as owner",
        "witness_exercises": "Submitted exercises naming you as independent witness",
        "my_acceptances": "Pending exact-scope decisions naming you as stakeholder reviewer",
    }
    groups = []
    visible = visible_shadow_cycles(user)
    for attention, _label in shadow_action_choices_for_user(user, department):
        queryset, selected_attention, spec = shadow_action_queryset(
            user, attention, queryset=visible,
        )
        groups.append(_group(
            key=keys[attention], area="Field operation", title=spec["title"],
            count=queryset.count(),
            url=_queue_url("finance:shadow_workspace", attention=selected_attention),
            definition=spec["definition"],
            scope=named_roles.get(attention, f"Acting Finance office: {department.name}"),
        ))
    return groups


def _voucher_groups(user, department):
    from accounting.access import can_post_journals, can_prepare_journals
    from vouchers.access import has_explicit_permission
    from vouchers.case_exports import visible_cases_for_user
    from vouchers.models import VoucherCase
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user):
        return []
    stages = []
    for allowed, stage in (
        (has_explicit_permission(user, "vouchers.certify_budget_obligation"), VoucherCase.BUDGET_DRAFT),
        (has_explicit_permission(user, "vouchers.initiate_payable_case"), VoucherCase.PAYABLE_PREPARATION),
        (has_explicit_permission(user, "vouchers.review_payable_intake"), VoucherCase.PAYABLE_REVIEW),
        (has_explicit_permission(user, "vouchers.prepare_disbursement_voucher"), VoucherCase.ACCOUNTING_PREPARATION),
        (has_explicit_permission(user, "vouchers.track_wet_signatures"), VoucherCase.AWAITING_SIGNATURES),
        (has_explicit_permission(user, "vouchers.validate_accounting_voucher"), VoucherCase.ACCOUNTING_VALIDATION),
        (can_prepare_journals(user) or can_post_journals(user), VoucherCase.ACCOUNTING_POSTING),
        (can_prepare_journals(user) or can_post_journals(user), VoucherCase.ACCOUNTING_EVENT_POSTING),
        (has_explicit_permission(user, "vouchers.review_returned_instruments"), VoucherCase.ACCOUNTING_RETURNED_ITEM),
        (has_explicit_permission(user, "vouchers.issue_payment_instruments"), VoucherCase.TREASURY_CHECK_PREPARATION),
        (has_explicit_permission(user, "vouchers.prepare_bank_advice"), VoucherCase.ACCOUNTING_BANK_ADVICE),
        (has_explicit_permission(user, "vouchers.release_payment_instruments"), VoucherCase.TREASURY_RELEASE),
    ):
        if allowed:
            stages.append(stage)
    if not stages:
        return []
    count = visible_cases_for_user(user).filter(current_stage__in=stages).count()
    return [_group(
        key="voucher-ready", area="Voucher case", title="Shared cases ready for your role",
        count=count, url=_queue_url("vouchers:workspace", attention="ready_for_me"),
        definition="Cases whose current governed stage has an action permission held by this account.",
        scope=f"Current Voucher Workbench role and {department.name} visibility; UAT preview is excluded.",
    )]


def _budget_groups(user, department):
    from budget.access import has_budget_permission
    from budget.models import AllotmentReleaseOrder, BudgetVersion, ObligationRequest

    groups = []
    can_view_obligation_registry = has_budget_permission(user, "view_obligation_registry")
    can_certify_obligations = has_budget_permission(user, "certify_obligations")
    can_initiate_obligations = has_budget_permission(user, "initiate_obligation_requests")
    if has_budget_permission(user, "prepare_budget_proposals"):
        count = BudgetVersion.objects.filter(
            department_id=department.pk, status__in=(BudgetVersion.DRAFT, BudgetVersion.RETURNED),
        ).count()
        groups.append(_group(
            key="budget-version-preparation", area="Budget", title="Budget versions to prepare or correct",
            count=count, url=_queue_url("budget:workspace", attention="needs_preparation"),
            definition="Draft or returned budget versions available to a proposal preparer.", scope=department.name,
        ))
    if has_budget_permission(user, "review_budget_proposals"):
        count = BudgetVersion.objects.filter(department_id=department.pk, status=BudgetVersion.FOR_REVIEW).count()
        groups.append(_group(
            key="budget-version-review", area="Budget", title="Budget versions for independent review",
            count=count, url=_queue_url("budget:workspace", attention="awaiting_proposal_review"),
            definition="Submitted budget versions awaiting a permitted independent review.", scope=department.name,
        ))
    if has_budget_permission(user, "prepare_allotment_releases"):
        count = AllotmentReleaseOrder.objects.filter(
            department_id=department.pk,
            status__in=(AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED),
        ).count()
        groups.append(_group(
            key="allotment-preparation", area="Budget", title="Allotment orders to prepare or correct",
            count=count, url=_queue_url("budget:allotment_workspace", attention="needs_preparation"),
            definition="Draft or returned allotment orders available to a preparer.", scope=department.name,
        ))
    if has_budget_permission(user, "approve_allotment_releases"):
        count = AllotmentReleaseOrder.objects.filter(
            department_id=department.pk, status=AllotmentReleaseOrder.FOR_REVIEW,
        ).count()
        groups.append(_group(
            key="allotment-review", area="Budget", title="Allotment orders for independent review",
            count=count, url=_queue_url("budget:allotment_workspace", attention="awaiting_review"),
            definition="Submitted allotment orders awaiting a permitted post-or-return decision.", scope=department.name,
        ))
    if can_initiate_obligations and not (can_view_obligation_registry or can_certify_obligations):
        count = ObligationRequest.objects.filter(
            requesting_department_id=department.pk,
            status__in=(ObligationRequest.DRAFT, ObligationRequest.RETURNED),
        ).count()
        groups.append(_group(
            key="obligation-preparation", area="Budget", title="Obligation requests to prepare or correct",
            count=count, url=_queue_url("budget:obligation_workspace", attention="needs_preparation"),
            definition="Own-office draft or returned obligation requests available to a requesting-office maker.",
            scope=department.name,
        ))
    if can_certify_obligations:
        obligation_scope = Q(department_id=department.pk)
        if can_initiate_obligations:
            obligation_scope |= Q(requesting_department_id=department.pk)
        count = ObligationRequest.objects.filter(
            obligation_scope, status=ObligationRequest.FOR_CERTIFICATION,
        ).count()
        groups.append(_group(
            key="obligation-certification", area="Budget", title="Obligations awaiting certification",
            count=count, url=_queue_url("budget:obligation_workspace", attention="awaiting_certification"),
            definition="Submitted obligation requests awaiting a permitted Budget certification or return.",
            scope=department.name,
        ))
    return groups


def _accounting_groups(user, department):
    from accounting.access import (
        can_approve_bank_reconciliation, can_approve_opening_balances,
        can_approve_period_close, can_post_journals, can_post_opening_balances,
        can_prepare_bank_reconciliation, can_prepare_journals, can_prepare_opening_balances,
        can_prepare_period_close, can_reopen_period,
    )
    from accounting.models import BankStatementBatch, JournalEntry, OpeningBalanceBatch
    from accounting.period_close_register import apply_period_close_filters, period_close_runs_for_department

    groups = []
    definitions = (
        (can_prepare_journals(user), "journal-preparation", "Accounting", "JEV drafts to complete or correct",
         JournalEntry.objects.filter(department_id=department.pk, status=JournalEntry.DRAFT),
         _queue_url("accounting:workspace", status=JournalEntry.DRAFT),
         "Draft and returned JEV work available to an Accounting maker."),
        (can_post_journals(user), "journal-posting", "Accounting", "JEVs awaiting independent posting",
         JournalEntry.objects.filter(department_id=department.pk, status=JournalEntry.SUBMITTED),
         _queue_url("accounting:workspace", attention="for_posting"),
         "Balanced submitted JEVs awaiting a permitted post-or-return decision."),
        (can_prepare_opening_balances(user), "opening-preparation", "Accounting", "Opening batches to prepare or correct",
         OpeningBalanceBatch.objects.filter(department_id=department.pk, status__in=(OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED)),
         _queue_url("accounting:opening_workspace", attention="needs_preparation"),
         "Draft or returned opening batches in the preparer's governed route."),
        (can_prepare_opening_balances(user), "opening-submission", "Accounting", "Validated opening batches ready to submit",
         OpeningBalanceBatch.objects.filter(department_id=department.pk, status=OpeningBalanceBatch.VALIDATED),
         _queue_url("accounting:opening_workspace", attention="ready_to_submit"),
         "Validated opening batches ready for the preparer to submit for independent review."),
        (can_approve_opening_balances(user), "opening-review", "Accounting", "Opening batches for independent review",
         OpeningBalanceBatch.objects.filter(department_id=department.pk, status=OpeningBalanceBatch.FOR_REVIEW),
         _queue_url("accounting:opening_workspace", attention="awaiting_review"),
         "Opening batches submitted for an independent approve-or-return decision."),
        (can_post_opening_balances(user), "opening-posting", "Accounting", "Approved opening batches awaiting posting",
         OpeningBalanceBatch.objects.filter(department_id=department.pk, status=OpeningBalanceBatch.APPROVED),
         _queue_url("accounting:opening_workspace", attention="awaiting_posting"),
         "Approved opening batches awaiting an authorized posting action."),
        (can_post_opening_balances(user), "opening-reconciliation", "Accounting", "Posted opening batches awaiting reconciliation",
         OpeningBalanceBatch.objects.filter(department_id=department.pk, status=OpeningBalanceBatch.POSTED),
         _queue_url("accounting:opening_workspace", attention="awaiting_reconciliation"),
         "Posted opening batches awaiting zero-difference reconciliation."),
        (can_prepare_bank_reconciliation(user), "bank-statement", "Reconciliation", "Bank batches needing a statement",
         BankStatementBatch.objects.filter(department_id=department.pk, status=BankStatementBatch.DRAFT, source_version=0),
         _queue_url("accounting:bank_reconciliation_workspace", attention="needs_statement"),
         "Draft bank batches that do not yet have a staged statement source."),
        (can_prepare_bank_reconciliation(user), "bank-control-correction", "Reconciliation", "Staged bank controls to correct",
         BankStatementBatch.objects.filter(department_id=department.pk, status=BankStatementBatch.DRAFT, source_version__gt=0),
         _queue_url("accounting:bank_reconciliation_workspace", attention="needs_control_correction"),
         "Staged draft statements whose declared or imported controls need correction."),
        (can_prepare_bank_reconciliation(user), "bank-returned", "Reconciliation", "Returned bank reconciliations to correct",
         BankStatementBatch.objects.filter(department_id=department.pk, status=BankStatementBatch.RETURNED),
         _queue_url("accounting:bank_reconciliation_workspace", attention="returned_correction"),
         "Bank reconciliations returned with an independent review reason."),
        (can_prepare_bank_reconciliation(user), "bank-matching", "Reconciliation", "Validated bank statements to match",
         BankStatementBatch.objects.filter(department_id=department.pk, status=BankStatementBatch.VALIDATED),
         _queue_url("accounting:bank_reconciliation_workspace", attention="needs_matching"),
         "Validated bank statements ready for matching, classification, and explanation."),
        (can_approve_bank_reconciliation(user), "bank-review", "Reconciliation", "Bank reconciliations for independent review",
         BankStatementBatch.objects.filter(department_id=department.pk, status=BankStatementBatch.FOR_REVIEW),
         _queue_url("accounting:bank_reconciliation_workspace", attention="for_review"),
         "Zero-difference reconciliation submissions awaiting an independent decision."),
    )
    for allowed, key, area, title, queryset, url, definition in definitions:
        if allowed:
            groups.append(_group(
                key=key, area=area, title=title, count=queryset.count(), url=url,
                definition=definition, scope=department.name,
            ))
    close_specs = (
        (can_prepare_period_close(user), "period-close-preparation", "Period-close checklists to prepare or correct",
         "needs_preparation", "Draft or returned period-close evidence available to an authorized preparer."),
        (can_approve_period_close(user), "period-close-review", "Period closes for independent review",
         "awaiting_review", "Submitted close evidence awaiting an independent close-or-return decision."),
        (can_reopen_period(user), "period-reopen-review", "Period reopen requests for decision",
         "awaiting_reopen_decision", "Closed periods whose retained reopen request awaits an independent decision."),
    )
    for allowed, key, title, attention, definition in close_specs:
        if allowed:
            queryset, _status, selected_attention = apply_period_close_filters(
                period_close_runs_for_department(department), attention=attention,
            )
            groups.append(_group(
                key=key, area="Accounting close", title=title, count=queryset.count(),
                url=_queue_url("accounting:period_close_workspace", attention=selected_attention),
                definition=definition, scope=department.name,
            ))
    return groups


def _bank_advice_groups(user, department):
    from vouchers.access import has_explicit_permission
    from vouchers.advice_register import apply_bank_advice_filters, visible_bank_advice_batches

    if not has_explicit_permission(user, "vouchers.view_bank_advice"):
        return []
    groups = []
    specs = (
        ("vouchers.prepare_bank_advice", "bank-advice-preparation", "Bank advice to prepare or correct",
         "needs_preparation", "Draft or returned advice versions available for preparation or a reasoned successor."),
        ("vouchers.approve_bank_advice", "bank-advice-review", "Bank advice for independent review",
         "awaiting_review", "Advice versions awaiting an independent Accounting approve-or-return decision."),
        ("vouchers.submit_bank_advice", "bank-advice-submission", "Approved advice to submit to the bank",
         "awaiting_bank_submission", "Approved advice versions awaiting retained bank-submission evidence."),
        ("vouchers.acknowledge_bank_advice", "bank-advice-response", "Submitted advice awaiting bank response",
         "awaiting_bank_response", "Submitted advice versions awaiting retained acknowledgement or return evidence."),
    )
    for permission, key, title, attention, definition in specs:
        if has_explicit_permission(user, permission):
            queryset, _status, selected_attention = apply_bank_advice_filters(
                visible_bank_advice_batches(user), attention=attention,
            )
            groups.append(_group(
                key=key, area="Bank advice", title=title, count=queryset.count(),
                url=_queue_url("vouchers:advice_workspace", attention=selected_attention),
                definition=definition,
                scope=f"Existing role-scoped bank-advice handoff; acting department: {department.name}",
            ))
    return groups


def _returned_instrument_groups(user, department):
    from vouchers.access import has_explicit_permission
    from vouchers.returned_instrument_register import (
        RETURNED_INSTRUMENT_ATTENTION_SPECS, returned_instrument_attention_queryset,
    )
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user):
        return []
    keys = {
        "accounting_review": "returned-instrument-accounting-review",
        "treasury_clarification": "returned-instrument-treasury-clarification",
        "treasury_replacement": "returned-instrument-treasury-replacement",
    }
    groups = []
    for attention, spec in RETURNED_INSTRUMENT_ATTENTION_SPECS.items():
        if has_explicit_permission(user, spec["permission"]):
            queryset, selected_attention, _work_spec = returned_instrument_attention_queryset(user, attention)
            scope = (
                f"Accounting register: {department.name}"
                if spec["scope_kind"] == "accounting"
                else f"Owning Treasury office: {department.name}"
            )
            groups.append(_group(
                key=keys[attention], area="Returned payment", title=spec["title"],
                count=queryset.count(),
                url=_queue_url("vouchers:advice_workspace", returned_attention=selected_attention),
                definition=spec["definition"], scope=scope,
            ))
    return groups


def _treasury_groups(user, department):
    from vouchers.access import has_explicit_permission
    from vouchers.models import TreasuryRemittanceBatch

    groups = []
    specs = (
        ("vouchers.prepare_remittances", "remittance-preparation", "Remittances to prepare or correct",
         TreasuryRemittanceBatch.objects.filter(status=TreasuryRemittanceBatch.DRAFT), TreasuryRemittanceBatch.DRAFT),
        ("vouchers.prepare_remittances", "remittance-returned", "Returned remittances to correct",
         TreasuryRemittanceBatch.objects.filter(status=TreasuryRemittanceBatch.RETURNED), TreasuryRemittanceBatch.RETURNED),
        ("vouchers.approve_remittances", "remittance-review", "Remittances for independent review",
         TreasuryRemittanceBatch.objects.filter(status=TreasuryRemittanceBatch.FOR_REVIEW), TreasuryRemittanceBatch.FOR_REVIEW),
        ("vouchers.release_remittances", "remittance-release", "Approved remittances awaiting release",
         TreasuryRemittanceBatch.objects.filter(status=TreasuryRemittanceBatch.APPROVED), TreasuryRemittanceBatch.APPROVED),
    )
    for permission, key, title, queryset, status in specs:
        if has_explicit_permission(user, permission):
            groups.append(_group(
                key=key, area="Treasury", title=title, count=queryset.count(),
                url=_queue_url("vouchers:remittance_workspace", status=status),
                definition="Records in the explicit governed state named by this attention group.",
                scope="Permitted central Finance remittance register",
            ))
    return groups


def _cash_groups(user, department):
    from vouchers.access import has_explicit_permission
    from vouchers.cash_register import CASH_ATTENTION_SPECS, cash_attention_queryset
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user):
        return []
    groups = []
    review_scope = "Permitted cross-office cash-control register"
    preparation_scope = f"Acting Treasury department: {department.name}"
    keys = {
        "policy_needs_preparation": "cash-policy-preparation",
        "policy_awaiting_review": "cash-policy-review",
        "position_needs_preparation": "cash-position-preparation",
        "position_awaiting_review": "cash-position-review",
    }
    for attention, spec in CASH_ATTENTION_SPECS.items():
        if has_explicit_permission(user, spec["permission"]):
            queryset, selected_attention, _work_spec = cash_attention_queryset(user, attention)
            groups.append(_group(
                key=keys[attention], area="Treasury cash", title=spec["title"],
                count=queryset.count(),
                url=_queue_url("vouchers:cash_workspace", attention=selected_attention),
                definition=spec["definition"],
                scope=review_scope if spec["permission"] == "vouchers.approve_cash_position" else preparation_scope,
            ))
    return groups


def _reporting_groups(user, department):
    from reporting.access import (
        can_approve_reports, can_generate_reports, can_review_reports, can_view_department_reports,
    )
    from reporting.models import ReportRun

    visible = ReportRun.objects.filter(definition__department=department)
    if not can_view_department_reports(user):
        visible = visible.filter(created_by=user)
    groups = []
    specs = (
        (can_generate_reports(user), "report-generation", "Draft reports ready to generate",
         visible.filter(status=ReportRun.DRAFT), "", ReportRun.DRAFT),
        (can_generate_reports(user), "report-rerun", "Failed reports to correct and rerun",
         visible.filter(status=ReportRun.FAILED), "generation_failed", ""),
        (can_review_reports(user), "report-review", "Reports ready for independent review",
         visible.filter(status=ReportRun.GENERATED).filter(Q(control_gate_required=False) | Q(control_status=ReportRun.CONTROL_RECONCILED)), "needs_review", ""),
        (can_approve_reports(user), "report-approval", "Reviewed reports awaiting approval",
         visible.filter(status=ReportRun.REVIEWED), "needs_approval", ""),
    )
    for allowed, key, title, queryset, attention, status in specs:
        if allowed:
            groups.append(_group(
                key=key, area="Reporting", title=title, count=queryset.count(),
                url=_queue_url("reporting:workspace", attention=attention, status=status),
                definition="Visible report runs in the explicit lifecycle state and control-gate condition named here.",
                scope=department.name,
            ))
    return groups


def _local_form_groups(user, department):
    from reporting.local_form_register_exports import (
        local_form_action_choices_for_user, local_form_action_queryset,
    )

    keys = {
        "needs_mapping": "local-form-mapping",
        "needs_reference": "local-form-reference",
        "candidate_sections": "local-form-section-decisions",
        "returned": "local-form-returned",
        "witness_tests": "local-form-test-witness",
        "for_review": "local-form-acceptance-review",
    }
    groups = []
    for attention, _label in local_form_action_choices_for_user(user, department):
        queryset, selected_attention, spec = local_form_action_queryset(user, attention)
        groups.append(_group(
            key=keys[attention], area="Local forms", title=spec["title"],
            count=queryset.count(),
            url=_queue_url("reporting:local_form_workspace", attention=selected_attention),
            definition=spec["definition"], scope=f"Acting office: {department.name}",
        ))
    return groups


def finance_work_attention(user):
    """Build permission-filtered, drillable cross-domain attention metrics without creating task state."""
    department = getattr(getattr(user, "employeeprofile", None), "assigned_department", None)
    generated_at = timezone.now()
    if department is None:
        return {"groups": [], "action_count": 0, "generated_at": generated_at, "department": None}
    groups = []
    groups.extend(_setup_groups(user, department))
    groups.extend(_discovery_groups(user, department))
    groups.extend(_field_operation_groups(user, department))
    groups.extend(_budget_groups(user, department))
    groups.extend(_voucher_groups(user, department))
    groups.extend(_accounting_groups(user, department))
    groups.extend(_bank_advice_groups(user, department))
    groups.extend(_returned_instrument_groups(user, department))
    groups.extend(_treasury_groups(user, department))
    groups.extend(_cash_groups(user, department))
    groups.extend(_reporting_groups(user, department))
    groups.extend(_local_form_groups(user, department))
    return {
        "groups": groups,
        "action_count": sum(group["count"] for group in groups),
        "generated_at": generated_at,
        "department": department,
    }
