from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Department
from .services import DEFAULT_DASHBOARD_TEMPLATE, get_department_home_context
from .services.query_service import get_department_by_slug, get_department_for_user
from .services.query_service import get_dashboard_template


class DepartmentServiceTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(
            name="Test Department",
            slug="test-dept",
            email="dept@example.gov",
            phone="09123456789",
            dashboard_template="home/authed/dashboards/generic.html",
        )

    def test_department_slug_lookup(self):
        found = get_department_by_slug("TEST-DEPT")
        self.assertEqual(found, self.dept)

    def test_department_for_user_without_profile(self):
        class DummyUser:
            employeeprofile = None

        self.assertIsNone(get_department_for_user(DummyUser()))

    def test_dashboard_template_fallback(self):
        self.dept.dashboard_template = ""
        self.assertEqual(
            get_dashboard_template(self.dept, DEFAULT_DASHBOARD_TEMPLATE),
            DEFAULT_DASHBOARD_TEMPLATE,
        )

    def test_department_home_context_contains_department(self):
        context = get_department_home_context(self.dept, None)
        self.assertIn("department", context)


class DynamicDepartmentDashboardTests(TestCase):
    """Exercise post-login dashboards with employees in different offices."""

    @classmethod
    def setUpTestData(cls):
        cls.departments = {
            "hr": Department.objects.create(
                name="Human Resources",
                slug="hr",
                description="People, appointments, and employee services.",
                dashboard_template="home/authed/dashboards/hr.html",
            ),
            "gso": Department.objects.create(
                name="General Services Office",
                slug="gso",
                description="Property, supplies, facilities, and procurement support.",
                dashboard_template="home/authed/dashboards/gso.html",
            ),
            "acctg": Department.objects.create(
                name="Accounting Office",
                slug="acctg",
                description="Accounting records, disbursements, and financial reporting.",
                dashboard_template="home/authed/dashboards/acctg.html",
            ),
            "planning": Department.objects.create(
                name="Municipal Planning and Development Office",
                slug="mpdo",
                description="Development planning, projects, and local data.",
                dashboard_template="",
            ),
        }

        user_model = get_user_model()
        cls.users = {}
        for slug, department in cls.departments.items():
            user = user_model.objects.create_user(
                username=f"{slug}-employee",
                email=f"{slug}@example.gov",
                password="dashboard-test-password",
                first_name=slug.upper(),
                last_name="Employee",
            )
            user.employeeprofile.assigned_department = department
            user.employeeprofile.position_title = "Administrative Officer"
            user.employeeprofile.save()
            cls.users[slug] = user

    def _dashboard_for(self, department_key):
        self.client.force_login(self.users[department_key])
        return self.client.get(reverse("department_dashboard"))

    def test_hr_employee_gets_hr_workspace_and_live_team_count(self):
        response = self._dashboard_for("hr")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/authed/dashboards/hr.html")
        self.assertContains(response, "Human Resources")
        self.assertContains(response, "Employee records")
        self.assertContains(response, "Leave administration")
        self.assertEqual(response.context["dashboard_metrics"][0]["value"], 1)

    def test_gso_employee_gets_gso_suggestions_not_hr_content(self):
        response = self._dashboard_for("gso")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/authed/dashboards/gso.html")
        self.assertContains(response, "Inventory register")
        self.assertContains(response, "Property issuance")
        self.assertNotContains(response, "Leave administration")

    def test_accounting_employee_gets_accounting_workspace(self):
        response = self._dashboard_for("acctg")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/authed/dashboards/acctg.html")
        self.assertContains(response, "Disbursement queue")
        self.assertContains(response, "Compliance and audit")

    def test_successful_employee_login_redirects_to_assigned_department_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "hr-employee",
                "password": "dashboard-test-password",
            },
        )

        self.assertRedirects(response, reverse("department_dashboard"), fetch_redirect_response=False)

        dashboard = self.client.get(response.url)
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Human Resources")
        self.assertContains(dashboard, "Employee records")

    def test_new_department_automatically_gets_extendable_default_dashboard(self):
        response = self._dashboard_for("planning")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/authed/dashboards/generic.html")
        self.assertContains(response, "Municipal Planning and Development Office")
        self.assertContains(response, "Office work queue")
        self.assertContains(response, "Reports and performance")
        self.assertContains(response, "PLANNING Employee")

    def test_missing_custom_template_falls_back_without_breaking_login(self):
        department = self.departments["planning"]
        department.dashboard_template = "home/authed/dashboards/not-created.html"
        department.save(update_fields=["dashboard_template"])

        response = self._dashboard_for("planning")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/authed/dashboards/generic.html")

    def test_employee_without_department_is_sent_to_internal_home(self):
        user = self.users["planning"]
        user.employeeprofile.assigned_department = None
        user.employeeprofile.save()
        self.client.force_login(user)

        response = self.client.get(reverse("department_dashboard"))

        self.assertRedirects(response, reverse("home"))
