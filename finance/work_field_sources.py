"""Personal source-version handoffs, distinct from cycle preparation."""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse


def completed_field_source_tasks(user, department, today):
    from .access import can_view_shadow_cycle
    from .cutover_services import _source_version_data
    from .models import FinanceAuditEvent, FinanceShadowSourceVersion
    from .shadow_register_exports import visible_shadow_cycles
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity
    from vouchers.roles import is_finance_uat_viewer

    if is_finance_uat_viewer(user):
        return []
    cycles = {str(c.pk): c for c in visible_shadow_cycles(user) if can_view_shadow_cycle(user, c)}
    if not cycles:
        return []
    sources = {(str(s.cycle_id), s.version): s for s in FinanceShadowSourceVersion.objects.filter(cycle_id__in=cycles)}
    labels = {
        "shadow_source_staged": "Staged redacted source CSV",
        "shadow_external_source_lock_recorded": "Recorded external source lock",
        "shadow_source_drift_accepted": "Independently accepted source-layout drift",
        "shadow_source_drift_rejected": "Independently rejected source-layout drift",
    }
    events = FinanceAuditEvent.objects.filter(
        target_type="financeshadowcycle", target_id__in=cycles, actor=user, action__in=labels,
    )
    mutable = {"is_current", "review_status", "review_note", "reviewed_by_id", "reviewed_at"}
    tasks = []
    for event in events:
        snapshot = event.snapshot
        if not isinstance(snapshot, dict) or type(snapshot.get("version")) is not int:
            continue
        source = sources.get((event.target_id, snapshot["version"]))
        cycle = cycles[event.target_id]
        if source is None or event.department_id != cycle.department_id:
            continue
        retained = json.loads(json.dumps(_source_version_data(source), cls=DjangoJSONEncoder))
        immutable = retained.keys() - mutable
        # Canonical serialization preserves JSON types as well as exact values.
        if _projection_checksum({k: snapshot.get(k) for k in immutable}) != _projection_checksum({k: retained[k] for k in immutable}):
            continue
        if snapshot.get("is_current") is not True:
            continue
        if event.action in ("shadow_source_staged", "shadow_external_source_lock_recorded"):
            expected_kind = source.UPLOADED_CSV if event.action == "shadow_source_staged" else source.EXTERNAL_LOCK
            initial_status = source.PENDING if source.schema_comparison == source.DRIFT else source.NOT_REQUIRED
            if (source.staged_by_id != event.actor_id or source.intake_kind != expected_kind
                    or snapshot.get("review_status") != initial_status
                    or snapshot.get("reviewed_by_id") is not None or snapshot.get("reviewed_at") is not None):
                continue
        else:
            expected_status = source.ACCEPTED if event.action == "shadow_source_drift_accepted" else source.REJECTED
            if (source.schema_comparison != source.DRIFT or source.review_status != expected_status
                    or source.reviewed_by_id != event.actor_id or source.staged_by_id == event.actor_id
                    or any(snapshot.get(k) != retained[k] for k in mutable - {"is_current"})):
                continue
        source_id = _source_record_identity("field-source", source.pk)
        event_id = _source_record_identity("field-event", event.pk)
        revision = _projection_checksum({"event": event.pk, "snapshot": snapshot, "retained": retained, "cycle_state": cycle.status})
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:field-event:{event_id}:completed", task_type=f"finance.field-source.{event.action}.completed.v1",
            case_id=f"field-source:{source_id}", area="Field operation", reference=f"{cycle.code} - source v{source.version}",
            subject=labels[event.action], transaction_type=source.get_intake_kind_display(), action="View recorded outcome",
            gate="The retained event matches this source version and attributes the staging or independent decision to your account.",
            owner_queue="Your recorded source action", scope=f"{cycle.department.name}; {cycle.enabled_scope}",
            received_at=event.created_at, due_on=None, due_state="Recorded completion",
            calendar_basis="Elapsed calendar days since the retained source action; staging is not approval or a deadline.",
            age_days=_age_days(event.created_at, today), state="Completed", source_state=source.get_review_status_display(),
            source_version=f"event-sha256:{revision}",
            exception="Current source version." if source.is_current else "Superseded source version; current cycle evidence is separate.",
            url=reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}),
        ))
    return tasks
