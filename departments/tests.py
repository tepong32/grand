from django.test import TestCase

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
