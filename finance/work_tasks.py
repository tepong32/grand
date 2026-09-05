from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5

from django.core.exceptions import ValidationError
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


def _source_record_identity(source_kind, pk):
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
    source_id = _source_record_identity(source_kind, item.pk)
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


def _setup_tasks(user, department, today):
    from finance.setup_register import setup_attention_choices_for_user, setup_attention_queryset

    role_labels = {
        "needs_preparation": "Finance configuration preparers",
        "awaiting_review": "Independent Accounting configuration approvers",
        "ready_to_schedule": "Finance configuration approvers",
        "ready_to_activate": "Finance configuration approvers",
    }
    tasks = []
    for action_key, _label in setup_attention_choices_for_user(user, department):
        queryset, _selected, spec = setup_attention_queryset(user, action_key, as_of=today)
        for item in queryset.order_by("-fiscal_year", "code", "-version", "pk"):
            source_id = _source_record_identity("setup-release", item.pk)
            received_at = item.created_at
            due_on = None
            due_state = "No structured target"
            calendar_basis = "The retained effective date is not treated as an action deadline."
            if action_key == "awaiting_review":
                received_at = item.submitted_at or item.updated_at
            elif action_key == "ready_to_schedule":
                received_at = item.approved_at or item.updated_at
                due_on = item.effective_from
                due_state = "Future effectivity awaiting scheduling"
                calendar_basis = "Retained effective date; it is not an inferred approval deadline."
            elif action_key == "ready_to_activate":
                received_at = item.approved_at or item.updated_at
                due_on = item.effective_from
                due_state = "Effectivity window is open"
                calendar_basis = "Retained effective period; activation still requires its governed readiness gate."
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:setup-release:{source_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.setup-release.{action_key}.v1",
                area="Finance setup",
                case_id=f"setup-release:{source_id}",
                reference=f"{item.code} v{item.version} · FY {item.fiscal_year}",
                transaction_type="Finance configuration release",
                subject=item.title,
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"{role_labels[action_key]} · {department.name}",
                scope=f"{department.name}; FY {item.fiscal_year}; effectivity {item.effective_from.isoformat()}",
                received_at=received_at,
                due_on=due_on,
                due_state=due_state,
                calendar_basis=calendar_basis,
                age_days=_age_days(received_at, today),
                state="Ready",
                source_state=item.get_status_display(),
                source_version=f"updated:{item.updated_at.isoformat()}",
                exception="",
                url=reverse("finance:release_detail", kwargs={"pk": item.pk}),
            ))
    return tasks


def _discovery_tasks(user, department, today):
    from finance.discovery_register import discovery_action_choices_for_user, discovery_action_queryset
    from finance.models import FinanceDiscoveryDecision

    tasks = []
    for action_key, _label in discovery_action_choices_for_user(user):
        queryset, _selected, spec = discovery_action_queryset(user, action_key)
        for item in queryset.order_by("phase", "code", "-version", "pk"):
            if action_key == "my_reviews":
                received_at = item.submitted_at or item.updated_at
            elif item.status == FinanceDiscoveryDecision.RETURNED:
                received_at = item.reviewed_at or item.updated_at
            else:
                received_at = item.created_at
            due_state = _due_state(item.due_date, today)
            exception = ""
            if item.status == FinanceDiscoveryDecision.RETURNED:
                exception = "The named reviewer returned this decision for correction."
            elif item.blocks_affected_scope:
                exception = "This unresolved decision blocks only its named affected scope."
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:discovery-decision:{item.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.discovery-decision.{action_key}.v1",
                area="Finance decisions",
                case_id=f"discovery-decision:{item.public_id}",
                reference=f"{item.code} v{item.version} · {item.phase}",
                transaction_type=item.get_coverage_kind_display(),
                subject=item.question,
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=(
                    f"Decision owners / discovery managers · {department.name}"
                    if action_key == "needs_preparation"
                    else "Named independent decision reviewer"
                ),
                scope=f"{item.department.name}; {item.affected_scope}",
                received_at=received_at,
                due_on=item.due_date,
                due_state=due_state,
                calendar_basis=(
                    "Retained local review target; no working-day or holiday adjustment inferred."
                    if item.due_date
                    else "No review target is stored; follow the locally accepted discovery plan."
                ),
                age_days=_age_days(received_at, today),
                state="Returned" if item.status == FinanceDiscoveryDecision.RETURNED else "Ready",
                source_state=item.get_status_display(),
                source_version=f"updated:{item.updated_at.isoformat()}",
                exception=exception,
                url=reverse("finance:discovery_decision_detail", kwargs={"public_id": item.public_id}),
            ))
    return tasks


def _budget_control_exception(item):
    difference = item.control_difference
    if difference:
        return f"Control difference is {difference:.2f}; the source workflow must reconcile it to zero before posting."
    if item.status == item.RETURNED:
        return "This record was returned with a retained correction reason."
    return ""


def _budget_tasks(user, department, today):
    from budget.access import has_budget_permission
    from budget.annual_exports import apply_annual_filters, next_annual_action
    from budget.control_exports import (
        apply_allotment_filters, apply_obligation_filters,
        next_allotment_action, next_obligation_action, obligation_scope_for_user,
    )
    from budget.models import AllotmentReleaseOrder, BudgetVersion, ObligationRequest
    from vouchers.roles import is_finance_uat_viewer

    tasks = []
    if is_finance_uat_viewer(user):
        return tasks
    version_specs = (
        (
            has_budget_permission(user, "prepare_budget_proposals"),
            "needs_preparation", "preparation", "Budget proposal preparers",
            "Draft or returned budget versions available to a proposal preparer.",
        ),
        (
            has_budget_permission(user, "review_budget_proposals"),
            "awaiting_proposal_review", "review", "Independent Budget proposal reviewers",
            "This submitted version awaits review, and the signed-in reviewer did not submit it.",
        ),
    )
    for allowed, attention, action_key, queue_label, gate in version_specs:
        if not allowed:
            continue
        queryset, _kind, _status, _selected = apply_annual_filters(
            BudgetVersion.objects.filter(department_id=department.pk),
            attention=attention, actor=user,
        )
        for item in queryset.select_related("fiscal_year", "budget_call").order_by(
            "-fiscal_year__year", "kind", "-version", "pk",
        ):
            received_at = item.submitted_at if action_key == "review" else item.created_at
            if item.status == BudgetVersion.RETURNED:
                received_at = item.decided_at or item.updated_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:budget-version:{item.public_id}:{action_key}",
                task_type=f"finance.budget-version.{action_key}.v1",
                area="Budget",
                case_id=f"budget-version:{item.public_id}",
                reference=f"FY {item.fiscal_year.year} · {item.get_kind_display()} v{item.version}",
                transaction_type=item.get_kind_display(),
                subject=item.title,
                action=next_annual_action(item),
                gate=gate,
                owner_queue=f"{queue_label} · {department.name}",
                scope=(
                    f"{department.name}; {item.requesting_department_label or 'consolidated / LGU-wide'}"
                ),
                received_at=received_at or item.updated_at,
                due_on=item.budget_call.proposal_due_on,
                due_state=_due_state(item.budget_call.proposal_due_on, today),
                calendar_basis="Proposal due date retained on the governed Budget call; no holiday adjustment inferred.",
                age_days=_age_days(received_at or item.updated_at, today),
                state="Returned" if item.status == BudgetVersion.RETURNED else "Ready",
                source_state=item.get_status_display(),
                source_version=f"state:{item.state_version};updated:{item.updated_at.isoformat()}",
                exception=(
                    "This version was returned with a retained correction reason."
                    if item.status == BudgetVersion.RETURNED else ""
                ),
                url=reverse("budget:version_detail", kwargs={"public_id": item.public_id}),
            ))

    allotment_specs = (
        (
            has_budget_permission(user, "prepare_allotment_releases"),
            "needs_preparation", "preparation", "Allotment order preparers",
            "This draft or returned order is editable in the acting Budget office before submission.",
        ),
        (
            has_budget_permission(user, "approve_allotment_releases"),
            "awaiting_review", "review", "Independent allotment reviewers",
            "This submitted order awaits post-or-return review, and the signed-in reviewer did not submit it.",
        ),
    )
    for allowed, attention, action_key, queue_label, gate in allotment_specs:
        if not allowed:
            continue
        queryset, _kind, _status, _selected = apply_allotment_filters(
            AllotmentReleaseOrder.objects.filter(department_id=department.pk),
            attention=attention, actor=user,
        )
        for item in queryset.select_related("fiscal_year", "authorization").prefetch_related("lines").order_by(
            "-fiscal_year__year", "-effective_date", "-created_at", "pk",
        ):
            received_at = item.submitted_at if action_key == "review" else item.created_at
            if item.status == AllotmentReleaseOrder.RETURNED:
                received_at = item.updated_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:allotment-order:{item.public_id}:{action_key}",
                task_type=f"finance.allotment-order.{action_key}.v1",
                area="Budget",
                case_id=f"allotment-order:{item.public_id}",
                reference=f"{item.order_number} · FY {item.fiscal_year.year}",
                transaction_type=item.get_kind_display(),
                subject=item.purpose,
                action=next_allotment_action(item),
                gate=gate,
                owner_queue=f"{queue_label} · {department.name}",
                scope=f"{department.name}; authority {item.authorization.ordinance_number}; effective {item.effective_date}",
                received_at=received_at or item.updated_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="The retained effective date is a ledger-control date, not an inferred action deadline.",
                age_days=_age_days(received_at or item.updated_at, today),
                state="Returned" if item.status == AllotmentReleaseOrder.RETURNED else "Ready",
                source_state=item.get_status_display(),
                source_version=f"state:{item.state_version};updated:{item.updated_at.isoformat()}",
                exception=_budget_control_exception(item),
                url=reverse("budget:allotment_detail", kwargs={"public_id": item.public_id}),
            ))

    can_view_registry = has_budget_permission(user, "view_obligation_registry")
    can_certify = has_budget_permission(user, "certify_obligations")
    can_initiate = has_budget_permission(user, "initiate_obligation_requests")
    obligation_specs = (
        (
            can_initiate and not (can_view_registry or can_certify),
            "needs_preparation", "preparation", "Requesting-office obligation preparers",
            "This own-office draft or returned request remains editable before certification.",
        ),
        (
            can_certify,
            "awaiting_certification", "certification", "Independent Budget obligation certifiers",
            "This submitted request awaits certification, and the signed-in certifier did not submit it.",
        ),
    )
    for allowed, attention, action_key, queue_label, gate in obligation_specs:
        if not allowed:
            continue
        queryset, _kind, _form, _status, _selected = apply_obligation_filters(
            obligation_scope_for_user(user), attention=attention, actor=user,
        )
        for item in queryset.select_related("fiscal_year", "authorization").prefetch_related("lines").order_by(
            "-fiscal_year__year", "-obligation_date", "-created_at", "pk",
        ):
            received_at = item.submitted_at if action_key == "certification" else item.created_at
            if item.status == ObligationRequest.RETURNED:
                received_at = item.updated_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:obligation-request:{item.public_id}:{action_key}",
                task_type=f"finance.obligation-request.{action_key}.v1",
                area="Budget",
                case_id=f"obligation-request:{item.public_id}",
                reference=f"{item.obligation_number or item.request_reference} · FY {item.fiscal_year.year}",
                transaction_type=f"{item.get_form_type_display()} · {item.get_kind_display()}",
                subject=f"{item.claimant_payee} · {item.particulars}",
                action=next_obligation_action(item),
                gate=gate,
                owner_queue=f"{queue_label} · {department.name}",
                scope=f"Budget: {item.department_label}; requesting office: {item.requesting_department_label}",
                received_at=received_at or item.updated_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="The obligation date is a transaction date, not an inferred action deadline.",
                age_days=_age_days(received_at or item.updated_at, today),
                state="Returned" if item.status == ObligationRequest.RETURNED else "Ready",
                source_state=item.get_status_display(),
                source_version=f"state:{item.state_version};updated:{item.updated_at.isoformat()}",
                exception=_budget_control_exception(item),
                url=reverse("budget:obligation_detail", kwargs={"public_id": item.public_id}),
            ))
    return tasks


def _payable_tasks(user, department, today):
    from vouchers.case_exports import payable_action_choices_for_user, payable_action_queryset
    from vouchers.models import PayableDocumentEvidence, PayableIntake
    from vouchers.services import payable_relationship_summary

    queue_labels = {
        "preparation": "Requesting-office payable preparers",
        "review": "Independent Accounting payable reviewers",
    }
    tasks = []
    for action_key, _label in payable_action_choices_for_user(user):
        queryset, _selected, spec = payable_action_queryset(user, action_key)
        for item in queryset.select_related(
            "requesting_department", "current_department", "payable_intake",
        ).prefetch_related("payable_document_evidence").order_by("-updated_at", "-pk"):
            intake = getattr(item, "payable_intake", None)
            summary = payable_relationship_summary(item)
            evidence = list(item.payable_document_evidence.all())
            pending_count = sum(row.status == PayableDocumentEvidence.PENDING for row in evidence)
            exception_parts = []
            if intake is None:
                exception_parts.append(
                    "The payable intake record is missing; stop and route this data-integrity exception for repair."
                )
            if item.obligation_binding_status != item.BINDING_LINKED:
                exception_parts.append(
                    f"Authoritative obligation link is {item.get_obligation_binding_status_display().lower()}."
                )
            if summary["difference"]:
                exception_parts.append(
                    f"Claim-to-allocation control difference is {summary['difference']:.2f}; reconcile it to zero."
                )
            if pending_count:
                exception_parts.append(f"{pending_count} documentary requirement(s) remain pending.")
            if intake is not None and intake.duplicate_warning and not intake.duplicate_review_note.strip():
                exception_parts.append("A duplicate warning still needs a recorded human review note.")
            if intake is not None and intake.status == PayableIntake.RETURNED:
                exception_parts.append("Accounting returned this same intake for governed correction.")
            projection_revision = _projection_checksum({
                "binding_error": item.obligation_binding_error,
                "binding_status": item.obligation_binding_status,
                "case_state_version": item.state_version,
                "claim_amount": str(intake.claim_amount) if intake is not None else "",
                "claim_reference": intake.claim_reference if intake is not None else "",
                "duplicate_review_note": intake.duplicate_review_note if intake is not None else "",
                "duplicate_warning": intake.duplicate_warning if intake is not None else "",
                "evidence": [
                    [row.pk, row.status, row.evidence_reference, row.decision_note, row.recorded_at.isoformat() if row.recorded_at else ""]
                    for row in evidence
                ],
                "intake_status": intake.status if intake is not None else "missing",
                "relationship": [
                    [row.pk, row.version, row.status, str(row.allocated_amount), row.change_reason]
                    for row in summary["allocations"]
                ],
            })
            received_at = (
                (intake.submitted_at if action_key == "review" else intake.prepared_at)
                if intake is not None else item.updated_at
            )
            if intake is not None and intake.status == PayableIntake.RETURNED:
                received_at = intake.reviewed_at or item.updated_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:payable-intake:{item.public_id}:{action_key}",
                task_type=f"finance.payable-intake.{action_key}.v1",
                area="Voucher case",
                case_id=f"voucher-case:{item.public_id}",
                reference=(
                    f"{item.reference_code} · {item.authoritative_obligation_number or 'obligation link pending'}"
                ),
                transaction_type=item.transaction_type.replace("-", " ").replace("_", " ").title(),
                subject=f"{item.payee_name} · {item.particulars}",
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"{queue_labels[action_key]} · {department.name}",
                scope=(
                    f"Requesting office: {item.requesting_department.name}; "
                    f"current office: {item.current_department.name}"
                ),
                received_at=received_at or item.updated_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="No payable action deadline is stored; follow the locally accepted voucher calendar.",
                age_days=_age_days(received_at or item.updated_at, today),
                state="Returned" if intake is not None and intake.status == PayableIntake.RETURNED else "Ready",
                source_state=(
                    f"{item.get_current_stage_display()} · {intake.get_status_display()}"
                    if intake is not None else f"{item.get_current_stage_display()} · intake record missing"
                ),
                source_version=f"projection-sha256:{projection_revision}",
                exception=" ".join(exception_parts),
                url=item.get_absolute_url(),
            ))
    return tasks


def _dv_custody_tasks(user, department, today):
    from vouchers.case_exports import (
        DV_ACTIVE_PRINT_STATES, dv_custody_action_choices_for_user,
        dv_custody_action_queryset, dv_signature_task_queryset,
    )
    from vouchers.models import VoucherPrintJob

    queue_labels = {
        "dv_preparation": "Accounting DV preparers",
        "signing_copy": "Controlled signing-copy preparers",
        "record_print": "Controlled print operators",
        "assemble_packet": "Finance packet and TracePoint custodians",
    }
    tasks = []
    for action_key, _label in dv_custody_action_choices_for_user(user):
        queryset, _selected, spec = dv_custody_action_queryset(user, action_key)
        for item in queryset.select_related(
            "requesting_department", "current_department", "voucher_template",
            "disbursement_voucher", "obligation", "payable_intake",
        ).prefetch_related(
            "payable_document_evidence", "print_jobs", "signature_tasks",
        ).order_by("-updated_at", "-pk"):
            obligation = getattr(item, "obligation", None)
            intake = getattr(item, "payable_intake", None)
            voucher = getattr(item, "disbursement_voucher", None)
            active_jobs = [job for job in item.print_jobs.all() if job.status in DV_ACTIVE_PRINT_STATES]
            job = sorted(active_jobs, key=lambda row: (row.version, row.pk), reverse=True)[0] if active_jobs else None
            exceptions = []
            if action_key == "dv_preparation":
                if obligation is None:
                    exceptions.append("The certified-obligation compatibility record is missing; stop for data repair.")
                if item.payable_document_evidence.exists() and (
                    intake is None or intake.status != intake.READY
                ):
                    exceptions.append("The transaction-specific payable intake is not Accounting-accepted.")
            elif action_key == "signing_copy":
                if voucher is None:
                    exceptions.append("The prepared DV record is missing; stop for data repair.")
            elif job is None:
                exceptions.append("The expected active print-control record is missing; stop for data repair.")
            if voucher is not None:
                amount_difference = voucher.gross_amount - voucher.total_deductions - voucher.net_amount
                if amount_difference != 0:
                    exceptions.append(
                        f"DV gross less deductions does not equal net; unexplained difference is {amount_difference:.2f}. Stop and repair the source evidence."
                    )
                if obligation is not None and voucher.gross_amount != obligation.certified_amount:
                    exceptions.append(
                        "DV gross does not equal the certified-obligation amount; stop and use the governed correction route."
                    )
            print_revision = [
                [
                    row.pk, row.version, row.status, row.output_checksum, row.signature_round,
                    row.copy_count, row.printer_or_form_stock, row.print_note,
                    row.printed_by_id, row.packet_reference, row.tracepoint_item_id,
                    row.custody_manifest, row.custody_confirmed_by_id, row.prepared_at.isoformat(),
                    row.printed_at.isoformat() if row.printed_at else "",
                    row.custody_confirmed_at.isoformat() if row.custody_confirmed_at else "",
                ]
                for row in item.print_jobs.all()
            ]
            signature_revision = [
                [row.pk, row.round_number, row.sequence, row.status, row.recorded_at.isoformat() if row.recorded_at else ""]
                for row in item.signature_tasks.all()
            ]
            projection_revision = _projection_checksum({
                "case_state_version": item.state_version,
                "dv": [
                    voucher.dv_number, voucher.voucher_date.isoformat(), str(voucher.gross_amount),
                    str(voucher.total_deductions), str(voucher.net_amount), voucher.prepared_by_id,
                ] if voucher is not None else [],
                "intake_status": intake.status if intake is not None else "",
                "obligation": [obligation.obr_number, str(obligation.certified_amount), obligation.certified_by_id]
                if obligation is not None else [],
                "print_jobs": print_revision,
                "signature_tasks": signature_revision,
                "template_checksum": item.voucher_template.workbook_checksum if item.voucher_template_id else "",
            })
            received_at = item.updated_at
            if job is not None:
                received_at = {
                    "record_print": job.prepared_at,
                    "assemble_packet": job.printed_at,
                }.get(action_key) or item.updated_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:dv-custody:{item.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.dv-custody.{action_key}.v1",
                area="Voucher case",
                case_id=f"voucher-case:{item.public_id}",
                reference=(
                    f"{item.reference_code} · {voucher.dv_number if voucher is not None else 'DV not yet numbered'}"
                ),
                transaction_type=item.transaction_type.replace("-", " ").replace("_", " ").title(),
                subject=f"{item.payee_name} · {item.particulars}",
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"{queue_labels[action_key]} · {department.name}",
                scope=(
                    f"Requesting office: {item.requesting_department.name}; "
                    f"current office: {item.current_department.name}"
                ),
                received_at=received_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="No DV/custody action deadline is stored; follow the locally accepted paper route.",
                age_days=_age_days(received_at, today),
                state="Ready",
                source_state=(
                    f"{item.get_current_stage_display()}"
                    + (f" · {job.get_status_display()} · print v{job.version}" if job is not None else "")
                ),
                source_version=f"projection-sha256:{projection_revision}",
                exception=" ".join(exceptions),
                url=item.get_absolute_url(),
            ))

    for signature in dv_signature_task_queryset(user):
        item = signature.case
        source_id = _source_record_identity("wet-signature", signature.pk)
        ready_jobs = [
            row for row in item.print_jobs.all()
            if row.status == VoucherPrintJob.AWAITING_SIGNATURES
            and row.signature_round == signature.round_number
        ]
        job = sorted(ready_jobs, key=lambda row: (row.version, row.pk), reverse=True)[0] if ready_jobs else None
        received_at = job.custody_confirmed_at if job is not None else item.updated_at
        revision = _projection_checksum({
            "case_state_version": item.state_version,
            "custody_department_id": signature.custody_department_id,
            "custody_instructions": signature.custody_instructions,
            "position": signature.position_snapshot,
            "print_checksum": job.output_checksum if job is not None else "",
            "role": signature.role_code,
            "round": signature.round_number,
            "sequence": signature.sequence,
            "signatory": signature.signatory_name_snapshot,
            "status": signature.status,
        })
        tasks.append(FinanceWorkTask(
            task_id=f"finwork:v1:wet-signature:{source_id}:record-return",
            task_type="finance.wet-signature.record-return.v1",
            area="Voucher case",
            case_id=f"wet-signature:{source_id}",
            reference=f"{item.reference_code} · signature round {signature.round_number}, step {signature.sequence}",
            transaction_type="Wet-signature custody",
            subject=f"{signature.signatory_name_snapshot} · {signature.position_snapshot or signature.role_code}",
            action="Confirm the physical evidence, then record this returned wet-signature step on the shared case.",
            gate="This is the earliest pending signature in the current round, and any required signing copy and TracePoint packet are ready.",
            owner_queue=f"Wet-signature return recorders · {department.name}",
            scope=(
                f"Current office: {item.current_department.name}; custody office: "
                f"{signature.custody_department.name if signature.custody_department_id else item.current_department.name}"
            ),
            received_at=received_at,
            due_on=None,
            due_state="No structured target",
            calendar_basis="No wet-signature return deadline is stored; follow the locally accepted physical-custody route.",
            age_days=_age_days(received_at, today),
            state="Ready",
            source_state=signature.get_status_display(),
            source_version=f"projection-sha256:{revision}",
            exception="A screen action records receipt evidence; it is not the wet signature itself.",
            url=item.get_absolute_url(),
        ))
    return tasks


def _accounting_validation_tasks(user, department, today):
    from finance.models import FinancePostingRule
    from vouchers.case_exports import (
        accounting_validation_action_choices_for_user,
        accounting_validation_action_queryset,
    )
    from vouchers.models import PayableIntake, VoucherPrintJob

    tasks = []
    for action_key, _label in accounting_validation_action_choices_for_user(user):
        queryset, _selected, spec = accounting_validation_action_queryset(user, action_key)
        queryset = queryset.select_related(
            "requesting_department", "current_department", "configuration_release",
            "voucher_template", "disbursement_voucher", "obligation", "payable_intake",
        ).prefetch_related(
            "obligation__allocation_lines", "print_jobs", "control_overrides",
        )
        for item in queryset.order_by("-updated_at", "-pk"):
            voucher = getattr(item, "disbursement_voucher", None)
            obligation = getattr(item, "obligation", None)
            intake = getattr(item, "payable_intake", None)
            allocation_lines = list(obligation.allocation_lines.all()) if obligation is not None else []
            print_jobs = list(item.print_jobs.all())
            exceptions = []
            if voucher is None:
                exceptions.append("The prepared DV record is missing; stop and route this data-integrity exception for repair.")
            if obligation is None:
                exceptions.append("The certified-obligation record is missing; stop and route this data-integrity exception for repair.")
            if voucher is not None:
                amount_difference = voucher.gross_amount - voucher.total_deductions - voucher.net_amount
                if amount_difference != 0:
                    exceptions.append(
                        f"DV gross less deductions does not equal net; unexplained difference is {amount_difference:.2f}. Stop before validation."
                    )
                if obligation is not None and voucher.gross_amount != obligation.certified_amount:
                    exceptions.append(
                        "DV gross does not equal the certified-obligation amount; stop and use the governed correction route."
                    )
                allocation_total = sum((line.amount for line in allocation_lines), start=Decimal("0.00"))
                if allocation_total != voucher.gross_amount:
                    exceptions.append(
                        f"Certified allocation lines do not equal DV gross; control difference is "
                        f"{allocation_total - voucher.gross_amount:.2f}. Stop before validation."
                    )
            if item.voucher_template_id and item.voucher_template.controlled_print_required:
                latest_job = max(print_jobs, key=lambda row: (row.version, row.pk)) if print_jobs else None
                if latest_job is None or latest_job.status != VoucherPrintJob.SIGNED_PACKET_RETURNED:
                    exceptions.append(
                        "The latest controlled signing copy has not returned as a signed TracePoint-linked packet."
                    )
            if intake is not None and intake.status != PayableIntake.READY:
                exceptions.append("The payable intake is not Accounting-accepted and payment-ready.")

            event_kind = FinancePostingRule.RECOGNITION
            if intake is not None:
                event_kind = {
                    PayableIntake.RECOGNIZE_WITH_DV: FinancePostingRule.RECOGNITION,
                    PayableIntake.LIQUIDATION_DECISION: FinancePostingRule.LIQUIDATION,
                }.get(intake.recognition_decision)
                if not event_kind:
                    exceptions.append(
                        "The payable intake has no DV-validation recognition route; use the configured earlier-accrual or settlement workflow."
                    )
            variant = None
            posting_rule = None
            if item.configuration_release_id is None:
                exceptions.append("No governed Finance Setup release is pinned to this voucher.")
            else:
                variant = item.configuration_release.transaction_variants.filter(
                    code=item.transaction_type,
                    status__in=("approved", "scheduled", "active", "superseded"),
                ).first()
                if variant is None:
                    exceptions.append("The pinned Finance Setup release has no governed variant for this transaction type.")
                elif event_kind:
                    posting_rule = variant.posting_rules.filter(event_kind=event_kind).first()
                    if posting_rule is None:
                        exceptions.append("The governed transaction variant has no posting rule for this accounting event.")
                    elif (
                        event_kind == FinancePostingRule.RECOGNITION
                        and posting_rule.recognition_point != FinancePostingRule.DV_VALIDATION
                    ):
                        exceptions.append("The governed recognition point is not DV validation; do not post it at this stage.")

            projection_revision = _projection_checksum({
                "allocations": [
                    [line.pk, line.fund_code, line.responsibility_center_code, line.account_code, str(line.amount)]
                    for line in allocation_lines
                ],
                "case_state_version": item.state_version,
                "dv": [
                    voucher.dv_number, voucher.voucher_date.isoformat(), str(voucher.gross_amount),
                    str(voucher.total_deductions), str(voucher.net_amount), voucher.prepared_by_id,
                ] if voucher is not None else [],
                "intake": [
                    intake.status, intake.recognition_decision, intake.recognition_basis,
                    intake.obligation_adjustment_decision, intake.obligation_adjustment_basis,
                ] if intake is not None else [],
                "obligation": [obligation.obr_number, str(obligation.certified_amount), obligation.certified_by_id]
                if obligation is not None else [],
                "posting_rule": [posting_rule.pk, posting_rule.created_at.isoformat()]
                if posting_rule is not None else [],
                "print_jobs": [
                    [row.pk, row.version, row.status, row.output_checksum, row.packet_reference, row.tracepoint_item_id]
                    for row in print_jobs
                ],
            })
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:accounting-validation:{item.public_id}:validation",
                task_type="finance.accounting-validation.validation.v1",
                area="Accounting",
                case_id=f"voucher-case:{item.public_id}",
                reference=(
                    f"{item.reference_code} · {voucher.dv_number if voucher is not None else 'DV record missing'}"
                ),
                transaction_type=item.transaction_type.replace("-", " ").replace("_", " ").title(),
                subject=f"{item.payee_name} · {item.particulars}",
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"Independent Accounting voucher validators · {department.name}",
                scope=f"Requesting office: {item.requesting_department.name}; current office: {item.current_department.name}",
                received_at=item.updated_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="No Accounting-validation deadline is stored; follow the locally accepted voucher calendar.",
                age_days=_age_days(item.updated_at, today),
                state="Exception" if exceptions else "Ready",
                source_state=item.get_current_stage_display(),
                source_version=f"projection-sha256:{projection_revision}",
                exception=" ".join(exceptions),
                url=item.get_absolute_url(),
            ))
    return tasks


def _journal_tasks(user, department, today):
    from accounting.journal_exports import (
        journal_action_choices_for_user, journal_action_queryset, next_journal_action,
    )
    from accounting.models import AccountingPeriod

    tasks = []
    queue_labels = {
        "preparation": "Accounting JEV preparers",
        "posting": "Independent Accounting JEV posters",
    }
    for action_key, _label in journal_action_choices_for_user(user):
        queryset, _selected = journal_action_queryset(user, action_key)
        queryset = queryset.select_related("period", "fund", "reversal_of").prefetch_related(
            "lines__account", "lines__responsibility_center", "subsidiary_lines", "audit_events",
        )
        for item in queryset.order_by("-entry_date", "-pk"):
            lines = list(item.lines.all())
            subsidiary_lines = list(item.subsidiary_lines.all())
            events = list(item.audit_events.all())
            latest_return = next((event for event in events if event.action == "returned"), None)
            total_debit = sum((line.debit for line in lines), start=Decimal("0.00"))
            total_credit = sum((line.credit for line in lines), start=Decimal("0.00"))
            difference = total_debit - total_credit
            exceptions = []
            if len(lines) < 2:
                exceptions.append("Fewer than two journal lines are present; stop before submission or posting.")
            if total_debit <= 0:
                exceptions.append("Total debit is not positive; stop before submission or posting.")
            if difference != 0:
                exceptions.append(
                    f"Debit and credit do not balance; control difference is {difference:.2f}. Stop before submission or posting."
                )
            if item.period.status != AccountingPeriod.OPEN:
                exceptions.append("The selected Accounting period is closed; use the governed open-period correction route.")
            if latest_return is not None:
                exceptions.append(f"Returned correction reason: {latest_return.reason}")
                if item.source_reference:
                    exceptions.append(
                        "This source-generated draft cannot be line-edited; discard it and recreate it from the corrected source evidence."
                    )
            projection_revision = _projection_checksum({
                "entry": [
                    item.reference, item.entry_date.isoformat(), item.period_id, item.period.status,
                    item.fund_id, item.source_type, item.source_reference, item.description,
                    item.status, item.created_by_id, item.submitted_by_id,
                ],
                "events": [
                    [event.pk, event.action, event.actor_id, event.reason, event.created_at.isoformat()]
                    for event in events
                ],
                "lines": [
                    [
                        line.pk, line.sequence, line.account_id, line.responsibility_center_id,
                        str(line.debit), str(line.credit), line.memo,
                    ]
                    for line in lines
                ],
                "source_snapshot": item.source_snapshot,
                "subsidiary_lines": [
                    [
                        row.pk, row.journal_line_id, row.category, row.reference_key,
                        row.source_code, str(row.debit), str(row.credit), row.source_snapshot,
                    ]
                    for row in subsidiary_lines
                ],
            })
            received_at = item.submitted_at if action_key == "posting" else item.created_at
            if latest_return is not None and action_key == "preparation":
                received_at = latest_return.created_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:journal-entry:{item.public_id}:{action_key}",
                task_type=f"finance.journal-entry.{action_key}.v1",
                area="Accounting",
                case_id=f"journal-entry:{item.public_id}",
                reference=f"{item.reference} · {item.entry_date.isoformat()}",
                transaction_type=item.get_source_type_display(),
                subject=item.description,
                action=next_journal_action(item),
                gate=(
                    "This draft belongs to the acting Accounting office and is available to an authorized JEV preparer."
                    if action_key == "preparation" else
                    "This submitted JEV belongs to the acting Accounting office and excludes the preparer and submitter unless a governed exemption applies."
                ),
                owner_queue=f"{queue_labels[action_key]} · {department.name}",
                scope=f"{department.name}; {item.period}; fund {item.fund.code}",
                received_at=received_at or item.updated_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="The JEV date is a ledger date, not an inferred action deadline.",
                age_days=_age_days(received_at or item.updated_at, today),
                state="Returned" if latest_return is not None else ("Exception" if exceptions else "Ready"),
                source_state=item.get_status_display(),
                source_version=f"projection-sha256:{projection_revision}",
                exception=" ".join(exceptions),
                url=reverse("accounting:entry_detail", kwargs={"public_id": item.public_id}),
            ))
    return tasks


def _treasury_payment_tasks(user, department, today):
    from vouchers.case_exports import (
        treasury_payment_action_choices_for_user, treasury_payment_action_queryset,
    )
    from vouchers.models import BankAdviceBatch, PaymentInstrument

    tasks = []
    for action_key, _label in treasury_payment_action_choices_for_user(user):
        queryset, _selected, spec = treasury_payment_action_queryset(user, action_key)
        queryset = queryset.select_related(
            "requesting_department", "current_department", "configuration_release",
            "disbursement_voucher", "obligation", "payee",
        ).prefetch_related(
            "obligation__allocation_lines", "payment_instruments__current_advice_batch",
            "payment_instruments__exceptions", "payee__authorized_claimants",
            "configuration_release__items",
        )
        for item in queryset.order_by("-updated_at", "-pk"):
            voucher = getattr(item, "disbursement_voucher", None)
            obligation = getattr(item, "obligation", None)
            instruments = list(item.payment_instruments.all())
            live_instruments = [
                row for row in instruments
                if row.status not in (PaymentInstrument.CANCELLED, PaymentInstrument.BANK_RETURNED)
            ]
            live_total = sum((row.amount for row in live_instruments), start=Decimal("0.00"))
            net_amount = voucher.net_amount if voucher is not None else Decimal("0.00")
            shared_exceptions = []
            if voucher is None:
                shared_exceptions.append(
                    "The prepared DV record is missing; stop and route this data-integrity exception for repair."
                )
            else:
                difference = voucher.gross_amount - voucher.total_deductions - voucher.net_amount
                if difference != 0:
                    shared_exceptions.append(
                        f"DV gross less deductions does not equal net; unexplained difference is {difference:.2f}."
                    )
            if obligation is None:
                shared_exceptions.append(
                    "The certified-obligation record is missing; stop and route this data-integrity exception for repair."
                )
            elif voucher is not None and voucher.gross_amount != obligation.certified_amount:
                shared_exceptions.append("DV gross does not equal the certified-obligation amount.")
            if voucher is not None and live_total > voucher.net_amount:
                shared_exceptions.append(
                    f"Active payment instruments exceed voucher net by {live_total - voucher.net_amount:.2f}; stop release."
                )
            issued_bank_accounts = {
                row.bank_account_code for row in instruments if row.status == PaymentInstrument.ISSUED
            }
            if item.configuration_release_id is None:
                configured_bank_accounts = set()
                shared_exceptions.append(
                    "No governed Finance Setup release is pinned to this voucher; stop payment processing and route the record for repair."
                )
            else:
                configured_bank_accounts = {
                    row.code for row in item.configuration_release.items.all()
                    if row.category == "bank_account" and row.status == "active"
                }
            invalid_bank_accounts = {
                row.bank_account_code for row in live_instruments
                if row.bank_account_code not in configured_bank_accounts
            }
            if invalid_bank_accounts:
                shared_exceptions.append(
                    "Active instruments reference a bank/payment account outside the voucher's pinned active Finance Setup: "
                    + ", ".join(sorted(invalid_bank_accounts)) + "."
                )
            if len(issued_bank_accounts) > 1:
                shared_exceptions.append(
                    "Issued checks use more than one bank account; this pilot case cannot enter one advice batch."
                )
            projection = {
                "case_state_version": item.state_version,
                "configured_bank_accounts": sorted(configured_bank_accounts),
                "instruments": [
                    [
                        str(row.public_id), row.bank_account_code, row.fund_code, row.check_number,
                        str(row.amount), row.status, row.operational_status, row.current_advice_batch_id,
                        row.replaces_id, row.issued_by_id, row.released_by_id, row.receipt_reference,
                    ]
                    for row in instruments
                ],
                "obligation": [obligation.obr_number, str(obligation.certified_amount)]
                if obligation is not None else [],
                "voucher": [
                    voucher.dv_number, str(voucher.gross_amount),
                    str(voucher.total_deductions), str(voucher.net_amount),
                ] if voucher is not None else [],
            }
            if action_key == "check_preparation":
                exceptions = list(shared_exceptions)
                remaining = net_amount - live_total
                issued = [row for row in instruments if row.status == PaymentInstrument.ISSUED]
                if remaining < 0:
                    next_action = "Stop and reconcile the over-issued instrument total before any further action."
                elif remaining > 0:
                    next_action = (
                        f"Confirm the governed bank/fund and current cash position, then register the next physical "
                        f"check; exact remaining net is {remaining:.2f}."
                    )
                elif issued and all(row.status == PaymentInstrument.ISSUED for row in live_instruments):
                    next_action = "Reconcile the issued-check total to voucher net, then submit this case to Accounting bank advice."
                else:
                    next_action = "Stop and reconcile instrument states before leaving Treasury check preparation."
                    exceptions.append(
                        "Voucher net is fully represented, but not solely by issued checks eligible for Accounting bank advice."
                    )
                projection["remaining_net"] = str(remaining)
                tasks.append(FinanceWorkTask(
                    task_id=f"finwork:v1:treasury-payment:{item.public_id}:check-preparation",
                    task_type="finance.treasury-payment.check-preparation.v1",
                    area="Treasury disbursement",
                    case_id=f"voucher-case:{item.public_id}",
                    reference=f"{item.reference_code} · {voucher.dv_number if voucher is not None else 'DV record missing'}",
                    transaction_type=item.transaction_type.replace("-", " ").replace("_", " ").title(),
                    subject=f"{item.payee_name} · {item.particulars}",
                    action=next_action,
                    gate=spec["definition"],
                    owner_queue=f"Treasury check preparation · {department.name}",
                    scope=f"Requesting office: {item.requesting_department.name}; current office: {item.current_department.name}",
                    received_at=item.updated_at,
                    due_on=None,
                    due_state="No structured target",
                    calendar_basis="The check and voucher dates are transaction dates, not inferred Treasury deadlines.",
                    age_days=_age_days(item.updated_at, today),
                    state="Exception" if exceptions else "Ready",
                    source_state=item.get_current_stage_display(),
                    source_version=f"projection-sha256:{_projection_checksum(projection)}",
                    exception=" ".join(exceptions),
                    url=item.get_absolute_url(),
                ))
                continue

            advised = [row for row in instruments if row.status == PaymentInstrument.ADVISED]
            for instrument in advised:
                exceptions = list(shared_exceptions)
                advice = instrument.current_advice_batch
                if advice is None:
                    exceptions.append("The advised check has no current bank-advice version; stop release.")
                elif advice.status != BankAdviceBatch.ACKNOWLEDGED:
                    exceptions.append(
                        f"Current bank advice is {advice.get_status_display().lower()}, not acknowledged; stop release."
                    )
                if instrument.operational_status in (PaymentInstrument.STALE, PaymentInstrument.RETURNED):
                    exceptions.append(
                        f"The check is marked {instrument.get_operational_status_display().lower()}; resolve its exception first."
                    )
                valid_claimants = []
                if item.payee_id:
                    valid_claimants = [
                        row for row in item.payee.authorized_claimants.all()
                        if row.status == "active" and row.valid_from <= today
                        and (row.valid_to is None or row.valid_to >= today)
                    ]
                if not valid_claimants:
                    exceptions.append("No currently effective authorized claimant is configured for this payee.")
                release_projection = dict(projection)
                release_projection["release_instrument"] = str(instrument.public_id)
                release_projection["advice"] = [
                    str(advice.public_id), advice.version, advice.status, advice.snapshot_checksum,
                    advice.acknowledgement_reference, advice.acknowledgement_evidence_reference,
                ] if advice is not None else []
                release_projection["claimants"] = [
                    [row.pk, row.display_name, row.status, row.valid_from.isoformat(), row.valid_to.isoformat() if row.valid_to else ""]
                    for row in valid_claimants
                ]
                tasks.append(FinanceWorkTask(
                    task_id=f"finwork:v1:treasury-payment:{item.public_id}:{instrument.public_id}:release",
                    task_type="finance.treasury-payment.instrument-release.v1",
                    area="Treasury disbursement",
                    case_id=f"voucher-case:{item.public_id}",
                    reference=f"{item.reference_code} · check {instrument.check_number}",
                    transaction_type=item.transaction_type.replace("-", " ").replace("_", " ").title(),
                    subject=f"{item.payee_name} · {instrument.amount:.2f}",
                    action="Verify the authorized claimant in person, release this check, and record the actual receipt reference.",
                    gate=spec["definition"],
                    owner_queue=f"Treasury check release · {department.name}",
                    scope=f"Bank account: {instrument.bank_account_code}; fund: {instrument.fund_code or 'not recorded'}",
                    received_at=(advice.acknowledged_at if advice is not None else None) or item.updated_at,
                    due_on=None,
                    due_state="No structured target",
                    calendar_basis="No release deadline is inferred from the check, advice, or acknowledgement date.",
                    age_days=_age_days((advice.acknowledged_at if advice is not None else None) or item.updated_at, today),
                    state="Exception" if exceptions else "Ready",
                    source_state=instrument.get_status_display(),
                    source_version=f"projection-sha256:{_projection_checksum(release_projection)}",
                    exception=" ".join(exceptions),
                    url=item.get_absolute_url(),
                ))
            if not advised:
                exceptions = list(shared_exceptions)
                exceptions.append("No advised check exists in this Treasury-release case; stop and reconcile its instrument history.")
                tasks.append(FinanceWorkTask(
                    task_id=f"finwork:v1:treasury-payment:{item.public_id}:release-reconciliation",
                    task_type="finance.treasury-payment.release-reconciliation.v1",
                    area="Treasury disbursement",
                    case_id=f"voucher-case:{item.public_id}", reference=item.reference_code,
                    transaction_type=item.transaction_type.replace("-", " ").replace("_", " ").title(),
                    subject=f"{item.payee_name} · release evidence exception",
                    action="Stop release and reconcile the case's governed instrument and bank-advice lineage.",
                    gate=spec["definition"], owner_queue=f"Treasury check release · {department.name}",
                    scope=f"Requesting office: {item.requesting_department.name}; current office: {item.current_department.name}",
                    received_at=item.updated_at, due_on=None, due_state="No structured target",
                    calendar_basis="No release deadline is stored or inferred.",
                    age_days=_age_days(item.updated_at, today), state="Exception",
                    source_state=item.get_current_stage_display(),
                    source_version=f"projection-sha256:{_projection_checksum(projection)}",
                    exception=" ".join(exceptions), url=item.get_absolute_url(),
                ))
    return tasks


def _bank_reconciliation_tasks(user, department, today):
    from accounting.bank_register_exports import (
        bank_batch_snapshot, bank_reconciliation_action_choices_for_user,
        bank_reconciliation_action_queryset, next_bank_action,
    )
    from accounting.models import BankOutstandingItem, BankStatementMatch

    task_types = {
        "needs_statement": "statement-staging",
        "needs_control_correction": "control-correction",
        "returned_correction": "returned-correction",
        "needs_matching": "matching-and-exceptions",
        "for_review": "independent-close-review",
    }
    queue_labels = {
        "needs_statement": "Bank-statement preparers",
        "needs_control_correction": "Bank-statement preparers",
        "returned_correction": "Bank-reconciliation preparers",
        "needs_matching": "Bank-reconciliation preparers",
        "for_review": "Independent Accounting bank-reconciliation reviewers",
    }

    def retained_checksum(value):
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def retained_decimal(value):
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    tasks = []
    for action_key, _label in bank_reconciliation_action_choices_for_user(user):
        queryset, _selected, spec = bank_reconciliation_action_queryset(user, action_key)
        queryset = queryset.select_related("fund").prefetch_related("events")
        for item in queryset.order_by("-period_end", "bank_account_code", "pk"):
            current_rows = list(item.rows.filter(source_version=item.source_version).order_by("row_number", "pk"))
            current_matches = list(BankStatementMatch.objects.filter(
                batch=item, statement_row__source_version=item.source_version,
            ).select_related("statement_row", "journal_line__entry", "journal_line__account").order_by("pk"))
            evidence_items = list(BankOutstandingItem.objects.filter(batch=item).select_related(
                "journal_line__entry", "journal_line__account", "carried_from__batch", "cleared_by_match__batch",
            ).order_by("pk"))
            events = list(item.events.all())
            snapshot, snapshot_checksum, snapshot_error = bank_batch_snapshot(item)
            exceptions = []

            row_deposits = sum((row.deposit for row in current_rows), Decimal("0.00"))
            row_withdrawals = sum((row.withdrawal for row in current_rows), Decimal("0.00"))
            computed_closing = item.opening_balance + row_deposits - row_withdrawals
            if item.source_version == 0:
                if action_key != "needs_statement":
                    exceptions.append("The current statement source version is missing.")
            else:
                if not item.source_checksum:
                    exceptions.append("The staged statement has no retained source checksum.")
                if len(current_rows) != item.expected_row_count:
                    exceptions.append(
                        f"Current statement row count is {len(current_rows)}, not the declared {item.expected_row_count}."
                    )
                if row_deposits != item.expected_deposits:
                    exceptions.append(
                        f"Statement deposits differ from the declared total by {row_deposits - item.expected_deposits:.2f}; it must equal exactly zero."
                    )
                if row_withdrawals != item.expected_withdrawals:
                    exceptions.append(
                        f"Statement withdrawals differ from the declared total by {row_withdrawals - item.expected_withdrawals:.2f}; it must equal exactly zero."
                    )
                if computed_closing != item.closing_balance:
                    exceptions.append(
                        f"Opening plus deposits less withdrawals differs from closing by {computed_closing - item.closing_balance:.2f}; it must equal exactly zero."
                    )
                running = item.opening_balance
                for row in current_rows:
                    running += row.deposit - row.withdrawal
                    row_evidence = {
                        "source_version": row.source_version,
                        "row_number": row.row_number,
                        "transaction_date": row.transaction_date.isoformat(),
                        "bank_reference": row.bank_reference,
                        "description": row.description,
                        "withdrawal": str(row.withdrawal),
                        "deposit": str(row.deposit),
                        "running_balance": str(row.running_balance) if row.running_balance is not None else "",
                    }
                    if retained_checksum(row_evidence) != row.row_checksum:
                        exceptions.append(
                            f"Statement row {row.row_number} no longer reproduces its retained checksum."
                        )
                    if row.running_balance is not None and row.running_balance != running:
                        exceptions.append(
                            f"Statement row {row.row_number} has a running-balance difference of {row.running_balance - running:.2f}."
                        )
                validation = item.validation_summary or {}
                validation_deposits = retained_decimal(validation.get("deposits", "0.00"))
                validation_withdrawals = retained_decimal(validation.get("withdrawals", "0.00"))
                validation_closing = retained_decimal(validation.get("computed_closing", "0.00"))
                if item.status in (item.VALIDATED, item.FOR_REVIEW) and (
                    not validation.get("valid")
                    or validation.get("source_version") != item.source_version
                    or validation.get("row_count") != len(current_rows)
                    or validation_deposits != row_deposits
                    or validation_withdrawals != row_withdrawals
                    or validation_closing != computed_closing
                ):
                    exceptions.append("The retained validation summary no longer reproduces the current statement controls.")

            for match in current_matches:
                if retained_checksum(match.source_snapshot) != match.source_checksum:
                    exceptions.append(
                        f"Match evidence for statement row {match.statement_row.row_number} no longer reproduces its checksum."
                    )
                line = match.journal_line
                live_match = {
                    "statement": {
                        "row_id": match.statement_row_id,
                        "source_version": match.statement_row.source_version,
                        "row_number": match.statement_row.row_number,
                        "date": match.statement_row.transaction_date.isoformat(),
                        "reference": match.statement_row.bank_reference,
                        "description": match.statement_row.description,
                        "withdrawal": str(match.statement_row.withdrawal),
                        "deposit": str(match.statement_row.deposit),
                        "row_checksum": match.statement_row.row_checksum,
                    },
                    "ledger": {
                        "journal_line_id": line.pk,
                        "entry_public_id": str(line.entry.public_id),
                        "entry_reference": line.entry.reference,
                        "entry_date": line.entry.entry_date.isoformat(),
                        "source_type": line.entry.source_type,
                        "source_reference": line.entry.source_reference,
                        "account_code": line.account.code,
                        "debit": str(line.debit),
                        "credit": str(line.credit),
                        "memo": line.memo,
                    },
                }
                if match.status == BankStatementMatch.ACTIVE and live_match != match.source_snapshot:
                    exceptions.append(
                        f"Active match evidence for statement row {match.statement_row.row_number} no longer matches its retained source snapshot."
                    )

            for evidence in evidence_items:
                if retained_checksum(evidence.source_snapshot) != evidence.source_checksum:
                    exceptions.append(
                        f"Timing-item evidence {evidence.pk} no longer reproduces its retained checksum."
                    )
                if evidence.status == BankOutstandingItem.ACTIVE:
                    line = evidence.journal_line
                    live_fields = {
                        "journal_line_id": line.pk,
                        "entry_public_id": str(line.entry.public_id),
                        "entry_reference": line.entry.reference,
                        "entry_date": line.entry.entry_date.isoformat(),
                        "account_code": line.account.code,
                        "debit": str(line.debit),
                        "credit": str(line.credit),
                        "kind": evidence.kind,
                        "expected_clearance_date": evidence.expected_clearance_date.isoformat(),
                        "evidence_reference": evidence.evidence_reference,
                    }
                    if any(evidence.source_snapshot.get(key) != value for key, value in live_fields.items()):
                        exceptions.append(
                            f"Active timing-item evidence {evidence.pk} no longer matches its retained ledger snapshot."
                        )

            if snapshot_error:
                exceptions.append(snapshot_error)
            elif action_key in ("needs_matching", "for_review"):
                difference = Decimal(str(snapshot.get("difference", "0.00")))
                if snapshot.get("unmatched_statement_row_count", 0):
                    exceptions.append(
                        f"{snapshot['unmatched_statement_row_count']} statement row(s) remain unmatched."
                    )
                if snapshot.get("unclassified_ledger_line_count", 0):
                    exceptions.append(
                        f"{snapshot['unclassified_ledger_line_count']} ledger-only line(s) lack timing-item evidence."
                    )
                if difference != 0:
                    exceptions.append(
                        f"Adjusted bank balance differs from the posted book balance by {difference:.2f}; it must equal exactly zero."
                    )
                if action_key == "for_review" and not snapshot.get("ready_for_review"):
                    exceptions.append("The submitted reconciliation no longer satisfies its zero-difference review gate.")

            submitted_event = next(
                (event for event in events if event.action == "submitted_for_review"), None,
            )
            if action_key == "for_review":
                submitted_checksum = (
                    (submitted_event.snapshot or {}).get("snapshot_checksum", "")
                    if submitted_event else ""
                )
                if not submitted_checksum or submitted_checksum != snapshot_checksum:
                    exceptions.append("The submitted reconciliation snapshot checksum no longer reproduces.")

            returned_event = next(
                (event for event in events if event.action == "returned_for_correction"), None,
            )
            if action_key == "returned_correction":
                exceptions.append(
                    returned_event.reason.strip()
                    if returned_event and returned_event.reason.strip()
                    else "The reconciliation was returned without a retained correction reason."
                )

            projection = {
                "batch": [
                    str(item.public_id), item.department_id, item.statement_reference,
                    item.bank_account_code, item.bank_name, item.account_number_masked, item.fund_id,
                    item.period_start.isoformat(), item.period_end.isoformat(), item.received_on.isoformat(),
                    str(item.opening_balance), str(item.closing_balance), item.expected_row_count,
                    str(item.expected_deposits), str(item.expected_withdrawals), item.status,
                    item.source_version, item.source_filename, item.source_checksum,
                    item.validation_summary, item.created_by_id, item.submitted_by_id,
                    item.submitted_at.isoformat() if item.submitted_at else "",
                    item.reconciled_by_id, item.reconciled_at.isoformat() if item.reconciled_at else "",
                    item.reconciliation_checksum, item.state_version,
                ],
                "snapshot": snapshot,
                "snapshot_checksum": snapshot_checksum,
                "snapshot_error": snapshot_error,
                "rows": [[
                    row.pk, row.source_version, row.row_number, row.transaction_date.isoformat(),
                    row.bank_reference, row.description, str(row.withdrawal), str(row.deposit),
                    str(row.running_balance) if row.running_balance is not None else "", row.row_checksum,
                ] for row in current_rows],
                "matches": [[
                    match.pk, match.statement_row_id, match.journal_line_id, match.method,
                    match.reason, match.status, match.source_snapshot, match.source_checksum,
                    match.superseded_at.isoformat() if match.superseded_at else "",
                ] for match in current_matches],
                "timing_items": [[
                    evidence.pk, evidence.journal_line_id, evidence.kind, evidence.explanation,
                    evidence.evidence_reference, evidence.expected_clearance_date.isoformat(),
                    evidence.status, evidence.source_snapshot, evidence.source_checksum,
                    evidence.carried_from_id, evidence.cleared_by_match_id,
                ] for evidence in evidence_items],
                "events": [[
                    event.pk, event.action, event.actor_id, event.reason, event.snapshot,
                    event.created_at.isoformat(),
                ] for event in events],
            }
            received_at = item.updated_at
            if action_key == "for_review":
                received_at = item.submitted_at or item.updated_at
            elif action_key == "returned_correction" and returned_event:
                received_at = returned_event.created_at
            action = (
                next_bank_action(item, snapshot, snapshot_error)
                if action_key == "needs_matching" else spec["next_action"]
            )
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:bank-reconciliation:{item.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.bank-reconciliation.{task_types[action_key]}.v1",
                area="Bank reconciliation",
                case_id=f"bank-reconciliation:{item.public_id}",
                reference=f"{item.statement_reference} · {item.period_end.isoformat()}",
                transaction_type=f"Bank reconciliation · {item.fund.code}",
                subject=(
                    f"{item.bank_account_code} · {item.expected_row_count} row(s) · "
                    f"deposits {item.expected_deposits:.2f} · withdrawals {item.expected_withdrawals:.2f}"
                ),
                action=action,
                gate=spec["definition"],
                owner_queue=f"{queue_labels[action_key]} · {department.name}",
                scope=f"Accounting office: {department.name}; fund {item.fund.code}; bank account {item.bank_account_code}",
                received_at=received_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis=(
                    "Statement period, receipt date, and timing-item expected-clearance dates are retained evidence; "
                    "none is recast as this action's deadline."
                ),
                age_days=_age_days(received_at, today),
                state=(
                    "Returned" if action_key == "returned_correction"
                    else "Exception" if exceptions else "Ready"
                ),
                source_state=item.get_status_display(),
                source_version=f"projection-sha256:{_projection_checksum(projection)}",
                exception=" ".join(dict.fromkeys(exceptions)),
                url=reverse("accounting:bank_reconciliation_detail", kwargs={"public_id": item.public_id}),
            ))
    return tasks


def _bank_advice_tasks(user, department, today):
    from vouchers.advice import advice_snapshot
    from vouchers.advice_register import (
        bank_advice_action_choices_for_user, bank_advice_action_queryset,
    )
    from vouchers.models import BankAdviceBatch, PaymentInstrument

    queue_labels = {
        "needs_preparation": "Bank-advice preparers",
        "awaiting_review": "Independent Accounting bank-advice reviewers",
        "awaiting_bank_submission": "Authorized bank-advice submitters",
        "awaiting_bank_response": "Bank-response evidence recorders",
    }
    tasks = []
    for action_key, _label in bank_advice_action_choices_for_user(user):
        queryset, _selected, spec = bank_advice_action_queryset(user, action_key)
        queryset = queryset.select_related(
            "accounting_department", "configuration_release", "created_by",
            "review_submitted_by", "approved_by", "bank_submitted_by", "supersedes",
        ).prefetch_related("items__instrument__case", "events")
        for item in queryset.order_by("-advice_date", "-created_at", "pk"):
            advice_items = list(item.items.all())
            events = list(item.events.all())
            snapshot = advice_snapshot(item)
            retained_total = sum(
                (row.amount_snapshot for row in advice_items), start=Decimal("0.00"),
            )
            snapshot_checksum = hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            exceptions = []
            if len(advice_items) != item.item_count:
                exceptions.append(
                    f"Retained item count is {len(advice_items)}, not the recorded {item.item_count}; stop and repair the governed evidence."
                )
            if retained_total != item.total_amount:
                exceptions.append(
                    f"Retained instrument total differs from the advice total by {retained_total - item.total_amount:.2f}; it must equal exactly zero."
                )
            if snapshot_checksum != item.snapshot_checksum:
                exceptions.append("The retained bank-advice snapshot checksum no longer reproduces.")
            expected_instrument_status = (
                PaymentInstrument.ADVISED
                if action_key in ("awaiting_bank_submission", "awaiting_bank_response")
                else PaymentInstrument.ISSUED
            )
            for row in advice_items:
                instrument = row.instrument
                if (
                    str(instrument.public_id) != str(row.instrument_public_id_snapshot)
                    or instrument.check_number != row.check_number_snapshot
                    or instrument.fund_code != row.fund_code_snapshot
                    or instrument.amount != row.amount_snapshot
                    or instrument.issued_at != row.issued_at_snapshot
                    or instrument.bank_account_code != item.bank_account_code
                ):
                    exceptions.append(
                        f"Live instrument {row.check_number_snapshot} no longer matches its retained advice snapshot."
                    )
                if instrument.current_advice_batch_id != item.pk:
                    exceptions.append(
                        f"Instrument {row.check_number_snapshot} no longer points to this current advice version."
                    )
                if instrument.status != expected_instrument_status:
                    exceptions.append(
                        f"Instrument {row.check_number_snapshot} is {instrument.get_status_display().lower()}, not the expected governed state."
                    )
            if item.configuration_release_id is None:
                exceptions.append("No Finance Setup release is pinned to this advice version.")
            if item.accounting_department_id is None:
                exceptions.append("No owning Accounting department is retained on this advice version.")
            if action_key == "awaiting_review" and (
                item.authority_reference.lower().startswith(("pending", "edit"))
                or item.local_applicability_note.lower().startswith(("pending", "edit"))
            ):
                exceptions.append("Starter or pending authority text must be replaced with the reviewed local basis before approval.")
            if item.status == BankAdviceBatch.REVIEW_RETURNED:
                exceptions.append(item.review_note.strip() or "Accounting returned this advice without a retained correction note.")
            elif item.status == BankAdviceBatch.RETURNED:
                exceptions.append(item.return_reason.strip() or "The bank returned this advice without a retained correction reason.")
            projection = {
                "batch": [
                    str(item.public_id), item.status, item.state_version, item.version,
                    item.advice_number, item.advice_date.isoformat(), item.bank_account_code,
                    item.configuration_release_id, item.accounting_department_id,
                    item.preparation_note, item.authority_reference, item.local_applicability_note,
                    item.item_count, str(item.total_amount), item.snapshot_checksum,
                    item.created_by_id, item.review_submitted_by_id, item.approved_by_id,
                    item.bank_submitted_by_id, item.acknowledged_by_id, item.returned_by_id,
                    item.review_submitted_at.isoformat() if item.review_submitted_at else "",
                    item.approved_at.isoformat() if item.approved_at else "", item.review_note,
                    item.bank_submitted_at.isoformat() if item.bank_submitted_at else "",
                    item.acknowledged_at.isoformat() if item.acknowledged_at else "",
                    item.returned_at.isoformat() if item.returned_at else "",
                    item.submission_reference,
                    item.submission_evidence_reference, item.acknowledgement_reference,
                    item.acknowledgement_evidence_reference, item.return_reason,
                    item.return_evidence_reference,
                ],
                "items": [
                    [
                        row.pk, row.instrument_id, str(row.instrument_public_id_snapshot),
                        row.check_number_snapshot, row.fund_code_snapshot, str(row.amount_snapshot),
                        row.issued_at_snapshot.isoformat() if row.issued_at_snapshot else "",
                        row.instrument.status, row.instrument.current_advice_batch_id,
                        str(row.instrument.public_id), row.instrument.check_number,
                        row.instrument.fund_code, str(row.instrument.amount),
                        row.instrument.issued_at.isoformat() if row.instrument.issued_at else "",
                        row.instrument.bank_account_code,
                        row.instrument.case_id, row.instrument.case.state_version,
                        row.instrument.case.current_stage,
                    ]
                    for row in advice_items
                ],
                "events": [
                    [
                        event.pk, event.action, event.actor_id, event.actor_department_id,
                        event.instrument_id, event.reason, event.snapshot,
                        event.created_at.isoformat(),
                    ]
                    for event in events
                ],
            }
            received_at = item.created_at
            if action_key == "awaiting_review":
                received_at = item.review_submitted_at or item.created_at
            elif action_key == "awaiting_bank_submission":
                received_at = item.approved_at or item.created_at
            elif action_key == "awaiting_bank_response":
                received_at = item.bank_submitted_at or item.created_at
            elif item.status == BankAdviceBatch.REVIEW_RETURNED:
                received_at = item.approved_at or item.created_at
            elif item.status == BankAdviceBatch.RETURNED:
                received_at = item.returned_at or item.created_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:bank-advice:{item.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.bank-advice.{action_key}.v1",
                area="Bank advice",
                case_id=f"bank-advice:{item.public_id}",
                reference=f"{item.advice_number} v{item.version} · {item.advice_date.isoformat()}",
                transaction_type=f"Bank advice · {item.bank_account_code}",
                subject=f"{item.item_count} instrument(s) · total {item.total_amount:.2f}",
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"{queue_labels[action_key]} · {item.accounting_department.name if item.accounting_department_id else department.name}",
                scope=f"Accounting office: {item.accounting_department.name if item.accounting_department_id else 'missing'}; bank account {item.bank_account_code}",
                received_at=received_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="The advice date is an evidence date, not an inferred preparation, review, submission, or response deadline.",
                age_days=_age_days(received_at, today),
                state=(
                    "Returned" if item.status in (BankAdviceBatch.REVIEW_RETURNED, BankAdviceBatch.RETURNED)
                    else "Exception" if exceptions else "Ready"
                ),
                source_state=item.get_status_display(),
                source_version=f"projection-sha256:{_projection_checksum(projection)}",
                exception=" ".join(dict.fromkeys(exceptions)),
                url=reverse("vouchers:advice_detail", kwargs={"public_id": item.public_id}),
            ))
    return tasks


def _returned_payment_tasks(user, department, today):
    from finance.models import FinancePostingRule
    from vouchers.advice import advice_snapshot
    from vouchers.models import (
        BankAdviceBatch, PaymentInstrument, PaymentInstrumentException,
        ReturnedInstrumentReview, VoucherPostingRequest,
    )
    from vouchers.returned_instrument_register import (
        returned_instrument_attention_choices_for_user, returned_instrument_attention_queryset,
    )

    queue_labels = {
        "accounting_review": "Independent Accounting returned-payment reviewers",
        "treasury_clarification": "Owning Treasury exception preparers",
        "treasury_replacement": "Owning Treasury instrument issuers",
    }
    tasks = []
    for action_key, _label in returned_instrument_attention_choices_for_user(user):
        queryset, _selected, spec = returned_instrument_attention_queryset(user, action_key)
        queryset = queryset.select_related(
            "case", "case__configuration_release", "instrument", "instrument__current_advice_batch",
            "exception", "exception__policy", "exception__policy__treasury_department",
            "prepared_by", "reviewed_by", "posting_request", "original_payment_request",
        )
        for item in queryset.order_by("-prepared_at", "-version", "pk"):
            instrument = item.instrument
            case = item.case
            source_exception = item.exception
            posting_request = item.posting_request
            source_posting = item.original_payment_request
            exceptions = []
            if source_exception.kind != PaymentInstrumentException.RETURNED:
                exceptions.append("The pinned exception is not a bank-return event.")
            if source_exception.status != PaymentInstrumentException.OPEN:
                exceptions.append("The pinned bank-return exception is already resolved; stop duplicate action.")
            if instrument.case_id != case.pk or source_exception.instrument_id != instrument.pk:
                exceptions.append("Returned-payment instrument, exception, and case lineage do not agree.")
            if instrument.operational_status != PaymentInstrument.RETURNED:
                exceptions.append("The instrument is not marked as a current returned-payment exception.")
            if instrument.amount <= 0:
                exceptions.append("The returned instrument amount is not positive.")
            if action_key in ("accounting_review", "treasury_clarification"):
                if instrument.status != PaymentInstrument.RELEASED:
                    exceptions.append("The instrument is no longer in the released state required for returned-payment review.")
                advice = instrument.current_advice_batch
                if advice is None or advice.status != BankAdviceBatch.ACKNOWLEDGED:
                    exceptions.append("The released instrument has no current acknowledged bank-advice evidence.")
                else:
                    retained_advice = advice_snapshot(advice)
                    retained_advice_total = sum(
                        (row.amount_snapshot for row in advice.items.all()), start=Decimal("0.00"),
                    )
                    retained_advice_checksum = hashlib.sha256(
                        json.dumps(retained_advice, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
                    if (
                        len(retained_advice["items"]) != advice.item_count
                        or retained_advice_total != advice.total_amount
                        or retained_advice_checksum != advice.snapshot_checksum
                    ):
                        exceptions.append("The acknowledged bank-advice count, total, or checksum no longer reproduces.")
                if source_posting is None or source_posting.status not in (
                    VoucherPostingRequest.POSTED, VoucherPostingRequest.NOT_REQUIRED,
                ):
                    exceptions.append("The original payment-release Accounting decision is missing or incomplete.")
                else:
                    source_payload_checksum = hashlib.sha256(
                        json.dumps(source_posting.payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
                    source_rule_checksum = hashlib.sha256(
                        json.dumps(source_posting.posting_rule_snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
                    ).hexdigest()
                    if source_payload_checksum != source_posting.payload_checksum:
                        exceptions.append("The original payment-release payload checksum no longer reproduces.")
                    if source_rule_checksum != source_posting.posting_rule_checksum:
                        exceptions.append("The original payment-release posting-rule checksum no longer reproduces.")
                    try:
                        source_amount = Decimal(str(source_posting.payload.get("event_amount", "")))
                    except (InvalidOperation, TypeError, ValueError):
                        exceptions.append("The original payment-release payload has no exact event amount.")
                    else:
                        if source_amount != instrument.amount:
                            exceptions.append(
                                f"Returned instrument and original payment evidence differ by {instrument.amount - source_amount:.2f}; it must equal exactly zero."
                            )
            if action_key == "accounting_review":
                release = case.configuration_release
                variant = release.transaction_variants.filter(
                    code=case.transaction_type,
                    status__in=("approved", "scheduled", "active", "superseded"),
                ).first() if release is not None else None
                rule = variant.posting_rules.filter(
                    event_kind=FinancePostingRule.REVERSAL,
                    recognition_point=FinancePostingRule.PAYMENT_RETURN,
                ).first() if variant is not None else None
                if rule is None:
                    exceptions.append("The pinned Finance Setup release has no reviewed returned-payment reversal or no-entry rule.")
            if action_key == "treasury_clarification" and not item.accounting_decision_reason.strip():
                exceptions.append("Accounting returned this item without a retained clarification instruction.")
            if action_key == "treasury_replacement":
                if instrument.status != PaymentInstrument.BANK_RETURNED:
                    exceptions.append("Accounting has not moved the original instrument to the bank-returned state.")
                if posting_request is None or posting_request.status not in (
                    VoucherPostingRequest.POSTED, VoucherPostingRequest.NOT_REQUIRED,
                ):
                    exceptions.append("The returned-payment Accounting entry is not complete.")
                if hasattr(instrument, "replacement"):
                    exceptions.append("A controlled replacement already exists; stop duplicate issuance.")
            if posting_request is not None:
                payload_checksum = hashlib.sha256(
                    json.dumps(posting_request.payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                rule_checksum = hashlib.sha256(
                    json.dumps(posting_request.posting_rule_snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                if payload_checksum != posting_request.payload_checksum:
                    exceptions.append("The returned-payment posting payload checksum no longer reproduces.")
                if rule_checksum != posting_request.posting_rule_checksum:
                    exceptions.append("The pinned returned-payment posting-rule checksum no longer reproduces.")
            projection = {
                "review": [
                    str(item.public_id), item.status, item.outcome, item.version,
                    item.state_version, item.treasury_evidence_reference, item.treasury_note,
                    item.accounting_decision_reason, item.accounting_evidence_reference,
                    item.prepared_by_id, item.reviewed_by_id, item.closed_by_id,
                    item.posting_request_id, item.original_payment_request_id, item.supersedes_id,
                    item.prepared_at.isoformat(),
                    item.reviewed_at.isoformat() if item.reviewed_at else "",
                    item.closed_at.isoformat() if item.closed_at else "",
                ],
                "case": [
                    case.pk, str(case.public_id), case.current_stage, case.current_department_id,
                    case.configuration_release_id, case.state_version, case.transaction_type,
                ],
                "instrument": [
                    instrument.pk, str(instrument.public_id), instrument.status,
                    instrument.operational_status, str(instrument.amount), instrument.bank_account_code,
                    instrument.current_advice_batch_id,
                    instrument.current_advice_batch.status if instrument.current_advice_batch_id else "",
                    instrument.current_advice_batch.snapshot_checksum if instrument.current_advice_batch_id else "",
                ],
                "exception": [
                    source_exception.pk, str(source_exception.public_id), source_exception.kind,
                    source_exception.status, source_exception.observed_on.isoformat(),
                    source_exception.reason, source_exception.evidence_reference,
                    source_exception.policy_id,
                ],
                "posting": (
                    [
                        posting_request.pk, str(posting_request.public_id), posting_request.status,
                        posting_request.version, posting_request.payload,
                        posting_request.payload_checksum, posting_request.posting_rule_snapshot,
                        posting_request.posting_rule_checksum,
                    ] if posting_request is not None else []
                ),
                "original_posting": (
                    [
                        item.original_payment_request_id, item.original_payment_request.status,
                        item.original_payment_request.version, item.original_payment_request.payload_checksum,
                        item.original_payment_request.posting_rule_checksum,
                    ] if item.original_payment_request_id else []
                ),
            }
            received_at = item.prepared_at
            if action_key == "treasury_clarification":
                received_at = item.reviewed_at or item.prepared_at
            elif action_key == "treasury_replacement":
                received_at = (
                    posting_request.posted_at if posting_request is not None and posting_request.posted_at
                    else item.reviewed_at or item.prepared_at
                )
            scope_department = (
                case.configuration_release.department.name
                if spec["scope_kind"] == "accounting" and case.configuration_release_id
                else source_exception.policy.treasury_department.name
            )
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:returned-payment:{item.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.returned-payment.{action_key}.v1",
                area="Returned payment",
                case_id=f"returned-payment:{item.public_id}",
                reference=f"{case.reference_code} · check {instrument.check_number} · review v{item.version}",
                transaction_type="Bank-returned payment",
                subject=f"Instrument amount {instrument.amount:.2f} · observed {source_exception.observed_on.isoformat()}",
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"{queue_labels[action_key]} · {scope_department}",
                scope=f"{scope_department}; bank account {instrument.bank_account_code}; case {case.reference_code}",
                received_at=received_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="The bank-return observation date is evidence timing, not an inferred Accounting or Treasury action deadline.",
                age_days=_age_days(received_at, today),
                state="Returned" if action_key == "treasury_clarification" else ("Exception" if exceptions else "Ready"),
                source_state=item.get_status_display(),
                source_version=f"projection-sha256:{_projection_checksum(projection)}",
                exception=" ".join(dict.fromkeys(exceptions)),
                url=(
                    f"{reverse('vouchers:advice_workspace')}?returned_attention={action_key}"
                    f"#returned-review-{item.public_id}"
                ),
            ))
    return tasks


def _remittance_tasks(user, department, today):
    from django.db.models import Q

    from finance.models import FinanceConfigurationItem, FinancePostingRule
    from vouchers.models import TreasuryRemittanceBatch, TreasuryRemittanceLine
    from vouchers.remittance_register import (
        remittance_action_choices_for_user, remittance_action_queryset,
    )
    from vouchers.remittances import _digest, _validate_live_lines

    queue_labels = {
        "preparation": "Treasury remittance preparers",
        "returned": "Treasury remittance preparers",
        "review": "Independent Accounting remittance reviewers",
        "release": "Treasury remittance release officers",
    }
    tasks = []
    for action_key, _label in remittance_action_choices_for_user(user):
        queryset, _selected, spec = remittance_action_queryset(user, action_key)
        queryset = queryset.select_related(
            "configuration_release", "configuration_release__department", "transaction_variant",
            "recipient_party", "treasury_department", "created_by", "submitted_by", "reviewed_by",
            "posting_rule",
        ).prefetch_related("lines", "posting_requests")
        for item in queryset.order_by("-remittance_date", "-pk"):
            lines = list(item.lines.all())
            active_lines = [row for row in lines if row.status == TreasuryRemittanceLine.ACTIVE]
            active_total = sum((row.amount for row in active_lines), start=Decimal("0.00"))
            exceptions = []
            if active_total != item.total_amount:
                exceptions.append(
                    f"Active remittance lines differ from the batch control total by {active_total - item.total_amount:.2f}."
                )
            if item.status in (
                TreasuryRemittanceBatch.FOR_REVIEW, TreasuryRemittanceBatch.APPROVED,
            ):
                try:
                    _validate_live_lines(item)
                except ValidationError as exc:
                    exceptions.extend(getattr(exc, "messages", [str(exc)]))
            configured = set(FinanceConfigurationItem.objects.filter(
                release=item.configuration_release,
                category__in=("fund", "bank_account"), status="active",
                effective_from__lte=item.remittance_date,
            ).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=item.remittance_date),
            ).values_list("category", "code"))
            if ("fund", item.fund_code) not in configured:
                exceptions.append("The remittance fund is not active in its pinned Finance Setup release.")
            if ("bank_account", item.bank_account_code) not in configured:
                exceptions.append("The remittance bank/payment account is not active in its pinned Finance Setup release.")
            if (
                item.recipient_party.status != "active"
                or item.recipient_party.party_type != item.recipient_party.AGENCY
                or item.recipient_party.effective_from > item.remittance_date
                or (
                    item.recipient_party.effective_to is not None
                    and item.recipient_party.effective_to < item.remittance_date
                )
            ):
                exceptions.append("The pinned remittance recipient is not an active government agency.")
            if (
                item.transaction_variant.status != "active"
                or item.transaction_variant.effective_from > item.remittance_date
                or (
                    item.transaction_variant.effective_to is not None
                    and item.transaction_variant.effective_to < item.remittance_date
                )
            ):
                exceptions.append("The pinned remittance transaction variant is not active.")
            live_rule = item.transaction_variant.posting_rules.filter(
                event_kind=FinancePostingRule.REMITTANCE,
                recognition_point=FinancePostingRule.DEDUCTION_REMITTANCE,
                accounting_effect=FinancePostingRule.JOURNAL_ENTRY,
            ).first()
            if action_key in ("preparation", "returned") and live_rule is None:
                exceptions.append("No active governed deduction-remittance posting rule is available for this variant.")
            if action_key in ("review", "release"):
                if item.posting_rule_id is None or not item.posting_rule_snapshot or not item.posting_rule_checksum:
                    exceptions.append("The submitted remittance does not carry a complete pinned posting-rule snapshot.")
                elif _digest(item.posting_rule_snapshot) != item.posting_rule_checksum:
                    exceptions.append("The pinned remittance posting-rule checksum no longer matches its snapshot.")
                elif item.posting_rule_id != (live_rule.pk if live_rule is not None else None):
                    exceptions.append("The pinned posting rule no longer matches the governed remittance rule; return for review.")
            if not active_lines:
                next_action = "Add at least one posted withholding balance, then reconcile the exact schedule total before submission."
            else:
                next_action = spec["next_action"]
            if item.status == TreasuryRemittanceBatch.RETURNED:
                exceptions.append(item.review_reason.strip() or "Accounting returned this batch with retained correction instructions.")
            projection = {
                "batch": [
                    item.state_version, item.status, str(item.total_amount), item.fund_code,
                    item.bank_account_code, item.remittance_date.isoformat(), item.payment_method,
                    item.configuration_release_id, item.transaction_variant_id, item.recipient_party_id,
                    item.created_by_id, item.submitted_by_id, item.reviewed_by_id,
                    item.posting_rule_id, item.posting_rule_checksum,
                    item.posting_rule_snapshot,
                ],
                "configured_routes": sorted([list(row) for row in configured]),
                "lines": [
                    [
                        row.pk, str(row.lineage_key), row.version, row.status, row.fund_code,
                        row.account_code, row.reference_key, row.deduction_code, str(row.amount),
                        str(row.available_balance_snapshot), row.source_checksum, row.tax_rule_checksum,
                    ]
                    for row in lines
                ],
                "posting_requests": [
                    [str(row.public_id), row.version, row.status, row.jev_number, row.payload_checksum, row.failure_reason]
                    for row in item.posting_requests.all()
                ],
            }
            received_at = item.submitted_at if action_key == "review" else item.updated_at
            if action_key == "release":
                received_at = item.reviewed_at or item.updated_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:treasury-remittance:{item.public_id}:{action_key}",
                task_type=f"finance.treasury-remittance.{action_key}.v1",
                area="Treasury remittance",
                case_id=f"treasury-remittance:{item.public_id}",
                reference=item.reference_code,
                transaction_type=item.transaction_variant.label,
                subject=f"{item.recipient_party.display_name} · {item.total_amount:.2f}",
                action=next_action,
                gate=spec["definition"],
                owner_queue=f"{queue_labels[action_key]} · {department.name}",
                scope=(
                    f"Treasury: {item.treasury_department.name}; Finance ledger: {item.finance_department_label}; "
                    f"fund {item.fund_code}; bank {item.bank_account_code}"
                ),
                received_at=received_at or item.updated_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="The remittance date is a transaction date, not an inferred review or release deadline.",
                age_days=_age_days(received_at or item.updated_at, today),
                state=(
                    "Returned" if item.status == TreasuryRemittanceBatch.RETURNED
                    else "Exception" if exceptions else "Ready"
                ),
                source_state=item.get_status_display(),
                source_version=f"projection-sha256:{_projection_checksum(projection)}",
                exception=" ".join(exceptions),
                url=item.get_absolute_url(),
            ))
    return tasks


def _cash_control_tasks(user, department, today):
    from accounting.models import Fund
    from finance.models import FinanceConfigurationItem
    from vouchers.cash_positions import (
        _checksum, _position_snapshot, latest_reconciled_bank_position,
    )
    from vouchers.cash_register import cash_attention_choices_for_user, cash_attention_queryset
    from vouchers.models import TreasuryCashPolicy, TreasuryCashPosition

    tasks = []
    for action_key, _label in cash_attention_choices_for_user(user):
        queryset, _selected, spec = cash_attention_queryset(user, action_key)
        if spec["kind"] == "policy":
            queryset = queryset.select_related(
                "configuration_release", "configuration_release__department", "treasury_department",
                "created_by", "submitted_by", "approved_by", "supersedes",
            )
        else:
            queryset = queryset.select_related(
                "policy", "policy__configuration_release", "policy__configuration_release__department",
                "policy__treasury_department", "created_by", "submitted_by", "approved_by", "supersedes",
            )
        for item in queryset.order_by("-pk"):
            if spec["kind"] == "policy":
                policy = item
                exceptions = []
                bank_is_active = FinanceConfigurationItem.objects.filter(
                    release=policy.configuration_release, category="bank_account",
                    code=policy.bank_account_code, status="active",
                ).exists()
                fund_is_active = Fund.objects.filter(
                    department_id=policy.configuration_release.department_id,
                    code=policy.fund_code, is_active=True,
                ).exists()
                if not bank_is_active:
                    exceptions.append("The policy bank/payment account is not active in its pinned Finance Setup.")
                if not fund_is_active:
                    exceptions.append("The policy fund is not active in the pinned Accounting setup.")
                if not policy.authority_reference.strip() or not policy.local_applicability_note.strip():
                    exceptions.append("The reviewed authority and local-applicability evidence must both be recorded.")
                if policy.status == TreasuryCashPolicy.RETURNED:
                    action = "Prepare a reasoned successor policy version from the returned record; do not overwrite or resubmit it."
                    exceptions.append("This policy was returned; its correction instructions remain in the append-only cash events.")
                else:
                    action = spec["next_action"]
                projection = {
                    "route": [policy.configuration_release_id, policy.bank_account_code, policy.fund_code],
                    "policy": [
                        policy.state_version, policy.status, policy.version, policy.mode,
                        str(policy.minimum_reserve), policy.position_max_age_days,
                        policy.unclaimed_after_days, policy.stale_after_days,
                        policy.effective_from.isoformat(), policy.effective_to.isoformat() if policy.effective_to else "",
                        policy.authority_reference, policy.local_applicability_note,
                        policy.created_by_id, policy.submitted_by_id, policy.supersedes_id,
                    ],
                    "route_active": [bank_is_active, fund_is_active],
                }
                received_at = policy.submitted_at if action_key == "policy_awaiting_review" else policy.created_at
                tasks.append(FinanceWorkTask(
                    task_id=f"finwork:v1:treasury-cash-policy:{policy.public_id}:{action_key.replace('_', '-')}",
                    task_type=f"finance.treasury-cash-policy.{action_key}.v1",
                    area="Treasury cash control",
                    case_id=f"treasury-cash-policy:{policy.public_id}",
                    reference=f"{policy.bank_account_code} · {policy.fund_code} · v{policy.version}",
                    transaction_type=f"Cash policy · {policy.get_mode_display()}",
                    subject=f"Reserve {policy.minimum_reserve:.2f}; position age limit {policy.position_max_age_days} day(s)",
                    action=action,
                    gate=spec["definition"],
                    owner_queue=(
                        "Independent cash-control reviewers"
                        if action_key == "policy_awaiting_review"
                        else f"Treasury cash-policy preparers · {policy.treasury_department.name}"
                    ),
                    scope=f"{policy.treasury_department.name}; Finance Setup {policy.configuration_release.code}",
                    received_at=received_at or policy.created_at,
                    due_on=None,
                    due_state="No structured target",
                    calendar_basis="Policy effectivity is retained as a control period, not inferred as a review deadline.",
                    age_days=_age_days(received_at or policy.created_at, today),
                    state=(
                        "Returned" if policy.status == TreasuryCashPolicy.RETURNED
                        else "Exception" if exceptions else "Ready"
                    ),
                    source_state=policy.get_status_display(),
                    source_version=f"projection-sha256:{_projection_checksum(projection)}",
                    exception=" ".join(exceptions),
                    url=reverse("vouchers:cash_policy_detail", kwargs={"public_id": policy.public_id}),
                ))
                continue

            position = item
            policy = position.policy
            exceptions = []
            exact_available = position.approved_available_cash
            if not position.evidence_reference.strip():
                exceptions.append("The retained cash-position evidence reference is blank.")
            try:
                reconciliation, snapshot = latest_reconciled_bank_position(policy, position.as_of_date)
            except ValidationError as exc:
                exceptions.extend(getattr(exc, "messages", [str(exc)]))
            else:
                if (
                    str(reconciliation.public_id) != str(position.reconciliation_public_id)
                    or reconciliation.reconciliation_checksum != position.reconciliation_checksum
                    or snapshot["book_balance"] != str(position.reconciled_book_balance)
                ):
                    exceptions.append("The pinned reconciliation is no longer the authoritative bank position for this date.")
            if action_key == "position_awaiting_review":
                if not position.snapshot_checksum:
                    exceptions.append("The submitted position has no immutable snapshot checksum.")
                elif _checksum(_position_snapshot(position)) != position.snapshot_checksum:
                    exceptions.append("The submitted cash-position checksum no longer matches its evidence.")
            if position.status == TreasuryCashPosition.RETURNED:
                action = "Prepare a reasoned successor position for the same policy/date; do not overwrite or resubmit the returned snapshot."
                exceptions.append("This position was returned; its correction instructions remain in the append-only cash events.")
            else:
                action = (
                    f"{spec['next_action']} Exact available cash is {exact_available:.2f} "
                    "after inflows, outflows, holds, and minimum reserve."
                )
            projection = {
                "position": [
                    position.state_version, position.status, position.version,
                    position.as_of_date.isoformat(), str(position.reconciliation_public_id),
                    position.reconciliation_checksum, position.reconciliation_period_end.isoformat(),
                    str(position.reconciled_book_balance), str(position.confirmed_inflows),
                    str(position.confirmed_outflows), str(position.other_holds),
                    str(policy.minimum_reserve), str(exact_available), position.evidence_reference,
                    position.preparation_note, position.snapshot_checksum,
                    position.created_by_id, position.submitted_by_id, position.supersedes_id,
                ],
                "policy": [policy.state_version, policy.status, policy.mode, policy.bank_account_code, policy.fund_code],
            }
            received_at = position.submitted_at if action_key == "position_awaiting_review" else position.created_at
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:treasury-cash-position:{position.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.treasury-cash-position.{action_key}.v1",
                area="Treasury cash control",
                case_id=f"treasury-cash-position:{position.public_id}",
                reference=f"{policy.bank_account_code} · {policy.fund_code} · {position.as_of_date} · v{position.version}",
                transaction_type="Cash-position snapshot",
                subject=(
                    f"{position.reconciled_book_balance:.2f} + {position.confirmed_inflows:.2f} - "
                    f"{position.confirmed_outflows:.2f} - {position.other_holds:.2f} - "
                    f"{policy.minimum_reserve:.2f} = {exact_available:.2f}"
                ),
                action=action,
                gate=spec["definition"],
                owner_queue=(
                    "Independent cash-position reviewers"
                    if action_key == "position_awaiting_review"
                    else f"Treasury cash-position preparers · {policy.treasury_department.name}"
                ),
                scope=f"{policy.treasury_department.name}; reconciliation {position.reconciliation_public_id}",
                received_at=received_at or position.created_at,
                due_on=None,
                due_state="No structured target",
                calendar_basis="The as-of and reconciliation dates are control dates, not inferred review deadlines.",
                age_days=_age_days(received_at or position.created_at, today),
                state=(
                    "Returned" if position.status == TreasuryCashPosition.RETURNED
                    else "Exception" if exceptions else "Ready"
                ),
                source_state=position.get_status_display(),
                source_version=f"projection-sha256:{_projection_checksum(projection)}",
                exception=" ".join(exceptions),
                url=reverse("vouchers:cash_policy_detail", kwargs={"public_id": policy.public_id}),
            ))
    return tasks


def _reporting_tasks(user, department, today):
    from reporting.models import ReportDefinition
    from reporting.run_register_exports import (
        report_action_choices_for_user, report_action_queryset,
    )
    from reporting.services import report_run_integrity_errors

    queue_labels = {
        "generation": "Report generators",
        "generation_failed": "Report generators",
        "control_blocked": "Report generators and source owners",
        "needs_review": "Independent report reviewers",
        "needs_approval": "Report approvers",
    }
    tasks = []
    for action_key, _label in report_action_choices_for_user(user):
        queryset, _selected, spec = report_action_queryset(user, action_key)
        queryset = queryset.select_related(
            "definition", "definition__department", "template_version", "schedule",
            "created_by", "reviewed_by", "approved_by",
        ).prefetch_related("source_records", "events")
        for item in queryset.order_by("-created_at", "-pk"):
            exceptions = []
            template = item.template_version
            definition_snapshot = item.parameters.get("_definition_snapshot", {})
            if not item.definition.is_active:
                exceptions.append("The pinned report definition is no longer active; prepare a successor under the current definition.")
            if template.definition_id != item.definition_id or not template.supports_format(item.output_format):
                exceptions.append("The pinned template does not support this report definition and output format.")
            if not template.is_mapping_ready:
                exceptions.append("The pinned template mapping has not passed controlled preflight.")
            if action_key == "generation_failed":
                exceptions.append(item.error_message.strip() or "The prior generation failed without a retained error message.")
            if action_key == "control_blocked":
                exceptions.append(item.control_message.strip() or "Required control evidence does not reconcile exactly.")
            if action_key in ("control_blocked", "needs_review", "needs_approval"):
                exceptions.extend(report_run_integrity_errors(item))
            if action_key == "needs_approval":
                if definition_snapshot.get("applicability_status") == ReportDefinition.APPLICABILITY_CANDIDATE:
                    exceptions.append("Local applicability was still pending when this report was generated; generate a successor after confirmation.")
                if not template.is_official_ready:
                    exceptions.append("The pinned template has not completed independent promotion and fidelity validation for official use.")
            source_projection = [
                [
                    source.pk, source.source_app, source.source_model, source.source_pk,
                    source.source_public_id, source.source_reference,
                    source.source_date.isoformat() if source.source_date else "",
                    source.control_group, str(source.amount), source.source_checksum,
                    source.source_url, source.snapshot,
                ]
                for source in item.source_records.all()
            ]
            event_projection = [
                [event.pk, event.action, event.from_status, event.to_status, event.note, event.actor_id]
                for event in item.events.all()
            ]
            projection = {
                "run": [
                    item.status, item.output_format, item.period_start.isoformat(), item.period_end.isoformat(),
                    item.parameters, item.row_count, item.source_record_count,
                    item.dataset_checksum, item.control_totals, item.control_checksum,
                    item.control_status, item.control_message, item.control_gate_required,
                    item.checksum, item.reproduction_key, item.error_message,
                    item.definition_id, item.template_version_id, item.schedule_id,
                    item.created_by_id, item.reviewed_by_id, item.approved_by_id,
                ],
                "definition": [
                    item.definition.is_active, item.definition.updated_at.isoformat(),
                    item.definition.applicability_status,
                ],
                "template": [
                    template.is_active, template.render_mode, template.mapping_checksum,
                    template.mapping_validated_at.isoformat() if template.mapping_validated_at else "",
                    template.fidelity_status,
                    template.fidelity_validated_at.isoformat() if template.fidelity_validated_at else "",
                    template.approved_at.isoformat() if template.approved_at else "",
                ],
                "sources": source_projection,
                "events": event_projection,
            }
            received_at = item.created_at
            if action_key in ("control_blocked", "needs_review"):
                received_at = item.generated_at or item.updated_at
            elif action_key == "needs_approval":
                received_at = item.reviewed_at or item.updated_at
            due_on = item.scheduled_for.date() if item.scheduled_for else None
            tasks.append(FinanceWorkTask(
                task_id=f"finwork:v1:report-run:{item.public_id}:{action_key.replace('_', '-')}",
                task_type=f"finance.report-run.{action_key}.v1",
                area="Reporting",
                case_id=f"report-run:{item.public_id}",
                reference=f"{item.definition.name} · {item.period_start} to {item.period_end}",
                transaction_type=f"{item.output_format.upper()} report · {item.definition.dataset_label}",
                subject=(
                    f"{item.row_count} row(s); {item.source_record_count} retained source(s); "
                    f"control: {item.get_control_status_display()}"
                ),
                action=spec["next_action"],
                gate=spec["definition"],
                owner_queue=f"{queue_labels[action_key]} · {department.name}",
                scope=f"{department.name}; dataset {definition_snapshot.get('dataset_key', item.definition.dataset_key)}",
                received_at=received_at,
                due_on=due_on,
                due_state=_due_state(due_on, today),
                calendar_basis=(
                    "The stored schedule time is shown for scheduled generation; report period dates are coverage dates, not inferred action deadlines."
                    if item.scheduled_for else
                    "The report period is a coverage range, not an inferred generation, review, or approval deadline."
                ),
                age_days=_age_days(received_at, today),
                state=(
                    "Exception" if exceptions or action_key in ("generation_failed", "control_blocked")
                    else "Ready"
                ),
                source_state=item.get_status_display(),
                source_version=f"projection-sha256:{_projection_checksum(projection)}",
                exception=" ".join(dict.fromkeys(exceptions)),
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
    tasks = _setup_tasks(user, department, today)
    tasks.extend(_discovery_tasks(user, department, today))
    tasks.extend(_budget_tasks(user, department, today))
    tasks.extend(_payable_tasks(user, department, today))
    tasks.extend(_dv_custody_tasks(user, department, today))
    tasks.extend(_accounting_validation_tasks(user, department, today))
    tasks.extend(_journal_tasks(user, department, today))
    tasks.extend(_treasury_payment_tasks(user, department, today))
    tasks.extend(_bank_reconciliation_tasks(user, department, today))
    tasks.extend(_bank_advice_tasks(user, department, today))
    tasks.extend(_returned_payment_tasks(user, department, today))
    tasks.extend(_remittance_tasks(user, department, today))
    tasks.extend(_cash_control_tasks(user, department, today))
    tasks.extend(_reporting_tasks(user, department, today))
    tasks.extend(_field_operation_tasks(user, department, today))
    tasks.extend(_local_form_tasks(user, department, today))
    tasks.sort(key=lambda task: (task.area, task.reference.lower(), task.task_type, task.task_id))
    task_count = len(tasks)
    return {
        "tasks": [task.as_dict() for task in tasks[:display_limit]],
        "task_count": task_count,
        "tasks_truncated": task_count > display_limit,
        "task_coverage": (
            "Finance setup releases", "Discovery decisions", "Budget controls", "Payable intake",
            "DV preparation and controlled custody", "Accounting validation and JEV controls",
            "Treasury check preparation and instrument release",
            "Bank-statement matching, exception resolution, and independent close",
            "Bank-advice handoff and returned-payment resolution",
            "Treasury remittance and cash controls",
            "Report generation, reconciliation, review, and approval",
            "Field-operation cycle and nested-record gates", "Local forms",
        ),
    }
