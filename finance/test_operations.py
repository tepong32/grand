from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from departments.services.internal_howto_seed import seed_finance_internal_howtos
from profiles.models import EmployeeProfile
from vouchers.models import VoucherCase
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP


class FinanceOperationsEntryTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(
            name="Municipal Accounting Office", slug="accounting-operations-entry",
        )
        cls.general_services = Department.objects.create(
            name="General Services Office", slug="gso-operations-entry",
        )
        cls.finance_user = cls._employee("finance.entry", cls.accounting)
        cls.reporting_only_user = cls._employee("reports.only", cls.general_services)
        cls.voucher_only_user = cls._employee("voucher.only", cls.general_services)
        cls.no_access_user = cls._employee("ordinary.employee", cls.general_services)
        cls.uat_user = cls._employee("finance.uat", cls.accounting)
        cls._grant(
            cls.finance_user,
            "finance.view_finance_setup",
            "budget.view_budget_workspace",
            "vouchers.view_voucher_workbench",
            "accounting.view_accounting_workspace",
            "reporting.view_reporting_workspace",
        )
        cls._grant(cls.reporting_only_user, "reporting.view_reporting_workspace")
        cls._grant(
            cls.voucher_only_user,
            "vouchers.view_voucher_workbench",
            "vouchers.initiate_payable_case",
        )
        cls._grant(cls.uat_user, "vouchers.view_voucher_workbench")
        cls.uat_user.groups.add(Group.objects.create(name=FINANCE_UAT_VIEWER_GROUP))

    @classmethod
    def _employee(cls, username, department):
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="finance-entry-test-password",
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
                content_type__app_label=app_label,
                codename=codename,
            ))

    def test_entry_shows_all_existing_finance_destinations_and_keeps_routes_stable(self):
        self.client.force_login(self.finance_user)

        response = self.client.get(reverse("finance_operations:overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finance operations")
        self.assertContains(response, "One entry point, existing controls")
        self.assertContains(response, reverse("budget:obligation_workspace"))
        self.assertContains(response, reverse("vouchers:workspace"))
        self.assertContains(response, reverse("accounting:workspace"))
        self.assertContains(response, reverse("reporting:workspace"))
        self.assertContains(response, reverse("finance:workspace"))
        self.assertContains(response, "Find a shared Finance case")
        self.assertContains(response, reverse("finance_operations:my_work"))
        self.assertContains(response, 'action="/finance/vouchers/"')
        self.assertContains(response, "Hidden cases do not affect results")
        self.assertContains(response, "Open Decisions")
        self.assertContains(response, "Open Field operations")
        self.assertContains(response, "Personal tutorial checkmarks")
        self.assertEqual(reverse("finance_operations:overview"), "/finance/")
        self.assertEqual(reverse("finance_operations:my_work"), "/finance/my-work/")
        self.assertEqual(reverse("finance:workspace"), "/finance/setup/")
        self.assertEqual(reverse("vouchers:workspace"), "/finance/vouchers/")
        self.assertEqual(reverse("accounting:workspace"), "/finance/accounting/")

    def test_entry_omits_workspaces_not_allowed_to_the_account(self):
        self.client.force_login(self.voucher_only_user)

        response = self.client.get(reverse("finance_operations:overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("vouchers:workspace"))
        self.assertContains(response, "Find a shared Finance case")
        self.assertNotContains(response, reverse("budget:obligation_workspace"))
        self.assertNotContains(response, reverse("accounting:workspace"))
        self.assertNotContains(response, reverse("reporting:workspace"))
        self.assertNotContains(response, reverse("finance:workspace"))
        self.assertNotContains(response, "Open Decisions")
        self.assertNotContains(response, "Open Field operations")

    def test_reporting_permission_alone_does_not_grant_finance_entry(self):
        self.client.force_login(self.reporting_only_user)

        response = self.client.get(reverse("finance_operations:overview"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.client.get(reverse("finance_operations:my_work")).status_code,
            403,
        )
        reporting = self.client.get(reverse("reporting:workspace"))
        self.assertEqual(reporting.status_code, 200)
        self.assertNotContains(reporting, reverse("finance_operations:overview"))

    def test_ordinary_employee_is_denied_and_anonymous_user_is_redirected(self):
        self.client.force_login(self.no_access_user)
        self.assertEqual(
            self.client.get(reverse("finance_operations:overview")).status_code,
            403,
        )
        self.client.logout()
        response = self.client.get(reverse("finance_operations:overview"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_my_work_voucher_count_matches_exact_role_scoped_queue(self):
        VoucherCase.objects.create(
            reference_code="MY-WORK-OWN-001",
            requesting_department=self.general_services,
            current_department=self.general_services,
            payee_name="Visible claimant",
            particulars="Visible requesting-office case",
            authoritative_obligation_amount=Decimal("100.00"),
            current_stage=VoucherCase.PAYABLE_PREPARATION,
            created_by=self.voucher_only_user,
        )
        VoucherCase.objects.create(
            reference_code="MY-WORK-HIDDEN-001",
            requesting_department=self.accounting,
            current_department=self.accounting,
            payee_name="Hidden claimant",
            particulars="Another office case",
            authoritative_obligation_amount=Decimal("200.00"),
            current_stage=VoucherCase.PAYABLE_PREPARATION,
            created_by=self.finance_user,
        )
        self.client.force_login(self.voucher_only_user)

        response = self.client.get(reverse("finance_operations:my_work"))
        queue = self.client.get(reverse("vouchers:workspace"), {"attention": "ready_for_me"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Work needing attention")
        group = next(item for item in response.context["groups"] if item["key"] == "voucher-ready")
        self.assertEqual(group["count"], 1)
        self.assertEqual(group["count"], queue.context["queue_count"])
        self.assertEqual(group["url"], f'{reverse("vouchers:workspace")}?attention=ready_for_me')
        self.assertContains(response, "Current Voucher Workbench role and General Services Office visibility")
        self.assertContains(response, "does not create assignments, approvals, notifications, or a second status")

    def test_uat_preview_stages_are_not_presented_as_personal_actions(self):
        VoucherCase.objects.create(
            reference_code="MY-WORK-UAT-001",
            requesting_department=self.accounting,
            current_department=self.accounting,
            payee_name="UAT example",
            particulars="Preview-only case",
            authoritative_obligation_amount=Decimal("300.00"),
            current_stage=VoucherCase.ACCOUNTING_PREPARATION,
            created_by=self.finance_user,
        )
        self.client.force_login(self.uat_user)

        response = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("voucher-ready", {item["key"] for item in response.context["groups"]})
        self.assertEqual(response.context["action_count"], 0)
        self.assertContains(response, "No supported action group is assigned")

    def test_my_work_has_department_specific_floating_guide(self):
        seed_finance_internal_howtos()
        self.client.force_login(self.voucher_only_user)

        response = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="grand-howto-toggle"')
        self.assertContains(response, "Triage your office&#x27;s Finance work")
        self.assertContains(response, "Relevant here")
        self.assertContains(response, "Read an exact work item when available")
        self.assertContains(response, "Checkmarks are your private learning progress only")

    def test_my_work_permission_shapes_supported_zero_count_groups_and_exact_links(self):
        self._grant(
            self.finance_user,
            "accounting.prepare_journal_entries",
            "accounting.prepare_opening_balances",
            "accounting.prepare_bank_reconciliation",
            "reporting.generate_reports",
            "vouchers.prepare_remittances",
        )
        self.client.force_login(self.finance_user)

        response = self.client.get(reverse("finance_operations:my_work"))

        self.assertEqual(response.status_code, 200)
        groups = {item["key"]: item for item in response.context["groups"]}
        self.assertEqual(groups["journal-preparation"]["url"], "/finance/accounting/?status=draft")
        self.assertEqual(
            groups["opening-submission"]["url"],
            "/finance/accounting/opening/?attention=ready_to_submit",
        )
        self.assertEqual(
            groups["bank-matching"]["url"],
            "/finance/accounting/bank-reconciliation/?attention=needs_matching",
        )
        self.assertEqual(groups["report-generation"]["url"], "/reports/?attention=generation")
        self.assertEqual(groups["report-rerun"]["url"], "/reports/?attention=generation_failed")
        self.assertEqual(
            groups["remittance-preparation"]["url"],
            "/finance/vouchers/remittances/?attention=preparation",
        )
        self.assertEqual(response.context["action_count"], 0)
