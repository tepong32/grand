from __future__ import annotations

from django.urls import reverse


def completed_accounting_tasks(user, department, today):
    """Successful attributed actions remain history under current source access."""
    from accounting.access import can_view_accounting
    from accounting.models import AccountingAuditEvent, OpeningBalanceEvent, PeriodCloseEvent
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
    tasks = []
    for model, relation, kind, route, labels in specs:
        events = model.objects.filter(
            department_id=department.pk, actor_id=user.pk, action__in=labels,
            **{f"{relation}__department_id": department.pk},
        ).select_related(relation, f"{relation}__period")
        if model is AccountingAuditEvent:
            events = events.exclude(entry__source_type="opening")
        for event in events:
            item = getattr(event, relation)
            event_id = _source_record_identity(f"{kind}-event", event.pk)
            reference = (item.reference if kind == "journal-entry" else
                         item.source_reference if kind == "opening-batch" else f"{item.period} v{item.version}")
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
                owner_queue=f"Recorded actor: {event.actor_label}", scope=f"{department.name}; {item.period}",
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
