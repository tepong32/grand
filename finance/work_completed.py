from __future__ import annotations

from django.urls import reverse


def completed_accounting_tasks(user, department, today):
    """Successful attributed actions remain history under current source access."""
    from accounting.access import can_view_accounting, can_view_bank_reconciliation
    from accounting.models import AccountingAuditEvent, BankReconciliationEvent, OpeningBalanceEvent, PeriodCloseEvent
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_accounting(user):
        return []
    specs = (
        (AccountingAuditEvent, "entry", "journal-entry", "accounting:entry_detail", {
            "submitted": "Submitted JEV for posting", "posted": "Posted JEV", "returned": "Returned JEV for correction",
        }),
        (OpeningBalanceEvent, "batch", "opening-batch", "accounting:opening_detail", {
            "submitted": "Submitted opening balances", "approved": "Approved opening balances",
            "returned": "Returned opening balances", "posted": "Posted opening balances", "reconciled": "Reconciled opening balances",
        }),
        (PeriodCloseEvent, "run", "period-close", "accounting:period_close_detail", {
            "submitted": "Submitted close checklist", "returned": "Returned close checklist",
            "period_closed": "Closed Accounting period", "reopen_requested": "Submitted period-reopen request",
            "reopen_returned": "Returned period-reopen request", "period_reopened": "Reopened Accounting period",
        }),
    )
    if can_view_bank_reconciliation(user):
        specs += ((BankReconciliationEvent, "batch", "bank-reconciliation", "accounting:bank_reconciliation_detail", {
            "submitted_for_review": "Submitted bank reconciliation for independent review",
            "returned_for_correction": "Returned bank reconciliation for correction",
            "reconciled": "Reconciled bank statement and ledger evidence",
        }),)
    tasks = []
    for model, relation, kind, route, labels in specs:
        events = model.objects.filter(
            department_id=department.pk, actor_id=user.pk, action__in=labels,
            **{f"{relation}__department_id": department.pk},
        ).select_related(relation)
        if model is not BankReconciliationEvent:
            events = events.select_related(f"{relation}__period")
        if model is AccountingAuditEvent:
            events = events.exclude(entry__source_type="opening")
        for event in events:
            item = getattr(event, relation)
            event_id = _source_record_identity(f"{kind}-event", event.pk)
            reference = (item.reference if kind == "journal-entry" else
                         item.source_reference if kind == "opening-batch" else
                         item.statement_reference if kind == "bank-reconciliation" else f"{item.period} v{item.version}")
            scope = (f"{department.name}; bank {item.bank_account_code}; {item.period_start} to {item.period_end}"
                     if kind == "bank-reconciliation" else f"{department.name}; {item.period}")
            label = labels[event.action]
            revision = _projection_checksum({
                "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
                "actor_label": event.actor_label, "at": event.created_at.isoformat(),
                "snapshot": event.snapshot, "reason": event.reason, "source_id": str(item.public_id),
                "current_state": item.status, "reference": reference,
            })
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:{kind}-event:{event_id}:completed",
                task_type=f"finance.{kind}.{event.action}.completed.v1", area="Accounting",
                case_id=f"{kind}:{item.public_id}", reference=reference, subject=label,
                transaction_type="Recorded Accounting action", action="View recorded outcome",
                gate=f"The retained event attributes this completed action to you: {label}." + (f" Reason: {event.reason}" if event.reason else ""),
                owner_queue=f"Recorded actor: {event.actor_label}", scope=scope,
                received_at=event.created_at, due_on=None, due_state="Recorded completion",
                calendar_basis="Elapsed calendar days since this recorded action. The source's current state is shown separately.",
                age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_status_display(),
                source_version=f"event-sha256:{revision}", exception="",
                url=reverse(route, kwargs={"public_id": item.public_id}),
            ))
    return tasks


def completed_budget_tasks(user, department, today):
    """Project retained Budget actions only when their exact source is still readable."""
    from budget.access import can_view, has_budget_permission
    from budget.control_exports import obligation_scope_for_user
    from budget.models import (
        AllotmentReleaseOrder, AppropriationAuthorization, BudgetAuditEvent, BudgetCall,
        BudgetVersion, ObligationRequest,
    )
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view(user):
        return []
    authorizations = {
        str(item.public_id): item for item in AppropriationAuthorization.objects.filter(
            department_id=department.pk, version__department_id=department.pk,
        ).select_related("version", "version__fiscal_year")
    }
    specs = (
        (BudgetCall.objects.filter(department_id=department.pk), "budget-call", "budget:call_detail", "title", {
            "submit": "Submitted Budget call", "publish": "Published Budget call",
            "return": "Returned Budget call", "close": "Closed Budget proposal intake",
        }),
        (BudgetVersion.objects.filter(department_id=department.pk), "budget-version", "budget:version_detail", "title", {
            "submit": "Submitted Budget proposal", "approve": "Approved Budget proposal",
            "return": "Returned Budget proposal", "consolidated": "Consolidated Budget proposals",
            "appropriation_submit": "Submitted appropriation authority",
            "appropriation_authorize": "Authorized appropriation",
            "appropriation_return": "Returned appropriation authority",
        }),
        (AllotmentReleaseOrder.objects.filter(department_id=department.pk) if has_budget_permission(user, "view_allotment_control")
         else AllotmentReleaseOrder.objects.none(), "allotment-order", "budget:allotment_detail", "order_number", {
            "allotment_submit": "Submitted allotment order", "allotment_post": "Posted allotment order",
            "allotment_return": "Returned allotment order",
        }),
        (obligation_scope_for_user(user), "obligation-request", "budget:obligation_detail", "request_reference", {
            "obligation_submit": "Submitted obligation request", "obligation_certify": "Certified obligation",
            "obligation_return": "Returned obligation request",
        }),
    )
    tasks = []
    for queryset, kind, route, reference_field, labels in specs:
        sources = {str(item.public_id): item for item in queryset.select_related("fiscal_year")}
        events = BudgetAuditEvent.objects.filter(
            actor_id=user.pk, target_type=queryset.model._meta.model_name,
            target_id__in=sources, action__in=labels,
        )
        for event in events:
            item = sources[event.target_id]
            source_kind, source_route = kind, route
            fiscal_year = item.fiscal_year
            reference = getattr(item, reference_field)
            if event.department_id != item.department_id:
                continue
            if event.action.startswith("appropriation_"):
                # Authority events are retained on their parent version. Resolve and
                # verify the explicit authority link before exposing that outcome.
                authority_id = event.snapshot.get("authorization_id") if isinstance(event.snapshot, dict) else None
                authority = authorizations.get(str(authority_id))
                if authority is None or authority.version_id != item.pk:
                    continue
                item, source_kind, source_route = authority, "appropriation-authorization", "budget:authorization_detail"
                reference = item.ordinance_number
            event_id = _source_record_identity("budget-event", event.pk)
            label = labels[event.action]
            revision = _projection_checksum({
                "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
                "actor_label": event.actor_label, "at": event.created_at.isoformat(),
                "snapshot": event.snapshot, "reason": event.reason, "source_id": str(item.public_id),
                "current_state": item.status, "reference": reference,
            })
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:budget-event:{event_id}:completed",
                task_type=f"finance.{source_kind}.{event.action}.completed.v1", area="Budget",
                case_id=f"{source_kind}:{item.public_id}", reference=reference, subject=label,
                transaction_type="Recorded Budget action", action="View recorded outcome",
                gate=f"The retained event attributes this completed action to you: {label}." + (f" Reason: {event.reason}" if event.reason else ""),
                owner_queue=f"Recorded actor: {event.actor_label}", scope=f"{department.name}; {fiscal_year}",
                received_at=event.created_at, due_on=None, due_state="Recorded completion",
                calendar_basis="Elapsed calendar days since this recorded action. The source's current state is shown separately.",
                age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_status_display(),
                source_version=f"event-sha256:{revision}", exception="",
                url=reverse(source_route, kwargs={"public_id": item.public_id}),
            ))
    return tasks


def completed_payment_handoff_tasks(user, department, today):
    """Keep bank/Accounting/Treasury event attribution within current source reads."""
    from vouchers.access import can_view_workbench, has_explicit_permission
    from vouchers.advice_register import visible_bank_advice_batches
    from vouchers.models import BankAdviceEvent, RemittanceEvent
    from vouchers.remittance_register import visible_remittance_batches
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_workbench(user):
        return []
    specs = []
    if has_explicit_permission(user, "vouchers.view_bank_advice"):
        specs.append((BankAdviceEvent, visible_bank_advice_batches(user), "bank-advice", "Bank advice", "vouchers:advice_detail", {
            "advice_submitted_for_review": "Submitted bank advice for review",
            "advice_approved": "Approved bank advice", "advice_returned_by_reviewer": "Returned bank advice for correction",
            "advice_submitted_to_bank": "Submitted advice to the bank",
            "advice_acknowledged_by_bank": "Recorded bank acknowledgement", "advice_returned_by_bank": "Recorded bank return",
        }))
    if any(has_explicit_permission(user, code) for code in (
        "vouchers.view_remittance_workbench", "vouchers.prepare_remittances", "vouchers.approve_remittances",
        "vouchers.release_remittances", "vouchers.view_remittance_audit",
    )):
        specs.append((RemittanceEvent, visible_remittance_batches(user), "treasury-remittance", "Treasury", "vouchers:remittance_detail", {
            "submitted_for_accounting_review": "Submitted remittance for review",
            "approved_for_release": "Approved remittance release", "returned_for_correction": "Returned remittance for correction",
            "actual_remittance_released": "Recorded remittance release", "remittance_jev_posted": "Synchronized posted remittance",
        }))
    tasks = []
    for model, visible, kind, area, route, labels in specs:
        events = model.objects.filter(actor=user, batch__in=visible, action__in=labels).select_related("batch", "actor_department")
        for event in events:
            item = event.batch
            if kind == "bank-advice":
                # Treasury may submit Accounting advice across its established office boundary.
                if event.action != "advice_submitted_to_bank" and event.actor_department_id != item.accounting_department_id:
                    continue
                reference, payload = f"{item.advice_number} v{item.version}", event.snapshot
                scope = f"{department.name}; bank {item.bank_account_code}"
            else:
                expected_office = (item.treasury_department_id if event.action in (
                    "submitted_for_accounting_review", "actual_remittance_released",
                ) else item.finance_department_id)
                if event.actor_department_id != expected_office:
                    continue
                reference, payload = item.reference_code, event.metadata
                scope = f"{department.name}; fund {item.fund_code}"
            event_id = _source_record_identity(f"{kind}-event", event.pk)
            label = labels[event.action]
            revision = _projection_checksum({
                "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
                "actor_department_id": event.actor_department_id, "at": event.created_at.isoformat(),
                "evidence": payload, "reason": event.reason, "source_id": str(item.public_id),
                "current_state": item.status, "reference": reference,
            })
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:{kind}-event:{event_id}:completed",
                task_type=f"finance.{kind}.{event.action}.completed.v1", area=area,
                case_id=f"{kind}:{item.public_id}", reference=reference, subject=label,
                transaction_type="Recorded payment handoff", action="View recorded outcome",
                gate=f"The retained event attributes this completed action to your account: {label}." + (f" Reason: {event.reason}" if event.reason else ""),
                owner_queue=f"Recorded actor account: {user.get_username()}", scope=scope,
                received_at=event.created_at, due_on=None, due_state="Recorded completion",
                calendar_basis="Elapsed calendar days since this recorded action. The source's current state is shown separately.",
                age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_status_display(),
                source_version=f"event-sha256:{revision}", exception="",
                url=reverse(route, kwargs={"public_id": item.public_id}),
            ))
    return tasks


def completed_setup_tasks(user, department, today):
    """Credit retained release transitions under the current source read boundary."""
    from .access import can_view_finance_setup
    from .models import FinanceAuditEvent
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user) or not can_view_finance_setup(user):
        return []
    labels = {
        "submit": "Submitted setup release for review", "return": "Returned setup release for correction",
        "approve": "Approved setup release", "schedule": "Scheduled setup release",
        "activate": "Activated setup release", "rollback": "Restored a prior approved setup release",
        "retire": "Retired setup release",
    }
    events = FinanceAuditEvent.objects.filter(
        department_id=department.pk, release__department_id=department.pk, actor_id=user.pk,
        target_type="financeconfigurationrelease", action__in=labels,
    ).select_related("release")
    tasks = []
    for event in events:
        item = event.release
        if event.target_id != str(item.pk):
            continue
        source_id = _source_record_identity("setup-release", item.pk)
        event_id = _source_record_identity("setup-release-event", event.pk)
        label = labels[event.action]
        reference = f"{item.code} v{item.version} · FY {item.fiscal_year}"
        revision = _projection_checksum({
            "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
            "department_id": event.department_id, "at": event.created_at.isoformat(),
            "snapshot": event.snapshot, "reason": event.reason, "source_id": str(source_id),
            "current_state": item.status, "reference": reference,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:setup-release-event:{event_id}:completed",
            task_type=f"finance.setup-release.{event.action}.completed.v1", area="Finance setup",
            case_id=f"setup-release:{source_id}", reference=reference, subject=label,
            transaction_type="Recorded setup release action", action="View recorded outcome",
            gate=f"The retained event attributes this completed action to your account: {label}." + (f" Reason: {event.reason}" if event.reason else ""),
            owner_queue=f"Recorded actor account: {user.get_username()}", scope=f"{department.name}; FY {item.fiscal_year}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since this recorded action. The source's current state is shown separately.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_status_display(),
            source_version=f"event-sha256:{revision}", exception="",
            url=reverse("finance:release_detail", kwargs={"pk": item.pk}),
        ))
    return tasks


def completed_discovery_tasks(user, department, today):
    """Retain named cross-office access without equating recorded evidence to acceptance."""
    from .access import can_view_finance_discovery_decision
    from .discovery_register import visible_discovery_decisions
    from .models import FinanceAuditEvent
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity
    from vouchers.roles import is_finance_uat_viewer

    if not getattr(user, "is_active", False) or is_finance_uat_viewer(user):
        return []
    labels = {
        "discovery_decision_submitted": "Submitted discovery decision for review",
        "discovery_decision_returned": "Returned discovery decision for correction",
        "discovery_decision_recorded": "Recorded discovery decision",
    }
    sources = {str(item.pk): item for item in visible_discovery_decisions(user)}
    events = FinanceAuditEvent.objects.filter(actor_id=user.pk, target_type="financediscoverydecision", action__in=labels, target_id__in=sources)
    tasks = []
    for event in events:
        item = sources.get(event.target_id)
        if item is None or event.department_id != item.department_id or not can_view_finance_discovery_decision(user, item):
            continue
        event_id = _source_record_identity("discovery-decision-event", event.pk)
        label = labels[event.action]
        reference = f"{item.code} v{item.version} · {item.phase}"
        revision = _projection_checksum({
            "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
            "department_id": event.department_id, "at": event.created_at.isoformat(),
            "snapshot": event.snapshot, "reason": event.reason, "source_id": str(item.public_id),
            "current_state": item.status, "reference": reference,
            "evidence_label": item.evidence_label, "scope_blocked": item.is_current_blocker,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:discovery-decision-event:{event_id}:completed",
            task_type=f"finance.discovery-decision.{event.action}.completed.v1", area="Finance decisions",
            case_id=f"discovery-decision:{item.public_id}", reference=reference, subject=label,
            transaction_type="Recorded discovery action", action="View recorded outcome",
            gate=f"The retained event attributes this action to your account: {label}. Recording a finding does not itself establish local acceptance." + (f" Reason: {event.reason}" if event.reason else ""),
            owner_queue=f"Recorded actor account: {user.get_username()}", scope=f"{item.department.name}; {item.affected_scope}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since this recorded action. Current evidence and source state remain separate.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_status_display(),
            source_version=f"event-sha256:{revision}",
            exception=f"Current evidence: {item.get_evidence_label_display()}." + (" The named scope remains blocked." if item.is_current_blocker else ""),
            url=reverse("finance:discovery_decision_detail", kwargs={"public_id": item.public_id}),
        ))
    return tasks


def completed_payable_tasks(user, department, today):
    """Payable acceptance is retained readiness for DV preparation, not payment approval."""
    from vouchers.access import can_view_workbench
    from vouchers.case_exports import visible_cases_for_user
    from vouchers.models import VoucherCase, VoucherEvent
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_workbench(user):
        return []
    specs = {
        "payable_submitted": (VoucherCase.PAYABLE_PREPARATION, VoucherCase.PAYABLE_REVIEW, "Submitted payable for Accounting review"),
        "payable_returned": (VoucherCase.PAYABLE_REVIEW, VoucherCase.PAYABLE_PREPARATION, "Returned payable for correction"),
        "payable_accepted": (VoucherCase.PAYABLE_REVIEW, VoucherCase.ACCOUNTING_PREPARATION, "Accepted payable for DV preparation"),
    }
    events = VoucherEvent.objects.filter(actor_id=user.pk, case__in=visible_cases_for_user(user), action__in=specs).select_related("case", "actor_department")
    tasks = []
    for event in events:
        item = event.case
        before, after, label = specs[event.action]
        if event.from_stage != before or event.to_stage != after:
            continue
        if event.action == "payable_submitted" and event.actor_department_id != item.requesting_department_id:
            continue
        event_id = _source_record_identity("payable-event", event.pk)
        revision = _projection_checksum({
            "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
            "actor_department_id": event.actor_department_id, "at": event.created_at.isoformat(),
            "metadata": event.metadata, "reason": event.reason, "source_id": str(item.public_id),
            "from_stage": event.from_stage, "to_stage": event.to_stage, "state_version": event.state_version,
            "current_stage": item.current_stage, "reference": item.reference_code,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:payable-event:{event_id}:completed",
            task_type=f"finance.payable-intake.{event.action}.completed.v1", area="Voucher case",
            case_id=f"voucher-case:{item.public_id}", reference=item.reference_code, subject=label,
            transaction_type="Recorded payable action", action="View recorded outcome",
            gate=f"The retained event attributes this action to your account: {label}. Payable readiness does not authorize payment release." + (f" Reason: {event.reason}" if event.reason else ""),
            owner_queue=f"Recorded actor account: {user.get_username()}; office: {event.actor_department.name}",
            scope=f"Current source access; recorded acting office: {event.actor_department.name}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained payable action. Current case custody and stage remain separate.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_current_stage_display(),
            source_version=f"event-sha256:{revision}", exception="",
            url=reverse("vouchers:case_detail", kwargs={"public_id": item.public_id}),
        ))
    return tasks


def completed_dv_tasks(user, department, today):
    """Credit retained DV actions, keeping custody recording distinct from signing."""
    from vouchers.access import can_view_workbench
    from vouchers.case_exports import visible_cases_for_user
    from vouchers.models import VoucherCase, VoucherEvent
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity
    from .work_dv_print_history import PRINT_HISTORY_ACTIONS, print_history_evidence

    if is_finance_uat_viewer(user) or not can_view_workbench(user):
        return []
    preparation_targets = {VoucherCase.AWAITING_SIGNATURES, VoucherCase.ACCOUNTING_VALIDATION}
    specs = {
        "dv_prepared": (VoucherCase.ACCOUNTING_PREPARATION, preparation_targets, "Prepared DV for review"),
        "dv_corrected": (VoucherCase.ACCOUNTING_PREPARATION, preparation_targets, "Corrected DV for renewed review"),
        "wet_signature_returned": (VoucherCase.AWAITING_SIGNATURES, {VoucherCase.AWAITING_SIGNATURES}, "Recorded a wet-signature return"),
        "wet_signatures_completed": (VoucherCase.AWAITING_SIGNATURES, {VoucherCase.ACCOUNTING_VALIDATION}, "Recorded final wet-signature return for validation"),
        "accounting_validated": (VoucherCase.ACCOUNTING_VALIDATION, {VoucherCase.ACCOUNTING_POSTING}, "Validated DV for Accounting posting"),
    }
    specs.update({action: (VoucherCase.AWAITING_SIGNATURES, {VoucherCase.AWAITING_SIGNATURES}, label)
                  for action, (_actor, label) in PRINT_HISTORY_ACTIONS.items()})
    events = list(VoucherEvent.objects.filter(
        actor_id=user.pk, case__in=visible_cases_for_user(user), action__in=specs,
    ).select_related("case", "actor_department"))
    print_evidence = print_history_evidence(events)
    tasks = []
    for event in events:
        item = event.case
        before, targets, label = specs[event.action]
        if event.from_stage != before or event.to_stage not in targets:
            continue
        detail = print_evidence.get(event.pk)
        if event.action in PRINT_HISTORY_ACTIONS:
            if detail is None:
                continue
            label = detail["label"]
        event_id = _source_record_identity("dv-event", event.pk)
        revision = _projection_checksum({
            "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
            "actor_department_id": event.actor_department_id, "at": event.created_at.isoformat(),
            "metadata": event.metadata, "reason": event.reason, "source_id": str(item.public_id),
            "from_stage": event.from_stage, "to_stage": event.to_stage, "state_version": event.state_version,
            "current_stage": item.current_stage, "reference": item.reference_code,
            **({"print_evidence": detail["snapshot"]} if detail else {}),
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:dv-event:{event_id}:completed",
            task_type=f"finance.dv.{event.action}.completed.v1", area="Voucher case",
            case_id=f"voucher-case:{item.public_id}", reference=item.reference_code, subject=label,
            transaction_type="Recorded DV action", action="View recorded outcome",
            gate=f"The retained event attributes this action to your account: {label}. This does not authorize payment release." + (f" Reason: {event.reason}" if event.reason else ""),
            owner_queue=f"Recorded actor account: {user.get_username()}; office: {event.actor_department.name}",
            scope=f"Current source access; recorded acting office: {event.actor_department.name}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained DV action. Current case custody and stage remain separate.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_current_stage_display(),
            source_version=f"event-sha256:{revision}",
            exception=(f"Copy state: {detail['state']}. {detail['exception']}".strip() if detail else
                       "This credits custody recording, not the recorder's own wet signature." if event.action.startswith("wet_signature") else ""),
            url=reverse("vouchers:case_detail", kwargs={"public_id": item.public_id}),
        ))
    return tasks


def completed_returned_payment_tasks(user, department, today):
    """Retained review-version actions do not imply completed replacement/payment."""
    from uuid import UUID
    from vouchers.access import can_view_workbench, has_explicit_permission
    from vouchers.case_exports import visible_cases_for_user
    from vouchers.models import ReturnedInstrumentReview, VoucherCase, VoucherEvent
    from vouchers.returned_instrument_register import visible_returned_instrument_reviews
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_workbench(user) or not has_explicit_permission(user, "vouchers.view_bank_advice"):
        return []
    reviews = {item.public_id: item for item in visible_returned_instrument_reviews(user).select_related("supersedes")}
    specs = {
        "returned_instrument_sent_to_accounting": (VoucherCase.COMPLETED, "Submitted bank-return evidence", "prepared_by_id"),
        "returned_instrument_clarified": (VoucherCase.ACCOUNTING_RETURNED_ITEM, "Submitted clarified bank-return evidence", "prepared_by_id"),
        "returned_instrument_review_returned": (VoucherCase.ACCOUNTING_RETURNED_ITEM, "Returned bank-return evidence for clarification", "reviewed_by_id"),
        "returned_instrument_accounting_decided": (VoucherCase.ACCOUNTING_RETURNED_ITEM, "Recorded the returned-payment Accounting decision", "reviewed_by_id"),
    }
    events = VoucherEvent.objects.filter(actor_id=user.pk, action__in=specs, case__in=visible_cases_for_user(user)).select_related("case", "actor_department")
    tasks = []
    for event in events:
        if not isinstance(event.metadata, dict):
            continue
        try:
            review = reviews.get(UUID(str(event.metadata.get("review_public_id"))))
        except (ValueError, TypeError, AttributeError):
            continue
        if review is None or review.case_id != event.case_id:
            continue
        before, label, actor_field = specs[event.action]
        if event.from_stage != before or getattr(review, actor_field) != event.actor_id:
            continue
        targets = {VoucherCase.ACCOUNTING_RETURNED_ITEM}
        if event.action == "returned_instrument_clarified":
            if not review.supersedes_id or str(review.supersedes.public_id) != event.metadata.get("supersedes"):
                continue
        if event.action == "returned_instrument_accounting_decided":
            outcome = event.metadata.get("outcome")
            if outcome not in (ReturnedInstrumentReview.REISSUE, ReturnedInstrumentReview.CLOSE_WITHOUT_REISSUE) or outcome != review.outcome:
                continue
            targets = {VoucherCase.ACCOUNTING_EVENT_POSTING,
                       VoucherCase.TREASURY_CHECK_PREPARATION if outcome == ReturnedInstrumentReview.REISSUE else VoucherCase.COMPLETED}
        if event.to_stage not in targets:
            continue
        item = event.case
        event_id = _source_record_identity("returned-payment-event", event.pk)
        revision = _projection_checksum({
            "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
            "actor_department_id": event.actor_department_id, "at": event.created_at.isoformat(),
            "metadata": event.metadata, "reason": event.reason, "case_id": str(item.public_id),
            "from_stage": event.from_stage, "to_stage": event.to_stage, "state_version": event.state_version,
            "review_id": str(review.public_id), "review_status": review.status, "review_version": review.version,
            "current_stage": item.current_stage, "reference": item.reference_code,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:returned-payment-event:{event_id}:completed",
            task_type=f"finance.returned-payment.{event.action}.completed.v1", area="Returned payment",
            case_id=f"returned-payment:{review.public_id}", reference=f"{item.reference_code} · review v{review.version}",
            subject=label, transaction_type="Recorded returned-payment action", action="View source case",
            gate=f"The retained event attributes this action to your account: {label}." + (f" Reason: {event.reason}" if event.reason else ""),
            owner_queue=f"Recorded actor account: {user.get_username()}; office: {event.actor_department.name}",
            scope=f"Current review-register and case read access; recorded acting office: {event.actor_department.name}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained review action; current review and case states remain separate.",
            age_days=_age_days(event.created_at, today), state="Completed",
            source_state=f"{review.get_status_display()} · {item.get_current_stage_display()}",
            source_version=f"event-sha256:{revision}",
            exception="An Accounting decision does not by itself complete required posting, replacement or payment release.",
            url=reverse("vouchers:case_detail", kwargs={"public_id": item.public_id}),
        ))
    return tasks


def completed_instrument_tasks(user, department, today):
    """Physical instrument actions remain distinct from ledger completion."""
    from uuid import UUID
    from vouchers.access import can_view_workbench
    from vouchers.case_exports import visible_cases_for_user
    from vouchers.models import PaymentInstrument, VoucherCase, VoucherEvent
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_workbench(user):
        return []
    preparation = {VoucherCase.TREASURY_CHECK_PREPARATION}
    event_posting = {VoucherCase.ACCOUNTING_EVENT_POSTING}
    release = {VoucherCase.TREASURY_RELEASE}
    active_stages = set(dict(VoucherCase.STAGE_CHOICES)) - {VoucherCase.COMPLETED, VoucherCase.CANCELLED}
    specs = {
        "check_issued": (preparation, preparation | event_posting, "Registered an issued physical check", "issued_by_id"),
        "replacement_check_issued": (preparation, preparation | event_posting, "Registered a controlled replacement check", "issued_by_id"),
        "checks_submitted_for_advice": (preparation, {VoucherCase.ACCOUNTING_BANK_ADVICE}, "Submitted issued checks for bank advice", None),
        "check_released": (release, release | event_posting, "Recorded a physical check release", "released_by_id"),
        "disbursement_completed": (release, {VoucherCase.COMPLETED} | event_posting, "Recorded final check release", "released_by_id"),
        "check_cancelled": (active_stages, preparation | event_posting, "Cancelled a physical check", "cancelled_by_id"),
    }
    cases = visible_cases_for_user(user)
    instruments = {item.public_id: item for item in PaymentInstrument.objects.filter(case__in=cases).select_related("replaces")}
    events = VoucherEvent.objects.filter(actor_id=user.pk, case__in=cases, action__in=specs).select_related("case", "actor_department")
    tasks = []
    for event in events:
        before, after, label, actor_field = specs[event.action]
        if event.from_stage not in before or event.to_stage not in after or not isinstance(event.metadata, dict):
            continue
        instrument = None
        if actor_field:
            try:
                instrument = instruments.get(UUID(str(event.metadata.get("instrument_id"))))
            except (ValueError, TypeError, AttributeError):
                continue
            if (instrument is None or instrument.case_id != event.case_id or getattr(instrument, actor_field) != event.actor_id
                    or event.metadata.get("check_number") != instrument.check_number):
                continue
            if event.action == "replacement_check_issued":
                if not instrument.replaces_id or event.metadata.get("replaces_instrument_id") != str(instrument.replaces.public_id):
                    continue
            elif event.action == "check_issued" and instrument.replaces_id:
                continue
        item = event.case
        event_id = _source_record_identity("instrument-event", event.pk)
        revision = _projection_checksum({
            "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
            "actor_department_id": event.actor_department_id, "at": event.created_at.isoformat(),
            "metadata": event.metadata, "reason": event.reason, "case_id": str(item.public_id),
            "from_stage": event.from_stage, "to_stage": event.to_stage, "state_version": event.state_version,
            "instrument_id": str(instrument.public_id) if instrument else None,
            "instrument_status": instrument.status if instrument else None,
            "current_stage": item.current_stage, "reference": item.reference_code,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:instrument-event:{event_id}:completed",
            task_type=f"finance.payment-instrument.{event.action}.completed.v1", area="Treasury disbursement",
            case_id=f"voucher-case:{item.public_id}",
            reference=f"{item.reference_code} · check {instrument.check_number}" if instrument else item.reference_code,
            subject=label, transaction_type="Recorded instrument action", action="View source case",
            gate=f"The retained event attributes this action to your account: {label}." + (f" Reason: {event.reason}" if event.reason else ""),
            owner_queue=f"Recorded actor account: {user.get_username()}; office: {event.actor_department.name}",
            scope=f"Current case read access; recorded acting office: {event.actor_department.name}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained instrument action; no deadline inferred.",
            age_days=_age_days(event.created_at, today), state="Completed",
            source_state=(f"{instrument.get_status_display()} · " if instrument else "") + item.get_current_stage_display(),
            source_version=f"event-sha256:{revision}",
            exception="Physical issue, cancellation or release does not by itself complete required Accounting posting.",
            url=reverse("vouchers:case_detail", kwargs={"public_id": item.public_id}),
        ))
    return tasks


def completed_cash_tasks(user, department, today):
    from vouchers.cash_register import can_view_cash, visible_cash_policies
    from vouchers.models import TreasuryCashEvent
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_cash(user):
        return []
    labels = {
        "cash_policy_submitted": "Submitted cash policy for independent review",
        "cash_policy_activated": "Activated cash policy",
        "cash_policy_returned": "Returned cash policy for correction",
        "cash_position_submitted": "Submitted cash position for independent review",
        "cash_position_approved": "Approved cash position",
        "cash_position_returned": "Returned cash position for correction",
    }
    events = TreasuryCashEvent.objects.filter(
        policy__in=visible_cash_policies(user), actor=user, actor_department=department,
        action__in=labels, instrument__isnull=True,
    ).select_related("policy__treasury_department", "position")
    tasks = []
    for event in events:
        is_position = event.action.startswith("cash_position_")
        if is_position and (event.position_id is None or event.position.policy_id != event.policy_id):
            continue
        if not is_position and event.position_id is not None:
            continue
        item = event.position if is_position else event.policy
        policy = event.policy
        kind = "treasury-cash-position" if is_position else "treasury-cash-policy"
        event_id = _source_record_identity(f"{kind}-event", event.pk)
        reference = f"{policy.bank_account_code} / {policy.fund_code} · policy v{policy.version}"
        if is_position:
            reference += f" · position {item.as_of_date} v{item.version}"
        label = labels[event.action]
        revision = _projection_checksum({
            "event_id": str(event_id), "action": event.action, "actor_id": event.actor_id,
            "actor_department_id": event.actor_department_id, "at": event.created_at.isoformat(),
            "snapshot": event.snapshot, "reason": event.reason, "source_id": str(item.public_id),
            "current_state": item.status, "reference": reference,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:{kind}-event:{event_id}:completed",
            task_type=f"finance.{kind}.{event.action}.completed.v1", area="Treasury",
            case_id=f"{kind}:{item.public_id}", reference=reference, subject=label,
            transaction_type="Recorded cash-control action", action="View recorded outcome",
            gate=f"The retained event attributes this completed action to you: {label}." + (f" Reason: {event.reason}" if event.reason else ""),
            owner_queue=f"Recorded actor: {user.get_full_name() or user.username}",
            scope=f"{policy.treasury_department.name}; bank {policy.bank_account_code}; fund {policy.fund_code}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since this recorded action. Current source state is shown separately.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_status_display(),
            source_version=f"event-sha256:{revision}", exception="",
            url=reverse("vouchers:cash_policy_detail", kwargs={"public_id": policy.public_id}),
        ))
    return tasks


def completed_report_tasks(user, department, today):
    """Credit retained personal report actions under current run-register scope."""
    from reporting.access import can_view_reporting
    from reporting.models import ReportRunEvent
    from reporting.run_register_exports import visible_report_runs
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_reporting(user):
        return []
    labels = {
        "generated": "Generated report output", "review": "Reviewed report evidence",
        "approve": "Approved report output", "supersede": "Superseded report output",
    }
    events = ReportRunEvent.objects.filter(
        run__in=visible_report_runs(user), actor_id=user.pk, action__in=labels,
    ).exclude(action="generated", run__schedule__isnull=False).select_related("run__definition")
    tasks = []
    for event in events:
        item = event.run
        event_id = _source_record_identity("report-run-event", event.pk)
        label = labels[event.action]
        revision = _projection_checksum({
            "event_id": str(event_id), "actor_id": event.actor_id, "action": event.action,
            "at": event.created_at.isoformat(), "from": event.from_status, "to": event.to_status,
            "note": event.note, "run": str(item.public_id), "state": item.status,
            "checksum": item.checksum, "reproduction_key": item.reproduction_key,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:report-run-event:{event_id}:completed",
            task_type=f"finance.report-run.{event.action}.completed.v1", area="Reporting",
            case_id=f"report-run:{item.public_id}",
            reference=f"{item.definition.name} - {item.period_start} to {item.period_end}",
            subject=label, transaction_type="Recorded report action", action="View recorded outcome",
            gate=f"The retained event attributes this action to your account: {label}.",
            owner_queue="Your recorded report action", scope=f"{department.name}; dataset {item.definition.dataset_key}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained action; report coverage dates are not deadlines.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=item.get_status_display(),
            source_version=f"event-sha256:{revision}", exception="",
            url=reverse("reporting:run_detail", kwargs={"public_id": item.public_id}),
        ))
    return tasks
