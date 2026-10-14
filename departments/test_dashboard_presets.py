from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from departments.services.dashboard_service import _workspace_sections, DEPARTMENT_WORKSPACE_PRESETS
from departments.services.workspace_presets import ADDITIONAL_PRESETS, PRESET_ALIASES


class DepartmentPresetTests(TestCase):
    def test_every_preset_and_alias_has_honest_next_steps(self):
        for slug in (*DEPARTMENT_WORKSPACE_PRESETS, *ADDITIONAL_PRESETS, *PRESET_ALIASES, "future-office"):
            with self.subTest(slug=slug):
                department = Department.objects.create(name=slug, slug=slug)
                sections = _workspace_sections(department)
                self.assertGreaterEqual(len(sections), 3)
                for section in sections:
                    self.assertTrue(section["title"])
                    self.assertTrue(section["description"])
                    self.assertIn(section["status"], ("Available", "Restricted", "Planned"))
                    if section["status"] != "Available":
                        self.assertFalse(section.get("url_name"))
                        self.assertFalse(section.get("url"))
                    elif section.get("url_name"):
                        self.assertTrue(reverse(section["url_name"]))

    def test_hr_leave_administration_requires_management_authority(self):
        department = Department.objects.create(name="Human Resources", slug="hr")
        user = get_user_model().objects.create_user(username="hr-preset", email="hr-preset@example.com")
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save()
        section = _workspace_sections(department, user)[1]
        self.assertEqual(section["status"], "Restricted")
        user.user_permissions.add(Permission.objects.get(content_type__app_label="leave_mgt", codename="manage_leave_credits"))
        user = get_user_model().objects.get(pk=user.pk)
        section = _workspace_sections(department, user)[1]
        self.assertEqual(section["url_name"], "leave_manage")

    def test_finance_links_follow_existing_permissions(self):
        department = Department.objects.create(name="Treasury", slug="treasury")
        user = get_user_model().objects.create_user(username="treasury-preset", email="treasury-preset@example.com")
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save()
        before = _workspace_sections(department, user)
        self.assertFalse(any(row.get("url_name") == "vouchers:collection_register" for row in before))
        self.assertEqual(before[0]["status"], "Restricted")
        user.user_permissions.add(Permission.objects.get(content_type__app_label="vouchers", codename="view_collection_register"))
        user = get_user_model().objects.get(pk=user.pk)
        after = _workspace_sections(department, user)
        self.assertTrue(any(row.get("url_name") == "vouchers:collection_register" for row in after))

    def test_planning_page_shows_its_scope_without_blank_links(self):
        department = Department.objects.create(name="Planning Office", slug="mpdo")
        user = get_user_model().objects.create_user(username="planning-preset", email="planning-preset@example.com")
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save()
        self.client.force_login(user)
        response = self.client.get(reverse("department_dashboard"))
        self.assertContains(response, "Development plans")
        self.assertContains(response, "Project monitoring")
        self.assertContains(response, "Planned office workspace")
        self.assertNotContains(response, 'href=""')
        self.assertNotContains(response, 'href="#" class="workspace-action"')
        self.assertNotContains(response, "Create employee account")

    def test_signup_entry_points_and_password_recovery_have_real_urls(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, reverse("password_reset"))
        self.assertContains(response, reverse("account_signup"))
        self.assertContains(response, "Employee sign in")
        self.assertNotContains(response, "/password-reset/")
        self.assertContains(self.client.get(reverse("account_signup")), "Create citizen account")
        self.assertContains(self.client.get(reverse("account_login")), "Citizen sign in")

    def test_unknown_office_retains_generic_dashboard_fallback(self):
        department = Department.objects.create(name="Future Office", slug="future-custom-office")
        user = get_user_model().objects.create_user(username="future-preset", email="future-preset@example.com")
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save()
        self.client.force_login(user)
        response = self.client.get(reverse("department_dashboard"))
        self.assertContains(response, "Office work queue")
        self.assertContains(response, "Reports and performance")


class FinanceDashboardVisibilityTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        from vouchers.models import VoucherCase
        cls.office = Department.objects.create(name="General Services Office", slug="gso")
        cls.other_office = Department.objects.create(name="Engineering Office", slug="engineering")
        cls.accounting = Department.objects.create(name="Accounting Office", slug="accounting")
        cls.clerk = get_user_model().objects.create_user(username="dashboard-payable-clerk")
        cls.clerk.employeeprofile.assigned_department = cls.office
        cls.clerk.employeeprofile.save()
        cls.clerk.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="vouchers",
            codename__in=("view_voucher_workbench", "initiate_payable_case")))
        for office in (cls.office, cls.other_office):
            for stage in (VoucherCase.PAYABLE_PREPARATION, VoucherCase.PAYABLE_REVIEW, VoucherCase.COMPLETED):
                VoucherCase.objects.create(reference_code=f"SCOPE-{office.pk}-{stage}",
                    requesting_department=office,
                    current_department=office if stage == VoucherCase.PAYABLE_PREPARATION else cls.accounting,
                    current_stage=stage, created_by=cls.clerk, payee_name="Synthetic supplier",
                    particulars="Synthetic legacy case for read-scope checks", authoritative_obligation_amount=0)

    def finance_card(self, sections):
        return next(row for row in sections if row.get("url_name") == "vouchers:workspace")

    def test_requesting_dashboard_counts_match_visible_workbench(self):
        from vouchers.models import VoucherCase
        before = list(VoucherCase.objects.order_by("pk").values_list("pk", "state_version", "current_stage"))
        card = self.finance_card(_workspace_sections(self.office, self.clerk))
        self.assertEqual({item["label"]: item["value"] for item in card["summary_items"]},
                         {"For this office": 1, "Open shared": 2, "Completed": 1})
        self.client.force_login(self.clerk)
        dashboard = self.client.get(reverse("department_dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(self.finance_card(dashboard.context["dashboard_sections"])["summary_items"],
                         card["summary_items"])
        workbench = self.client.get(reverse("vouchers:workspace"))
        self.assertEqual(workbench.status_code, 200)
        self.assertEqual((workbench.context["queue_count"], workbench.context["open_count"],
                          workbench.context["completed_count"]), (1, 2, 1))
        self.assertEqual(list(VoucherCase.objects.order_by("pk").values_list("pk", "state_version", "current_stage")), before)

    def test_uat_viewer_keeps_existing_broader_read_scope(self):
        from django.contrib.auth.models import Group
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        self.clerk.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        card = self.finance_card(_workspace_sections(self.office, self.clerk))
        self.assertEqual({item["label"]: item["value"] for item in card["summary_items"]},
                         {"For this office": 2, "Open shared": 4, "Completed": 2})
        self.client.force_login(self.clerk)
        workbench = self.client.get(reverse("vouchers:workspace"))
        self.assertEqual(workbench.status_code, 200)
        self.assertEqual((workbench.context["queue_count"], workbench.context["open_count"],
                          workbench.context["completed_count"]), (2, 4, 2))
