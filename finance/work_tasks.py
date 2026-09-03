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
            "Field-operation cycle and nested-record gates", "Local forms",
        ),
    }
