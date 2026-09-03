from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from reporting.models import FinanceLocalFormAcceptance
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from vouchers.case_exports import (
    accounting_validation_action_queryset, apply_case_filters,
    dv_custody_action_queryset, dv_signature_task_queryset,
    payable_action_queryset, visible_cases_for_user,
)
from vouchers.models import (
    BudgetAllocationLine, BudgetObligation, DisbursementVoucher, PayableIntake, VoucherCase,
    VoucherOutput, VoucherPrintJob, WetSignatureTask,
)
from vouchers.services import validate_accounting

from accounting.journal_exports import journal_action_queryset
from accounting.models import (
    AccountingAuditEvent, AccountingPeriod, FiscalYear, Fund, JournalEntry, JournalLine,
    LedgerAccount, ResponsibilityCenter,
)
from budget.annual_exports import apply_annual_filters
from budget.control_exports import apply_allotment_filters, apply_obligation_filters, obligation_scope_for_user
from budget.models import (
    AllotmentReleaseOrder, AppropriationAuthorization, BudgetCall, BudgetVersion, ObligationRequest,
)

from .models import (
    FinanceConfigurationRelease, FinanceCutoverDecision, FinanceCutoverReadinessExercise,
    FinanceCutoverReadinessPlan, FinanceShadowComparison, FinanceShadowCycle,
    FinanceDiscoveryDecision, FinanceShadowDefect, FinanceStakeholderAcceptance,
    FinanceTemplateVersion, FinanceWorkflowExemption,
)
from .work_attention import finance_work_attention
from .work_tasks import finance_work_tasks


class FinanceWorkTaskContractTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="task-contract-accounting",
        )
        cls.budget = Department.objects.create(
            name="Municipal Budget Office", slug="task-contract-budget",
        )
        cls.worker = cls._employee("task.contract.worker", cls.accounting)
        cls.reviewer = cls._employee("task.contract.reviewer", cls.accounting)
        cls.uat = cls._employee("task.contract.uat", cls.accounting)
        cls._grant(
            cls.worker,
            "finance.view_finance_setup",
            "finance.manage_finance_configuration",
            "finance.manage_finance_discovery",
            "finance.manage_shadow_operation",
            "reporting.manage_local_form_acceptance",
        )
        cls._grant(
            cls.reviewer,
            "finance.view_finance_setup",
            "finance.approve_finance_configuration",
            "finance.review_shadow_reconciliation",
            "finance.authorize_finance_cutover",
        )
        cls._grant(
            cls.uat,
            "finance.view_finance_setup",
            "finance.manage_shadow_operation",
            "reporting.manage_local_form_acceptance",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])

    @classmethod
    def _employee(cls, username, department):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="task-contract-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        return get_user_model().objects.get(pk=user.pk)

    @staticmethod
    def _grant(user, *permissions):
        for permission in permissions:
            app_label, codename = permission.split(".", 1)
            user.user_permissions.add(Permission.objects.get(
                content_type__app_label=app_label, codename=codename,
            ))

    def _form(self, department=None, code="task-form"):
        return FinanceLocalFormAcceptance.objects.create(
            department=department or self.accounting,
            code=code,
            version=1,
            name="Locally controlled disbursement form",
            form_number="Local Form TC-1",
            purpose="Retain the locally accepted disbursement layout.",
            source_type=FinanceLocalFormAcceptance.SOURCE_UNMAPPED,
            authority_reference="Synthetic local authority for task-contract testing.",
            local_acceptance_note="Pending named-office comparison.",
            reference_kind="pdf",
            delivery_mode=FinanceLocalFormAcceptance.DELIVERY_BOTH,
            signatory_instructions="Prepared, reviewed, and approved by separate authorized roles.",
            recipient_instructions="Accounting and Records receive controlled copies.",
            deadline_instructions="Use the locally approved Finance calendar.",
            retention_instructions="Retain under the approved Accounting file plan.",
            pagination_instructions="Number every page and continuation.",
            overflow_instructions="Use a numbered continuation without shrinking text.",
            accessibility_instructions="Keep labels readable and preserve logical order.",
            created_by=self.worker,
        )

    def _cycle(self, *, code="task-cycle", status=FinanceShadowCycle.DRAFT):
        today = timezone.localdate()
        return FinanceShadowCycle.objects.create(
            department=self.accounting,
            code=code,
            title="Controlled parallel-run checkpoint",
            fiscal_year=today.year,
            run_kind=FinanceShadowCycle.PARALLEL,
            enabled_scope="Synthetic Accounting fund and disbursement scope.",
            source_extract_reference="Redacted retained register TC-1.",
            source_checksum="1" * 64,
            source_schema_signature="2" * 64,
            planned_start=today - timedelta(days=5),
            planned_end=today - timedelta(days=1),
            status=status,
            reconciled_by=self.reviewer if status == FinanceShadowCycle.RECONCILED else None,
            reconciled_at=timezone.now() if status == FinanceShadowCycle.RECONCILED else None,
            created_by=self.worker,
        )

    def _defect(self, cycle, *, code="task-defect", owner=None):
        owner = owner or self.worker
        comparison = FinanceShadowComparison.objects.create(
            cycle=cycle,
            comparison_level=FinanceShadowComparison.CASE,
            control_code=f"{code}-control",
            label=f"Control for {code}",
            source_reference="Synthetic retained source register.",
            grand_reference="Synthetic GRAND control result.",
            source_amount=Decimal("100.00"),
            grand_amount=Decimal("90.00"),
            outcome=FinanceShadowComparison.OPEN_DEFECT,
            explanation="Synthetic unexplained difference requiring correction.",
            evidence_reference="Synthetic task-contract evidence.",
            defect_owner=owner,
            created_by=self.worker,
        )
        return FinanceShadowDefect.objects.create(
            cycle=cycle,
            comparison=comparison,
            code=code,
            severity=FinanceShadowDefect.HIGH,
            summary=f"Resolve {code}",
            impact="The test control does not balance.",
            owner=owner,
            correction_due_at=timezone.now() + timedelta(days=2),
            escalation_route_snapshot="Accounting reviewer",
            created_by=self.worker,
        )

    def _readiness_plan(self, cycle):
        return FinanceCutoverReadinessPlan.objects.create(
            cycle=cycle,
            curriculum_register_reference="Synthetic role curriculum.",
            quick_guides_reference="Synthetic quick guide.",
            supervisor_runbook_reference="Synthetic supervisor runbook.",
            support_owner=self.reviewer,
            support_channels_and_hours="Finance help desk, 08:00–17:00.",
            support_escalation_procedure="Accounting head then authorized management.",
            local_acceptance_note="Synthetic task-contract acceptance note.",
            status=FinanceCutoverReadinessPlan.APPROVED,
            evidence_checksum="3" * 64,
            created_by=self.worker,
            submitted_by=self.worker,
            submitted_at=timezone.now(),
            approved_by=self.reviewer,
            approved_at=timezone.now(),
            review_note="Synthetic independent plan review.",
        )

    def _exercise(self, cycle, *, code="task-exercise"):
        plan = self._readiness_plan(cycle)
        return FinanceCutoverReadinessExercise.objects.create(
            cycle=cycle,
            plan=plan,
            kind=FinanceCutoverReadinessExercise.SECURITY_ACCESS,
            code=code,
            title="Verify least-privilege field access",
            enabled_scope=cycle.enabled_scope,
            procedure="Use synthetic accounts to exercise permitted and denied paths.",
            expected_result="Every permitted and denied path matches the approved role matrix.",
            owner=self.worker,
            witness=self.reviewer,
            support_route_snapshot="Finance support owner",
            scheduled_for=timezone.now() + timedelta(hours=1),
            due_at=timezone.now() + timedelta(days=1),
            created_by=self.worker,
        )

    def _release(self, *, code, status, effective_from):
        now = timezone.now()
        return FinanceConfigurationRelease.objects.create(
            department=self.accounting,
            code=code,
            version=1,
            title=f"Controlled setup release {code}",
            fiscal_year=effective_from.year,
            status=status,
            effective_from=effective_from,
            created_by=self.worker,
            submitted_by=self.worker if status != "draft" else None,
            submitted_at=now if status != "draft" else None,
            approved_by=self.reviewer if status in {"approved", "scheduled"} else None,
            approved_at=now if status in {"approved", "scheduled"} else None,
        )

    def _decision(self, *, code, status, due_date):
        now = timezone.now()
        return FinanceDiscoveryDecision.objects.create(
            department=self.accounting,
            code=code,
            version=1,
            phase="F1",
            coverage_kind=FinanceDiscoveryDecision.BALANCE,
            question=f"Which retained balance control governs {code}?",
            proposed_outcome="Remain unresolved until the named local evidence is reviewed.",
            affected_scope=f"Synthetic exact scope for {code}.",
            evidence_label=FinanceDiscoveryDecision.UNRESOLVED,
            evidence_needed="Retained locally accepted control and a redacted replay.",
            blocks_affected_scope=True,
            owner=self.worker,
            reviewer=self.reviewer,
            due_date=due_date,
            status=status,
            submitted_by=self.worker if status == FinanceDiscoveryDecision.SUBMITTED else None,
            submitted_at=now if status == FinanceDiscoveryDecision.SUBMITTED else None,
            reviewed_at=now if status == FinanceDiscoveryDecision.RETURNED else None,
            review_note="Return for exact retained evidence." if status == FinanceDiscoveryDecision.RETURNED else "",
            created_by=self.worker,
        )

    def test_ids_are_stable_and_separate_actions_on_one_source(self):
        item = self._form()

        first = finance_work_tasks(self.worker)
        second = finance_work_tasks(self.worker)
        first_ids = [task["task_id"] for task in first["tasks"]]
        second_ids = [task["task_id"] for task in second["tasks"]]

        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(first_ids), 2)
        self.assertEqual(len(set(first_ids)), 2)
        self.assertTrue(all(str(item.public_id) in task_id for task_id in first_ids))
        self.assertEqual(
            {task["task_type"] for task in first["tasks"]},
            {"finance.local-form.needs_mapping.v1", "finance.local-form.needs_reference.v1"},
        )
        self.assertEqual(FinanceLocalFormAcceptance.objects.get(pk=item.pk).status, item.status)

    def test_items_are_source_linked_scoped_and_timing_is_not_invented(self):
        form = self._form()
        hidden = self._form(department=self.budget, code="hidden-task-form")
        cycle = self._cycle()

        result = finance_work_tasks(self.worker)
        tasks = result["tasks"]

        self.assertEqual(result["task_count"], 3)
        self.assertFalse(any(str(hidden.public_id) in task["task_id"] for task in tasks))
        form_tasks = [task for task in tasks if str(form.public_id) in task["task_id"]]
        self.assertTrue(all(task["due_state"] == "No structured target" for task in form_tasks))
        self.assertTrue(all("locally accepted deadline" in task["calendar_basis"] for task in form_tasks))
        cycle_task = next(task for task in tasks if str(cycle.public_id) in task["task_id"])
        self.assertEqual(cycle_task["due_state"], "Past planned date")
        self.assertEqual(cycle_task["url"], reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}))
        self.assertIn("updated:", cycle_task["source_version"])

    def test_uat_preview_account_gets_no_item_level_tasks(self):
        self._form()
        self._cycle()

        result = finance_work_tasks(self.uat)

        self.assertEqual(result["task_count"], 0)
        self.assertEqual(result["tasks"], [])

    def test_my_work_displays_contract_and_authoritative_record_link(self):
        item = self._form()
        self.client.force_login(self.worker)

        response = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Exact work items")
        self.assertContains(response, f"finwork:v1:local-form:{item.public_id}:needs-mapping")
        self.assertContains(response, item.get_absolute_url())
        self.assertContains(response, "not a second transaction, assignment, or approval")

    def test_each_named_defect_is_its_own_stable_task(self):
        cycle = self._cycle(code="nested-defect-cycle")
        first = self._defect(cycle, code="difference-a")
        second = self._defect(cycle, code="difference-b")

        owner_tasks = [
            task for task in finance_work_tasks(self.worker)["tasks"]
            if task["task_type"] == "finance.field-defect.my_defects.v1"
        ]

        self.assertEqual(len(owner_tasks), 2)
        defect_group = next(
            group
            for group in finance_work_attention(self.worker)["groups"]
            if group["key"] == "field-defect-correction"
        )
        self.assertEqual(defect_group["count"], 1)
        self.assertEqual(len({task["case_id"] for task in owner_tasks}), 2)
        self.assertTrue(all(task["reference"].startswith(f"{cycle.code} · defect") for task in owner_tasks))
        self.assertEqual(
            {task["url"] for task in owner_tasks},
            {
                reverse("finance:shadow_defect_resolution", kwargs={"pk": first.pk}),
                reverse("finance:shadow_defect_resolution", kwargs={"pk": second.pk}),
            },
        )
        self.assertEqual(
            [task["task_id"] for task in owner_tasks],
            [
                task["task_id"] for task in finance_work_tasks(self.worker)["tasks"]
                if task["task_type"] == "finance.field-defect.my_defects.v1"
            ],
        )

        FinanceShadowDefect.objects.filter(pk=first.pk).update(
            status=FinanceShadowDefect.RESOLUTION_REVIEW,
            resolution_note="Corrected the synthetic control input.",
            resolution_evidence_reference="Synthetic corrected comparison.",
            resolution_submitted_by=self.worker,
            resolution_submitted_at=timezone.now(),
        )
        review_tasks = [
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"] == "finance.field-defect.review_defects.v1"
        ]
        remaining_owner_tasks = [
            task for task in finance_work_tasks(self.worker)["tasks"]
            if task["task_type"] == "finance.field-defect.my_defects.v1"
        ]

        self.assertEqual(len(review_tasks), 1)
        self.assertIn("difference-a", review_tasks[0]["reference"])
        self.assertEqual(review_tasks[0]["url"], reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}))
        self.assertEqual(len(remaining_owner_tasks), 1)
        self.assertIn("difference-b", remaining_owner_tasks[0]["reference"])

    def test_exercise_owner_and_independent_witness_get_separate_exact_actions(self):
        cycle = self._cycle(code="nested-exercise-cycle")
        exercise = self._exercise(cycle)

        owner_task = next(
            task for task in finance_work_tasks(self.worker)["tasks"]
            if task["task_type"] == "finance.field-exercise.my_exercises.v1"
        )
        self.assertEqual(
            owner_task["url"],
            reverse("finance:cutover_readiness_exercise_result", kwargs={"pk": exercise.pk}),
        )
        self.assertIn("no holiday adjustment inferred", owner_task["calendar_basis"])

        FinanceCutoverReadinessExercise.objects.filter(pk=exercise.pk).update(
            status=FinanceCutoverReadinessExercise.SUBMITTED,
            actual_result="The synthetic allowed and denied paths matched the role matrix.",
            evidence_reference="Synthetic access-control worksheet.",
            evidence_checksum="4" * 64,
            submitted_by=self.worker,
            submitted_at=timezone.now(),
        )
        witness_tasks = [
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"] == "finance.field-exercise.witness_exercises.v1"
        ]
        former_owner_tasks = [
            task for task in finance_work_tasks(self.worker)["tasks"]
            if task["task_type"] == "finance.field-exercise.my_exercises.v1"
        ]

        self.assertEqual(len(witness_tasks), 1)
        self.assertIn("independent witness", witness_tasks[0]["gate"])
        self.assertEqual(witness_tasks[0]["url"], reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}))
        self.assertEqual(former_owner_tasks, [])

    def test_stakeholder_and_cutover_authority_tasks_keep_deadline_and_version_limits_plain(self):
        cycle = self._cycle(code="nested-authority-cycle", status=FinanceShadowCycle.RECONCILED)
        acceptance = FinanceStakeholderAcceptance.objects.create(
            cycle=cycle,
            stakeholder_kind=FinanceStakeholderAcceptance.ACCOUNTING,
            assigned_reviewer=self.reviewer,
            enabled_scope=cycle.enabled_scope,
            created_by=self.worker,
        )
        decision = FinanceCutoverDecision.objects.create(
            cycle=cycle,
            authority_matrix_reference="Synthetic retained authority matrix.",
            enabled_scope=cycle.enabled_scope,
            cutover_at=timezone.now() + timedelta(days=3),
            opening_reconciliation_reference="Synthetic zero-difference opening reconciliation.",
            rollback_criteria="Any unexplained difference or control failure.",
            legacy_read_only_retention_plan="Retain the legacy system read-only under the local records plan.",
            backup_recovery_evidence="Synthetic recovery evidence; not field acceptance.",
            signed_authority_reference="Synthetic retained signed authority record.",
            signed_authority_checksum="5" * 64,
            signature_custody_reference="Synthetic Records custody location.",
            prepared_by=self.worker,
        )
        FinanceCutoverDecision.objects.filter(pk=decision.pk).update(
            status=FinanceCutoverDecision.SUBMITTED,
            submitted_by=self.worker,
            submitted_at=timezone.now(),
        )

        tasks = finance_work_tasks(self.reviewer)["tasks"]
        acceptance_task = next(
            task for task in tasks
            if task["task_type"] == "finance.field-stakeholder.my_acceptances.v1"
        )
        authority_task = next(
            task for task in tasks
            if task["task_type"] == "finance.field-cutover.authorize_cutover.v1"
        )

        self.assertEqual(
            acceptance_task["url"],
            reverse("finance:stakeholder_acceptance_decide", kwargs={"pk": acceptance.pk}),
        )
        self.assertEqual(acceptance_task["due_state"], "No structured target")
        self.assertTrue(acceptance_task["source_version"].startswith("projection-sha256:"))
        self.assertIn("not an inferred approval deadline", authority_task["calendar_basis"])
        self.assertTrue(authority_task["source_version"].startswith("submitted:"))
        self.assertEqual(authority_task["url"], reverse("finance:shadow_cycle_detail", kwargs={"pk": cycle.pk}))

        initial_task_id = acceptance_task["task_id"]
        initial_version = acceptance_task["source_version"]
        acceptance.training_evidence_reference = "New synthetic training evidence reference."
        acceptance.save(update_fields=("training_evidence_reference",))
        changed_task = next(
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"] == "finance.field-stakeholder.my_acceptances.v1"
        )
        self.assertEqual(changed_task["task_id"], initial_task_id)
        self.assertNotEqual(changed_task["source_version"], initial_version)

        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("finance_operations:my_work"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, changed_task["task_id"])
        self.assertContains(response, authority_task["task_id"])
        self.assertContains(response, "Proposed cutover is upcoming")

    def test_setup_release_tasks_separate_preparation_review_schedule_and_activation(self):
        today = timezone.localdate()
        draft = self._release(code="setup-draft", status="draft", effective_from=today + timedelta(days=10))
        submitted = self._release(code="setup-review", status="submitted", effective_from=today + timedelta(days=8))
        future = self._release(code="setup-schedule", status="approved", effective_from=today + timedelta(days=5))
        ready = self._release(code="setup-activate", status="approved", effective_from=today)

        preparer_tasks = [
            task for task in finance_work_tasks(self.worker)["tasks"]
            if task["task_type"].startswith("finance.setup-release.")
        ]
        reviewer_tasks = [
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"].startswith("finance.setup-release.")
        ]

        self.assertEqual(len(preparer_tasks), 1)
        self.assertIn("setup-draft", preparer_tasks[0]["reference"])
        self.assertEqual(preparer_tasks[0]["url"], reverse("finance:release_detail", kwargs={"pk": draft.pk}))
        self.assertEqual(
            {task["task_type"] for task in reviewer_tasks},
            {
                "finance.setup-release.awaiting_review.v1",
                "finance.setup-release.ready_to_schedule.v1",
                "finance.setup-release.ready_to_activate.v1",
            },
        )
        task_by_type = {task["task_type"]: task for task in reviewer_tasks}
        self.assertEqual(task_by_type["finance.setup-release.awaiting_review.v1"]["due_on"], None)
        self.assertEqual(task_by_type["finance.setup-release.ready_to_schedule.v1"]["due_on"], future.effective_from)
        self.assertEqual(task_by_type["finance.setup-release.ready_to_activate.v1"]["due_on"], ready.effective_from)
        self.assertIn("not an inferred approval deadline", task_by_type["finance.setup-release.ready_to_schedule.v1"]["calendar_basis"])

        self._grant(self.worker, "finance.approve_finance_configuration")
        self.assertFalse(any(
            task["task_type"] == "finance.setup-release.awaiting_review.v1"
            and "setup-review" in task["reference"]
            for task in finance_work_tasks(self.worker)["tasks"]
        ))
        self.assertEqual(submitted.submitted_by_id, self.worker.pk)

    def test_discovery_tasks_preserve_named_review_scope_returned_state_and_dates(self):
        today = timezone.localdate()
        draft = self._decision(
            code="DEC-TASK-DRAFT", status=FinanceDiscoveryDecision.DRAFT,
            due_date=today + timedelta(days=2),
        )
        returned = self._decision(
            code="DEC-TASK-RETURN", status=FinanceDiscoveryDecision.RETURNED,
            due_date=today - timedelta(days=1),
        )
        submitted = self._decision(
            code="DEC-TASK-REVIEW", status=FinanceDiscoveryDecision.SUBMITTED,
            due_date=None,
        )

        preparer_tasks = [
            task for task in finance_work_tasks(self.worker)["tasks"]
            if task["task_type"] == "finance.discovery-decision.needs_preparation.v1"
        ]
        review_tasks = [
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"] == "finance.discovery-decision.my_reviews.v1"
        ]

        self.assertEqual(len(preparer_tasks), 2)
        self.assertEqual(len(review_tasks), 1)
        self.assertIn(str(submitted.public_id), review_tasks[0]["task_id"])
        self.assertEqual(
            review_tasks[0]["url"],
            reverse("finance:discovery_decision_detail", kwargs={"public_id": submitted.public_id}),
        )
        returned_task = next(task for task in preparer_tasks if str(returned.public_id) in task["task_id"])
        draft_task = next(task for task in preparer_tasks if str(draft.public_id) in task["task_id"])
        self.assertEqual(returned_task["state"], "Returned")
        self.assertEqual(returned_task["due_state"], "Past planned date")
        self.assertIn("returned this decision", returned_task["exception"])
        self.assertEqual(draft_task["due_state"], "Within planned period")
        self.assertIn("blocks only its named affected scope", draft_task["exception"])


class FinanceBudgetWorkTaskContractTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.budget = Department.objects.create(name="Municipal Budget Office", slug="task-budget")
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="task-budget-ledger")
        cls.requesting = Department.objects.create(name="General Services Office", slug="task-budget-requesting")
        cls.preparer = cls._employee(
            "task.budget.preparer", cls.budget,
            "view_budget_workspace", "prepare_budget_proposals",
            "view_allotment_control", "prepare_allotment_releases",
        )
        cls.reviewer = cls._employee(
            "task.budget.reviewer", cls.budget,
            "view_budget_workspace", "review_budget_proposals",
            "view_allotment_control", "approve_allotment_releases",
        )
        cls.requester = cls._employee(
            "task.budget.requester", cls.requesting,
            "view_budget_workspace", "initiate_obligation_requests",
        )
        cls.certifier = cls._employee(
            "task.budget.certifier", cls.budget,
            "view_budget_workspace", "view_obligation_registry", "certify_obligations",
        )
        cls.uat = cls._employee(
            "task.budget.uat", cls.budget, "view_budget_workspace", "prepare_budget_proposals",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        today = timezone.localdate()
        cls.fiscal_year = FiscalYear.objects.create(
            department_id=cls.accounting.pk, department_label=cls.accounting.name,
            year=today.year, label=f"FY {today.year}",
            starts_on=date(today.year, 1, 1), ends_on=date(today.year, 12, 31),
            business_date=today, status=FiscalYear.APPROVED,
        )
        cls.call = BudgetCall.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            fiscal_year=cls.fiscal_year, title="Controlled annual Budget call",
            authority_reference="Synthetic retained Budget authority.",
            instructions="Prepare and independently review each exact version.",
            proposal_opens_on=today - timedelta(days=10), proposal_due_on=today + timedelta(days=10),
            status=BudgetCall.PUBLISHED, created_by_id=cls.preparer.pk,
            created_by_label=cls.preparer.username,
        )
        cls.authority_version = BudgetVersion.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            budget_call=cls.call, fiscal_year=cls.fiscal_year, kind=BudgetVersion.FINAL,
            version=90, title="Synthetic operational authority source",
            change_explanation="Synthetic task-contract fixture.", status=BudgetVersion.AUTHORIZED,
            created_by_id=cls.preparer.pk, created_by_label=cls.preparer.username,
        )
        cls.authority = AppropriationAuthorization.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            version=cls.authority_version, authority_type=AppropriationAuthorization.ORDINANCE,
            ordinance_number="ORD-TASK-001", ordinance_date=today - timedelta(days=30),
            effectivity_date=date(today.year, 1, 1), review_status=AppropriationAuthorization.FAVORABLE,
            review_reference="Synthetic independent review.", review_date=today - timedelta(days=20),
            evidence_reference="Synthetic retained signed schedule.", signed_control_total=Decimal("0.00"),
            status=AppropriationAuthorization.AUTHORIZED,
            created_by_id=cls.preparer.pk, created_by_label=cls.preparer.username,
            submitted_by_id=cls.preparer.pk, submitted_by_label=cls.preparer.username,
            authorized_by_id=cls.reviewer.pk, authorized_by_label=cls.reviewer.username,
        )

    @classmethod
    def _employee(cls, username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="budget-task-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="budget", codename__in=permissions,
        ))
        return get_user_model().objects.get(pk=user.pk)

    def _version(self, code, status, submitted_by=None):
        return BudgetVersion.objects.create(
            department_id=self.budget.pk, department_label=self.budget.name,
            budget_call=self.call, fiscal_year=self.fiscal_year,
            kind=BudgetVersion.DEPARTMENT, version=code,
            title=f"Department proposal {code}", requesting_department_id=self.requesting.pk,
            requesting_department_label=self.requesting.name,
            change_explanation="Synthetic exact-task version.", status=status,
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
            submitted_by_id=submitted_by.pk if submitted_by else None,
            submitted_by_label=submitted_by.username if submitted_by else "",
            submitted_at=timezone.now() if submitted_by else None,
        )

    def _allotment(self, number, status, submitted_by=None, signed_total="0.00"):
        return AllotmentReleaseOrder.objects.create(
            department_id=self.budget.pk, department_label=self.budget.name,
            authorization=self.authority, fiscal_year=self.fiscal_year,
            order_number=number, kind=AllotmentReleaseOrder.INITIAL,
            release_date=timezone.localdate(), effective_date=timezone.localdate(),
            authority_reference="Synthetic allotment authority.",
            evidence_reference="Synthetic signed ARO reference.", purpose="Controlled operating release.",
            signed_control_total=Decimal(signed_total), status=status,
            created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
            submitted_by_id=submitted_by.pk if submitted_by else None,
            submitted_by_label=submitted_by.username if submitted_by else "",
            submitted_at=timezone.now() if submitted_by else None,
        )

    def _obligation(self, reference, status, submitted_by=None, signed_total="0.00"):
        return ObligationRequest.objects.create(
            department_id=self.budget.pk, department_label=self.budget.name,
            authorization=self.authority, fiscal_year=self.fiscal_year,
            requesting_department_id=self.requesting.pk, requesting_department_label=self.requesting.name,
            kind=ObligationRequest.ORIGINAL, form_type=ObligationRequest.OBR,
            request_reference=reference, obligation_date=timezone.localdate(),
            claimant_payee="Synthetic claimant", particulars="Controlled obligation request.",
            evidence_reference="Synthetic retained request evidence.",
            signed_control_total=Decimal(signed_total), status=status,
            created_by_id=self.requester.pk, created_by_label=self.requester.username,
            submitted_by_id=submitted_by.pk if submitted_by else None,
            submitted_by_label=submitted_by.username if submitted_by else "",
            submitted_at=timezone.now() if submitted_by else None,
        )

    def test_budget_versions_have_exact_due_dates_and_independent_review_scope(self):
        draft = self._version(1, BudgetVersion.DRAFT)
        review = self._version(2, BudgetVersion.FOR_REVIEW, self.preparer)
        self_review = self._version(3, BudgetVersion.FOR_REVIEW, self.reviewer)

        reviewer_source, *_rest = apply_annual_filters(
            BudgetVersion.objects.filter(department_id=self.budget.pk),
            attention="awaiting_proposal_review", actor=self.reviewer,
        )
        reviewer_tasks = [
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"] == "finance.budget-version.review.v1"
        ]
        preparer_tasks = [
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["task_type"] == "finance.budget-version.preparation.v1"
        ]

        self.assertEqual(set(reviewer_source), {review})
        self.assertEqual(len(reviewer_tasks), 1)
        self.assertIn(str(review.public_id), reviewer_tasks[0]["task_id"])
        self.assertNotIn(str(self_review.public_id), reviewer_tasks[0]["task_id"])
        self.assertEqual(preparer_tasks[0]["due_on"], self.call.proposal_due_on)
        self.assertEqual(preparer_tasks[0]["url"], reverse("budget:version_detail", kwargs={"public_id": draft.public_id}))
        self.client.force_login(self.reviewer)
        source_page = self.client.get(reverse("budget:workspace"), {"attention": "awaiting_proposal_review"})
        self.assertEqual([item.pk for item in source_page.context["versions"]], [review.pk])
        self.assertFalse(any(
            task["task_type"].startswith("finance.budget-")
            for task in finance_work_tasks(self.uat)["tasks"]
        ))
        self.assertNotIn(
            "budget-version-preparation",
            {group["key"] for group in finance_work_attention(self.uat)["groups"]},
        )

    def test_allotment_tasks_surface_nonzero_controls_and_exclude_self_review(self):
        draft = self._allotment("ARO-TASK-DRAFT", AllotmentReleaseOrder.DRAFT, signed_total="100.00")
        review = self._allotment("ARO-TASK-REVIEW", AllotmentReleaseOrder.FOR_REVIEW, self.preparer)
        self_review = self._allotment("ARO-TASK-SELF", AllotmentReleaseOrder.FOR_REVIEW, self.reviewer)

        reviewer_source, *_rest = apply_allotment_filters(
            AllotmentReleaseOrder.objects.filter(department_id=self.budget.pk),
            attention="awaiting_review", actor=self.reviewer,
        )
        preparer_task = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if str(draft.public_id) in task["task_id"]
        )
        reviewer_tasks = [
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"] == "finance.allotment-order.review.v1"
        ]

        self.assertEqual(set(reviewer_source), {review})
        self.assertEqual(len(reviewer_tasks), 1)
        self.assertNotIn(str(self_review.public_id), reviewer_tasks[0]["task_id"])
        self.assertIn("Control difference is 100.00", preparer_task["exception"])
        self.assertIn("reconcile it to zero", preparer_task["exception"])
        self.client.force_login(self.reviewer)
        source_page = self.client.get(reverse("budget:allotment_workspace"), {"attention": "awaiting_review"})
        self.assertEqual([item.pk for item in source_page.context["orders"]], [review.pk])

    def test_obligation_tasks_keep_requesting_scope_zero_control_and_certifier_independence(self):
        draft = self._obligation("REQ-TASK-DRAFT", ObligationRequest.DRAFT, signed_total="25.00")
        review = self._obligation("REQ-TASK-REVIEW", ObligationRequest.FOR_CERTIFICATION, self.requester)
        self_review = self._obligation("REQ-TASK-SELF", ObligationRequest.FOR_CERTIFICATION, self.certifier)

        certifier_source, *_rest = apply_obligation_filters(
            obligation_scope_for_user(self.certifier), attention="awaiting_certification", actor=self.certifier,
        )
        requester_tasks = [
            task for task in finance_work_tasks(self.requester)["tasks"]
            if task["task_type"] == "finance.obligation-request.preparation.v1"
        ]
        certifier_tasks = [
            task for task in finance_work_tasks(self.certifier)["tasks"]
            if task["task_type"] == "finance.obligation-request.certification.v1"
        ]

        self.assertEqual(set(certifier_source), {review})
        self.assertEqual(len(requester_tasks), 1)
        self.assertIn(str(draft.public_id), requester_tasks[0]["task_id"])
        self.assertIn("Control difference is 25.00", requester_tasks[0]["exception"])
        self.assertEqual(len(certifier_tasks), 1)
        self.assertIn(str(review.public_id), certifier_tasks[0]["task_id"])
        self.assertNotIn(str(self_review.public_id), certifier_tasks[0]["task_id"])
        self.client.force_login(self.certifier)
        source_page = self.client.get(
            reverse("budget:obligation_workspace"), {"attention": "awaiting_certification"},
        )
        self.assertEqual([item.pk for item in source_page.context["requests"]], [review.pk])


class FinancePayableWorkTaskContractTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="task-payable-accounting",
        )
        cls.requesting = Department.objects.create(
            name="General Services Office", slug="task-payable-requesting",
        )
        cls.other_requesting = Department.objects.create(
            name="Municipal Engineering Office", slug="task-payable-other-requesting",
        )
        cls.preparer = cls._employee(
            "task.payable.preparer", cls.requesting,
            "view_voucher_workbench", "initiate_payable_case",
        )
        cls.other_preparer = cls._employee(
            "task.payable.other", cls.other_requesting,
            "view_voucher_workbench", "initiate_payable_case",
        )
        cls.reviewer = cls._employee(
            "task.payable.reviewer", cls.accounting,
            "view_voucher_workbench", "review_payable_intake",
        )
        cls.uat = cls._employee(
            "task.payable.uat", cls.accounting,
            "view_voucher_workbench", "review_payable_intake",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])

    @classmethod
    def _employee(cls, username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="payable-task-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers", codename__in=permissions,
        ))
        return get_user_model().objects.get(pk=user.pk)

    def _case(
        self, reference, *, stage, requesting=None, current=None, prepared_by=None,
        submitted_by=None, status=PayableIntake.DRAFT, claim="100.00", with_intake=True,
    ):
        requesting = requesting or self.requesting
        current = current or requesting
        prepared_by = prepared_by or self.preparer
        item = VoucherCase.objects.create(
            reference_code=reference,
            requesting_department=requesting,
            current_department=current,
            payee_name="Synthetic LGU supplier",
            particulars="Controlled payable work-item contract fixture.",
            authoritative_obligation_number=f"OBR-{reference}",
            authoritative_obligation_amount=Decimal(claim),
            obligation_binding_status=VoucherCase.BINDING_LINKED,
            current_stage=stage,
            created_by=prepared_by,
        )
        if with_intake:
            PayableIntake.objects.create(
                case=item,
                claim_reference=f"CLAIM-{reference}",
                claim_amount=Decimal(claim),
                initial_allocation_amount=Decimal(claim),
                initial_relationship_type=PayableIntake.FULL,
                evidence_reference="Synthetic retained payable evidence reference.",
                status=status,
                submitted_by=submitted_by,
                submitted_at=timezone.now() if submitted_by else None,
                reviewed_by=self.reviewer if status == PayableIntake.RETURNED else None,
                reviewed_at=timezone.now() if status == PayableIntake.RETURNED else None,
                decision_reason="Correct the named control difference." if status == PayableIntake.RETURNED else "",
                prepared_by=prepared_by,
            )
        return item

    def test_preparation_tasks_are_exact_requesting_office_items_with_no_invented_due_date(self):
        own = self._case(
            "PAY-TASK-PREP", stage=VoucherCase.PAYABLE_PREPARATION,
            status=PayableIntake.DRAFT,
        )
        returned = self._case(
            "PAY-TASK-RETURN", stage=VoucherCase.PAYABLE_PREPARATION,
            status=PayableIntake.RETURNED,
        )
        self._case(
            "PAY-TASK-OTHER", stage=VoucherCase.PAYABLE_PREPARATION,
            requesting=self.other_requesting, current=self.other_requesting,
            prepared_by=self.other_preparer,
        )
        self._case(
            "PAY-TASK-MISROUTED", stage=VoucherCase.PAYABLE_PREPARATION,
            current=self.accounting,
        )

        source, _selected, _spec = payable_action_queryset(self.preparer, "preparation")
        tasks = [
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["task_type"] == "finance.payable-intake.preparation.v1"
        ]

        self.assertEqual(set(source), {own, returned})
        self.assertEqual(len(tasks), 2)
        own_task = next(task for task in tasks if str(own.public_id) in task["task_id"])
        returned_task = next(task for task in tasks if str(returned.public_id) in task["task_id"])
        self.assertIsNone(own_task["due_on"])
        self.assertEqual(own_task["due_state"], "No structured target")
        self.assertIn("No payable action deadline is stored", own_task["calendar_basis"])
        self.assertEqual(own_task["url"], own.get_absolute_url())
        self.assertIn("Claim-to-allocation control difference is 100.00", own_task["exception"])
        self.assertEqual(returned_task["state"], "Returned")
        self.assertIn("returned this same intake", returned_task["exception"])

    def test_review_tasks_and_source_queue_exclude_maker_and_wrong_current_office(self):
        review = self._case(
            "PAY-TASK-REVIEW", stage=VoucherCase.PAYABLE_REVIEW,
            current=self.accounting, submitted_by=self.preparer, status=PayableIntake.FOR_REVIEW,
        )
        self._case(
            "PAY-TASK-SELF", stage=VoucherCase.PAYABLE_REVIEW,
            current=self.accounting, prepared_by=self.reviewer,
            submitted_by=self.reviewer, status=PayableIntake.FOR_REVIEW,
        )
        self._case(
            "PAY-TASK-WRONG-OFFICE", stage=VoucherCase.PAYABLE_REVIEW,
            current=self.other_requesting, submitted_by=self.preparer,
            status=PayableIntake.FOR_REVIEW,
        )

        source, _selected, _spec = payable_action_queryset(self.reviewer, "review")
        filtered_source, *_filters = apply_case_filters(
            visible_cases_for_user(self.reviewer),
            actionable_stages=(VoucherCase.PAYABLE_REVIEW,),
            attention="ready_for_me", actor=self.reviewer,
        )
        tasks = [
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"] == "finance.payable-intake.review.v1"
        ]

        self.assertEqual(set(source), {review})
        self.assertEqual(set(filtered_source), {review})
        self.assertEqual(len(tasks), 1)
        self.assertIn(str(review.public_id), tasks[0]["task_id"])
        self.assertIn("Independent Accounting", tasks[0]["gate"])
        self.client.force_login(self.reviewer)
        page = self.client.get(reverse("vouchers:workspace"), {"attention": "ready_for_me"})
        self.assertEqual(page.status_code, 200)
        self.assertEqual([item.pk for item in page.context["queue_cases"]], [review.pk])
        voucher_group = next(
            group for group in finance_work_attention(self.reviewer)["groups"]
            if group["key"] == "voucher-ready"
        )
        self.assertEqual(voucher_group["count"], page.context["queue_count"])
        self.assertEqual(voucher_group["count"], 1)

    def test_projection_version_changes_without_changing_task_identity(self):
        item = self._case(
            "PAY-TASK-REVISION", stage=VoucherCase.PAYABLE_REVIEW,
            current=self.accounting, submitted_by=self.preparer, status=PayableIntake.FOR_REVIEW,
        )
        first = next(
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if str(item.public_id) in task["task_id"]
        )
        intake = item.payable_intake
        intake.duplicate_warning = "Synthetic possible duplicate needing human review."
        intake.save(update_fields=("duplicate_warning",))
        second = next(
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if str(item.public_id) in task["task_id"]
        )

        self.assertEqual(second["task_id"], first["task_id"])
        self.assertNotEqual(second["source_version"], first["source_version"])
        self.assertIn("duplicate warning", second["exception"])

    def test_missing_intake_is_a_visible_blocker_and_uat_gets_no_exact_actions(self):
        item = self._case(
            "PAY-TASK-MISSING", stage=VoucherCase.PAYABLE_PREPARATION,
            with_intake=False,
        )
        task = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if str(item.public_id) in task["task_id"]
        )

        self.assertIn("payable intake record is missing", task["exception"])
        self.assertIn("intake record missing", task["source_state"])
        self.assertFalse(any(
            task["task_type"].startswith("finance.payable-intake.")
            for task in finance_work_tasks(self.uat)["tasks"]
        ))
        self.assertNotIn(
            "voucher-ready",
            {group["key"] for group in finance_work_attention(self.uat)["groups"]},
        )


class FinanceDVCustodyWorkTaskContractTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="task-dv-accounting",
        )
        cls.requesting = Department.objects.create(
            name="General Services Office", slug="task-dv-requesting",
        )
        cls.other = Department.objects.create(
            name="Municipal Engineering Office", slug="task-dv-other",
        )
        cls.preparer = cls._employee(
            "task.dv.preparer", cls.accounting,
            "view_voucher_workbench", "prepare_disbursement_voucher",
        )
        cls.certifier = cls._employee(
            "task.dv.certifier", cls.accounting,
            "view_voucher_workbench", "prepare_disbursement_voucher",
        )
        cls.print_operator = cls._employee(
            "task.dv.print", cls.accounting,
            "view_voucher_workbench", "control_dv_printing", "link_tracepoint_custody",
        )
        cls.signature_operator = cls._employee(
            "task.dv.signature", cls.accounting,
            "view_voucher_workbench", "track_wet_signatures",
        )
        cls.validator = cls._employee(
            "task.dv.validator", cls.accounting,
            "view_voucher_workbench", "validate_accounting_voucher",
        )
        cls.uat = cls._employee(
            "task.dv.uat", cls.accounting,
            "view_voucher_workbench", "prepare_disbursement_voucher",
            "control_dv_printing", "track_wet_signatures", "link_tracepoint_custody",
            "validate_accounting_voucher",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        today = timezone.localdate()
        cls.release = FinanceConfigurationRelease.objects.create(
            department=cls.accounting, code="task-dv-release", version=1,
            title="Synthetic DV task release", fiscal_year=today.year,
            status="active", effective_from=today, created_by=cls.preparer,
        )
        cls.template = FinanceTemplateVersion.objects.create(
            department=cls.accounting, release=cls.release,
            document_type="disbursement-voucher", version=1,
            title="Synthetic controlled DV task template",
            controlled_print_required=True, workbook="finance/templates/task-dv.xlsx",
            workbook_checksum="a" * 64, effective_from=today, created_by=cls.preparer,
        )

    @classmethod
    def _employee(cls, username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="dv-task-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers", codename__in=permissions,
        ))
        return get_user_model().objects.get(pk=user.pk)

    def _case(
        self, reference, *, stage=VoucherCase.ACCOUNTING_PREPARATION,
        current=None, certified_by=None, with_voucher=False, controlled=True,
        dv_prepared_by=None,
    ):
        item = VoucherCase.objects.create(
            reference_code=reference, requesting_department=self.requesting,
            current_department=current or self.accounting,
            configuration_release=self.release,
            voucher_template=self.template if controlled else None,
            payee_name="Synthetic LGU supplier",
            particulars="Controlled DV and physical-custody task fixture.",
            authoritative_obligation_number=f"OBR-{reference}",
            authoritative_obligation_amount=Decimal("100.00"),
            obligation_binding_status=VoucherCase.BINDING_LINKED,
            current_stage=stage, created_by=self.preparer,
        )
        obligation = BudgetObligation.objects.create(
            case=item, obr_number=f"OBR-{reference}", obligation_date=timezone.localdate(),
            budget_source_reference="Synthetic retained appropriation evidence.",
            certified_amount=Decimal("100.00"), certified_by=certified_by or self.certifier,
            certified_at=timezone.now(),
        )
        BudgetAllocationLine.objects.create(
            obligation=obligation, fund_code="general-fund",
            responsibility_center_code="task-gso", account_code="5-02-03",
            amount=Decimal("100.00"),
        )
        if with_voucher:
            DisbursementVoucher.objects.create(
                case=item, dv_number=f"DV-{reference}", voucher_date=timezone.localdate(),
                gross_amount=Decimal("100.00"), total_deductions=Decimal("10.00"),
                net_amount=Decimal("90.00"), prepared_by=dv_prepared_by or self.preparer,
                prepared_at=timezone.now(),
            )
        return item

    def _print_job(self, item, status):
        output = VoucherOutput.objects.create(
            case=item, output_type="signing-copy", version=1, template=self.template,
            file=f"vouchers/outputs/{item.reference_code}/signing-copy/v1/dv.xlsx",
            checksum="b" * 64, input_snapshot={"case": item.reference_code},
            status=VoucherOutput.OFFICIAL, generated_by=self.print_operator,
        )
        printed = status in {VoucherPrintJob.PRINTED, VoucherPrintJob.AWAITING_SIGNATURES}
        return VoucherPrintJob.objects.create(
            case=item, version=1, output=output, output_checksum=output.checksum,
            signature_round=1, status=status,
            copy_count=2 if printed else None,
            printer_or_form_stock="Accounting printer 1 · A4 controlled stock" if printed else "",
            print_note="Two legible copies counted." if printed else "",
            prepared_by=self.print_operator,
            printed_by=self.print_operator if printed else None,
            printed_at=timezone.now() if printed else None,
            archive_manifest={"sha256": output.checksum, "relative_path": output.file.name},
        )

    def test_dv_preparation_scope_enforces_current_office_and_certifier_separation(self):
        ready = self._case("DV-TASK-READY")
        self._case("DV-TASK-WRONG", current=self.other)
        self_certified = self._case("DV-TASK-SELF", certified_by=self.preparer)

        source, _selected, _spec = dv_custody_action_queryset(self.preparer, "dv_preparation")
        filtered_source, *_filters = apply_case_filters(
            visible_cases_for_user(self.preparer),
            actionable_stages=(VoucherCase.ACCOUNTING_PREPARATION,),
            attention="ready_for_me", actor=self.preparer,
        )
        tasks = [
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["task_type"] == "finance.dv-custody.dv_preparation.v1"
        ]

        self.assertEqual(set(source), {ready})
        self.assertEqual(set(filtered_source), {ready})
        self.assertEqual(len(tasks), 1)
        self.assertIn(str(ready.public_id), tasks[0]["task_id"])
        self.assertIsNone(tasks[0]["due_on"])
        self.assertIn("gross-deduction-net equation", tasks[0]["action"])

        FinanceWorkflowExemption.objects.create(
            department=self.accounting,
            control_code=FinanceWorkflowExemption.BUDGET_CERTIFIER_DV_PREPARATION,
            subject_user=self.preparer,
            rationale="Synthetic scarce-staff exception with named compensating review.",
            created_by=self.certifier,
        )
        exempt_source, _selected, _spec = dv_custody_action_queryset(
            self.preparer, "dv_preparation",
        )
        self.assertEqual(set(exempt_source), {ready, self_certified})

    def test_print_actions_are_state_specific_and_do_not_overlap(self):
        signing_copy = self._case(
            "DV-TASK-COPY", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True,
        )
        record_print = self._case(
            "DV-TASK-PRINT", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True,
        )
        assemble = self._case(
            "DV-TASK-PACKET", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True,
        )
        self._print_job(record_print, VoucherPrintJob.READY_TO_PRINT)
        self._print_job(assemble, VoucherPrintJob.PRINTED)

        expected = {
            "signing_copy": signing_copy,
            "record_print": record_print,
            "assemble_packet": assemble,
        }
        for action, item in expected.items():
            with self.subTest(action=action):
                queryset, _selected, _spec = dv_custody_action_queryset(self.print_operator, action)
                self.assertEqual(set(queryset), {item})

        tasks = [
            task for task in finance_work_tasks(self.print_operator)["tasks"]
            if task["task_type"].startswith("finance.dv-custody.")
        ]
        self.assertEqual(len(tasks), 3)
        self.assertEqual(
            {task["case_id"] for task in tasks},
            {f"voucher-case:{item.public_id}" for item in expected.values()},
        )

    def test_only_earliest_ready_signature_is_projected_for_controlled_copy(self):
        item = self._case(
            "DV-TASK-SIGN", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True,
        )
        first = WetSignatureTask.objects.create(
            case=item, round_number=1, sequence=1, role_code="department-head",
            signatory_name_snapshot="Synthetic Department Head",
            position_snapshot="Department Head", custody_department=self.accounting,
            custody_instructions="Route through the counted Accounting packet.",
        )
        second = WetSignatureTask.objects.create(
            case=item, round_number=1, sequence=2, role_code="municipal-accountant",
            signatory_name_snapshot="Synthetic Municipal Accountant",
            position_snapshot="Municipal Accountant", custody_department=self.accounting,
        )
        self.assertFalse(dv_signature_task_queryset(self.signature_operator).exists())

        job = self._print_job(item, VoucherPrintJob.AWAITING_SIGNATURES)
        first_query = list(dv_signature_task_queryset(self.signature_operator))
        first_task = next(
            task for task in finance_work_tasks(self.signature_operator)["tasks"]
            if task["task_type"] == "finance.wet-signature.record-return.v1"
        )
        self.assertEqual(first_query, [first])
        self.assertIn("step 1", first_task["reference"])
        self.assertIn("not the wet signature itself", first_task["exception"])

        first.status = WetSignatureTask.SIGNED_RETURNED
        first.recorded_by = self.signature_operator
        first.recorded_at = timezone.now()
        first.note = "Signed paper received in the controlled packet."
        first.save(update_fields=("status", "recorded_by", "recorded_at", "note"))
        self.assertEqual(list(dv_signature_task_queryset(self.signature_operator)), [second])
        next_task = next(
            task for task in finance_work_tasks(self.signature_operator)["tasks"]
            if task["task_type"] == "finance.wet-signature.record-return.v1"
        )
        self.assertIn("step 2", next_task["reference"])
        self.assertEqual(job.status, VoucherPrintJob.AWAITING_SIGNATURES)

    def test_projection_identity_is_stable_and_checksum_tracks_print_evidence(self):
        item = self._case(
            "DV-TASK-REVISION", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True,
        )
        job = self._print_job(item, VoucherPrintJob.READY_TO_PRINT)
        first = next(
            task for task in finance_work_tasks(self.print_operator)["tasks"]
            if str(item.public_id) in task["task_id"]
        )
        job.printer_or_form_stock = "Accounting printer 2 · replacement controlled stock"
        job.save(update_fields=("printer_or_form_stock",))
        second = next(
            task for task in finance_work_tasks(self.print_operator)["tasks"]
            if str(item.public_id) in task["task_id"]
        )

        self.assertEqual(second["task_id"], first["task_id"])
        self.assertNotEqual(second["source_version"], first["source_version"])

    def test_unbalanced_legacy_dv_is_visible_as_stop_exception_and_uat_has_no_actions(self):
        item = self._case(
            "DV-TASK-UNBALANCED", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True,
        )
        DisbursementVoucher.objects.filter(case=item).update(net_amount=Decimal("89.99"))
        task = next(
            task for task in finance_work_tasks(self.print_operator)["tasks"]
            if str(item.public_id) in task["task_id"]
        )

        self.assertIn("unexplained difference is 0.01", task["exception"])
        self.assertIn("Stop and repair", task["exception"])
        self.assertFalse(any(
            task["task_type"].startswith(("finance.dv-custody.", "finance.wet-signature."))
            for task in finance_work_tasks(self.uat)["tasks"]
        ))
        self.assertNotIn(
            "voucher-ready", {group["key"] for group in finance_work_attention(self.uat)["groups"]},
        )

    def test_accounting_validation_tasks_share_scope_and_expose_cent_level_mismatch(self):
        ready = self._case(
            "DV-TASK-VALIDATE", stage=VoucherCase.ACCOUNTING_VALIDATION,
            with_voucher=True, controlled=False,
        )
        self._case(
            "DV-TASK-VALIDATE-WRONG-OFFICE", stage=VoucherCase.ACCOUNTING_VALIDATION,
            current=self.other, with_voucher=True, controlled=False,
        )
        self._case(
            "DV-TASK-VALIDATE-SELF", stage=VoucherCase.ACCOUNTING_VALIDATION,
            with_voucher=True, controlled=False, dv_prepared_by=self.validator,
        )

        source, _selected, _spec = accounting_validation_action_queryset(self.validator)
        workspace_source, *_filters = apply_case_filters(
            visible_cases_for_user(self.validator),
            actionable_stages=(VoucherCase.ACCOUNTING_VALIDATION,),
            attention="ready_for_me", actor=self.validator,
        )
        tasks = [
            task for task in finance_work_tasks(self.validator)["tasks"]
            if task["task_type"] == "finance.accounting-validation.validation.v1"
        ]
        self.assertEqual(set(source), {ready})
        self.assertEqual(set(workspace_source), {ready})
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["case_id"], f"voucher-case:{ready.public_id}")
        self.assertIsNone(tasks[0]["due_on"])

        first_version = tasks[0]["source_version"]
        DisbursementVoucher.objects.filter(case=ready).update(net_amount=Decimal("89.99"))
        changed = next(
            task for task in finance_work_tasks(self.validator)["tasks"]
            if task["case_id"] == f"voucher-case:{ready.public_id}"
            and task["task_type"] == "finance.accounting-validation.validation.v1"
        )
        self.assertEqual(changed["task_id"], tasks[0]["task_id"])
        self.assertNotEqual(changed["source_version"], first_version)
        self.assertIn("unexplained difference is 0.01", changed["exception"])

    def test_accounting_validation_service_rejects_wrong_current_office_and_uat_gets_no_task(self):
        wrong_office = self._case(
            "DV-TASK-VALIDATE-SERVICE", stage=VoucherCase.ACCOUNTING_VALIDATION,
            current=self.other, with_voucher=True, controlled=False,
        )
        with self.assertRaises(PermissionDenied):
            validate_accounting(
                case=wrong_office, actor=self.validator, jev_number="TASK-JEV-DENIED",
                jev_date=timezone.localdate(), note="Must not cross office custody.",
                expected_version=wrong_office.state_version, idempotency_key="task-wrong-office-validation",
            )
        self.assertFalse(accounting_validation_action_queryset(self.uat)[0].exists())
        self.assertFalse(any(
            task["task_type"].startswith("finance.accounting-validation.")
            for task in finance_work_tasks(self.uat)["tasks"]
        ))


class FinanceAccountingWorkTaskContractTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="task-jev-accounting",
        )
        cls.other = Department.objects.create(
            name="Municipal Engineering Office", slug="task-jev-other",
        )
        cls.preparer = cls._employee(
            "task.jev.preparer", cls.accounting,
            "prepare_journal_entries", "post_journal_entries",
        )
        cls.poster = cls._employee(
            "task.jev.poster", cls.accounting, "post_journal_entries",
        )
        cls.outsider = cls._employee(
            "task.jev.outsider", cls.other, "prepare_journal_entries", "post_journal_entries",
        )
        cls.uat = cls._employee(
            "task.jev.uat", cls.accounting, "prepare_journal_entries", "post_journal_entries",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        owner = {"department_id": cls.accounting.pk, "department_label": cls.accounting.name}
        cls.period = AccountingPeriod.objects.create(
            **owner, fiscal_year=2027, period_number=1, label="January 2027",
            starts_on=date(2027, 1, 1), ends_on=date(2027, 1, 31),
        )
        cls.closed_period = AccountingPeriod.objects.create(
            **owner, fiscal_year=2027, period_number=2, label="February 2027",
            starts_on=date(2027, 2, 1), ends_on=date(2027, 2, 28),
            status=AccountingPeriod.CLOSED,
        )
        cls.fund = Fund.objects.create(**owner, code="TASK-GF", name="Task General Fund")
        cls.center = ResponsibilityCenter.objects.create(
            **owner, code="TASK-ACCOUNTING", name="Task Accounting Office",
        )
        cls.cash = LedgerAccount.objects.create(
            **owner, code="TASK-101", title="Task Cash", account_type="asset", normal_balance="debit",
        )
        cls.payable = LedgerAccount.objects.create(
            **owner, code="TASK-201", title="Task Payable", account_type="liability", normal_balance="credit",
        )

    @classmethod
    def _employee(cls, username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="jev-task-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="accounting", codename__in=permissions,
        ))
        return get_user_model().objects.get(pk=user.pk)

    def _entry(
        self, reference, *, status=JournalEntry.DRAFT, period=None,
        creator=None, submitter=None, debit=Decimal("100.00"), credit=Decimal("100.00"),
    ):
        creator = creator or self.preparer
        entry = JournalEntry.objects.create(
            department_id=self.accounting.pk, department_label=self.accounting.name,
            reference=reference,
            entry_date=date(2027, 2, 15) if period == self.closed_period else date(2027, 1, 15),
            period=period or self.period, fund=self.fund, source_type="manual",
            description=f"Exact Accounting task for {reference}", status=JournalEntry.DRAFT,
            created_by_id=creator.pk, created_by_label=creator.username,
        )
        JournalLine.objects.create(
            entry=entry, sequence=1, account=self.cash, responsibility_center=self.center,
            debit=debit, credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            entry=entry, sequence=2, account=self.payable, responsibility_center=self.center,
            debit=Decimal("0.00"), credit=credit,
        )
        if status != JournalEntry.DRAFT:
            JournalEntry.objects.filter(pk=entry.pk).update(
                status=status,
                submitted_by_id=submitter.pk if submitter else None,
                submitted_by_label=submitter.username if submitter else "",
                submitted_at=timezone.now() if submitter else None,
            )
            entry.refresh_from_db()
        return entry

    def test_preparation_tasks_match_shared_source_and_expose_exact_control_exceptions(self):
        ready = self._entry("TASK-JEV-READY")
        unbalanced = self._entry("TASK-JEV-UNBALANCED", credit=Decimal("99.99"))
        closed = self._entry("TASK-JEV-CLOSED", period=self.closed_period)
        returned = self._entry("TASK-JEV-RETURNED")
        AccountingAuditEvent.objects.create(
            department_id=self.accounting.pk, department_label=self.accounting.name,
            entry=returned, action="returned", actor_id=self.poster.pk,
            actor_label=self.poster.username, reason="Correct the retained allotment reference.",
        )

        source, _selected = journal_action_queryset(self.preparer, "preparation")
        tasks = [
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["task_type"] == "finance.journal-entry.preparation.v1"
        ]
        self.assertEqual({entry.pk for entry in source}, {ready.pk, unbalanced.pk, closed.pk, returned.pk})
        self.assertEqual(
            {task["case_id"] for task in tasks},
            {f"journal-entry:{entry.public_id}" for entry in (ready, unbalanced, closed, returned)},
        )
        exceptions = {task["case_id"]: task["exception"] for task in tasks}
        self.assertIn("control difference is 0.01", exceptions[f"journal-entry:{unbalanced.public_id}"])
        self.assertIn("period is closed", exceptions[f"journal-entry:{closed.public_id}"])
        self.assertIn("Correct the retained allotment reference", exceptions[f"journal-entry:{returned.public_id}"])
        self.assertTrue(all(task["due_on"] is None for task in tasks))

    def test_posting_source_tasks_and_attention_apply_submitter_separation(self):
        own = self._entry(
            "TASK-JEV-OWN-POST", status=JournalEntry.SUBMITTED,
            creator=self.preparer, submitter=self.preparer,
        )
        independent = self._entry(
            "TASK-JEV-INDEPENDENT", status=JournalEntry.SUBMITTED,
            creator=self.preparer, submitter=self.preparer,
        )
        poster_source, _selected = journal_action_queryset(self.poster, "posting")
        self.assertEqual({entry.pk for entry in poster_source}, {own.pk, independent.pk})
        self.assertFalse(journal_action_queryset(self.preparer, "posting")[0].exists())
        tasks = [
            task for task in finance_work_tasks(self.poster)["tasks"]
            if task["task_type"] == "finance.journal-entry.posting.v1"
        ]
        self.assertEqual(len(tasks), 2)
        group = next(
            group for group in finance_work_attention(self.poster)["groups"]
            if group["key"] == "journal-posting"
        )
        self.assertEqual(group["count"], len(tasks))

        FinanceWorkflowExemption.objects.create(
            department=self.accounting,
            control_code=FinanceWorkflowExemption.JOURNAL_PREPARER_SELF_POSTING,
            subject_user=self.preparer,
            rationale="Synthetic named staffing exception for task-source parity.",
            created_by=self.poster,
        )
        self.assertEqual(journal_action_queryset(self.preparer, "posting")[0].count(), 2)

    def test_task_identity_is_stable_and_revision_tracks_money_evidence(self):
        entry = self._entry("TASK-JEV-REVISION")
        first = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"journal-entry:{entry.public_id}"
        )
        line = entry.lines.get(sequence=2)
        line.credit = Decimal("99.99")
        line.save(update_fields=("credit",))
        second = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"journal-entry:{entry.public_id}"
        )
        self.assertEqual(second["task_id"], first["task_id"])
        self.assertNotEqual(second["source_version"], first["source_version"])
        self.assertIn("control difference is 0.01", second["exception"])

    def test_wrong_office_and_uat_accounts_receive_no_exact_journal_actions(self):
        self._entry("TASK-JEV-SCOPED")
        self.assertFalse(journal_action_queryset(self.outsider, "preparation")[0].exists())
        self.assertFalse(any(
            task["task_type"].startswith("finance.journal-entry.")
            for task in finance_work_tasks(self.outsider)["tasks"]
        ))
        self.assertFalse(any(
            task["task_type"].startswith("finance.journal-entry.")
            for task in finance_work_tasks(self.uat)["tasks"]
        ))
