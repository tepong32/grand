"""Read-only source-layout review eligibility shared by queues and pages."""

from .access import can_review_shadow_reconciliation, department_for_user
from .models import FinanceShadowCycle, FinanceShadowSourceVersion


def source_drift_review_records(user, *, cycles):
    department = department_for_user(user)
    records = FinanceShadowSourceVersion.objects.all()
    if not department or not can_review_shadow_reconciliation(user, department):
        return records.none()
    return records.filter(
        cycle__in=cycles, cycle__department=department, cycle__status=FinanceShadowCycle.DRAFT,
        is_current=True, schema_comparison=FinanceShadowSourceVersion.DRIFT,
        review_status=FinanceShadowSourceVersion.PENDING,
    ).exclude(staged_by=user).select_related("cycle", "cycle__department", "staged_by")


def source_drift_task(item, spec, today):
    from django.urls import reverse
    from .work_tasks import FinanceWorkTask, _age_days, _projection_checksum, _source_record_identity

    identity = _source_record_identity("field-source", item.pk)
    revision = _projection_checksum({
        "source": item.pk, "version": item.version, "checksum": item.source_checksum,
        "schema": item.schema_signature, "predecessor_schema": item.predecessor_schema_signature,
        "review": item.review_status, "current": item.is_current,
        "staged_by": item.staged_by_id, "at": item.staged_at.isoformat(),
        "cycle": item.cycle_id, "status": item.cycle.status,
    })
    return FinanceWorkTask(
        task_id=f"finwork:v1:field-source:{identity}:review", task_type="finance.field-source.review.v1",
        case_id=f"field-source:{identity}", area="Field operation",
        reference=f"{item.cycle.code} - source v{item.version}", subject="Review changed source headings",
        transaction_type=item.get_intake_kind_display(), action=spec["next_action"], gate=spec["definition"],
        owner_queue="Independent source-layout reviewers", scope=f"{item.cycle.department.name}; {item.cycle.enabled_scope}",
        received_at=item.staged_at, due_on=None, due_state="No target date",
        calendar_basis="Elapsed calendar days since source staging; no review deadline is inferred.",
        age_days=_age_days(item.staged_at, today), state="Ready", source_state=item.get_review_status_display(),
        source_version=f"projection-sha256:{revision}", exception="",
        url=reverse("finance:shadow_source_drift_review", kwargs={"pk": item.pk}),
    )
