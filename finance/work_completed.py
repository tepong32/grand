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
