import json

from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse


def field_plan_task(item, action_key, spec, today):
    from .cutover_services import _plan_data, _readiness_plan_data, _qualification_plan_data
    from .models import FinanceAuditEvent
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    cycle = item.cycle
    kind = spec["source_kind"]
    source_id = _source_record_identity(kind, item.pk)
    data = {
        "reconciliation_plan": _plan_data,
        "readiness_plan": _readiness_plan_data,
        "qualification_plan": _qualification_plan_data,
    }[spec["family"]](item)
    prefix = {
        "reconciliation_plan": "shadow_reconciliation_plan",
        "readiness_plan": "cutover_readiness_plan",
        "qualification_plan": "cutover_qualification_plan",
    }[spec["family"]]
    returned = None
    if item.status == item.RETURNED:
        returned = FinanceAuditEvent.objects.filter(
            department=cycle.department, target_type="financeshadowcycle", target_id=str(cycle.pk),
            action=f"{prefix}_returned", snapshot__plan_id=item.pk,
        ).order_by("-created_at", "-pk").first()
    received = (returned.created_at if returned else None) if item.status == item.RETURNED else (
        item.submitted_at if spec["mode"] == "review" else item.created_at
    )
    exception = (returned.reason if returned else "The retained return event is missing; inspect source history before correction.") if item.status == item.RETURNED else ""
    revision = _projection_checksum(json.loads(json.dumps({
        "plan": data, "return_event": returned.pk if returned else None, "exception": exception,
    }, cls=DjangoJSONEncoder)))
    return FinanceWorkTask(
        task_id=f"finwork:v1:{kind}:{source_id}:{spec['mode']}",
        task_type=f"finance.{kind}.{spec['mode']}.v1", area="Field operation",
        case_id=f"{kind}:{source_id}", reference=f"{cycle.code} - {spec['plan_label']}",
        transaction_type=spec["plan_label"], subject=cycle.title,
        action=spec["next_action"], gate=spec["definition"],
        owner_queue="Field-plan preparers" if spec["mode"] == "prepare" else "Independent field-plan reviewers",
        scope=f"{cycle.department.name}; {cycle.enabled_scope}",
        received_at=received, due_on=None, due_state="No structured target",
        calendar_basis="Elapsed calendar days since preparation, submission or retained return; cycle and run dates are not plan-review deadlines.",
        age_days=_age_days(received, today), state="Returned" if item.status == item.RETURNED else "Ready",
        source_state=item.get_status_display(), source_version=f"projection-sha256:{revision}", exception=exception,
        url=reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}),
    )
