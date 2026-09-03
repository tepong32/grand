from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from reporting.models import FinanceLocalFormAcceptance
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP

from .models import FinanceShadowCycle
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
        cls.uat = cls._employee("task.contract.uat", cls.accounting)
        cls._grant(
            cls.worker,
            "finance.view_finance_setup",
            "finance.manage_shadow_operation",
            "reporting.manage_local_form_acceptance",
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

    def _cycle(self):
        today = timezone.localdate()
        return FinanceShadowCycle.objects.create(
            department=self.accounting,
            code="task-cycle",
            title="Controlled parallel-run checkpoint",
            fiscal_year=today.year,
            run_kind=FinanceShadowCycle.PARALLEL,
            enabled_scope="Synthetic Accounting fund and disbursement scope.",
            source_extract_reference="Redacted retained register TC-1.",
            source_checksum="1" * 64,
            source_schema_signature="2" * 64,
            planned_start=today - timedelta(days=5),
            planned_end=today - timedelta(days=1),
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
