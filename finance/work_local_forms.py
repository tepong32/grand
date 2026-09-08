from django.urls import reverse


def completed_local_form_tasks(user, department, today):
    from reporting.access import can_view_reporting
    from reporting.models import FinanceLocalFormEvent, FinanceLocalFormTestAttempt
    from vouchers.roles import is_finance_uat_viewer
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    if is_finance_uat_viewer(user) or not can_view_reporting(user):
        return []
    labels = {
        "submitted": "Submitted local form for acceptance", "returned": "Returned local form for correction",
        "accepted": "Accepted local form", "test_attempt_submitted": "Submitted local-form test",
        "test_passed": "Witnessed local-form test pass", "test_failed": "Witnessed local-form test failure",
        "test_not_applicable": "Witnessed local-form test not applicable",
    }
    events = FinanceLocalFormEvent.objects.filter(form__department=department, actor=user, action__in=labels).select_related("form")
    attempts = {(item.form_id, item.category, str(item.attempt)): item
                for item in FinanceLocalFormTestAttempt.objects.filter(form__department=department)}
    tasks = []
    for event in events:
        item = event.form
        label = labels[event.action]
        state = item.get_status_display()
        if event.action.startswith("test_"):
            if not isinstance(event.snapshot, dict):
                continue
            attempt = attempts.get((item.pk, event.snapshot.get("category"), str(event.snapshot.get("attempt"))))
            if attempt is None or attempt.evidence_checksum != event.snapshot.get("evidence_checksum"):
                continue
            actor_id = attempt.created_by_id if event.action == "test_attempt_submitted" else attempt.reviewed_by_id
            if event.actor_id != actor_id:
                continue
            if event.action == "test_attempt_submitted":
                if event.snapshot.get("basis_checksum") != attempt.basis_checksum:
                    continue
            elif event.action != f"test_{attempt.status}":
                continue
            label += f": {attempt.get_category_display()} (attempt {attempt.attempt})"
            state = f"{attempt.get_status_display()}; form {state}"
        event_id = _source_record_identity("local-form-event", event.pk)
        revision = _projection_checksum({
            "event_id": str(event_id), "actor": event.actor_id, "action": event.action,
            "at": event.created_at.isoformat(), "snapshot": event.snapshot, "reason": event.reason,
            "form_id": str(item.public_id), "current_state": state,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:local-form-event:{event_id}:completed",
            task_type=f"finance.local-form.{event.action}.completed.v1", area="Local forms",
            case_id=f"local-form:{item.public_id}", reference=f"{item.code} v{item.version}",
            subject=label, transaction_type="Recorded local-form action", action="View recorded outcome",
            gate=f"The retained event attributes this action to your account: {label}.",
            owner_queue="Your recorded local-form action", scope=f"{department.name}; form {item.form_number or item.code}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained action; no local deadline is inferred.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=state,
            source_version=f"event-sha256:{revision}", exception="",
            url=reverse("reporting:local_form_detail", kwargs={"public_id": item.public_id}),
        ))
    return tasks
