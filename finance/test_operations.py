from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from profiles.models import EmployeeProfile


class FinanceOperationsEntryTests(TestCase):
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
        cls._grant(
            cls.finance_user,
            "finance.view_finance_setup",
            "budget.view_budget_workspace",
            "vouchers.view_voucher_workbench",
            "accounting.view_accounting_workspace",
            "reporting.view_reporting_workspace",
        )
        cls._grant(cls.reporting_only_user, "reporting.view_reporting_workspace")
        cls._grant(cls.voucher_only_user, "vouchers.view_voucher_workbench")

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
        self.assertContains(response, "Open Decisions")
        self.assertContains(response, "Open Field operations")
        self.assertContains(response, "Personal tutorial checkmarks")
        self.assertEqual(reverse("finance_operations:overview"), "/finance/")
        self.assertEqual(reverse("finance:workspace"), "/finance/setup/")
        self.assertEqual(reverse("vouchers:workspace"), "/finance/vouchers/")
        self.assertEqual(reverse("accounting:workspace"), "/finance/accounting/")

    def test_entry_omits_workspaces_not_allowed_to_the_account(self):
        self.client.force_login(self.voucher_only_user)

        response = self.client.get(reverse("finance_operations:overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("vouchers:workspace"))
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
