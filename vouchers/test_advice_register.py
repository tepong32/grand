from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from profiles.models import EmployeeProfile

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
