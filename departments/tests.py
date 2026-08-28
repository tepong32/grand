from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from assistance.models import AssistanceRequest, AssistanceType
from .models import Department, InternalHowTo, InternalHowToStep, InternalHowToStepCompletion
from .services import DEFAULT_DASHBOARD_TEMPLATE, get_department_home_context
from .services.internal_howtos import set_step_completion, visible_internal_how_tos
from .services.internal_howto_seed import seed_finance_internal_howtos
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
            "mswd": Department.objects.create(
                name="Municipal Social Welfare and Development Office",
                slug="mswd",
                description="Social protection, citizen assistance, and community programs.",
                dashboard_template="home/authed/dashboards/mswd.html",
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

        assistance_type = AssistanceType.objects.create(
            name="Educational Assistance",
            slug="educational-assistance",
            description="Student support",
            requirements="Required records",
        )
        for index, status in enumerate(("submitted", "pending", "review", "approved"), start=1):
            AssistanceRequest.objects.create(
                reference_code=f"MSWD-DASH-{index}",
                assistance_type=assistance_type,
                full_name=f"Citizen {index}",
                email=f"citizen{index}@example.com",
                phone=f"0917000000{index}",
                status=status,
            )

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

    def test_mswd_employee_gets_department_workspace_with_assistance_module(self):
        response = self._dashboard_for("mswd")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/authed/dashboards/mswd.html")
        self.assertTemplateUsed(response, "home/authed/dashboards/generic.html")
        self.assertFalse(
            any(template.name == "assistance/mswd/dashboard.html" for template in response.templates)
        )
        self.assertContains(response, "Municipal Social Welfare and Development Office")
        self.assertContains(response, "Assistance Requests")
        self.assertContains(response, "Open Assistance Processing")
        self.assertContains(response, reverse("assistance:mswd_dashboard"))
        self.assertContains(response, "Social Welfare Programs")
        self.assertContains(response, "Activities and Events")
        self.assertContains(response, "Beneficiaries and Citizens")
        self.assertNotContains(response, "Citizen 1")

        assistance_section = response.context["dashboard_sections"][0]
        summary = {item["label"]: item["value"] for item in assistance_section["summary_items"]}
        self.assertEqual(summary, {"Active": 4, "Awaiting action": 2, "Under review": 1})

    def test_mswd_missing_custom_template_uses_generic_workspace_not_assistance_queue(self):
        department = self.departments["mswd"]
        department.dashboard_template = "home/authed/dashboards/not-created.html"
        department.save(update_fields=["dashboard_template"])

        response = self._dashboard_for("mswd")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home/authed/dashboards/generic.html")
        self.assertContains(response, "Assistance Requests")
        self.assertNotContains(response, "Citizen 1")

    def test_non_mswd_employee_cannot_open_assistance_processing(self):
        self.client.force_login(self.users["hr"])

        response = self.client.get(reverse("assistance:mswd_dashboard"))

        self.assertRedirects(response, reverse("home"))

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


class InternalHowToTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="accounting")
        cls.hr = Department.objects.create(name="Human Resources", slug="hr-howto")
        cls.preparer = cls._employee("howto.preparer", cls.accounting)
        cls.successor = cls._employee("howto.successor", cls.accounting)
        cls.outsider = cls._employee("howto.outsider", cls.hr)
        permission = Permission.objects.get(content_type__app_label="accounting", codename="prepare_opening_balances")
        cls.preparer.user_permissions.add(permission)
        cls.successor.user_permissions.add(permission)
        cls.outsider.user_permissions.add(permission)
        cls.guide = InternalHowTo.objects.create(
            department=cls.accounting,
            slug="opening-controls-test",
            version=1,
            title="Opening controls test guide",
            summary="Synthetic role and department guide.",
            required_permission="accounting.prepare_opening_balances",
            page_patterns=["department_dashboard", "accounting:opening_*"],
            status=InternalHowTo.DRAFT,
        )
        cls.step = InternalHowToStep.objects.create(
            how_to=cls.guide,
            position=1,
            title="Synthetic controlled step",
            instruction="Follow the current department's synthetic instruction.",
            expected_result="Synthetic result is visible.",
        )
        cls.guide.status = InternalHowTo.PUBLISHED
        cls.guide.save(update_fields=("status", "updated_at"))
        InternalHowTo.objects.create(
            department=cls.accounting,
            slug="draft-hidden",
            title="Hidden draft guide",
            summary="Not published.",
            status=InternalHowTo.DRAFT,
        )
        InternalHowTo.objects.create(
            department=cls.accounting,
            slug="retired-hidden",
            title="Hidden retired guide",
            summary="No longer current.",
            status=InternalHowTo.RETIRED,
        )

    @classmethod
    def _employee(cls, username, department):
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.test",
            password="internal-howto-test-password",
        )
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save(update_fields=("assigned_department",))
        return get_user_model().objects.get(pk=user.pk)

    def test_visibility_is_computed_from_current_department_role_and_publication(self):
        department, guides = visible_internal_how_tos(self.preparer, "department_dashboard")
        self.assertEqual(department, self.accounting)
        self.assertEqual([guide.pk for guide in guides], [self.guide.pk])
        self.assertTrue(guides[0].matches_current_page)

        permission = Permission.objects.get(content_type__app_label="accounting", codename="prepare_opening_balances")
        self.preparer.user_permissions.remove(permission)
        self.preparer = get_user_model().objects.get(pk=self.preparer.pk)
        self.assertEqual(visible_internal_how_tos(self.preparer)[1], [])
        self.assertEqual(visible_internal_how_tos(self.outsider)[1], [])

    def test_reassignment_removes_old_guides_without_assigning_them_to_users(self):
        self.assertEqual(len(visible_internal_how_tos(self.preparer)[1]), 1)
        profile = self.preparer.employeeprofile
        profile.assigned_department = self.hr
        profile.save(update_fields=("assigned_department",))
        self.preparer = get_user_model().objects.get(pk=self.preparer.pk)
        self.assertEqual(visible_internal_how_tos(self.preparer)[1], [])
        self.assertFalse(hasattr(self.guide, "user_id"))

    def test_successor_sees_guide_but_not_predecessor_progress(self):
        completion, completed = set_step_completion(user=self.preparer, step_id=self.step.pk, completed=True)
        self.assertTrue(completed)
        self.assertEqual(completion.department, self.accounting)
        predecessor_guide = visible_internal_how_tos(self.preparer)[1][0]
        successor_guide = visible_internal_how_tos(self.successor)[1][0]
        self.assertEqual(predecessor_guide.completed_count, 1)
        self.assertEqual(successor_guide.completed_count, 0)
        self.assertFalse(InternalHowToStepCompletion.objects.filter(user=self.successor).exists())

    def test_floating_nonmodal_panel_renders_and_saves_progress(self):
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("department_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="grand-howto-toggle"')
        self.assertContains(response, 'id="grand-howto-panel"')
        self.assertContains(response, "Opening controls test guide")
        self.assertContains(response, "hidden")
        self.assertNotContains(response, "modal-backdrop")

        response = self.client.post(
            reverse("departments:internal_howto_step_completion", args=(self.step.pk,)),
            {"completed": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"step_id": self.step.pk, "completed": True})
        self.assertTrue(InternalHowToStepCompletion.objects.filter(user=self.preparer, step=self.step).exists())

    def test_completion_endpoint_rejects_other_departments_and_missing_permissions(self):
        endpoint = reverse("departments:internal_howto_step_completion", args=(self.step.pk,))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(endpoint, {"completed": "true"}).status_code, 403)

        permission = Permission.objects.get(
            content_type__app_label="accounting",
            codename="prepare_opening_balances",
        )
        self.preparer.user_permissions.remove(permission)
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.post(endpoint, {"completed": "true"}).status_code, 403)
        self.assertFalse(InternalHowToStepCompletion.objects.filter(step=self.step).exists())

    def test_current_page_guides_are_ordered_before_other_page_guides(self):
        broad = InternalHowTo.objects.create(
            department=self.accounting,
            slug="broad-guide",
            title="A different-page guide",
            summary="Visible in the department but intended for another page.",
            page_patterns=["vouchers:*"],
            status=InternalHowTo.DRAFT,
            sort_order=1,
        )
        InternalHowToStep.objects.create(
            how_to=broad,
            position=1,
            title="Broad step",
            instruction="Use the broad guide when it is relevant.",
        )
        broad.status = InternalHowTo.PUBLISHED
        broad.save(update_fields=("status", "updated_at"))

        guides = visible_internal_how_tos(self.preparer, "accounting:opening_workspace")[1]
        self.assertEqual([guide.pk for guide in guides[:2]], [self.guide.pk, broad.pk])
        self.assertTrue(guides[0].matches_current_page)
        self.assertFalse(guides[1].matches_current_page)

    def test_published_content_and_steps_require_a_new_version(self):
        guide = InternalHowTo.objects.get(pk=self.guide.pk)
        guide.title = "Silently changed title"
        with self.assertRaisesMessage(ValidationError, "new version"):
            guide.full_clean()
        step = InternalHowToStep.objects.get(pk=self.step.pk)
        step.instruction = "Silently changed instruction"
        with self.assertRaisesMessage(ValidationError, "new guide version"):
            step.save()

    def test_finance_seed_is_repeatable_and_preserves_published_guides(self):
        InternalHowTo.objects.filter(department=self.accounting).update(status=InternalHowTo.RETIRED)
        first = seed_finance_internal_howtos()
        second = seed_finance_internal_howtos()
        self.assertGreaterEqual(first["guides_created"], 1)
        self.assertGreaterEqual(second["guides_preserved"], 1)
        self.assertTrue(InternalHowTo.objects.filter(
            department=self.accounting,
            slug="finance-opening-prepare",
            status=InternalHowTo.PUBLISHED,
        ).exists())

    def test_finance_seed_supersedes_an_old_guide_without_copying_personal_progress(self):
        old = InternalHowTo.objects.create(
            department=self.accounting,
            slug="finance-requesting-office-payable-intake",
            version=1,
            title="Old payable intake guide",
            summary="Synthetic predecessor instructions.",
            required_permission="vouchers.initiate_payable_case",
            page_patterns=["vouchers:*"],
            status=InternalHowTo.DRAFT,
        )
        old_step = InternalHowToStep.objects.create(
            how_to=old, position=1, title="Old step", instruction="Follow the predecessor instruction.",
        )
        old.status = InternalHowTo.PUBLISHED
        old.save(update_fields=("status", "updated_at"))
        InternalHowToStepCompletion.objects.create(
            user=self.preparer, step=old_step, department=self.accounting,
        )

        counts = seed_finance_internal_howtos()

        old.refresh_from_db()
        current = InternalHowTo.objects.get(
            department=self.accounting,
            slug="finance-requesting-office-payable-intake",
            status=InternalHowTo.PUBLISHED,
        )
        self.assertEqual(old.status, InternalHowTo.RETIRED)
        self.assertEqual(current.version, 2)
        self.assertGreaterEqual(counts["guides_retired"], 1)
        self.assertTrue(InternalHowToStepCompletion.objects.filter(user=self.preparer, step=old_step).exists())
        self.assertFalse(InternalHowToStepCompletion.objects.filter(user=self.preparer, step__how_to=current).exists())
