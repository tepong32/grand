from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
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
    payable_action_queryset, treasury_payment_action_queryset, visible_cases_for_user,
)
from vouchers.models import (
    BankAdviceBatch, BudgetAllocationLine, BudgetObligation, DisbursementVoucher,
    PayableIntake, PaymentInstrument, VoucherCase, VoucherOutput, VoucherPrintJob,
    WetSignatureTask,
)
from vouchers.services import (
    VoucherWorkflowError, issue_check, release_check, submit_checks_for_advice, validate_accounting,
)

from accounting.journal_exports import journal_action_queryset
from accounting.bank_register_exports import bank_reconciliation_action_queryset
from accounting.close_services import (
    create_period_close_run, decide_period_close_run, decide_period_reopen,
    refresh_period_close_run, request_period_reopen, submit_period_close_run,
)
from accounting.models import (
    AccountingAuditEvent, AccountingPeriod, BankStatementBatch,
    BankStatementRow, FiscalYear, Fund, JournalEntry, JournalLine, LedgerAccount,
    PeriodCloseRun, PostingMapping, ResponsibilityCenter,
)
from accounting.period_close_register import period_close_action_queryset
from accounting.services import (
    decide_bank_reconciliation, match_bank_statement_row, submit_bank_reconciliation,
)
from budget.annual_exports import apply_annual_filters
from budget.control_exports import apply_allotment_filters, apply_obligation_filters, obligation_scope_for_user
from budget.models import (
    AllotmentReleaseOrder, AppropriationAuthorization, BudgetCall, BudgetVersion, ObligationRequest,
)

from .models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceCutoverDecision, FinanceCutoverReadinessExercise,
    FinanceCutoverReadinessPlan, FinanceShadowComparison, FinanceShadowCycle,
    FinanceDiscoveryDecision, FinanceParty, FinancePartyClaimant, FinanceShadowDefect, FinanceStakeholderAcceptance,
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

    def test_work_export_requires_explicit_grant_and_matches_bounded_live_projection(self):
        from pathlib import Path
        from .models import FinanceAuditEvent
        from .work_exports import build_work_export
        today = timezone.localdate()
        FinanceConfigurationRelease.objects.bulk_create([
            FinanceConfigurationRelease(
                department=self.accounting, code=f"export-{index:03}", title="=FORMULA()" if index == 0 else f"Release {index}",
                fiscal_year=today.year, effective_from=today, created_by=self.worker,
            ) for index in range(101)
        ])
        FinanceConfigurationRelease.objects.create(
            department=self.budget, code="foreign-export", title="Foreign confidential source",
            fiscal_year=today.year, effective_from=today, created_by=self.worker,
        )
        route = reverse("finance_operations:my_work_export")
        self.client.force_login(self.worker)
        with tempfile.TemporaryDirectory() as directory, self.settings(GRAND_EXPORT_ROOT=directory):
            self.assertEqual(self.client.get(route).status_code, 403)
            with self.assertRaises(PermissionDenied):
                build_work_export(self.worker)
            self.assertEqual(list(Path(directory).rglob("*.csv")), [])
            self.assertFalse(self.client.get(reverse("finance_operations:my_work")).context["can_export_work"])
            permission = Permission.objects.get(content_type__app_label="finance", codename="export_finance_work")
            group = Group.objects.create(name="Explicit My Work Exporters")
            group.permissions.add(permission)
            self.worker.groups.add(group)
            page = self.client.get(reverse("finance_operations:my_work"))
            self.assertTrue(page.context["can_export_work"])
            expected = finance_work_tasks(self.worker)
            self.assertEqual(expected["task_count"], 101)
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertEqual(response["X-GRAND-Export-Row-Count"], "100")
            self.assertEqual(response["X-GRAND-Export-Eligible-Count"], "101")
            self.assertEqual(response["X-GRAND-Export-Truncated"], "true")
            rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
            self.assertEqual([row["task_id"] for row in rows], [row["task_id"] for row in expected["tasks"]])
            self.assertEqual([row["url"] for row in rows], [row["url"] for row in expected["tasks"]])
            self.assertEqual(rows[0]["subject"], "'=FORMULA()")
            self.assertNotIn(b"Foreign confidential source", response.content)
            artifacts = list(Path(directory).rglob("*.csv"))
            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0].read_bytes(), response.content)
            manifest = json.loads(Path(str(artifacts[0]) + ".manifest.json").read_text(encoding="utf-8"))
            digest = hashlib.sha256(response.content).hexdigest()
            self.assertEqual(manifest["sha256"], digest)
            self.assertEqual(response["X-GRAND-Export-SHA256"], digest)
            event = FinanceAuditEvent.objects.get(action="work_exported")
            self.assertEqual(event.actor, self.worker)
            self.assertEqual(event.department, self.accounting)
            self.assertEqual(event.target_id, manifest["metadata"]["export_id"])
            self.assertEqual(event.snapshot["sha256"], digest)
            self.assertEqual(event.snapshot["task_ids"], [row["task_id"] for row in rows])
            self.assertTrue(event.snapshot["truncated"])
            self.assertEqual(FinanceConfigurationRelease.objects.filter(status="draft").count(), 102)
            for params in ({"view": "unknown"}, {"days": "999"}):
                self.assertEqual(self.client.get(route, params).status_code, 404)
            self.assertEqual(self.client.post(route).status_code, 405)
            # Current action permission is re-evaluated even when export remains granted.
            self.worker.user_permissions.remove(Permission.objects.get(content_type__app_label="finance", codename="manage_finance_configuration"))
            empty = self.client.get(route)
            self.assertEqual(empty.status_code, 200)
            self.assertEqual(empty["X-GRAND-Export-Row-Count"], "0")
            self.assertEqual(list(csv.DictReader(io.StringIO(empty.content.decode("utf-8-sig")))), [])
            group.permissions.remove(permission)
            self.assertEqual(self.client.get(route).status_code, 403)
            self.uat.user_permissions.add(permission)
            self.client.force_login(self.uat)
            self.assertEqual(self.client.get(route).status_code, 403)

    def test_work_export_preserves_view_filters_and_fails_closed_without_receipt(self):
        from unittest.mock import patch
        from .models import FinanceAuditEvent
        from .work_exports import build_work_export
        self._grant(self.worker, "finance.export_finance_work")
        self._cycle()
        self.client.force_login(self.worker)
        with tempfile.TemporaryDirectory() as directory, self.settings(GRAND_EXPORT_ROOT=directory):
            for view in ("ready", "waiting", "returned", "upcoming", "past_dates", "completed"):
                expected = finance_work_tasks(self.worker, view=view, planned_days=14)
                response = self.client.get(reverse("finance_operations:my_work_export"), {"view": view, "days": "14"})
                self.assertEqual(response.status_code, 200)
                rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
                self.assertEqual([row["task_id"] for row in rows], [row["task_id"] for row in expected["tasks"]])
                event = FinanceAuditEvent.objects.filter(action="work_exported").first()
                self.assertEqual((event.snapshot["view"], event.snapshot["planned_days"]), (view, 14))
            before = FinanceAuditEvent.objects.count()
            with patch("finance.work_exports.archive_export", side_effect=OSError("Synthetic archive failure")):
                with self.assertRaisesMessage(OSError, "Synthetic archive failure"):
                    build_work_export(self.worker)
            self.assertEqual(FinanceAuditEvent.objects.count(), before)
            with patch("finance.work_exports.FinanceAuditEvent.objects.create", side_effect=RuntimeError("Synthetic audit failure")):
                with self.assertRaisesMessage(RuntimeError, "Synthetic audit failure"):
                    build_work_export(self.worker)
            self.assertEqual(FinanceAuditEvent.objects.count(), before)

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

    def test_date_views_use_retained_calendar_boundaries_before_truncation(self):
        today = timezone.localdate()
        self._decision(code="a-undated", status=FinanceDiscoveryDecision.DRAFT, due_date=None)
        past = self._decision(code="b-past", status=FinanceDiscoveryDecision.DRAFT, due_date=today - timedelta(days=1))
        current = self._decision(code="c-today", status=FinanceDiscoveryDecision.DRAFT, due_date=today)
        last = self._decision(code="a-last-dated", status=FinanceDiscoveryDecision.DRAFT, due_date=today + timedelta(days=6))
        next_week = self._decision(code="e-next", status=FinanceDiscoveryDecision.DRAFT, due_date=today + timedelta(days=7))
        result = finance_work_tasks(self.worker, view="upcoming", display_limit=1)
        self.assertEqual(result["task_count"], 2)
        self.assertTrue(result["tasks_truncated"])
        self.assertEqual(result["tasks"][0]["case_id"], f"discovery-decision:{current.public_id}")
        self.assertEqual({task["case_id"] for task in finance_work_tasks(self.worker, view="upcoming", planned_days=14)["tasks"]},
                         {f"discovery-decision:{item.public_id}" for item in (current, last, next_week)})
        self.assertEqual([task["case_id"] for task in finance_work_tasks(self.worker, view="past_dates")["tasks"]],
                         [f"discovery-decision:{past.public_id}"])
        self.assertEqual(finance_work_tasks(self.uat, view="upcoming")["task_count"], 0)
        self.assertEqual(finance_work_tasks(self.reviewer, view="upcoming")["task_count"], 0)
        self.client.force_login(self.worker)
        response = self.client.get(reverse("finance_operations:my_work"), {"view": "upcoming", "days": "14"})
        self.assertEqual(response.context["task_count"], 3)
        self.assertContains(response, "including today")
        self.assertContains(response, "Retained local review target")
        self.assertEqual(self.client.get(reverse("finance_operations:my_work"), {"view": "upcoming", "days": "-1"}).status_code, 404)

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

    def test_setup_waiting_is_personal_and_rechecks_current_source_access(self):
        from .services import transition_release
        from .work_tasks import _source_record_identity

        today = timezone.localdate()
        own = self._release(code="Z-own-submission", status="draft", effective_from=today)
        transition_release(own, "submit", self.worker)
        other = self._release(code="A-other-submission", status="submitted", effective_from=today)
        other.created_by = self.reviewer; other.submitted_by = self.reviewer
        other.save(update_fields=("created_by", "submitted_by"))
        foreign = self._release(code="A-foreign-submission", status="submitted", effective_from=today)
        foreign.department = self.budget; foreign.save(update_fields=("department",))
        self._release(code="A-draft", status="draft", effective_from=today)
        self._release(code="A-approved", status="approved", effective_from=today)
        result = finance_work_tasks(self.worker, view="waiting", display_limit=1)
        self.assertEqual(result["task_count"], 1)
        task = result["tasks"][0]
        self.assertEqual(task["case_id"], f"setup-release:{_source_record_identity('setup-release', own.pk)}")
        self.assertEqual(task["url"], reverse("finance:release_detail", args=[own.pk]))
        self.assertIsNone(task["due_on"])
        self.assertEqual(task["state"], "Waiting")
        self.client.force_login(self.worker)
        self.assertEqual(self.client.get(task["url"]).status_code, 200)
        uat_owned = self._release(code="UAT-owned", status="submitted", effective_from=today)
        uat_owned.created_by = self.uat; uat_owned.submitted_by = self.uat
        uat_owned.save(update_fields=("created_by", "submitted_by"))
        self._grant(self.uat, "finance.manage_finance_configuration", "finance.approve_finance_configuration")
        self.assertEqual(finance_work_tasks(self.uat, view="waiting")["task_count"], 0)
        self.worker.user_permissions.clear()
        self.assertEqual(finance_work_tasks(self.worker, view="waiting")["task_count"], 0)

    def test_setup_returned_uses_retained_reason_and_current_draft_state_before_limit(self):
        from .services import transition_release

        today = timezone.localdate()
        self._release(code="A-ordinary-draft", status="draft", effective_from=today)
        returned = self._release(code="Z-returned", status="draft", effective_from=today)
        transition_release(returned, "submit", self.worker)
        transition_release(returned, "return", self.reviewer, "Correct the retained workbook evidence.")
        resubmitted = self._release(code="B-resubmitted", status="draft", effective_from=today)
        transition_release(resubmitted, "submit", self.worker)
        transition_release(resubmitted, "return", self.reviewer, "Earlier correction")
        transition_release(resubmitted, "submit", self.worker)
        result = finance_work_tasks(self.worker, view="returned", display_limit=1)
        self.assertEqual(result["task_count"], 1)
        task = result["tasks"][0]
        self.assertIn("Z-returned", task["reference"])
        self.assertEqual(task["exception"], "Correct the retained workbook evidence.")
        self.assertEqual(task["source_state"], "Draft")
        self.assertEqual(task["received_at"], returned.events.get(action="return").created_at)
        self.assertEqual(finance_work_tasks(self.reviewer, view="returned")["task_count"], 0)
        transition_release(returned, "submit", self.worker)
        self.assertEqual(finance_work_tasks(self.worker, view="returned")["task_count"], 0)
        self.assertEqual(finance_work_tasks(self.worker, view="waiting")["task_count"], 2)

    def test_setup_waiting_excludes_current_governed_approval_before_truncation(self):
        from .services import transition_release
        from .setup_register import setup_attention_queryset

        today = timezone.localdate()
        own = self._release(code="Z-exempt-review", status="submitted", effective_from=today)
        self._grant(self.worker, "finance.approve_finance_configuration")
        exemption = FinanceWorkflowExemption.objects.create(
            department=self.accounting, control_code=FinanceWorkflowExemption.RELEASE_SELF_APPROVAL,
            subject_user=self.worker, rationale="Synthetic authorized exception", created_by=self.reviewer,
            effective_from=today + timedelta(days=1),
        )
        self.assertEqual(finance_work_tasks(self.worker, view="waiting", display_limit=1)["task_count"], 1)
        exemption.effective_from = today; exemption.save(update_fields=("effective_from",))
        self.assertTrue(setup_attention_queryset(self.worker, "awaiting_review")[0].filter(pk=own.pk).exists())
        self.assertEqual(finance_work_tasks(self.worker, view="waiting", display_limit=1)["task_count"], 0)
        task = next(task for task in finance_work_tasks(self.worker)["tasks"] if "Z-exempt-review" in task["reference"])
        self.assertIn("exemption", task["action"])
        self.assertIn("Independent return is unavailable", task["gate"])
        exemption.is_active = False; exemption.save(update_fields=("is_active",))
        self.assertEqual(finance_work_tasks(self.worker, view="waiting")["task_count"], 1)
        exemption.is_active = True; exemption.save(update_fields=("is_active",))
        transition_release(own, "approve", self.worker, "Synthetic governed exemption approval.")
        self.assertEqual(finance_work_tasks(self.worker, view="waiting")["task_count"], 0)

    def test_setup_completion_credits_retained_actions_and_keeps_current_state_separate(self):
        from .services import transition_release

        today = timezone.localdate()
        release = self._release(code="COMPLETED-SETUP", status="draft", effective_from=today + timedelta(days=5))
        self._release(code="STATUS-ONLY", status="active", effective_from=today)
        transition_release(release, "submit", self.worker)
        first_id = finance_work_tasks(self.worker, view="completed")["tasks"][0]["task_id"]
        transition_release(release, "return", self.reviewer, "Retain the correction reason.")
        transition_release(release, "submit", self.worker)
        transition_release(release, "approve", self.reviewer, "Reviewed corrected basis.")
        transition_release(release, "schedule", self.reviewer)
        prepared = finance_work_tasks(self.worker, view="completed")
        self.assertEqual(prepared["task_count"], 2)
        self.assertEqual(len({task["task_id"] for task in prepared["tasks"]}), 2)
        self.assertIn(first_id, {task["task_id"] for task in prepared["tasks"]})
        for task in prepared["tasks"]:
            self.assertEqual(task["state"], "Completed")
            self.assertEqual(task["source_state"], "Scheduled")
            self.assertEqual(task["subject"], "Submitted setup release for review")
            self.assertEqual(task["url"], reverse("finance:release_detail", args=[release.pk]))
            self.assertIsNone(task["due_on"])
        reviewed = finance_work_tasks(self.reviewer, view="completed", display_limit=1)
        self.assertEqual(reviewed["task_count"], 3)
        self.assertTrue(reviewed["tasks_truncated"])
        self.assertEqual(reviewed["tasks"][0]["subject"], "Scheduled setup release")
        transition_release(release, "retire", self.reviewer)
        self.assertEqual(finance_work_tasks(self.reviewer, view="completed")["task_count"], 4)
        self.client.force_login(self.worker)
        response = self.client.get(reverse("finance_operations:my_work"), {"view": "completed"})
        self.assertContains(response, "Submitted setup release for review")
        self.assertNotContains(response, "STATUS-ONLY")

    def test_setup_completion_rechecks_read_scope_and_rejects_inconsistent_event_targets(self):
        from .models import FinanceAuditEvent
        from .services import transition_release

        today = timezone.localdate()
        release = self._release(code="COMPLETED-SCOPE", status="draft", effective_from=today)
        transition_release(release, "submit", self.worker)
        base = dict(department=self.accounting, release=release, actor=self.worker,
                    target_type="financeconfigurationrelease", target_id=str(release.pk), action="submit")
        for changes in ({"target_id": "missing"}, {"target_type": "financetemplateversion"},
                        {"department": self.budget}, {"actor": self.reviewer}, {"action": "created"}):
            FinanceAuditEvent.objects.create(**{**base, **changes})
        self.assertEqual(finance_work_tasks(self.worker, view="completed")["task_count"], 1)
        self.worker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(finance_work_tasks(self.worker, view="completed")["task_count"], 0)
        self.worker.groups.clear()
        self.worker.user_permissions.clear()
        self.assertEqual(finance_work_tasks(self.worker, view="completed")["task_count"], 0)
        self._grant(self.worker, "finance.view_finance_setup")
        self.assertEqual(finance_work_tasks(self.worker, view="completed")["task_count"], 1)
        release.department = self.budget; release.save(update_fields=("department",))
        self.assertEqual(finance_work_tasks(self.worker, view="completed")["task_count"], 0)

    def test_discovery_waiting_preserves_named_cross_office_access_and_review_target(self):
        from .discovery_services import submit_discovery_decision, review_discovery_decision

        today = timezone.localdate()
        named_owner = self._employee("discovery.cross.office.owner", self.budget)
        item = self._decision(code="WAIT-DISCOVERY", status=FinanceDiscoveryDecision.DRAFT, due_date=today + timedelta(days=3))
        item.owner = named_owner; item.save()
        submit_discovery_decision(item, named_owner)
        result = finance_work_tasks(named_owner, view="waiting", display_limit=1)
        self.assertEqual(result["task_count"], 1)
        task = result["tasks"][0]
        self.assertEqual(task["case_id"], f"discovery-decision:{item.public_id}")
        self.assertEqual(task["due_on"], item.due_date)
        self.assertIn("Retained local review target", task["calendar_basis"])
        self.assertIn(self.reviewer.username, task["owner_queue"])
        self.assertIn(self.accounting.name, task["scope"])
        self.client.force_login(named_owner)
        self.assertEqual(self.client.get(task["url"]).status_code, 200)
        page = self.client.get(reverse("finance_operations:my_work"), {"view": "waiting"})
        self.assertContains(page, "WAIT-DISCOVERY")
        self.assertContains(page, "Retained local review target")
        self.assertEqual(finance_work_tasks(self.reviewer, view="waiting")["task_count"], 0)
        review_discovery_decision(item, self.reviewer, record=False, reason="Retain the exact local control.")
        self.assertEqual(finance_work_tasks(named_owner, view="waiting")["task_count"], 0)
        self.assertEqual(finance_work_tasks(named_owner, view="returned")["task_count"], 1)
        submit_discovery_decision(item, named_owner)
        self.assertEqual(finance_work_tasks(named_owner, view="waiting")["task_count"], 1)
        named_owner.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(finance_work_tasks(named_owner, view="waiting")["task_count"], 0)

    def test_discovery_completion_retains_attribution_without_claiming_scope_acceptance(self):
        from .discovery_services import submit_discovery_decision, review_discovery_decision

        today = timezone.localdate()
        item = self._decision(code="HISTORY-DISCOVERY", status=FinanceDiscoveryDecision.DRAFT, due_date=today)
        submit_discovery_decision(item, self.worker)
        first_id = finance_work_tasks(self.worker, view="completed")["tasks"][0]["task_id"]
        review_discovery_decision(item, self.reviewer, record=False, reason="Clarify the unresolved control.")
        submit_discovery_decision(item, self.worker)
        review_discovery_decision(item, self.reviewer, record=True, reason="Record the unresolved finding; keep its scope blocked.")
        item.refresh_from_db()
        self.assertTrue(item.is_current_blocker)
        self.assertEqual(finance_work_tasks(self.worker, view="waiting")["task_count"], 0)
        prepared = finance_work_tasks(self.worker, view="completed")
        self.assertEqual(prepared["task_count"], 2)
        self.assertIn(first_id, {task["task_id"] for task in prepared["tasks"]})
        reviewed = finance_work_tasks(self.reviewer, view="completed", display_limit=1)
        self.assertEqual(reviewed["task_count"], 2)
        self.assertTrue(reviewed["tasks_truncated"])
        task = reviewed["tasks"][0]
        self.assertEqual(task["subject"], "Recorded discovery decision")
        self.assertIn("Unresolved", task["exception"])
        self.assertIn("scope remains blocked", task["exception"])
        self.assertIn("does not itself establish local acceptance", task["gate"])
        self.assertEqual(task["source_state"], item.get_status_display())

    def test_discovery_history_requires_current_named_or_office_read_access(self):
        from .discovery_services import submit_discovery_decision
        from .models import FinanceAuditEvent

        today = timezone.localdate()
        named_owner = self._employee("discovery.history.owner", self.budget)
        item = self._decision(code="READ-DISCOVERY", status=FinanceDiscoveryDecision.DRAFT, due_date=None)
        item.owner = named_owner; item.save()
        submit_discovery_decision(item, named_owner)
        base = dict(department=self.accounting, actor=named_owner, target_type="financediscoverydecision",
                    target_id=str(item.pk), action="discovery_decision_submitted")
        for changes in ({"department": self.budget}, {"target_id": "missing"}, {"target_type": "financeconfigurationrelease"}):
            FinanceAuditEvent.objects.create(**{**base, **changes})
        self.assertEqual(finance_work_tasks(named_owner, view="completed")["task_count"], 1)
        self.worker.user_permissions.clear()
        self.assertEqual(finance_work_tasks(self.worker, view="waiting")["task_count"], 0)
        named_owner.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(finance_work_tasks(named_owner, view="completed")["task_count"], 0)
        named_owner.groups.clear()
        named_owner.is_active = False; named_owner.save(update_fields=("is_active",))
        self.assertEqual(finance_work_tasks(named_owner, view="completed")["task_count"], 0)

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

    def test_budget_waiting_preserves_personal_and_source_access_boundaries(self):
        version = self._version(8, BudgetVersion.FOR_REVIEW, self.preparer)
        order = self._allotment("WAIT-ALLOT", AllotmentReleaseOrder.FOR_REVIEW, self.preparer)
        obligation = self._obligation("WAIT-OBLIGATION", ObligationRequest.FOR_CERTIFICATION, self.requester)
        own_ids = {task["case_id"] for task in finance_work_tasks(self.preparer, view="waiting")["tasks"]}
        self.assertEqual(own_ids, {f"budget-version:{version.public_id}", f"allotment-order:{order.public_id}"})
        self.assertEqual(finance_work_tasks(self.reviewer, view="waiting")["task_count"], 0)
        self.assertEqual([task["case_id"] for task in finance_work_tasks(self.requester, view="waiting")["tasks"]],
                         [f"obligation-request:{obligation.public_id}"])
        self.client.force_login(self.requester)
        self.assertEqual(self.client.get(reverse("budget:obligation_detail", args=(obligation.public_id,))).status_code, 200)
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label="budget", codename="view_allotment_control"))
        self.assertEqual([task["case_id"] for task in finance_work_tasks(self.preparer, view="waiting")["tasks"]],
                         [f"budget-version:{version.public_id}"])
        self.requester.employeeprofile.assigned_department = self.accounting
        self.requester.employeeprofile.save(update_fields=("assigned_department",))
        moved = get_user_model().objects.get(pk=self.requester.pk)
        self.assertEqual(finance_work_tasks(moved, view="waiting")["task_count"], 0)
        self.assertEqual(finance_work_tasks(self.uat, view="waiting")["task_count"], 0)

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

    def test_payable_waiting_follows_own_review_and_dv_preparation_handoffs(self):
        review = self._case("A-WAIT-REVIEW", stage=VoucherCase.PAYABLE_REVIEW, current=self.accounting,
                            status=PayableIntake.FOR_REVIEW, submitted_by=self.preparer)
        ready = self._case("B-WAIT-DV", stage=VoucherCase.ACCOUNTING_PREPARATION, current=self.accounting,
                           status=PayableIntake.READY, submitted_by=self.preparer)
        intake = ready.payable_intake
        intake.reviewed_at = timezone.now(); intake.save(update_fields=("reviewed_at",))
        self._case("FOREIGN-WAIT", stage=VoucherCase.PAYABLE_REVIEW, current=self.accounting,
                   requesting=self.other_requesting, status=PayableIntake.FOR_REVIEW, submitted_by=self.preparer)
        self._case("OTHERS-WAIT", stage=VoucherCase.PAYABLE_REVIEW, current=self.accounting,
                   prepared_by=self.other_preparer, submitted_by=self.other_preparer, status=PayableIntake.FOR_REVIEW)
        self._case("DRAFT-WAIT", stage=VoucherCase.PAYABLE_PREPARATION)
        result = finance_work_tasks(self.preparer, view="waiting")
        self.assertEqual(result["task_count"], 2)
        self.assertEqual({task["case_id"] for task in result["tasks"]}, {f"voucher-case:{review.public_id}", f"voucher-case:{ready.public_id}"})
        for task in result["tasks"]:
            self.assertIsNone(task["due_on"])
            self.assertIn(self.accounting.name, task["owner_queue"])
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(result["tasks"][0]["url"]).status_code, 200)
        ready.current_stage = VoucherCase.AWAITING_SIGNATURES; ready.save(update_fields=("current_stage",))
        self.assertEqual(finance_work_tasks(self.preparer, view="waiting")["task_count"], 1)
        DisbursementVoucher.objects.create(
            case=ready, dv_number="DV-PAYABLE-WAIT", voucher_date=timezone.localdate(),
            gross_amount=Decimal("100.00"), total_deductions=Decimal("0.00"), net_amount=Decimal("100.00"),
            prepared_by=self.reviewer, prepared_at=timezone.now())
        self.assertEqual(finance_work_tasks(self.preparer, view="waiting")["task_count"], 2)
        self.preparer.user_permissions.clear()
        self.assertEqual(finance_work_tasks(self.preparer, view="waiting")["task_count"], 0)

    def test_payable_waiting_excludes_current_case_action_before_limit(self):
        self.reviewer.user_permissions.add(Permission.objects.get(content_type__app_label="vouchers", codename="prepare_disbursement_voucher"))
        self._case("A-ACTIONABLE-DV", stage=VoucherCase.ACCOUNTING_PREPARATION, current=self.accounting,
                   requesting=self.accounting, prepared_by=self.reviewer, submitted_by=self.reviewer, status=PayableIntake.READY)
        other = self._case("Z-OTHER-OFFICE-DV", stage=VoucherCase.ACCOUNTING_PREPARATION, current=self.other_requesting,
                           requesting=self.accounting, prepared_by=self.reviewer, submitted_by=self.reviewer, status=PayableIntake.READY)
        result = finance_work_tasks(self.reviewer, view="waiting", display_limit=1)
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["tasks"][0]["case_id"], f"voucher-case:{other.public_id}")
        self.reviewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(finance_work_tasks(self.reviewer, view="waiting")["task_count"], 0)

    def test_payable_completion_keeps_event_custody_after_case_moves(self):
        from vouchers.models import VoucherEvent

        item = self._case("PAYABLE-HISTORY", stage=VoucherCase.TREASURY_CHECK_PREPARATION, current=self.other_requesting,
                          status=PayableIntake.READY, submitted_by=self.preparer)
        submitted = VoucherEvent.objects.create(case=item, actor=self.preparer, actor_department=self.requesting,
            action="payable_submitted", from_stage=VoucherCase.PAYABLE_PREPARATION, to_stage=VoucherCase.PAYABLE_REVIEW,
            state_version=1, idempotency_key="history-submit")
        VoucherEvent.objects.create(case=item, actor=self.reviewer, actor_department=self.accounting,
            action="payable_accepted", from_stage=VoucherCase.PAYABLE_REVIEW, to_stage=VoucherCase.ACCOUNTING_PREPARATION,
            reason="Reviewed claim readiness.", state_version=2, idempotency_key="history-accept")
        VoucherEvent.objects.create(case=item, actor=self.preparer, actor_department=self.requesting,
            action="payable_submitted", from_stage=VoucherCase.COMPLETED, to_stage=VoucherCase.PAYABLE_REVIEW,
            state_version=3, idempotency_key="history-inconsistent")
        prepared = finance_work_tasks(self.preparer, view="completed")
        self.assertEqual(prepared["task_count"], 1)
        self.assertEqual(prepared["tasks"][0]["received_at"], submitted.created_at)
        reviewed = finance_work_tasks(self.reviewer, view="completed")
        self.assertEqual(reviewed["task_count"], 1)
        task = reviewed["tasks"][0]
        self.assertEqual(task["subject"], "Accepted payable for DV preparation")
        self.assertIn(self.accounting.name, task["owner_queue"])
        self.assertEqual(task["source_state"], item.get_current_stage_display())
        self.assertIn("does not authorize payment release", task["gate"])
        self.preparer.user_permissions.clear()
        self.assertEqual(finance_work_tasks(self.preparer, view="completed")["task_count"], 0)

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


    def test_payable_detail_review_controls_match_source_actor_and_office(self):
        ready = self._case("PAY-PAGE-READY", stage=VoucherCase.PAYABLE_REVIEW,
            current=self.accounting, submitted_by=self.preparer, status=PayableIntake.FOR_REVIEW)
        own = self._case("PAY-PAGE-OWN", stage=VoucherCase.PAYABLE_REVIEW,
            current=self.accounting, prepared_by=self.reviewer, submitted_by=self.reviewer,
            status=PayableIntake.FOR_REVIEW)
        other = self._case("PAY-PAGE-OTHER", stage=VoucherCase.PAYABLE_REVIEW,
            current=self.other_requesting, submitted_by=self.preparer, status=PayableIntake.FOR_REVIEW)
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("vouchers:case_detail", args=(ready.public_id,)))
        self.assertContains(response, "Record review decision")
        self.assertTrue(response.context["case_ready_for_user"])
        for case in (own, other):
            response = self.client.get(reverse("vouchers:case_detail", args=(case.public_id,)))
            with self.subTest(case=case.reference_code, control="review form"):
                self.assertNotContains(response, "Record review decision")
            with self.subTest(case=case.reference_code, control="main action"):
                self.assertFalse(response.context["case_ready_for_user"])


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
            "prepare_disbursement_voucher",
        )
        cls.print_operator.user_permissions.add(Permission.objects.get(
            content_type__app_label="tracepoint", codename="prepare_tracked_packets",
        ))
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

    def test_signing_copy_requires_output_authority_and_keeps_replacement_available(self):
        item = self._case("DV-PRINT-AUTH", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True)
        operator = self._employee(
            "dv.print.limited", self.accounting, "view_voucher_workbench", "control_dv_printing",
        )
        self.client.force_login(operator)
        url = reverse("vouchers:case_detail", args=[item.public_id])
        action = reverse("vouchers:case_action", args=[item.public_id, "prepare-controlled-print"])
        with self.subTest(scope="missing DV preparation grant"):
            self.assertFalse(dv_custody_action_queryset(operator, "signing_copy")[0].exists())
        with self.subTest(scope="generic action queue"):
            self.assertFalse(apply_case_filters(
                visible_cases_for_user(operator), actionable_stages=(VoucherCase.AWAITING_SIGNATURES,),
                attention="ready_for_me", actor=operator,
            )[0].exists())
        with self.subTest(scope="source form"):
            self.assertNotContains(self.client.get(url), action)
        operator.user_permissions.add(Permission.objects.get(
            content_type__app_label="vouchers", codename="prepare_disbursement_voucher",
        ))
        self.assertEqual(set(dv_custody_action_queryset(operator, "signing_copy")[0]), {item})
        self.assertContains(self.client.get(url), action)
        self._print_job(item, VoucherPrintJob.AWAITING_SIGNATURES)
        self.assertFalse(dv_custody_action_queryset(operator, "signing_copy")[0].exists())
        response = self.client.get(url)
        self.assertContains(response, action)
        with self.subTest(scope="replacement is not the pending main step"):
            self.assertFalse(response.context["case_ready_for_user"])
        item.configuration_release = None
        item.save(update_fields=("configuration_release",))
        with self.subTest(scope="missing pinned owner"):
            self.assertNotContains(self.client.get(url), action)

    def test_packet_assembly_requires_creation_authority_only_for_new_packets(self):
        item = self._case("DV-PACKET-AUTH", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True)
        self._print_job(item, VoucherPrintJob.PRINTED)
        operator = self._employee(
            "dv.packet.limited", self.accounting,
            "view_voucher_workbench", "control_dv_printing", "link_tracepoint_custody",
        )
        self.client.force_login(operator)
        url = reverse("vouchers:case_detail", args=[item.public_id])
        action = reverse("vouchers:case_action", args=[item.public_id, "assemble-finance-packet"])
        with self.subTest(scope="new packet queue"):
            self.assertFalse(dv_custody_action_queryset(operator, "assemble_packet")[0].exists())
        with self.subTest(scope="new packet source form"):
            self.assertNotContains(self.client.get(url), action)
        self._attach_packet(item)
        self.assertEqual(set(dv_custody_action_queryset(operator, "assemble_packet")[0]), {item})
        self.assertContains(self.client.get(url), action)
        item.current_department = self.other
        item.save(update_fields=("current_department",))
        with self.subTest(scope="wrong custody office"):
            self.assertNotContains(self.client.get(url), action)

    def _attach_packet(self, item):
        from tracepoint.models import PacketItem, TrackedPacket

        packet = TrackedPacket.objects.create(
            tracking_number=f"DV-PACKET-{item.pk}", title="Synthetic counted signing packet",
            contents_manifest="One retained signing copy.", expected_document_count=1,
            origin_department=self.accounting, final_destination_department=self.accounting,
            prepared_by=self.print_operator,
        )
        packet_item = PacketItem.objects.create(
            reference_number=f"DV-ITEM-{item.pk}", origin_packet=packet, current_packet=packet,
            title="Synthetic signing copy", created_by=self.print_operator,
        )
        item.tracepoint_item = packet_item
        item.save(update_fields=("tracepoint_item",))

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
        from vouchers.services import VoucherWorkflowError, record_signature_return

        with self.assertRaisesMessage(VoucherWorkflowError, "TracePoint"):
            record_signature_return(case=item, task=first, actor=self.signature_operator, note="Missing packet",
                                    expected_version=item.state_version, idempotency_key="missing-packet")
        self.assertFalse(dv_signature_task_queryset(self.signature_operator).exists())
        self.assertEqual(item.events.count(), 0)
        self._attach_packet(item)
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

    def test_instrument_history_keeps_physical_release_separate_from_posting(self):
        from vouchers.models import VoucherEvent

        item = self._case("INSTRUMENT-HISTORY", stage=VoucherCase.ACCOUNTING_EVENT_POSTING, with_voucher=True)
        instrument = PaymentInstrument.objects.create(case=item, bank_account_code="synthetic", check_number="HISTORY-CHECK",
            amount=Decimal("90.00"), status=PaymentInstrument.RELEASED,
            issued_by=self.print_operator, issued_at=timezone.now(), released_by=self.print_operator, released_at=timezone.now())
        for index, (action, before, after) in enumerate((
            ("check_issued", VoucherCase.TREASURY_CHECK_PREPARATION, VoucherCase.TREASURY_CHECK_PREPARATION),
            ("disbursement_completed", VoucherCase.TREASURY_RELEASE, VoucherCase.ACCOUNTING_EVENT_POSTING),
        )):
            VoucherEvent.objects.create(case=item, action=action, from_stage=before, to_stage=after,
                actor=self.print_operator, actor_department=self.other, state_version=index+1,
                idempotency_key=f"instrument-history-{index}",
                metadata={"instrument_id": str(instrument.public_id), "check_number": instrument.check_number})
        for key, actor, instrument_id, number in (
            ("bad-id", self.print_operator, "invalid", instrument.check_number),
            ("wrong-number", self.print_operator, str(instrument.public_id), "ANOTHER-CHECK"),
            ("wrong-actor", self.preparer, str(instrument.public_id), instrument.check_number),
        ):
            VoucherEvent.objects.create(case=item, action="disbursement_completed", from_stage=VoucherCase.TREASURY_RELEASE,
                to_stage=VoucherCase.ACCOUNTING_EVENT_POSTING, actor=actor, actor_department=self.accounting,
                state_version=3, idempotency_key=key, metadata={"instrument_id": instrument_id, "check_number": number})
        tasks = finance_work_tasks(self.print_operator, view="completed")["tasks"]
        self.assertEqual(len(tasks), 2)
        self.assertEqual(len({task["task_id"] for task in tasks}), 2)
        self.assertTrue(any(task["subject"] == "Recorded final check release" for task in tasks))
        for task in tasks:
            self.assertIn(item.get_current_stage_display(), task["source_state"])
            self.assertIn(self.other.name, task["scope"])
            self.assertIn("does not by itself complete", task["exception"])
            self.assertIsNone(task["due_on"])
        self.assertFalse(finance_work_tasks(self.preparer, view="completed")["tasks"])
        self.print_operator.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertFalse(finance_work_tasks(self.print_operator, view="completed")["tasks"])

    def test_event_posting_waiting_maps_authorized_source_before_limit(self):
        from vouchers.models import VoucherPostingRequest

        self.preparer.user_permissions.add(Permission.objects.get(
            content_type__app_label="accounting", codename="prepare_journal_entries"))
        for reference, office in (("A-EVENT-ACTION", self.accounting), ("Z-EVENT-WAIT", self.other)):
            item = self._case(reference, stage=VoucherCase.ACCOUNTING_EVENT_POSTING,
                              current=office, with_voucher=True, dv_prepared_by=self.signature_operator)
            request = VoucherPostingRequest.objects.create(
                case=item, kind=VoucherPostingRequest.PAYMENT, jev_date=timezone.localdate(),
                finance_department_id=office.pk, finance_department_label=office.name,
                requested_by=self.preparer, payload={}, payload_checksum="a" * 64)
        result = finance_work_tasks(self.preparer, view="waiting", display_limit=1)
        self.assertEqual([task["reference"] for task in result["tasks"]], ["Z-EVENT-WAIT"])
        self.assertFalse(result["tasks_truncated"])
        request.status = VoucherPostingRequest.CANCELLED
        request.save(update_fields=("status",))
        self.assertFalse(finance_work_tasks(self.preparer, view="waiting")["tasks"])

    def test_advice_waiting_excludes_initial_and_batch_actions_before_limit(self):
        from vouchers.models import BankAdviceItem

        self.preparer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers", codename__in=("view_bank_advice", "prepare_bank_advice", "approve_bank_advice")))
        for reference, office in (("A-INITIAL", self.accounting), ("B-REVIEW", self.accounting), ("Z-ADVICE-WAIT", self.other)):
            item = self._case(reference, stage=VoucherCase.ACCOUNTING_BANK_ADVICE, with_voucher=True, current=office)
            instrument = PaymentInstrument.objects.create(case=item, bank_account_code="synthetic", check_number=reference,
                amount=Decimal("90.00"), status=PaymentInstrument.ISSUED, issued_by=self.print_operator, issued_at=timezone.now())
            if reference == "B-REVIEW":
                batch = BankAdviceBatch.objects.create(advice_number="B-REVIEW", advice_date=timezone.localdate(),
                    bank_account_code="synthetic", accounting_department=self.accounting, status=BankAdviceBatch.FOR_REVIEW,
                    created_by=self.signature_operator, total_amount=Decimal("90.00"), item_count=1)
                BankAdviceItem.objects.create(batch=batch, instrument=instrument, amount_snapshot=instrument.amount)
                instrument.current_advice_batch = batch
                instrument.save(update_fields=("current_advice_batch",))
        result = finance_work_tasks(self.preparer, view="waiting", display_limit=1)
        self.assertEqual([task["reference"] for task in result["tasks"]], ["Z-ADVICE-WAIT"])
        self.assertFalse(result["tasks_truncated"])
        self.assertFalse(finance_work_tasks(self.uat, view="waiting")["tasks"])

    def test_advice_waiting_keeps_issuer_through_release_and_excludes_cancellation(self):
        item = self._case("ISSUER-WAIT", stage=VoucherCase.ACCOUNTING_BANK_ADVICE, with_voucher=True)
        instrument = PaymentInstrument.objects.create(case=item, bank_account_code="synthetic", check_number="ISSUER-WAIT",
            amount=Decimal("90.00"), status=PaymentInstrument.ISSUED, issued_by=self.print_operator, issued_at=timezone.now())
        for status in (PaymentInstrument.ISSUED, PaymentInstrument.ADVISED):
            instrument.status = status
            instrument.save(update_fields=("status",))
            tasks = finance_work_tasks(self.print_operator, view="waiting")["tasks"]
            self.assertEqual([task["reference"] for task in tasks], ["ISSUER-WAIT"])
            self.assertIsNone(tasks[0]["due_on"])
        instrument.status = PaymentInstrument.CANCELLED
        instrument.save(update_fields=("status",))
        self.assertFalse(finance_work_tasks(self.print_operator, view="waiting")["tasks"])
        instrument.status = PaymentInstrument.ADVISED
        instrument.save(update_fields=("status",))
        item.current_stage = VoucherCase.TREASURY_RELEASE
        item.save(update_fields=("current_stage",))
        self.assertEqual(len(finance_work_tasks(self.print_operator, view="waiting")["tasks"]), 1)
        item.current_stage = VoucherCase.COMPLETED
        item.save(update_fields=("current_stage",))
        self.assertFalse(finance_work_tasks(self.print_operator, view="waiting")["tasks"])

    def test_posting_waiting_maps_source_actions_before_limit_and_retains_requester(self):
        from vouchers.models import VoucherPostingRequest

        self.preparer.user_permissions.add(Permission.objects.get(
            content_type__app_label="accounting", codename="prepare_journal_entries"))
        for reference, office in (("A-POST-ACTION", self.accounting), ("Z-POST-WAIT", self.other)):
            item = self._case(reference, stage=VoucherCase.ACCOUNTING_POSTING, with_voucher=True, current=office)
            VoucherPostingRequest.objects.create(
                case=item, kind=VoucherPostingRequest.RECOGNITION, jev_date=timezone.localdate(),
                finance_department_id=office.pk, finance_department_label=office.name,
                requested_by=self.preparer, payload={}, payload_checksum="a" * 64)
        result = finance_work_tasks(self.preparer, view="waiting", display_limit=1)
        self.assertEqual([task["reference"] for task in result["tasks"]], ["Z-POST-WAIT"])
        self.assertFalse(result["tasks_truncated"])
        item = self._case("REQUESTER-ONLY", stage=VoucherCase.ACCOUNTING_POSTING,
                          with_voucher=True, dv_prepared_by=self.signature_operator)
        request = VoucherPostingRequest.objects.create(
            case=item, kind=VoucherPostingRequest.RECOGNITION, jev_date=timezone.localdate(),
            finance_department_id=self.accounting.pk, finance_department_label=self.accounting.name,
            requested_by=self.validator, payload={}, payload_checksum="a" * 64)
        tasks = finance_work_tasks(self.validator, view="waiting")["tasks"]
        self.assertEqual([task["reference"] for task in tasks], ["REQUESTER-ONLY"])
        self.assertIn("source synchronization", tasks[0]["owner_queue"])
        self.assertIsNone(tasks[0]["due_on"])
        request.status = VoucherPostingRequest.CANCELLED
        request.save(update_fields=("status",))
        self.assertFalse(finance_work_tasks(self.validator, view="waiting")["tasks"])

    def test_dv_completion_keeps_each_recorded_action_after_custody_moves(self):
        from vouchers.models import VoucherEvent

        item = self._case("DV-HISTORY", stage=VoucherCase.TREASURY_RELEASE, current=self.other, with_voucher=True)
        expected = []
        for index, (action, before, after) in enumerate((
            ("dv_prepared", VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.AWAITING_SIGNATURES),
            ("dv_corrected", VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.ACCOUNTING_VALIDATION),
            ("dv_corrected", VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.AWAITING_SIGNATURES),
            ("accounting_validated", VoucherCase.ACCOUNTING_VALIDATION, VoucherCase.ACCOUNTING_POSTING),
        )):
            expected.append(VoucherEvent.objects.create(
                case=item, action=action, from_stage=before, to_stage=after,
                actor=self.preparer, actor_department=self.accounting, state_version=index+1,
                idempotency_key=f"history-{index}", reason="Retained review evidence"))
        VoucherEvent.objects.create(case=item, action="dv_prepared", from_stage=VoucherCase.TREASURY_RELEASE,
            to_stage=VoucherCase.ACCOUNTING_VALIDATION, actor=self.preparer, actor_department=self.accounting,
            state_version=5, idempotency_key="inconsistent")
        VoucherEvent.objects.create(case=item, action="dv_prepared", from_stage=VoucherCase.ACCOUNTING_PREPARATION,
            to_stage=VoucherCase.ACCOUNTING_VALIDATION, actor=self.validator, actor_department=self.accounting,
            state_version=6, idempotency_key="other-actor")
        self._case("DV-NO-HISTORY", stage=VoucherCase.COMPLETED, with_voucher=True)
        tasks = finance_work_tasks(self.preparer, view="completed")["tasks"]
        self.assertEqual(len(tasks), len(expected))
        self.assertEqual(len({task["task_id"] for task in tasks}), len(expected))
        self.assertEqual({task["received_at"] for task in tasks}, {event.created_at for event in expected})
        for task in tasks:
            self.assertEqual(task["case_id"], f"voucher-case:{item.public_id}")
            self.assertEqual(task["source_state"], item.get_current_stage_display())
            self.assertIn(self.accounting.name, task["scope"])
            self.assertIn("does not authorize payment release", task["gate"])
            self.assertIsNone(task["due_on"])
        self.assertEqual(self.client.get(tasks[0]["url"]).status_code, 302)
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(tasks[0]["url"]).status_code, 200)
        self.preparer.user_permissions.clear()
        self.assertFalse(finance_work_tasks(self.preparer, view="completed")["tasks"])

    def test_signature_completion_credits_service_recorder_not_signatory(self):
        from vouchers.services import record_signature_return

        item = self._case("DV-RECORDER", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True, controlled=False)
        first = WetSignatureTask.objects.create(case=item, round_number=1, sequence=1, role_code="head",
            signatory_name_snapshot="Actual paper signatory")
        second = WetSignatureTask.objects.create(case=item, round_number=1, sequence=2, role_code="accountant",
            signatory_name_snapshot="Another paper signatory")
        record_signature_return(case=item, task=first, actor=self.signature_operator, note="Received first paper",
            expected_version=item.state_version, idempotency_key="first-paper")
        item.refresh_from_db()
        record_signature_return(case=item, task=second, actor=self.signature_operator, note="Received final paper",
            expected_version=item.state_version, idempotency_key="final-paper")
        tasks = finance_work_tasks(self.signature_operator, view="completed")["tasks"]
        self.assertEqual(len(tasks), 2)
        self.assertEqual({task["task_type"] for task in tasks}, {
            "finance.dv.wet_signature_returned.completed.v1", "finance.dv.wet_signatures_completed.completed.v1"})
        for task in tasks:
            self.assertIn("custody recording", task["exception"])
            self.assertIn("not the recorder's own wet signature", task["exception"])
        self.assertFalse(finance_work_tasks(self.preparer, view="completed")["tasks"])
        self.signature_operator.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertFalse(finance_work_tasks(self.signature_operator, view="completed")["tasks"])

    def test_dv_waiting_uses_retained_stage_handoff_and_current_preparer(self):
        from vouchers.models import VoucherEvent

        item = self._case("DV-WAIT-OWN", stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True)
        self._case("DV-WAIT-OTHER", stage=VoucherCase.AWAITING_SIGNATURES,
                   with_voucher=True, dv_prepared_by=self.validator)
        self._case("DV-WAIT-MISSING", stage=VoucherCase.AWAITING_SIGNATURES)
        first = VoucherEvent.objects.create(
            case=item, action="dv_prepared", from_stage=VoucherCase.ACCOUNTING_PREPARATION,
            to_stage=item.current_stage, actor=self.preparer, actor_department=self.accounting,
            state_version=1, idempotency_key="prepare")
        VoucherEvent.objects.create(
            case=item, action="wet_signature_returned", from_stage=item.current_stage,
            to_stage=item.current_stage, actor=self.signature_operator, actor_department=self.accounting,
            state_version=2, idempotency_key="partial")
        tasks = finance_work_tasks(self.preparer, view="waiting")["tasks"]
        self.assertEqual([task["reference"] for task in tasks], [item.reference_code])
        self.assertEqual(tasks[0]["received_at"], first.created_at)
        self.assertIsNone(tasks[0]["due_on"])
        self.assertEqual(tasks[0]["url"], reverse("vouchers:case_detail", kwargs={"public_id": item.public_id}))
        identity = tasks[0]["case_id"]
        item.current_stage = VoucherCase.ACCOUNTING_VALIDATION
        item.save(update_fields=("current_stage",))
        tasks = finance_work_tasks(self.preparer, view="waiting")["tasks"]
        self.assertEqual(tasks[0]["case_id"], identity)
        self.assertIsNone(tasks[0]["received_at"])
        self.assertIn("no retained handoff time", tasks[0]["exception"])
        final = VoucherEvent.objects.create(
            case=item, action="wet_signatures_completed", from_stage=VoucherCase.AWAITING_SIGNATURES,
            to_stage=item.current_stage, actor=self.signature_operator, actor_department=self.accounting,
            state_version=3, idempotency_key="complete")
        task = finance_work_tasks(self.preparer, view="waiting")["tasks"][0]
        self.assertEqual(task["received_at"], final.created_at)
        self.assertIn("Independent Accounting validation", task["owner_queue"])
        self.assertFalse(finance_work_tasks(self.uat, view="waiting")["tasks"])
        item.current_stage = VoucherCase.COMPLETED
        item.save(update_fields=("current_stage",))
        self.assertFalse(finance_work_tasks(self.preparer, view="waiting")["tasks"])

    def test_dv_waiting_excludes_authorized_signature_children_before_limit(self):
        for reference, controlled, packet in (("A-ACTION", True, True), ("B-LEGACY", False, False), ("Z-WAIT", True, False)):
            item = self._case(reference, stage=VoucherCase.AWAITING_SIGNATURES, with_voucher=True,
                              controlled=controlled, dv_prepared_by=self.signature_operator)
            WetSignatureTask.objects.create(
                case=item, round_number=1, sequence=1, role_code="department-head",
                signatory_name_snapshot="Synthetic Head", position_snapshot="Head",
                custody_department=self.accounting)
            if controlled:
                self._print_job(item, VoucherPrintJob.AWAITING_SIGNATURES)
            if packet:
                self._attach_packet(item)
        result = finance_work_tasks(self.signature_operator, view="waiting", display_limit=1)
        self.assertEqual([task["reference"] for task in result["tasks"]], ["Z-WAIT"])

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


    def test_completed_actions_require_retained_attribution_and_current_source_access(self):
        from accounting.services import submit_entry, return_entry
        entry = self._entry("COMPLETED-ACTION")
        submit_entry(entry, self.preparer)
        return_entry(entry, self.poster, "Correct the retained reference")
        self._entry("TERMINAL-WITHOUT-EVENT", status=JournalEntry.POSTED)
        first = finance_work_tasks(self.preparer, view="completed")["tasks"]
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["subject"], "Submitted JEV for posting")
        self.assertEqual(first[0]["state"], "Completed")
        self.assertEqual(first[0]["source_state"], "Draft")
        self.assertEqual([task["subject"] for task in finance_work_tasks(self.poster, view="completed")["tasks"]],
                         ["Returned JEV for correction"])
        submit_entry(entry, self.preparer)
        history = finance_work_tasks(self.preparer, view="completed")["tasks"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["task_id"], first[0]["task_id"])
        self.assertGreaterEqual(history[0]["received_at"], history[1]["received_at"])
        self.assertEqual(finance_work_tasks(self.preparer, view="completed", display_limit=1)["task_count"], 2)
        self.assertEqual(finance_work_tasks(self.outsider, view="completed")["task_count"], 0)
        self.assertEqual(finance_work_tasks(self.uat, view="completed")["task_count"], 0)
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("finance_operations:my_work"), {"view": "completed"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Completed by me")
        self.assertContains(response, "Submitted JEV for posting")
        self.assertContains(response, "Recorded:</strong>")
        self.preparer.user_permissions.clear()
        self.assertEqual(finance_work_tasks(self.preparer, view="completed")["task_count"], 0)

    def test_waiting_is_personal_currently_authorized_and_excludes_actionable_records(self):
        own = self._entry("WAIT-OWN", status=JournalEntry.SUBMITTED, submitter=self.preparer)
        self._entry("WAIT-OTHER", status=JournalEntry.SUBMITTED, creator=self.poster, submitter=self.poster)
        self._entry("WAIT-DRAFT")
        result = finance_work_tasks(self.preparer, view="waiting", display_limit=1)
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["tasks"][0]["case_id"], f"journal-entry:{own.public_id}")
        self.assertEqual(result["tasks"][0]["state"], "Waiting")
        self.assertIsNone(result["tasks"][0]["due_on"])
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("finance_operations:my_work"), {"view": "waiting"})
        self.assertContains(response, "Work you prepared or submitted")
        self.assertEqual(response.context["task_count"], 1)
        self.assertEqual(self.client.get(reverse("finance_operations:my_work"), {"view": "unknown"}).status_code, 404)
        FinanceWorkflowExemption.objects.create(
            department=self.accounting, control_code=FinanceWorkflowExemption.JOURNAL_PREPARER_SELF_POSTING,
            subject_user=self.preparer, rationale="Synthetic named exemption", created_by=self.poster,
        )
        self.assertEqual(finance_work_tasks(self.preparer, view="waiting")["task_count"], 0)
        self.assertEqual(finance_work_tasks(self.outsider, view="waiting")["task_count"], 0)
        self.assertEqual(finance_work_tasks(self.uat, view="waiting")["task_count"], 0)
        self.preparer.user_permissions.clear()
        self.assertEqual(finance_work_tasks(self.preparer, view="waiting")["task_count"], 0)

    def test_returned_filter_uses_current_stage_and_precedes_display_limit(self):
        self._entry("A-READY")
        returned = self._entry("Z-RETURNED")
        resubmitted = self._entry("B-RESUBMITTED", status=JournalEntry.SUBMITTED, creator=self.poster, submitter=self.poster)
        for entry in (returned, resubmitted):
            AccountingAuditEvent.objects.create(
                department_id=self.accounting.pk, department_label=self.accounting.name,
                entry=entry, action="returned", actor_id=self.poster.pk,
                actor_label=self.poster.username, reason="Retained correction instruction",
            )
        result = finance_work_tasks(self.preparer, view="returned", display_limit=1)
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["tasks"][0]["case_id"], f"journal-entry:{returned.public_id}")
        self.assertFalse(result["tasks_truncated"])
        self.assertFalse(any(task["case_id"] == f"journal-entry:{resubmitted.public_id}"
                             for task in finance_work_tasks(self.poster, view="returned")["tasks"]))


class FinanceBankReconciliationWorkTaskContractTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="task-bank-reconciliation-accounting",
        )
        cls.other = Department.objects.create(
            name="Other Accounting Office", slug="task-bank-reconciliation-other",
        )
        cls.preparer = cls._employee(
            "task.bank.preparer", cls.accounting,
            "view_bank_reconciliation", "prepare_bank_reconciliation",
            "approve_bank_reconciliation", "export_bank_reconciliation",
        )
        cls.reviewer = cls._employee(
            "task.bank.reviewer", cls.accounting,
            "view_bank_reconciliation", "approve_bank_reconciliation",
        )
        cls.outsider = cls._employee(
            "task.bank.outsider", cls.other,
            "view_bank_reconciliation", "prepare_bank_reconciliation",
            "approve_bank_reconciliation",
        )
        cls.uat = cls._employee(
            "task.bank.uat", cls.accounting,
            "view_bank_reconciliation", "prepare_bank_reconciliation",
            "approve_bank_reconciliation",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        cls.fund = Fund.objects.create(
            department_id=cls.accounting.pk, department_label=cls.accounting.name,
            code="TASK-BANK-GF", name="Task Bank General Fund",
        )
        cls.other_fund = Fund.objects.create(
            department_id=cls.other.pk, department_label=cls.other.name,
            code="TASK-BANK-OTHER", name="Other Bank Fund",
        )
        owner = {"department_id": cls.accounting.pk, "department_label": cls.accounting.name}
        cls.period = AccountingPeriod.objects.create(
            **owner, fiscal_year=2027, period_number=1, label="January 2027",
            starts_on=date(2027, 1, 1), ends_on=date(2027, 1, 31),
        )
        cls.center = ResponsibilityCenter.objects.create(
            **owner, code="TASK-BANK-CENTER", name="Task Bank Accounting",
        )
        cls.cash = LedgerAccount.objects.create(
            **owner, code="TASK-BANK-101", title="Task Bank Cash",
            account_type="asset", normal_balance="debit",
        )
        cls.revenue = LedgerAccount.objects.create(
            **owner, code="TASK-BANK-401", title="Task Bank Revenue",
            account_type="revenue", normal_balance="credit",
        )
        PostingMapping.objects.create(
            **owner, category=PostingMapping.BANK, source_code="TASK-BANK-ACCOUNT",
            label="Task bank-account mapping", account=cls.cash,
        )

    @classmethod
    def _employee(cls, username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="bank-task-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="accounting", codename__in=permissions,
        ))
        return get_user_model().objects.get(pk=user.pk)

    def _batch(
        self, reference, *, department=None, fund=None, status=BankStatementBatch.DRAFT,
        source_version=0, creator=None, submitter=None, expected_deposits=Decimal("0.00"),
        closing_balance=Decimal("0.00"), expected_row_count=0,
    ):
        department = department or self.accounting
        fund = fund or self.fund
        creator = creator or self.preparer
        return BankStatementBatch.objects.create(
            department_id=department.pk, department_label=department.name,
            statement_reference=reference, bank_account_code="TASK-BANK-ACCOUNT",
            bank_name="Task Municipal Bank", account_number_masked="***0001", fund=fund,
            period_start=date(2027, 1, 1), period_end=date(2027, 1, 31),
            received_on=date(2027, 2, 1), opening_balance=Decimal("0.00"),
            closing_balance=closing_balance, expected_row_count=expected_row_count,
            expected_deposits=expected_deposits, expected_withdrawals=Decimal("0.00"),
            status=status, source_version=source_version,
            source_filename="task-statement.csv" if source_version else "",
            source_checksum="a" * 64 if source_version else "",
            validation_summary={
                "valid": True, "source_version": source_version,
                "row_count": expected_row_count, "deposits": str(expected_deposits),
                "withdrawals": "0.00", "computed_closing": str(closing_balance), "errors": [],
            } if status in (BankStatementBatch.VALIDATED, BankStatementBatch.FOR_REVIEW) else {},
            created_by_id=creator.pk, created_by_label=creator.username,
            submitted_by_id=submitter.pk if submitter else None,
            submitted_by_label=submitter.username if submitter else "",
            submitted_at=timezone.now() if submitter else None,
        )

    @staticmethod
    def _row_checksum(*, source_version, row_number, transaction_date, description, deposit):
        payload = {
            "source_version": source_version, "row_number": row_number,
            "transaction_date": transaction_date.isoformat(), "bank_reference": "TASK-DEP-1",
            "description": description, "withdrawal": "0.00", "deposit": str(deposit),
            "running_balance": str(deposit),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def test_bank_waiting_is_personal_and_office_scoped_before_limit(self):
        self._batch("A-OTHER-MAKER", status=BankStatementBatch.FOR_REVIEW, source_version=1,
                    creator=self.reviewer, submitter=self.reviewer)
        own = self._batch("Z-OWN-WAIT", status=BankStatementBatch.FOR_REVIEW, source_version=1, submitter=self.preparer)
        self._batch("FOREIGN-WAIT", department=self.other, fund=self.other_fund,
                    status=BankStatementBatch.FOR_REVIEW, source_version=1, submitter=self.preparer)
        result = finance_work_tasks(self.preparer, view="waiting", display_limit=1)
        self.assertEqual([task["reference"] for task in result["tasks"]], [own.statement_reference])
        self.assertFalse(result["tasks_truncated"])
        self.assertEqual(result["tasks"][0]["received_at"], own.submitted_at)
        self.assertIsNone(result["tasks"][0]["due_on"])
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(result["tasks"][0]["url"]).status_code, 200)
        decide_bank_reconciliation(own, self.reviewer, decision=BankStatementBatch.RETURNED,
                                   evidence_note="Resolve the retained statement evidence before resubmission.")
        self.assertFalse(finance_work_tasks(self.preparer, view="waiting")["tasks"])
        self.assertTrue(any(task["case_id"] == f"bank-reconciliation:{own.public_id}" for task in
                            finance_work_tasks(self.reviewer, view="completed")["tasks"]))
        self.assertFalse(finance_work_tasks(self.uat, view="waiting")["tasks"])

    def test_bank_history_rechecks_specific_read_permission_and_event_office(self):
        from accounting.models import BankReconciliationEvent

        own = self._batch("BANK-HISTORY", status=BankStatementBatch.RETURNED)
        valid = BankReconciliationEvent.objects.create(batch=own, action="submitted_for_review",
            actor_id=self.preparer.pk, actor_label=self.preparer.username,
            department_id=self.accounting.pk, department_label=self.accounting.name)
        BankReconciliationEvent.objects.create(batch=own, action="submitted_for_review",
            actor_id=self.preparer.pk, actor_label=self.preparer.username,
            department_id=self.other.pk, department_label=self.other.name)
        BankReconciliationEvent.objects.create(batch=own, action="row_matched",
            actor_id=self.preparer.pk, actor_label=self.preparer.username,
            department_id=self.accounting.pk, department_label=self.accounting.name)
        tasks = finance_work_tasks(self.preparer, view="completed")["tasks"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["received_at"], valid.created_at)
        self.assertEqual(tasks[0]["source_state"], own.get_status_display())
        self.assertIsNone(tasks[0]["due_on"])
        self.preparer.user_permissions.remove(Permission.objects.get(
            content_type__app_label="accounting", codename="view_bank_reconciliation"))
        self.assertFalse(finance_work_tasks(self.preparer, view="completed")["tasks"])

    def test_source_screen_export_count_and_task_share_exact_preparation_scope(self):
        ready = self._batch("TASK-BRS-NEEDS-STATEMENT")
        self._batch(
            "TASK-BRS-OTHER-OFFICE", department=self.other, fund=self.other_fund,
            creator=self.outsider,
        )
        source, selected, _spec = bank_reconciliation_action_queryset(
            self.preparer, "needs_statement",
        )
        self.assertEqual(selected, "needs_statement")
        self.assertEqual(set(source), {ready})

        self.client.force_login(self.preparer)
        workspace = self.client.get(
            reverse("accounting:bank_reconciliation_workspace"), {"attention": "needs_statement"},
        )
        self.assertEqual(workspace.context["visible_count"], 1)
        self.assertContains(workspace, ready.statement_reference)
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            exported = self.client.get(
                reverse("accounting:bank_reconciliation_register_export"),
                {"attention": "needs_statement"},
            )
            rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
        self.assertEqual([row["batch_public_id"] for row in rows], [str(ready.public_id)])

        tasks = [
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["task_type"] == "finance.bank-reconciliation.statement-staging.v1"
        ]
        group = next(
            group for group in finance_work_attention(self.preparer)["groups"]
            if group["key"] == "bank-statement"
        )
        self.assertEqual(group["count"], len(tasks))
        self.assertEqual(tasks[0]["case_id"], f"bank-reconciliation:{ready.public_id}")
        self.assertEqual(
            tasks[0]["url"],
            reverse("accounting:bank_reconciliation_detail", kwargs={"public_id": ready.public_id}),
        )
        self.assertIsNone(tasks[0]["due_on"])

        first = tasks[0]
        BankStatementBatch.objects.filter(pk=ready.pk).update(bank_name="Task Municipal Bank Updated")
        changed = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"bank-reconciliation:{ready.public_id}"
        )
        self.assertEqual(changed["task_id"], first["task_id"])
        self.assertNotEqual(changed["source_version"], first["source_version"])

    def test_review_scope_excludes_creator_submitter_wrong_office_and_uat(self):
        submitted = self._batch(
            "TASK-BRS-FOR-REVIEW", status=BankStatementBatch.FOR_REVIEW,
            creator=self.preparer, submitter=self.preparer,
        )
        self.assertFalse(bank_reconciliation_action_queryset(self.preparer, "for_review")[0].exists())
        self.assertEqual(
            set(bank_reconciliation_action_queryset(self.reviewer, "for_review")[0]), {submitted},
        )
        self.assertFalse(bank_reconciliation_action_queryset(self.outsider, "for_review")[0].exists())
        self.assertFalse(bank_reconciliation_action_queryset(self.uat, "for_review")[0].exists())
        self.client.force_login(self.preparer)
        own_workspace = self.client.get(
            reverse("accounting:bank_reconciliation_workspace"), {"attention": "for_review"},
        )
        self.assertEqual(own_workspace.context["visible_count"], 0)
        self.assertNotContains(own_workspace, submitted.statement_reference)
        self.client.force_login(self.reviewer)
        review_workspace = self.client.get(
            reverse("accounting:bank_reconciliation_workspace"), {"attention": "for_review"},
        )
        self.assertEqual(review_workspace.context["visible_count"], 1)
        self.assertContains(review_workspace, submitted.statement_reference)
        self.client.force_login(self.uat)
        uat_workspace = self.client.get(reverse("accounting:bank_reconciliation_workspace"))
        self.assertEqual(uat_workspace.context["attention_choices"], (("reconciled", "Reconciled evidence"),))
        self.assertFalse(uat_workspace.context["can_prepare_bank"])
        reviewer_tasks = [
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["task_type"] == "finance.bank-reconciliation.independent-close-review.v1"
        ]
        self.assertEqual(len(reviewer_tasks), 1)
        self.assertIn("snapshot checksum no longer reproduces", reviewer_tasks[0]["exception"])
        self.assertFalse(any(
            task["task_type"].startswith("finance.bank-reconciliation.")
            for task in finance_work_tasks(self.uat)["tasks"]
        ))

    def test_zero_difference_submission_projects_ready_independent_close_and_completes(self):
        batch = self._batch(
            "TASK-BRS-READY-CLOSE", status=BankStatementBatch.VALIDATED, source_version=1,
            expected_row_count=1, expected_deposits=Decimal("100.00"),
            closing_balance=Decimal("100.00"),
        )
        description = "Task cleared deposit"
        row = BankStatementRow.objects.create(
            batch=batch, source_version=1, row_number=1, transaction_date=date(2027, 1, 15),
            bank_reference="TASK-DEP-1", description=description,
            withdrawal=Decimal("0.00"), deposit=Decimal("100.00"),
            running_balance=Decimal("100.00"),
            row_checksum=self._row_checksum(
                source_version=1, row_number=1, transaction_date=date(2027, 1, 15),
                description=description, deposit=Decimal("100.00"),
            ),
        )
        entry = JournalEntry.objects.create(
            department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="TASK-DEP-1", entry_date=date(2027, 1, 15), period=self.period,
            fund=self.fund, source_type="manual", description="Task cleared bank deposit",
            status=JournalEntry.DRAFT, created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        bank_line = JournalLine.objects.create(
            entry=entry, sequence=1, account=self.cash, responsibility_center=self.center,
            debit=Decimal("100.00"), credit=Decimal("0.00"), memo="TASK-DEP-1 bank receipt",
        )
        JournalLine.objects.create(
            entry=entry, sequence=2, account=self.revenue, responsibility_center=self.center,
            debit=Decimal("0.00"), credit=Decimal("100.00"), memo="Task deposit recognition",
        )
        JournalEntry.objects.filter(pk=entry.pk).update(status=JournalEntry.POSTED)
        entry.refresh_from_db()
        match_bank_statement_row(
            row, bank_line, self.preparer,
            reason="Exact date, reference, amount, and direction agree.",
        )
        submitted = submit_bank_reconciliation(batch, self.preparer)
        self.assertTrue(any(item["case_id"] == f"bank-reconciliation:{batch.public_id}"
                            for item in finance_work_tasks(self.preparer, view="waiting")["tasks"]))
        self.assertTrue(any(item["task_type"] == "finance.bank-reconciliation.submitted_for_review.completed.v1"
                            for item in finance_work_tasks(self.preparer, view="completed")["tasks"]))
        task = next(
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["case_id"] == f"bank-reconciliation:{batch.public_id}"
        )
        self.assertEqual(task["state"], "Ready")
        self.assertEqual(task["exception"], "")
        self.assertEqual(
            task["task_type"], "finance.bank-reconciliation.independent-close-review.v1",
        )
        reconciled = decide_bank_reconciliation(
            submitted, self.reviewer, decision=BankStatementBatch.RECONCILED,
            evidence_note="Independently reproduced the exact zero-difference BRS evidence.",
        )
        self.assertEqual(reconciled.status, BankStatementBatch.RECONCILED)
        self.assertFalse(finance_work_tasks(self.preparer, view="waiting")["tasks"])
        self.assertTrue(any(item["task_type"] == "finance.bank-reconciliation.reconciled.completed.v1"
                            for item in finance_work_tasks(self.reviewer, view="completed")["tasks"]))
        self.assertFalse(any(
            task["case_id"] == f"bank-reconciliation:{batch.public_id}"
            for task in finance_work_tasks(self.reviewer)["tasks"]
        ))

    def test_one_cent_control_and_row_tamper_change_revision_and_stop_the_task(self):
        batch = self._batch(
            "TASK-BRS-CENT", source_version=1, expected_row_count=1,
            expected_deposits=Decimal("100.00"), closing_balance=Decimal("100.00"),
        )
        description = "Task retained deposit"
        row = BankStatementRow.objects.create(
            batch=batch, source_version=1, row_number=1, transaction_date=date(2027, 1, 15),
            bank_reference="TASK-DEP-1", description=description,
            withdrawal=Decimal("0.00"), deposit=Decimal("99.99"),
            running_balance=Decimal("99.99"),
            row_checksum=self._row_checksum(
                source_version=1, row_number=1, transaction_date=date(2027, 1, 15),
                description=description, deposit=Decimal("99.99"),
            ),
        )
        first = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"bank-reconciliation:{batch.public_id}"
        )
        self.assertIn("deposits differ from the declared total by -0.01", first["exception"])
        self.assertIn("differs from closing by -0.01", first["exception"])
        BankStatementRow.objects.filter(pk=row.pk).update(description="Tampered retained deposit")
        changed = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"bank-reconciliation:{batch.public_id}"
        )
        self.assertEqual(changed["task_id"], first["task_id"])
        self.assertNotEqual(changed["source_version"], first["source_version"])
        self.assertIn("no longer reproduces its retained checksum", changed["exception"])

    def test_decision_service_rejects_self_return_and_cross_office_call(self):
        submitted = self._batch(
            "TASK-BRS-SERVICE-SELF", status=BankStatementBatch.FOR_REVIEW,
            creator=self.preparer, submitter=self.preparer,
        )
        with self.assertRaisesMessage(ValidationError, "independent"):
            decide_bank_reconciliation(
                submitted, self.preparer, decision=BankStatementBatch.RETURNED,
                evidence_note="Self-return must not bypass independent review.",
            )
        with self.assertRaises(PermissionDenied):
            decide_bank_reconciliation(
                submitted, self.outsider, decision=BankStatementBatch.RETURNED,
                evidence_note="A different office must not decide this statement.",
            )


class FinancePeriodCloseWorkTaskContractTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="task-period-close-accounting",
        )
        cls.other = Department.objects.create(
            name="Other Accounting Office", slug="task-period-close-other",
        )
        cls.preparer = cls._employee(
            "task.close.preparer", cls.accounting,
            "view_accounting_workspace", "prepare_period_close", "approve_period_close",
            "reopen_period", "export_period_close",
        )
        cls.reviewer = cls._employee(
            "task.close.reviewer", cls.accounting,
            "view_accounting_workspace", "approve_period_close", "reopen_period",
            "export_period_close",
        )
        cls.outsider = cls._employee(
            "task.close.outsider", cls.other,
            "view_accounting_workspace", "prepare_period_close", "approve_period_close",
            "reopen_period", "export_period_close",
        )
        cls.uat = cls._employee(
            "task.close.uat", cls.accounting,
            "view_accounting_workspace", "prepare_period_close", "approve_period_close",
            "reopen_period", "export_period_close",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        owner = {"department_id": cls.accounting.pk, "department_label": cls.accounting.name}
        cls.january = AccountingPeriod.objects.create(
            **owner, fiscal_year=2029, period_number=1, label="January 2029",
            starts_on=date(2029, 1, 1), ends_on=date(2029, 1, 31),
        )
        cls.february = AccountingPeriod.objects.create(
            **owner, fiscal_year=2029, period_number=2, label="February 2029",
            starts_on=date(2029, 2, 1), ends_on=date(2029, 2, 28),
        )
        cls.march = AccountingPeriod.objects.create(
            **owner, fiscal_year=2029, period_number=3, label="March 2029",
            starts_on=date(2029, 3, 1), ends_on=date(2029, 3, 31),
        )
        cls.fund = Fund.objects.create(
            **owner, code="TASK-CLOSE-GF", name="Task Close General Fund",
        )
        cls.debit_account = LedgerAccount.objects.create(
            **owner, code="TASK-CLOSE-101", title="Task Close Debit",
            account_type="asset", normal_balance="debit",
        )
        cls.credit_account = LedgerAccount.objects.create(
            **owner, code="TASK-CLOSE-201", title="Task Close Credit",
            account_type="liability", normal_balance="credit",
        )

    @classmethod
    def _employee(cls, username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="close-task-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="accounting", codename__in=permissions,
        ))
        return get_user_model().objects.get(pk=user.pk)

    def _run(self, period, *, actor=None):
        return create_period_close_run(
            period, self.accounting, actor or self.preparer,
            adjustment_review_note="Reviewed adjusting and closing entries; none are required.",
            evidence_reference=f"Task close binder / {period.fiscal_year} / {period.period_number}",
            preparer_note="Prepared for exact task-contract verification.",
        )

    def test_source_screen_export_count_and_task_share_exact_preparation_scope(self):
        run = self._run(self.january)
        source, selected, _spec = period_close_action_queryset(self.preparer, "needs_preparation")
        self.assertEqual(selected, "needs_preparation")
        self.assertEqual(set(source), {run})

        self.client.force_login(self.preparer)
        workspace = self.client.get(
            reverse("accounting:period_close_workspace"), {"attention": "needs_preparation"},
        )
        self.assertEqual(workspace.context["visible_count"], 1)
        self.assertContains(workspace, str(run.period))
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            exported = self.client.get(
                reverse("accounting:period_close_register_export"),
                {"attention": "needs_preparation"},
            )
            rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
        self.assertEqual([row["close_run_public_id"] for row in rows], [str(run.public_id)])

        tasks = [
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["task_type"] == "finance.period-close.checklist-preparation.v1"
        ]
        group = next(
            group for group in finance_work_attention(self.preparer)["groups"]
            if group["key"] == "period-close-preparation"
        )
        self.assertEqual(group["count"], len(tasks))
        self.assertEqual(tasks[0]["case_id"], f"period-close:{run.public_id}")
        self.assertEqual(
            tasks[0]["url"],
            reverse("accounting:period_close_detail", kwargs={"public_id": run.public_id}),
        )
        self.assertIsNone(tasks[0]["due_on"])

        first = tasks[0]
        refresh_period_close_run(
            run, self.preparer,
            adjustment_review_note=run.adjustment_review_note,
            evidence_reference=run.evidence_reference,
            preparer_note="Changed retained preparation note.",
        )
        changed = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"period-close:{run.public_id}"
        )
        self.assertEqual(changed["task_id"], first["task_id"])
        self.assertNotEqual(changed["source_version"], first["source_version"])

    def test_review_scope_excludes_maker_wrong_office_and_uat(self):
        run = self._run(self.january)
        submit_period_close_run(run, self.preparer)
        waiting = finance_work_tasks(self.preparer, view="waiting")["tasks"]
        self.assertEqual([task["case_id"] for task in waiting], [f"period-close:{run.public_id}"])
        self.assertEqual(finance_work_tasks(self.reviewer, view="waiting")["task_count"], 0)
        self.assertFalse(period_close_action_queryset(self.preparer, "awaiting_review")[0].exists())
        self.assertEqual(
            set(period_close_action_queryset(self.reviewer, "awaiting_review")[0]), {run},
        )
        self.assertFalse(period_close_action_queryset(self.outsider, "awaiting_review")[0].exists())
        self.assertFalse(period_close_action_queryset(self.uat, "awaiting_review")[0].exists())

        self.client.force_login(self.preparer)
        own_workspace = self.client.get(
            reverse("accounting:period_close_workspace"), {"attention": "awaiting_review"},
        )
        self.assertEqual(own_workspace.context["visible_count"], 0)
        self.client.force_login(self.reviewer)
        review_workspace = self.client.get(
            reverse("accounting:period_close_workspace"), {"attention": "awaiting_review"},
        )
        self.assertEqual(review_workspace.context["visible_count"], 1)
        self.assertContains(review_workspace, str(run.period))
        self.client.force_login(self.uat)
        uat_workspace = self.client.get(reverse("accounting:period_close_workspace"))
        self.assertEqual(uat_workspace.context["attention_choices"], ())
        self.assertFalse(uat_workspace.context["can_prepare_close"])
        self.assertFalse(any(
            task["task_type"].startswith("finance.period-close.")
            for task in finance_work_tasks(self.uat)["tasks"]
        ))

    def test_return_reason_and_checklist_tamper_change_revision_and_stop_task(self):
        run = self._run(self.january)
        submit_period_close_run(run, self.preparer)
        returned = decide_period_close_run(
            run, self.reviewer, approve=False,
            note="Correct the retained period-end schedule reference.",
        )
        first = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"period-close:{run.public_id}"
        )
        self.assertEqual(first["state"], "Returned")
        self.assertIn("Correct the retained period-end schedule reference", first["exception"])
        PeriodCloseRun.objects.filter(pk=returned.pk).update(
            checklist_snapshot={**returned.checklist_snapshot, "tampered": True},
        )
        changed = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"period-close:{run.public_id}"
        )
        self.assertEqual(changed["task_id"], first["task_id"])
        self.assertNotEqual(changed["source_version"], first["source_version"])
        self.assertIn("checklist no longer reproduces", changed["exception"])

    def test_close_then_reopen_projects_ready_independent_decision_and_completes(self):
        run = self._run(self.january)
        submit_period_close_run(run, self.preparer)
        closed = decide_period_close_run(
            run, self.reviewer, approve=True, note="Reproduced the exact close evidence.",
        )
        requested = request_period_reopen(
            closed, self.preparer,
            reason="A supported late adjustment requires governed correction.",
            authority_reference="Municipal Accountant memo TASK-CLOSE-01.",
        )
        self.assertFalse(
            period_close_action_queryset(self.preparer, "awaiting_reopen_decision")[0].exists()
        )
        task = next(
            task for task in finance_work_tasks(self.reviewer)["tasks"]
            if task["case_id"] == f"period-close:{run.public_id}"
        )
        self.assertEqual(task["task_type"], "finance.period-close.independent-reopen-decision.v1")
        self.assertEqual(task["state"], "Ready")
        self.assertEqual(task["exception"], "")
        reopened = decide_period_reopen(
            requested, self.reviewer, approve=True,
            note="Verified correction authority and period chronology.",
        )
        self.assertEqual(reopened.status, PeriodCloseRun.REOPENED)
        completed = finance_work_tasks(self.reviewer, view="completed")["tasks"]
        self.assertEqual([task["subject"] for task in completed], ["Reopened Accounting period", "Closed Accounting period"])
        self.assertFalse(any(
            task["case_id"] == f"period-close:{run.public_id}"
            for task in finance_work_tasks(self.reviewer)["tasks"]
        ))

    def test_one_cent_drift_and_direct_cross_office_calls_are_blocked(self):
        run = self._run(self.january)
        first = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"period-close:{run.public_id}"
        )
        entry = JournalEntry.objects.create(
            department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="TASK-CLOSE-CENT", entry_date=date(2029, 1, 15), period=self.january,
            fund=self.fund, description="Synthetic one-cent close drift",
            status=JournalEntry.DRAFT, created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        JournalLine.objects.create(
            entry=entry, sequence=1, account=self.debit_account,
            debit=Decimal("1.00"), credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            entry=entry, sequence=2, account=self.credit_account,
            debit=Decimal("0.00"), credit=Decimal("0.99"),
        )
        JournalEntry.objects.filter(pk=entry.pk).update(status=JournalEntry.POSTED)
        changed = next(
            task for task in finance_work_tasks(self.preparer)["tasks"]
            if task["case_id"] == f"period-close:{run.public_id}"
        )
        self.assertEqual(changed["task_id"], first["task_id"])
        self.assertNotEqual(changed["source_version"], first["source_version"])
        self.assertIn("differ by 0.01", changed["exception"])
        with self.assertRaises(PermissionDenied):
            refresh_period_close_run(
                run, self.outsider,
                adjustment_review_note=run.adjustment_review_note,
                evidence_reference=run.evidence_reference,
            )


class FinanceTreasuryPaymentWorkTaskContractTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="task-payment-accounting",
        )
        cls.treasury = Department.objects.create(
            name="Municipal Treasury Office", slug="task-payment-treasury",
        )
        cls.other = Department.objects.create(
            name="Other Treasury Office", slug="task-payment-other",
        )
        cls.officer = cls._employee(
            "task.payment.officer", cls.treasury,
            "view_voucher_workbench", "issue_payment_instruments", "release_payment_instruments",
        )
        cls.uat = cls._employee(
            "task.payment.uat", cls.treasury,
            "view_voucher_workbench", "issue_payment_instruments", "release_payment_instruments",
        )
        cls.uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        today = timezone.localdate()
        cls.release = FinanceConfigurationRelease.objects.create(
            department=cls.accounting, code="task-payment-release", version=1,
            title="Synthetic Treasury payment task release", fiscal_year=today.year,
            status="active", effective_from=today, created_by=cls.officer,
        )
        cls.party = FinanceParty.objects.create(
            department=cls.accounting, release=cls.release, code="task-payment-payee", version=1,
            display_name="Synthetic Treasury Task Payee", party_type=FinanceParty.SUPPLIER,
            effective_from=today, status="active", created_by=cls.officer,
        )
        FinanceConfigurationItem.objects.create(
            department=cls.accounting, release=cls.release, category="bank_account",
            code="task-bank", version=1, label="Synthetic Treasury task bank",
            status="active", effective_from=today, created_by=cls.officer,
        )
        cls.claimant = FinancePartyClaimant.objects.create(
            party=cls.party, display_name="Synthetic Authorized Claimant",
            relationship="Authorized representative", valid_from=today,
            status="active", created_by=cls.officer,
        )

    @classmethod
    def _employee(cls, username, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="payment-task-test",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers", codename__in=permissions,
        ))
        return get_user_model().objects.get(pk=user.pk)

    def _case(self, reference, *, stage=VoucherCase.TREASURY_CHECK_PREPARATION, current=None):
        item = VoucherCase.objects.create(
            reference_code=reference, requesting_department=self.other,
            current_department=current or self.treasury,
            configuration_release=self.release, payee=self.party,
            payee_name=self.party.display_name,
            particulars="Controlled Treasury payment task fixture.",
            authoritative_obligation_number=f"OBR-{reference}",
            authoritative_obligation_amount=Decimal("100.00"),
            obligation_binding_status=VoucherCase.BINDING_LINKED,
            current_stage=stage, created_by=self.officer,
        )
        obligation = BudgetObligation.objects.create(
            case=item, obr_number=f"OBR-{reference}", obligation_date=timezone.localdate(),
            budget_source_reference="Synthetic retained appropriation evidence.",
            certified_amount=Decimal("100.00"), certified_by=self.officer,
            certified_at=timezone.now(),
        )
        BudgetAllocationLine.objects.create(
            obligation=obligation, fund_code="general-fund",
            responsibility_center_code="task-treasury", account_code="5-02-03",
            amount=Decimal("100.00"),
        )
        DisbursementVoucher.objects.create(
            case=item, dv_number=f"DV-{reference}", voucher_date=timezone.localdate(),
            gross_amount=Decimal("100.00"), total_deductions=Decimal("10.00"),
            net_amount=Decimal("90.00"), prepared_by=self.officer,
            prepared_at=timezone.now(),
        )
        return item

    def _acknowledged_instrument(self, item, *, check_number="TASK-CHK-001"):
        advice = BankAdviceBatch.objects.create(
            advice_number=f"ADV-{item.reference_code}", advice_date=timezone.localdate(),
            bank_account_code="task-bank", status=BankAdviceBatch.ACKNOWLEDGED,
            configuration_release=self.release, accounting_department=self.accounting,
            preparation_note="Synthetic reconciled advice.", authority_reference="Synthetic authority.",
            local_applicability_note="Synthetic local acceptance only.", item_count=1,
            total_amount=Decimal("90.00"), snapshot_checksum="a" * 64,
            created_by=self.officer, acknowledged_by=self.officer,
            acknowledged_at=timezone.now(), acknowledgement_reference="TASK-BANK-ACK",
            acknowledgement_evidence_reference="Synthetic retained bank acknowledgement.",
        )
        return PaymentInstrument.objects.create(
            case=item, bank_account_code="task-bank", fund_code="general-fund",
            check_number=check_number, amount=Decimal("90.00"),
            status=PaymentInstrument.ADVISED, operational_status=PaymentInstrument.NORMAL,
            issued_by=self.officer, issued_at=timezone.now(), current_advice_batch=advice,
        )

    def test_check_preparation_source_workspace_and_exact_task_share_current_office_scope(self):
        ready = self._case("PAYMENT-TASK-READY")
        self._case("PAYMENT-TASK-WRONG-OFFICE", current=self.other)

        source, _selected, _spec = treasury_payment_action_queryset(
            self.officer, "check_preparation",
        )
        workspace_source, *_filters = apply_case_filters(
            visible_cases_for_user(self.officer),
            actionable_stages=(VoucherCase.TREASURY_CHECK_PREPARATION,),
            attention="ready_for_me", actor=self.officer,
        )
        tasks = [
            task for task in finance_work_tasks(self.officer)["tasks"]
            if task["task_type"] == "finance.treasury-payment.check-preparation.v1"
        ]
        self.assertEqual(set(source), {ready})
        self.assertEqual(set(workspace_source), {ready})
        self.assertEqual(len(tasks), 1)
        self.assertIn("exact remaining net is 90.00", tasks[0]["action"])
        self.assertIsNone(tasks[0]["due_on"])

        PaymentInstrument.objects.create(
            case=ready, bank_account_code="task-bank", fund_code="general-fund",
            check_number="TASK-CHK-PREP", amount=Decimal("90.00"),
            status=PaymentInstrument.ISSUED, issued_by=self.officer, issued_at=timezone.now(),
        )
        changed = next(
            task for task in finance_work_tasks(self.officer)["tasks"]
            if task["case_id"] == f"voucher-case:{ready.public_id}"
        )
        self.assertEqual(changed["task_id"], tasks[0]["task_id"])
        self.assertNotEqual(changed["source_version"], tasks[0]["source_version"])
        self.assertIn("submit this case to Accounting bank advice", changed["action"])

    def test_release_projects_one_task_per_check_and_bank_claimant_controls(self):
        item = self._case("PAYMENT-TASK-RELEASE", stage=VoucherCase.TREASURY_RELEASE)
        instrument = self._acknowledged_instrument(item)
        source, _selected, _spec = treasury_payment_action_queryset(self.officer, "release")
        tasks = [
            task for task in finance_work_tasks(self.officer)["tasks"]
            if task["task_type"] == "finance.treasury-payment.instrument-release.v1"
        ]
        self.assertEqual(set(source), {item})
        self.assertEqual(len(tasks), 1)
        self.assertIn(str(instrument.public_id), tasks[0]["task_id"])
        self.assertEqual(tasks[0]["state"], "Ready")

        instrument.current_advice_batch.status = BankAdviceBatch.SUBMITTED
        instrument.current_advice_batch.save(update_fields=("status",))
        blocked = next(
            task for task in finance_work_tasks(self.officer)["tasks"]
            if str(instrument.public_id) in task["task_id"]
        )
        self.assertEqual(blocked["state"], "Exception")
        self.assertIn("not acknowledged", blocked["exception"])

    def test_service_boundary_rejects_wrong_office_invalid_amount_and_invalid_release_evidence(self):
        wrong_office = self._case("PAYMENT-TASK-SERVICE-OFFICE", current=self.other)
        with self.assertRaises(PermissionDenied):
            issue_check(
                case=wrong_office, actor=self.officer, bank_account_code="task-bank",
                check_number="TASK-DENIED", amount=Decimal("1.00"),
                expected_version=wrong_office.state_version, idempotency_key="payment-wrong-office",
            )

        preparation = self._case("PAYMENT-TASK-SERVICE-AMOUNT")
        with self.assertRaisesMessage(VoucherWorkflowError, "positive amount"):
            issue_check(
                case=preparation, actor=self.officer, bank_account_code="task-bank",
                check_number="TASK-ZERO", amount=Decimal("0.00"),
                expected_version=preparation.state_version, idempotency_key="payment-zero",
            )
        wrong_stage = self._case(
            "PAYMENT-TASK-WRONG-STAGE", stage=VoucherCase.ACCOUNTING_BANK_ADVICE,
        )
        with self.assertRaisesMessage(VoucherWorkflowError, "currently assigned Treasury"):
            submit_checks_for_advice(
                case=wrong_stage, actor=self.officer,
                expected_version=wrong_stage.state_version, idempotency_key="payment-wrong-stage",
            )

        release_case = self._case("PAYMENT-TASK-SERVICE-RELEASE", stage=VoucherCase.TREASURY_RELEASE)
        instrument = self._acknowledged_instrument(release_case, check_number="TASK-CHK-RELEASE")
        expired = FinancePartyClaimant.objects.create(
            party=self.party, display_name="Expired Synthetic Claimant",
            valid_from=timezone.localdate() - timedelta(days=10),
            valid_to=timezone.localdate() - timedelta(days=1), status="active",
            created_by=self.officer,
        )
        with self.assertRaisesMessage(VoucherWorkflowError, "active authorized claimant"):
            release_check(
                case=release_case, instrument=instrument, actor=self.officer,
                claimant=expired, receipt_reference="TASK-RECEIPT",
                expected_version=release_case.state_version, idempotency_key="payment-expired-claimant",
            )
        with self.assertRaisesMessage(VoucherWorkflowError, "actual claimant receipt"):
            release_check(
                case=release_case, instrument=instrument, actor=self.officer,
                claimant=self.claimant, receipt_reference="",
                expected_version=release_case.state_version, idempotency_key="payment-empty-receipt",
            )

    def test_uat_account_receives_no_treasury_payment_actions(self):
        self._case("PAYMENT-TASK-UAT")
        self.assertFalse(treasury_payment_action_queryset(self.uat, "check_preparation")[0].exists())
        self.assertFalse(any(
            task["task_type"].startswith("finance.treasury-payment.")
            for task in finance_work_tasks(self.uat)["tasks"]
        ))

    def test_missing_pinned_setup_is_a_visible_stop_and_service_boundary(self):
        item = self._case("PAYMENT-TASK-MISSING-SETUP")
        VoucherCase.objects.filter(pk=item.pk).update(configuration_release=None)
        item.refresh_from_db()

        task = next(
            task for task in finance_work_tasks(self.officer)["tasks"]
            if task["case_id"] == f"voucher-case:{item.public_id}"
        )
        self.assertEqual(task["state"], "Exception")
        self.assertIn("No governed Finance Setup release is pinned", task["exception"])
        with self.assertRaisesMessage(VoucherWorkflowError, "no pinned Finance Setup release"):
            issue_check(
                case=item, actor=self.officer, bank_account_code="task-bank",
                check_number="TASK-NO-SETUP", amount=Decimal("90.00"),
                expected_version=item.state_version, idempotency_key="payment-no-setup",
            )
