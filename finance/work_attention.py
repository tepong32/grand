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
    from vouchers.case_exports import apply_case_filters, visible_cases_for_user
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
        (
            has_explicit_permission(user, "vouchers.control_dv_printing")
            or has_explicit_permission(user, "vouchers.track_wet_signatures"),
            VoucherCase.AWAITING_SIGNATURES,
        ),
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
    queryset, *_filters = apply_case_filters(
        visible_cases_for_user(user), actionable_stages=stages,
        attention="ready_for_me", actor=user,
    )
    count = queryset.count()
    return [_group(
        key="voucher-ready", area="Voucher case", title="Shared cases ready for your role",
        count=count, url=_queue_url("vouchers:workspace", attention="ready_for_me"),
        definition="Cases whose current governed stage has an action permission held by this account.",
        scope=f"Current Voucher Workbench role and {department.name} visibility; UAT preview is excluded.",
    )]


def _budget_groups(user, department):
    from budget.access import has_budget_permission
    from budget.annual_exports import apply_annual_filters
    from budget.control_exports import (
        apply_allotment_filters, apply_obligation_filters, obligation_scope_for_user,
    )
    from budget.models import AllotmentReleaseOrder, BudgetVersion
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user):
        return []

    groups = []
    can_view_obligation_registry = has_budget_permission(user, "view_obligation_registry")
    can_certify_obligations = has_budget_permission(user, "certify_obligations")
    can_initiate_obligations = has_budget_permission(user, "initiate_obligation_requests")
    if has_budget_permission(user, "prepare_budget_proposals"):
        queryset, _kind, _status, _attention = apply_annual_filters(
            BudgetVersion.objects.filter(department_id=department.pk),
            attention="needs_preparation", actor=user,
        )
        groups.append(_group(
            key="budget-version-preparation", area="Budget", title="Budget versions to prepare or correct",
            count=queryset.count(), url=_queue_url("budget:workspace", attention="needs_preparation"),
            definition="Draft or returned budget versions available to a proposal preparer.", scope=department.name,
        ))
    if has_budget_permission(user, "review_budget_proposals"):
        queryset, _kind, _status, _attention = apply_annual_filters(
            BudgetVersion.objects.filter(department_id=department.pk),
            attention="awaiting_proposal_review", actor=user,
        )
        groups.append(_group(
            key="budget-version-review", area="Budget", title="Budget versions for independent review",
            count=queryset.count(), url=_queue_url("budget:workspace", attention="awaiting_proposal_review"),
            definition="Submitted budget versions awaiting a permitted independent review.", scope=department.name,
        ))
    if has_budget_permission(user, "prepare_allotment_releases"):
        queryset, _kind, _status, _attention = apply_allotment_filters(
            AllotmentReleaseOrder.objects.filter(department_id=department.pk),
            attention="needs_preparation", actor=user,
        )
        groups.append(_group(
            key="allotment-preparation", area="Budget", title="Allotment orders to prepare or correct",
            count=queryset.count(), url=_queue_url("budget:allotment_workspace", attention="needs_preparation"),
            definition="Draft or returned allotment orders available to a preparer.", scope=department.name,
        ))
    if has_budget_permission(user, "approve_allotment_releases"):
        queryset, _kind, _status, _attention = apply_allotment_filters(
            AllotmentReleaseOrder.objects.filter(department_id=department.pk),
            attention="awaiting_review", actor=user,
        )
        groups.append(_group(
            key="allotment-review", area="Budget", title="Allotment orders for independent review",
            count=queryset.count(), url=_queue_url("budget:allotment_workspace", attention="awaiting_review"),
            definition="Submitted allotment orders awaiting a permitted post-or-return decision.", scope=department.name,
        ))
    if can_initiate_obligations and not (can_view_obligation_registry or can_certify_obligations):
        queryset, _kind, _form, _status, _attention = apply_obligation_filters(
            obligation_scope_for_user(user), attention="needs_preparation", actor=user,
        )
        groups.append(_group(
            key="obligation-preparation", area="Budget", title="Obligation requests to prepare or correct",
            count=queryset.count(), url=_queue_url("budget:obligation_workspace", attention="needs_preparation"),
            definition="Own-office draft or returned obligation requests available to a requesting-office maker.",
            scope=department.name,
        ))
    if can_certify_obligations:
        queryset, _kind, _form, _status, _attention = apply_obligation_filters(
            obligation_scope_for_user(user), attention="awaiting_certification", actor=user,
        )
        groups.append(_group(
            key="obligation-certification", area="Budget", title="Obligations awaiting certification",
            count=queryset.count(), url=_queue_url("budget:obligation_workspace", attention="awaiting_certification"),
            definition="Submitted obligation requests awaiting a permitted Budget certification or return.",
            scope=department.name,
        ))
    return groups


def _accounting_groups(user, department):
    from accounting.access import (
        can_approve_opening_balances, can_approve_period_close, can_post_journals,
        can_post_opening_balances, can_prepare_journals, can_prepare_opening_balances,
        can_prepare_period_close, can_reopen_period,
    )
    from accounting.bank_register_exports import (
        bank_reconciliation_action_choices_for_user, bank_reconciliation_action_queryset,
    )
    from accounting.journal_exports import journal_action_queryset
    from accounting.models import JournalEntry, OpeningBalanceBatch
    from accounting.period_close_register import apply_period_close_filters, period_close_runs_for_department

    groups = []
    definitions = (
        (can_prepare_journals(user), "journal-preparation", "Accounting", "JEV drafts to complete or correct",
         journal_action_queryset(user, "preparation")[0],
         _queue_url("accounting:workspace", status=JournalEntry.DRAFT),
         "Draft and returned JEV work available to an Accounting maker."),
        (can_post_journals(user), "journal-posting", "Accounting", "JEVs awaiting independent posting",
         journal_action_queryset(user, "posting")[0],
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
    )
    for allowed, key, area, title, queryset, url, definition in definitions:
        if allowed:
            groups.append(_group(
                key=key, area=area, title=title, count=queryset.count(), url=url,
                definition=definition, scope=department.name,
            ))
    bank_keys = {
        "needs_statement": "bank-statement",
        "needs_control_correction": "bank-control-correction",
        "returned_correction": "bank-returned",
        "needs_matching": "bank-matching",
        "for_review": "bank-review",
    }
    for attention, _label in bank_reconciliation_action_choices_for_user(user):
        queryset, selected_attention, spec = bank_reconciliation_action_queryset(user, attention)
        groups.append(_group(
            key=bank_keys[attention], area="Reconciliation", title=spec["title"],
            count=queryset.count(),
            url=_queue_url("accounting:bank_reconciliation_workspace", attention=selected_attention),
            definition=spec["definition"], scope=department.name,
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
    from vouchers.advice_register import (
        bank_advice_action_choices_for_user, bank_advice_action_queryset,
    )

    if not has_explicit_permission(user, "vouchers.view_bank_advice"):
        return []
    groups = []
    keys = {
        "needs_preparation": "bank-advice-preparation",
        "awaiting_review": "bank-advice-review",
        "awaiting_bank_submission": "bank-advice-submission",
        "awaiting_bank_response": "bank-advice-response",
    }
    for attention, title in bank_advice_action_choices_for_user(user):
        queryset, selected_attention, spec = bank_advice_action_queryset(user, attention)
        groups.append(_group(
            key=keys[attention], area="Bank advice", title=title, count=queryset.count(),
            url=_queue_url("vouchers:advice_workspace", attention=selected_attention),
            definition=spec["definition"],
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
    from vouchers.remittance_register import (
        remittance_action_choices_for_user, remittance_action_queryset,
    )

    groups = []
    keys = {
        "preparation": "remittance-preparation",
        "returned": "remittance-returned",
        "review": "remittance-review",
        "release": "remittance-release",
    }
    for action, _label in remittance_action_choices_for_user(user):
        queryset, selected, spec = remittance_action_queryset(user, action)
        scope = (
            "Permitted cross-office Finance remittance review"
            if spec["scope"] == "finance"
            else f"Owning Treasury office: {department.name}"
        )
        groups.append(_group(
            key=keys[action], area="Treasury", title=spec["title"], count=queryset.count(),
            url=_queue_url("vouchers:remittance_workspace", attention=selected),
            definition=spec["definition"], scope=scope,
        ))
    return groups


def _cash_groups(user, department):
    from vouchers.cash_register import cash_attention_choices_for_user, cash_attention_queryset

    groups = []
    review_scope = "Permitted cross-office cash-control register"
    preparation_scope = f"Acting Treasury department: {department.name}"
    keys = {
        "policy_needs_preparation": "cash-policy-preparation",
        "policy_awaiting_review": "cash-policy-review",
        "position_needs_preparation": "cash-position-preparation",
        "position_awaiting_review": "cash-position-review",
    }
    for attention, _label in cash_attention_choices_for_user(user):
        queryset, selected_attention, spec = cash_attention_queryset(user, attention)
        groups.append(_group(
            key=keys[attention], area="Treasury cash", title=spec["title"],
            count=queryset.count(),
            url=_queue_url("vouchers:cash_workspace", attention=selected_attention),
            definition=spec["definition"],
            scope=review_scope if spec["permission"] == "vouchers.approve_cash_position" else preparation_scope,
        ))
    return groups


def _reporting_groups(user, department):
    from reporting.run_register_exports import (
        report_action_choices_for_user, report_action_queryset,
    )

    groups = []
    keys = {
        "generation": "report-generation",
        "generation_failed": "report-rerun",
        "control_blocked": "report-control-blocked",
        "needs_review": "report-review",
        "needs_approval": "report-approval",
    }
    for action, _label in report_action_choices_for_user(user):
        queryset, selected, spec = report_action_queryset(user, action)
        groups.append(_group(
            key=keys[action], area="Reporting", title=spec["title"], count=queryset.count(),
            url=_queue_url("reporting:workspace", attention=selected),
            definition=spec["definition"], scope=department.name,
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
