from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from reporting.models import FinanceLocalFormAcceptance
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP

from accounting.models import FiscalYear
from budget.annual_exports import apply_annual_filters
from budget.control_exports import apply_allotment_filters, apply_obligation_filters, obligation_scope_for_user
from budget.models import (
    AllotmentReleaseOrder, AppropriationAuthorization, BudgetCall, BudgetVersion, ObligationRequest,
)

from .models import (
    FinanceConfigurationRelease, FinanceCutoverDecision, FinanceCutoverReadinessExercise,
    FinanceCutoverReadinessPlan, FinanceShadowComparison, FinanceShadowCycle,
    FinanceDiscoveryDecision, FinanceShadowDefect, FinanceStakeholderAcceptance,
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
