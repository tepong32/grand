from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from profiles.models import EmployeeProfile

from finance.work_tasks import finance_work_tasks

from .models import BankAdviceBatch


class BankAdviceRegisterAttentionTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(name="Accounting Office", slug="advice-register-accounting")
        cls.other = Department.objects.create(name="Other Accounting Office", slug="advice-register-other")
        cls.user = get_user_model().objects.create_user(username="advice.register", password="test-password")
        profile, _created = EmployeeProfile.objects.get_or_create(user=cls.user)
        profile.assigned_department = cls.accounting
        profile.save(update_fields=("assigned_department",))
        cls.user = get_user_model().objects.get(pk=cls.user.pk)
        cls.user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers",
            codename__in=("view_bank_advice", "prepare_bank_advice"),
        ))
        cls.draft = cls._batch("ADV-DRAFT", cls.accounting, cls.user, BankAdviceBatch.DRAFT)
        cls.returned = cls._batch("ADV-RETURNED", cls.accounting, cls.user, BankAdviceBatch.RETURNED)
        cls.approved = cls._batch("ADV-APPROVED", cls.accounting, cls.user, BankAdviceBatch.APPROVED)
        cls.hidden = cls._batch("ADV-HIDDEN", cls.other, cls.user, BankAdviceBatch.DRAFT)

    @staticmethod
    def _batch(number, department, user, status):
        return BankAdviceBatch.objects.create(
            advice_number=number,
            advice_date=date(2026, 9, 3),
            bank_account_code="GF-LBP",
            status=status,
            accounting_department=department,
            total_amount=Decimal("100.00"),
            created_by=user,
        )

    def test_source_attention_filter_is_exact_and_department_scoped(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vouchers:advice_workspace"), {"attention": "needs_preparation"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_attention"], "needs_preparation")
        self.assertEqual(response.context["visible_count"], 2)
        self.assertEqual(
            set(response.context["batches"].values_list("pk", flat=True)),
            {self.draft.pk, self.returned.pk},
        )
        self.assertContains(response, "These filters change only the visible source register")

    def test_my_work_count_and_link_match_the_source_register(self):
        self.client.force_login(self.user)

        work = self.client.get(reverse("finance_operations:my_work"))
        source = self.client.get(
            reverse("vouchers:advice_workspace"), {"attention": "needs_preparation"},
        )

        self.assertEqual(work.status_code, 200)
        group = next(item for item in work.context["groups"] if item["key"] == "bank-advice-preparation")
        self.assertEqual(group["count"], source.context["visible_count"])
        self.assertEqual(group["count"], 2)
        self.assertEqual(
            group["url"],
            f'{reverse("vouchers:advice_workspace")}?attention=needs_preparation',
        )
        self.assertNotContains(work, "ADV-HIDDEN")

    def test_exact_preparation_tasks_are_stable_source_linked_and_office_scoped(self):
        first = finance_work_tasks(self.user)
        second = finance_work_tasks(self.user)
        tasks = [task for task in first["tasks"] if task["area"] == "Bank advice"]

        self.assertEqual(len(tasks), 2)
        self.assertEqual(
            [task["task_id"] for task in tasks],
            [task["task_id"] for task in second["tasks"] if task["area"] == "Bank advice"],
        )
        self.assertTrue(all(task["source_version"].startswith("projection-sha256:") for task in tasks))
        self.assertTrue(all(task["due_state"] == "No structured target" for task in tasks))
        self.assertFalse(any(str(self.hidden.public_id) in task["task_id"] for task in tasks))

        draft_task = next(task for task in tasks if str(self.draft.public_id) in task["task_id"])
        prior_version = draft_task["source_version"]
        self.draft.preparation_note = "Updated draft preparation evidence."
        self.draft.save(update_fields=("preparation_note",))
        changed = next(
            task for task in finance_work_tasks(self.user)["tasks"]
            if str(self.draft.public_id) in task["task_id"]
        )
        self.assertEqual(changed["task_id"], draft_task["task_id"])
        self.assertNotEqual(changed["source_version"], prior_version)

    def test_one_cent_difference_is_a_blocking_task_exception(self):
        self.draft.total_amount = Decimal("0.01")
        self.draft.save(update_fields=("total_amount",))

        task = next(
            task for task in finance_work_tasks(self.user)["tasks"]
            if str(self.draft.public_id) in task["task_id"]
        )

        self.assertEqual(task["state"], "Exception")
        self.assertIn("differs from the advice total by -0.01", task["exception"])
        self.assertIn("must equal exactly zero", task["exception"])

    def test_independent_review_source_count_and_tasks_exclude_the_preparer(self):
        self.user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers",
            codename__in=("approve_bank_advice", "export_bank_advice"),
        ))
        peer = get_user_model().objects.create_user(
            username="advice.peer", email="advice.peer@example.test", password="test-password",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=peer)
        profile.assigned_department = self.accounting
        profile.save(update_fields=("assigned_department",))
        peer_batch = self._batch("ADV-PEER-REVIEW", self.accounting, peer, BankAdviceBatch.FOR_REVIEW)
        peer_batch.review_submitted_by = peer
        peer_batch.save(update_fields=("review_submitted_by",))
        self_batch = self._batch("ADV-SELF-REVIEW", self.accounting, self.user, BankAdviceBatch.FOR_REVIEW)
        self_batch.review_submitted_by = self.user
        self_batch.save(update_fields=("review_submitted_by",))
        self.client.force_login(self.user)

        source = self.client.get(
            reverse("vouchers:advice_workspace"), {"attention": "awaiting_review"},
        )
        review_tasks = [
            task for task in finance_work_tasks(self.user)["tasks"]
            if task["task_type"] == "finance.bank-advice.awaiting_review.v1"
        ]

        self.assertEqual(source.context["visible_count"], 1)
        self.assertEqual(list(source.context["batches"]), [peer_batch])
        self.assertEqual(len(review_tasks), 1)
        self.assertIn(str(peer_batch.public_id), review_tasks[0]["task_id"])
        self.assertNotIn(str(self_batch.public_id), review_tasks[0]["task_id"])

        exported = self.client.get(
            reverse("vouchers:advice_export"), {"attention": "awaiting_review"},
        )
        content = exported.content.decode("utf-8-sig")
        self.assertEqual(exported.status_code, 200)
        self.assertIn(str(peer_batch.public_id), content)
        self.assertNotIn(str(self_batch.public_id), content)

    def test_uat_preview_never_receives_bank_advice_actions(self):
        self.user.groups.add(Group.objects.create(name="Finance UAT Viewer"))
        self.client.force_login(self.user)

        source = self.client.get(reverse("vouchers:advice_workspace"))
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(source.context["attention_choices"], ())
        self.assertFalse(any(task["area"] == "Bank advice" for task in work.context["tasks"]))
        self.assertFalse(any(group["area"] == "Bank advice" for group in work.context["groups"]))
