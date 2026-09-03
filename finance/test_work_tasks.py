from __future__ import annotations

from datetime import timedelta
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

from .models import (
    FinanceCutoverDecision, FinanceCutoverReadinessExercise,
    FinanceCutoverReadinessPlan, FinanceShadowComparison, FinanceShadowCycle,
    FinanceShadowDefect, FinanceStakeholderAcceptance,
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
            "finance.manage_shadow_operation",
            "reporting.manage_local_form_acceptance",
        )
        cls._grant(
            cls.reviewer,
            "finance.view_finance_setup",
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
