from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime

from django.urls import reverse
from django.utils import timezone


@dataclass(frozen=True)
class FinanceWorkTask:
    """Stable read-only projection of one exact action over an authoritative record."""

    task_id: str
    task_type: str
    area: str
    case_id: str
    reference: str
    transaction_type: str
    subject: str
    action: str
    gate: str
    owner_queue: str
    scope: str
    received_at: datetime
    due_on: date | None
    due_state: str
    calendar_basis: str
    age_days: int
    state: str
    source_state: str
    source_version: str
    exception: str
    url: str

    def as_dict(self):
        return asdict(self)


def _age_days(value, today):
    if value is None:
        return 0
    received = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return max((today - received).days, 0)


def _due_state(due_on, today):
    if due_on is None:
        return "No structured target"
    if due_on < today:
        return "Past planned date"
    if due_on == today:
        return "Planned for today"
    return "Within planned period"


def _local_form_tasks(user, department, today):
    from reporting.local_form_register_exports import (
        local_form_action_choices_for_user, local_form_action_queryset,
    )
    from reporting.models import FinanceLocalFormAcceptance

    role_labels = {
        "needs_mapping": "Local-form preparers",
        "needs_reference": "Local-form preparers",
        "candidate_sections": "Local-form preparers",
        "returned": "Local-form preparers",
        "witness_tests": "Independent local-form witnesses",
        "for_review": "Independent local-form reviewers",
    }
    tasks = []
    for action_key, _label in local_form_action_choices_for_user(user, department):
        queryset, _selected, spec = local_form_action_queryset(user, action_key)
        for item in queryset.select_related("department").order_by("code", "-version", "pk"):
            exception = ""
            if action_key == "returned":
                exception = item.review_note.strip() or "Returned with a retained review decision."
            elif action_key == "needs_mapping":
                exception = "No governed output-template mapping is active for this form."
            elif action_key == "needs_reference":
                exception = "The current blank or safely redacted local reference is not retained."
            elif action_key == "candidate_sections":
                exception = "One or more starter sections still lack a locally evidenced decision."
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:local-form:{item.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.local-form.{action_key}.v1",
                area="Local forms",
                case_id=f"local-form:{item.public_id}",
                reference=f"{item.code} v{item.version}",
                transaction_type="Local Finance form",
                subject=item.name,
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"{role_labels[action_key]} · {department.name}",
                scope=f"{department.name}; form {item.form_number or item.code}",
                received_at=item.created_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="Use the locally accepted deadline instructions on the form record.",
                age_days=_age_days(item.created_at, today),
                state="Returned" if item.status == FinanceLocalFormAcceptance.RETURNED else "Ready",
                source_state=item.get_status_display(),
                source_version=str(item.version),
                exception=exception,
                url=item.get_absolute_url(),
            ))
    return tasks


def _field_operation_tasks(user, department, today):
    from finance.shadow_register_exports import (
        shadow_action_choices_for_user, shadow_action_queryset, visible_shadow_cycles,
    )

    role_labels = {
        "needs_source": "Field-operation preparers",
        "ready_to_prepare": "Field-operation preparers",
        "running": "Field-operation preparers",
        "for_review": "Independent reconciliation reviewers",
    }
    tasks = []
    visible = visible_shadow_cycles(user)
    for action_key, _label in shadow_action_choices_for_user(user, department):
        # Named defects, exercises, stakeholder decisions, and cutover decisions are
        # separate nested source records. They remain group-only until their own
        # record identity is projected instead of pretending the parent cycle is the task.
        if action_key not in role_labels:
            continue
        queryset, _selected, spec = shadow_action_queryset(
            user, action_key, queryset=visible,
        )
        for item in queryset.select_related("department").order_by(
            "-fiscal_year", "-planned_start", "code", "pk",
        ):
            exception = ""
            if action_key == "needs_source":
                exception = "The redacted source checksum or layout signature is incomplete."
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:field-cycle:{item.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.field-cycle.{action_key}.v1",
                area="Field operation",
                case_id=f"field-cycle:{item.public_id}",
                reference=f"{item.code} · FY {item.fiscal_year}",
                transaction_type=item.get_run_kind_display(),
                subject=item.title,
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"{role_labels[action_key]} · {item.department.name}",
                scope=f"{item.department.name}; {item.enabled_scope}",
                received_at=item.created_at,
                due_on=item.planned_end,
                due_state=_due_state(item.planned_end, today),
                calendar_basis="Calendar date retained in the field-cycle plan; no holiday adjustment inferred.",
                age_days=_age_days(item.created_at, today),
                state="Ready",
                source_state=item.get_status_display(),
                source_version=f"updated:{item.updated_at.isoformat()}",
                exception=exception,
                url=reverse("finance:shadow_cycle_detail", kwargs={"pk": item.pk}),
            ))
    return tasks


def finance_work_tasks(user, *, display_limit=100):
    """Return permission-filtered item projections without writing task or source state."""
    department = getattr(getattr(user, "employeeprofile", None), "assigned_department", None)
    if department is None:
        return {"tasks": [], "task_count": 0, "tasks_truncated": False, "task_coverage": ()}
    today = timezone.localdate()
    tasks = _field_operation_tasks(user, department, today)
    tasks.extend(_local_form_tasks(user, department, today))
    tasks.sort(key=lambda task: (task.area, task.reference.lower(), task.task_type, task.task_id))
    task_count = len(tasks)
    return {
        "tasks": [task.as_dict() for task in tasks[:display_limit]],
        "task_count": task_count,
        "tasks_truncated": task_count > display_limit,
        "task_coverage": ("Field-operation cycle gates", "Local forms"),
    }
