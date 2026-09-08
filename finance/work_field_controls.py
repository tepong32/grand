import json

from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.utils import timezone


def field_control_task(item, action_key, spec, today):
    from .cutover_services import _run_data, _qualification_evidence_data
    from .field_control_register import control_cycle
    from .models import FinanceAuditEvent
    from .work_tasks import FinanceWorkTask, _age_days, _due_state, _projection_checksum, _source_record_identity

    cycle = control_cycle(item)
    is_run = spec["family"] == "reconciliation_run"
    kind = spec["source_kind"]
    source_id = _source_record_identity(kind, item.pk)
    data = _run_data(item) if is_run else _qualification_evidence_data(item)
    prefix = "shadow_reconciliation_run" if is_run else "cutover_qualification_evidence"
    source_key = "run_id" if is_run else "evidence_id"
    returned = None
    if item.status == item.RETURNED:
        returned = FinanceAuditEvent.objects.filter(
            department=cycle.department, target_type="financeshadowcycle", target_id=str(cycle.pk),
            action=f"{prefix}_returned", **{f"snapshot__{source_key}": item.pk},
        ).order_by("-created_at", "-pk").first()
    received = (returned.created_at if returned else None) if item.status == item.RETURNED else (
        item.submitted_at if spec["mode"] == "review" else item.created_at
    )
    exception = (returned.reason if returned else "The retained return event is missing; inspect source history before correction.") if item.status == item.RETURNED else ""
    if is_run and item.open_defect_count:
        exception = (exception + f" {item.open_defect_count} open defect(s) remain in the retained run snapshot.").strip()
    revision = _projection_checksum(json.loads(json.dumps({
        "source": data, "parent_cycle_id": cycle.pk, "return_event": returned.pk if returned else None, "exception": exception,
    }, cls=DjangoJSONEncoder)))
    due = timezone.localtime(item.due_at).date() if is_run else None
    reference = f"{cycle.code} - run #{item.sequence}" if is_run else f"{cycle.code} - qualification #{item.sequence}: {item.cycle.code}"
    return FinanceWorkTask(
        task_id=f"finwork:v1:{kind}:{source_id}:{spec['mode']}", task_type=f"finance.{kind}.{spec['mode']}.v1",
        area="Field operation", case_id=f"{kind}:{source_id}", reference=reference,
        transaction_type=spec["label"], subject=cycle.title, action=spec["next_action"], gate=spec["definition"],
        owner_queue="Field evidence preparers" if spec["mode"] == "prepare" else "Independent field evidence reviewers",
        scope=f"{cycle.department.name}; {cycle.enabled_scope}", received_at=received,
        due_on=due, due_state=_due_state(due, today),
        calendar_basis=("Original scheduled-run target including the locally configured grace period; a return does not extend it."
                        if is_run else "Elapsed calendar days since preparation, submission or retained return; no qualification deadline is inferred."),
        age_days=_age_days(received, today), state="Returned" if item.status == item.RETURNED else "Ready",
        source_state=item.get_status_display(), source_version=f"projection-sha256:{revision}", exception=exception,
        url=reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}),
    )
