from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from finance.models import FinanceConfigurationRelease
from profiles.models import EmployeeProfile

from .models import TreasuryCashPolicy, TreasuryCashPosition


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
