from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from finance.models import FinanceConfigurationRelease
from finance.work_tasks import finance_work_tasks
from profiles.models import EmployeeProfile

from .cash_register import cash_attention_queryset
from .models import TreasuryCashPolicy, TreasuryCashPosition
from .roles import FINANCE_UAT_VIEWER_GROUP


class CashWorkRegisterTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.treasury = Department.objects.create(name="Municipal Treasury Office", slug="cash-register-treasury")
        cls.other = Department.objects.create(name="Other Treasury Office", slug="cash-register-other")
        cls.user = get_user_model().objects.create_user(username="cash.register", password="test-password")
        profile, _created = EmployeeProfile.objects.get_or_create(user=cls.user)
        profile.assigned_department = cls.treasury
        profile.save(update_fields=("assigned_department",))
        cls.user = get_user_model().objects.get(pk=cls.user.pk)
        cls.user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers",
            codename__in=("view_voucher_workbench", "view_cash_position", "prepare_cash_position"),
        ))
        cls.reviewer = get_user_model().objects.create_user(
            username="cash.reviewer", email="cash.reviewer@example.test", password="test-password",
        )
        reviewer_profile, _created = EmployeeProfile.objects.get_or_create(user=cls.reviewer)
        reviewer_profile.assigned_department = cls.other
        reviewer_profile.save(update_fields=("assigned_department",))
        cls.reviewer = get_user_model().objects.get(pk=cls.reviewer.pk)
        cls.reviewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers",
            codename__in=("view_voucher_workbench", "view_cash_position", "approve_cash_position"),
        ))
        cls.release = cls._release("cash-own", cls.treasury, cls.user)
        cls.other_release = cls._release("cash-other", cls.other, cls.user)
        cls.draft_policy = cls._policy(cls.release, cls.treasury, cls.user, TreasuryCashPolicy.DRAFT, 1)
        cls.returned_policy = cls._policy(cls.release, cls.treasury, cls.user, TreasuryCashPolicy.RETURNED, 2)
        cls.active_policy = cls._policy(cls.release, cls.treasury, cls.user, TreasuryCashPolicy.ACTIVE, 3)
        cls.hidden_policy = cls._policy(cls.other_release, cls.other, cls.user, TreasuryCashPolicy.DRAFT, 1)
        cls.review_policy = cls._policy(cls.release, cls.treasury, cls.user, TreasuryCashPolicy.FOR_REVIEW, 4)
        cls.other_review_policy = cls._policy(
            cls.other_release, cls.other, cls.user, TreasuryCashPolicy.FOR_REVIEW, 2,
        )
        cls.draft_position = cls._position(cls.active_policy, cls.user, TreasuryCashPosition.DRAFT, 1)
        cls.returned_position = cls._position(cls.active_policy, cls.user, TreasuryCashPosition.RETURNED, 2)
        cls.approved_position = cls._position(cls.active_policy, cls.user, TreasuryCashPosition.APPROVED, 3)
        cls.review_position = cls._position(cls.active_policy, cls.user, TreasuryCashPosition.FOR_REVIEW, 4)
        cls.other_review_position = cls._position(
            cls.other_review_policy, cls.user, TreasuryCashPosition.FOR_REVIEW, 1,
        )

    @staticmethod
    def _release(code, department, user):
        return FinanceConfigurationRelease.objects.create(
            department=department,
            code=code,
            title=f"{department.name} cash controls",
            fiscal_year=2026,
            status="active",
            effective_from=date(2026, 1, 1),
            created_by=user,
        )

    @staticmethod
    def _policy(release, department, user, status, version):
        return TreasuryCashPolicy.objects.create(
            configuration_release=release,
            treasury_department=department,
            bank_account_code="GF-LBP",
            fund_code="GF",
            mode=TreasuryCashPolicy.OBSERVE,
            minimum_reserve=Decimal("100.00"),
            position_max_age_days=35,
            unclaimed_after_days=30,
            stale_after_days=180,
            effective_from=date(2026, 1, 1),
            authority_reference="Synthetic reviewed authority.",
            local_applicability_note="Synthetic local acceptance fixture.",
            status=status,
            version=version,
            created_by=user,
        )

    @staticmethod
    def _position(policy, user, status, version):
        return TreasuryCashPosition.objects.create(
            policy=policy,
            as_of_date=date(2026, 9, 1),
            reconciliation_public_id=uuid4(),
            reconciliation_checksum=f"checksum-{version}",
            reconciliation_period_end=date(2026, 8, 31),
            reconciled_book_balance=Decimal("1000.00"),
            confirmed_inflows=Decimal("100.00"),
            confirmed_outflows=Decimal("50.00"),
            other_holds=Decimal("25.00"),
            evidence_reference="Synthetic cash schedule.",
            status=status,
            version=version,
            created_by=user,
        )

    def test_source_register_counts_policy_records_without_mixing_positions(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("vouchers:cash_workspace"), {"attention": "policy_needs_preparation"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cash_work_spec"]["kind"], "policy")
        self.assertEqual(response.context["cash_work_count"], 2)
        self.assertEqual(
            set(response.context["cash_work_items"].values_list("pk", flat=True)),
            {self.draft_policy.pk, self.returned_policy.pk},
        )
        self.assertNotContains(response, "counts actual records rather than mixing two kinds of work")
        self.assertContains(response, "This list does not assign, submit, approve, or alter any record")

    def test_position_source_and_my_work_counts_are_identical(self):
        self.client.force_login(self.user)

        source = self.client.get(
            reverse("vouchers:cash_workspace"), {"attention": "position_needs_preparation"},
        )
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.context["cash_work_spec"]["kind"], "position")
        self.assertEqual(source.context["cash_work_count"], 2)
        self.assertEqual(
            set(source.context["cash_work_items"].values_list("pk", flat=True)),
            {self.draft_position.pk, self.returned_position.pk},
        )
        group = next(item for item in work.context["groups"] if item["key"] == "cash-position-preparation")
        self.assertEqual(group["count"], source.context["cash_work_count"])
        self.assertEqual(
            group["url"],
            f'{reverse("vouchers:cash_workspace")}?attention=position_needs_preparation',
        )

    def test_independent_reviewer_source_and_my_work_cover_permitted_cross_office_records(self):
        self.client.force_login(self.reviewer)

        source = self.client.get(
            reverse("vouchers:cash_workspace"), {"attention": "position_awaiting_review"},
        )
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.context["cash_work_count"], 2)
        self.assertEqual(
            set(source.context["cash_work_items"].values_list("pk", flat=True)),
            {self.review_position.pk, self.other_review_position.pk},
        )
        group = next(item for item in work.context["groups"] if item["key"] == "cash-position-review")
        self.assertEqual(group["count"], source.context["cash_work_count"])
        self.assertEqual(group["scope"], "Permitted cross-office cash-control register")

    def test_exact_cash_tasks_preserve_source_count_and_show_the_control_equation(self):
        policy_source, _selected, _spec = cash_attention_queryset(
            self.user, "policy_needs_preparation",
        )
        position_source, _selected, _spec = cash_attention_queryset(
            self.user, "position_needs_preparation",
        )
        tasks = finance_work_tasks(self.user)["tasks"]
        policy_tasks = [
            row for row in tasks
            if row["task_type"] == "finance.treasury-cash-policy.policy_needs_preparation.v1"
        ]
        position_tasks = [
            row for row in tasks
            if row["task_type"] == "finance.treasury-cash-position.position_needs_preparation.v1"
        ]

        self.assertEqual(len(policy_tasks), policy_source.count())
        self.assertEqual(len(position_tasks), position_source.count())
        draft = next(
            row for row in position_tasks
            if row["case_id"] == f"treasury-cash-position:{self.draft_position.public_id}"
        )
        self.assertIn("1000.00 + 100.00 - 50.00 - 25.00 - 100.00 = 925.00", draft["subject"])
        self.assertIn("Accounting fund is not active", draft["exception"])
        returned = next(
            row for row in policy_tasks
            if row["case_id"] == f"treasury-cash-policy:{self.returned_policy.public_id}"
        )
        self.assertEqual(returned["state"], "Returned")
        self.assertIn("reasoned successor policy version", returned["action"])

        original = next(
            row for row in policy_tasks
            if row["case_id"] == f"treasury-cash-policy:{self.draft_policy.public_id}"
        )
        self.draft_policy.minimum_reserve = Decimal("101.00")
        self.draft_policy.save(update_fields=("minimum_reserve",))
        changed = next(
            row for row in finance_work_tasks(self.user)["tasks"]
            if row["case_id"] == original["case_id"]
        )
        self.assertEqual(changed["task_id"], original["task_id"])
        self.assertNotEqual(changed["source_version"], original["source_version"])

    def test_combined_role_does_not_receive_own_review_or_other_office_preparation(self):
        self.user.user_permissions.add(Permission.objects.get(
            content_type__app_label="vouchers", codename="approve_cash_position",
        ))

        self.assertEqual(
            set(cash_attention_queryset(self.user, "policy_needs_preparation")[0]),
            {self.draft_policy, self.returned_policy},
        )
        self.assertFalse(cash_attention_queryset(self.user, "policy_awaiting_review")[0].exists())
        self.assertFalse(cash_attention_queryset(self.user, "position_awaiting_review")[0].exists())

    def test_uat_account_has_no_exact_cash_actions(self):
        uat = get_user_model().objects.create_user(
            username="cash.register.uat", email="cash.register.uat@example.test",
            password="test-password",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=uat)
        profile.assigned_department = self.treasury
        profile.save(update_fields=("assigned_department",))
        uat.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers",
            codename__in=("view_cash_position", "prepare_cash_position", "approve_cash_position"),
        ))
        uat.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])

        self.assertFalse(cash_attention_queryset(uat, "policy_needs_preparation")[0].exists())
        self.assertFalse(any(
            row["task_type"].startswith("finance.treasury-cash-")
            for row in finance_work_tasks(uat)["tasks"]
        ))

    def test_review_and_returned_cash_evidence_requires_a_successor_not_rewrite(self):
        self.review_policy.minimum_reserve = Decimal("101.00")
        with self.assertRaisesMessage(ValidationError, "immutable"):
            self.review_policy.save()
        self.returned_policy.minimum_reserve = Decimal("102.00")
        with self.assertRaisesMessage(ValidationError, "immutable"):
            self.returned_policy.save()
        self.review_position.confirmed_inflows = Decimal("101.00")
        with self.assertRaisesMessage(ValidationError, "immutable"):
            self.review_position.save()
        self.returned_position.confirmed_inflows = Decimal("102.00")
        with self.assertRaisesMessage(ValidationError, "immutable"):
            self.returned_position.save()

    def test_reasoned_successor_replaces_returned_item_in_preparation_queue(self):
        successor_policy = self._policy(
            self.release, self.treasury, self.user, TreasuryCashPolicy.DRAFT, 5,
        )
        successor_policy.supersedes = self.returned_policy
        successor_policy.save(update_fields=("supersedes",))
        successor_position = self._position(
            self.active_policy, self.user, TreasuryCashPosition.DRAFT, 5,
        )
        successor_position.supersedes = self.returned_position
        successor_position.save(update_fields=("supersedes",))

        policies = cash_attention_queryset(self.user, "policy_needs_preparation")[0]
        positions = cash_attention_queryset(self.user, "position_needs_preparation")[0]
        self.assertIn(successor_policy, policies)
        self.assertNotIn(self.returned_policy, policies)
        self.assertIn(successor_position, positions)
        self.assertNotIn(self.returned_position, positions)
