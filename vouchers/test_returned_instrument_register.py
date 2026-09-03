from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from finance.models import FinanceConfigurationRelease
from profiles.models import EmployeeProfile

from .models import (
    PaymentInstrument, PaymentInstrumentException, ReturnedInstrumentReview,
    TreasuryCashPolicy, VoucherCase,
)


class ReturnedInstrumentWorkRegisterTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(name="Accounting Office", slug="returned-register-accounting")
        cls.other_accounting = Department.objects.create(
            name="Other Accounting Office", slug="returned-register-other-accounting",
        )
        cls.treasury = Department.objects.create(name="Treasury Office", slug="returned-register-treasury")
        cls.other_treasury = Department.objects.create(
            name="Other Treasury Office", slug="returned-register-other-treasury",
        )
        cls.requesting = Department.objects.create(name="Requesting Office", slug="returned-register-requesting")

        cls.reviewer = cls._user(
            "returned.reviewer", "returned.reviewer@example.test", cls.accounting,
            "view_voucher_workbench", "view_bank_advice", "review_returned_instruments",
        )
        cls.treasury_user = cls._user(
            "returned.treasury", "returned.treasury@example.test", cls.treasury,
            "view_voucher_workbench", "view_bank_advice", "manage_payment_exceptions",
            "issue_payment_instruments",
        )
        cls.accounting_release = cls._release("RETURNED-ACCT", cls.accounting, cls.reviewer)
        cls.other_accounting_release = cls._release(
            "RETURNED-OTHER-ACCT", cls.other_accounting, cls.reviewer,
        )
        cls.treasury_policy = cls._policy(cls.accounting_release, cls.treasury, cls.treasury_user, "TR")
        cls.other_treasury_policy = cls._policy(
            cls.other_accounting_release, cls.other_treasury, cls.treasury_user, "OTHER-TR",
        )

        cls.accounting_review = cls._review(
            "RET-ACCT", cls.accounting_release, cls.treasury_policy,
            ReturnedInstrumentReview.AWAITING_REVIEW, cls.treasury_user,
        )
        cls.hidden_accounting_review = cls._review(
            "RET-HIDDEN-ACCT", cls.other_accounting_release, cls.other_treasury_policy,
            ReturnedInstrumentReview.AWAITING_REVIEW, cls.treasury_user,
        )
        cls.treasury_clarification = cls._review(
            "RET-CLARIFY", cls.accounting_release, cls.treasury_policy,
            ReturnedInstrumentReview.RETURNED_FOR_CLARIFICATION, cls.treasury_user,
        )
        cls.hidden_treasury_clarification = cls._review(
            "RET-HIDDEN-TR", cls.other_accounting_release, cls.other_treasury_policy,
            ReturnedInstrumentReview.RETURNED_FOR_CLARIFICATION, cls.treasury_user,
        )
        cls.treasury_replacement = cls._review(
            "RET-REPLACE", cls.accounting_release, cls.treasury_policy,
            ReturnedInstrumentReview.READY_FOR_TREASURY, cls.treasury_user,
            outcome=ReturnedInstrumentReview.REISSUE,
        )

    @staticmethod
    def _user(username, email, department, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=email, password="test-password",
        )
        profile, _created = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        user = get_user_model().objects.get(pk=user.pk)
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers", codename__in=permissions,
        ))
        return user

    @staticmethod
    def _release(code, department, user):
        return FinanceConfigurationRelease.objects.create(
            department=department, code=code, title=f"{department.name} returned-payment controls",
            fiscal_year=2026, status="active", effective_from=date(2026, 1, 1), created_by=user,
        )

    @staticmethod
    def _policy(release, treasury_department, user, bank_code):
        return TreasuryCashPolicy.objects.create(
            configuration_release=release, treasury_department=treasury_department,
            bank_account_code=bank_code, fund_code="GF", mode=TreasuryCashPolicy.OBSERVE,
            minimum_reserve=Decimal("0.00"), position_max_age_days=35,
            unclaimed_after_days=30, stale_after_days=180, effective_from=date(2026, 1, 1),
            authority_reference="Synthetic reviewed authority.",
            local_applicability_note="Synthetic local acceptance fixture.",
            status=TreasuryCashPolicy.ACTIVE, created_by=user,
        )

    @classmethod
    def _review(cls, reference, release, policy, status, user, outcome=""):
        stage = (
            VoucherCase.TREASURY_CHECK_PREPARATION
            if status == ReturnedInstrumentReview.READY_FOR_TREASURY
            else VoucherCase.ACCOUNTING_RETURNED_ITEM
        )
        case = VoucherCase.objects.create(
            reference_code=reference, requesting_department=cls.requesting,
            current_department=release.department, configuration_release=release,
            payee_name="Synthetic payee", particulars="Synthetic returned-payment fixture",
            authoritative_obligation_amount=Decimal("100.00"), current_stage=stage, created_by=user,
        )
        instrument = PaymentInstrument.objects.create(
            case=case, bank_account_code=policy.bank_account_code, fund_code="GF",
            check_number=f"CHK-{reference}", amount=Decimal("100.00"),
            status=PaymentInstrument.BANK_RETURNED,
            operational_status=PaymentInstrument.RETURNED, issued_by=user,
        )
        exception = PaymentInstrumentException.objects.create(
            instrument=instrument, policy=policy, kind=PaymentInstrumentException.RETURNED,
            observed_on=date(2026, 9, 3), reason="Synthetic bank return.",
            evidence_reference="Synthetic bank-return evidence.", opened_by=user,
        )
        return ReturnedInstrumentReview.objects.create(
            exception=exception, case=case, instrument=instrument, status=status, outcome=outcome,
            treasury_evidence_reference="Synthetic Treasury evidence.",
            treasury_note="Synthetic Treasury note.", prepared_by=user,
        )

    def test_accounting_review_source_and_my_work_are_exact_and_office_scoped(self):
        self.client.force_login(self.reviewer)

        source = self.client.get(
            reverse("vouchers:advice_workspace"), {"returned_attention": "accounting_review"},
        )
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.context["returned_visible_count"], 1)
        self.assertEqual(list(source.context["returned_reviews"]), [self.accounting_review])
        group = next(
            item for item in work.context["groups"]
            if item["key"] == "returned-instrument-accounting-review"
        )
        self.assertEqual(group["count"], source.context["returned_visible_count"])
        self.assertEqual(
            group["url"],
            f'{reverse("vouchers:advice_workspace")}?returned_attention=accounting_review',
        )
        self.assertNotContains(source, "CHK-RET-HIDDEN-ACCT")

    def test_treasury_clarification_and_replacement_remain_separate_exact_queues(self):
        self.client.force_login(self.treasury_user)

        clarification = self.client.get(
            reverse("vouchers:advice_workspace"), {"returned_attention": "treasury_clarification"},
        )
        replacement = self.client.get(
            reverse("vouchers:advice_workspace"), {"returned_attention": "treasury_replacement"},
        )
        work = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(clarification.context["returned_visible_count"], 1)
        self.assertEqual(list(clarification.context["returned_reviews"]), [self.treasury_clarification])
        self.assertContains(clarification, "Create clarified successor")
        self.assertNotContains(clarification, "Returned payments awaiting Accounting decision")
        self.assertNotContains(clarification, "CHK-RET-HIDDEN-TR")
        self.assertEqual(replacement.context["returned_visible_count"], 1)
        self.assertEqual(list(replacement.context["returned_reviews"]), [self.treasury_replacement])
        clarification_group = next(
            item for item in work.context["groups"]
            if item["key"] == "returned-instrument-treasury-clarification"
        )
        replacement_group = next(
            item for item in work.context["groups"]
            if item["key"] == "returned-instrument-treasury-replacement"
        )
        self.assertEqual(clarification_group["count"], 1)
        self.assertEqual(replacement_group["count"], 1)
