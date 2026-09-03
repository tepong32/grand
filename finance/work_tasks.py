from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from uuid import UUID, uuid5

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


def _cutover_date_state(cutover_on, today):
    if cutover_on < today:
        return "Proposed cutover date has passed"
    if cutover_on == today:
        return "Proposed cutover is today"
    return "Proposed cutover is upcoming"


_FIELD_RECORD_NAMESPACE = UUID("9bdf0446-4b9e-4c98-b0c9-eb3e7e9876aa")


def _field_record_identity(source_kind, pk):
    return uuid5(_FIELD_RECORD_NAMESPACE, f"grand.finance.{source_kind}:{pk}")


def _projection_checksum(values):
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _nested_field_task(item, action_key, spec, department, today):
    source_kind = {
        "my_defects": "field-defect",
        "review_defects": "field-defect",
        "my_exercises": "field-exercise",
        "witness_exercises": "field-exercise",
        "my_acceptances": "field-stakeholder",
        "authorize_cutover": "field-cutover",
    }[action_key]
    exact_gates = {
        "my_defects": "This visible defect is Open and names the signed-in user as its correction owner.",
        "review_defects": "This defect awaits resolution review in the acting Finance office, and the signed-in reviewer did not submit its correction.",
        "my_exercises": "This visible exercise is Planned or Returned and names the signed-in user as its owner.",
        "witness_exercises": "This submitted exercise names the signed-in user as independent witness, who is neither its owner nor evidence submitter.",
        "my_acceptances": "This pending exact-scope acceptance belongs to an independently reconciled visible cycle and names the signed-in user as reviewer.",
        "authorize_cutover": "This submitted cutover record belongs to the acting Finance office, and the signed-in authority neither prepared nor submitted it.",
    }
    source_id = _field_record_identity(source_kind, item.pk)
    cycle = item.cycle
    common = {
        "task_id": f"finwork:v1:{source_kind}:{source_id}:{action_key.replace('_', '-')}",
        "task_type": f"finance.{source_kind}.{action_key}.v1",
        "area": "Field operation",
        "case_id": f"{source_kind}:{source_id}",
        "action": spec["next_action"],
        "gate": exact_gates[action_key],
        "scope": f"{cycle.department.name}; {cycle.enabled_scope}",
        "url": reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}),
    }
    if action_key == "my_defects":
        common["url"] = reverse("finance:shadow_defect_resolution", kwargs={"pk": item.pk})
    elif action_key == "my_exercises":
        common["url"] = reverse("finance:cutover_readiness_exercise_result", kwargs={"pk": item.pk})
    elif action_key == "my_acceptances":
        common["url"] = reverse("finance:stakeholder_acceptance_decide", kwargs={"pk": item.pk})
    if source_kind == "field-defect":
        due_on = timezone.localtime(item.correction_due_at).date()
        return FinanceWorkTask(
            **common,
            reference=f"{cycle.code} · defect {item.code}",
            transaction_type=f"Field defect · {item.get_severity_display()}",
            subject=item.summary,
            owner_queue=(
                f"Named defect owner · {cycle.department.name}"
                if action_key == "my_defects"
                else f"Independent reconciliation reviewers · {cycle.department.name}"
            ),
            received_at=item.created_at,
            due_on=due_on,
            due_state=_due_state(due_on, today),
            calendar_basis="Correction due time retained on the defect; no holiday adjustment inferred.",
            age_days=_age_days(item.created_at, today),
            state="Ready",
            source_state=item.get_status_display(),
            source_version=f"updated:{item.updated_at.isoformat()}",
            exception="Correction is past its retained due time." if item.is_overdue else "",
        )
    if source_kind == "field-exercise":
        due_on = timezone.localtime(item.due_at).date()
        exception = "Witness returned this exercise for a governed rerun." if item.status == item.RETURNED else ""
        if item.is_overdue:
            exception = "Exercise evidence is past its retained due time."
        return FinanceWorkTask(
            **common,
            reference=f"{cycle.code} · exercise {item.code}",
            transaction_type=item.get_kind_display(),
            subject=item.title,
            owner_queue=(
                f"Named exercise owner · {cycle.department.name}"
                if action_key == "my_exercises"
                else f"Named independent exercise witness · {cycle.department.name}"
            ),
            received_at=item.created_at,
            due_on=due_on,
            due_state=_due_state(due_on, today),
            calendar_basis="Exercise evidence due time retained on the source; no holiday adjustment inferred.",
            age_days=_age_days(item.created_at, today),
            state="Returned" if item.status == item.RETURNED else "Ready",
            source_state=item.get_status_display(),
            source_version=f"updated:{item.updated_at.isoformat()}",
            exception=exception,
        )
    if source_kind == "field-stakeholder":
        office = f" · {item.office.name}" if item.office_id else ""
        revision = _projection_checksum({
            "assigned_reviewer_id": item.assigned_reviewer_id,
            "cycle_id": item.cycle_id,
            "decision": item.decision,
            "enabled_scope": item.enabled_scope,
            "office_id": item.office_id,
            "stakeholder_kind": item.stakeholder_kind,
            "training_evidence_reference": item.training_evidence_reference,
            "uat_evidence_reference": item.uat_evidence_reference,
        })
        return FinanceWorkTask(
            **common,
            reference=f"{cycle.code} · {item.get_stakeholder_kind_display()}{office}",
            transaction_type="Field stakeholder acceptance",
            subject="Review the retained training, UAT, and exact-scope acceptance evidence.",
            owner_queue="Named stakeholder reviewer",
            received_at=item.created_at,
            due_on=None,
            due_state="No structured target",
            calendar_basis="No decision deadline is stored; follow the locally accepted field plan.",
            age_days=_age_days(item.created_at, today),
            state="Ready",
            source_state=item.get_decision_display(),
            source_version=f"projection-sha256:{revision}",
            exception="",
        )
    due_on = timezone.localtime(item.cutover_at).date()
    return FinanceWorkTask(
        **common,
        reference=f"{cycle.code} · cutover authority",
        transaction_type="Exact-scope cutover authority",
        subject=cycle.title,
        owner_queue=f"Authorized cutover decision-makers · {department.name}",
        received_at=item.submitted_at or item.created_at,
        due_on=due_on,
        due_state=_cutover_date_state(due_on, today),
        calendar_basis="This is the retained proposed cutover date, not an inferred approval deadline.",
        age_days=_age_days(item.submitted_at or item.created_at, today),
        state="Ready",
        source_state=item.get_status_display(),
        source_version=f"submitted:{item.submitted_at.isoformat() if item.submitted_at else 'not-recorded'}",
        exception="",
    )


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
        shadow_action_choices_for_user, shadow_action_queryset,
        shadow_action_record_queryset, visible_shadow_cycles,
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
        if action_key not in role_labels:
            records, _selected, spec = shadow_action_record_queryset(
                user, action_key, queryset=visible,
            )
            tasks.extend(
                _nested_field_task(item, action_key, spec, department, today)
                for item in records
            )
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
        "task_coverage": ("Field-operation cycle and nested-record gates", "Local forms"),
    }
