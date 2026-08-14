from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from .access import can_manage_social_welfare
from .models import ProgramActivity, SocialWelfareProgram


class SocialWelfareProgramsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mswd = Department.objects.create(
            name="Municipal Social Welfare and Development Office",
            slug="mswd",
            dashboard_template="home/authed/dashboards/mswd.html",
        )
        cls.hr = Department.objects.create(name="Human Resources", slug="hr")
        user_model = get_user_model()
        cls.manager = user_model.objects.create_user(
            username="mswd-head", email="mswd-head@example.gov", password="test-password", first_name="Mara", last_name="Santos"
        )
        cls.viewer = user_model.objects.create_user(
            username="mswd-viewer", email="mswd-viewer@example.gov", password="test-password", first_name="Leo", last_name="Cruz"
        )
        cls.delegated = user_model.objects.create_user(
            username="mswd-coordinator", email="mswd-coordinator@example.gov", password="test-password", first_name="Ana", last_name="Reyes"
        )
        cls.outsider = user_model.objects.create_user(
            username="hr-viewer", email="hr-viewer@example.gov", password="test-password", first_name="Hana", last_name="Lim"
        )
        for user in (cls.manager, cls.viewer, cls.delegated):
            user.employeeprofile.assigned_department = cls.mswd
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.outsider.employeeprofile.assigned_department = cls.hr
        cls.outsider.employeeprofile.save(update_fields=("assigned_department",))
        cls.mswd.deptHead_or_oic = cls.manager
        cls.mswd.save(update_fields=("deptHead_or_oic",))
        cls.delegated.user_permissions.add(
            Permission.objects.get(codename="manage_social_welfare_programs")
        )

        cls.program = SocialWelfareProgram.objects.create(
            department=cls.mswd,
            name="Barangay Nutrition Support",
            code="MSWD-NUTRITION-01",
            program_type=SocialWelfareProgram.TYPE_FEEDING,
            description="Coordinated nutrition sessions for priority communities.",
            status=SocialWelfareProgram.STATUS_ACTIVE,
            coordinator=cls.delegated,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=90),
            created_by=cls.manager,
            updated_by=cls.manager,
        )
        cls.upcoming = ProgramActivity.objects.create(
            program=cls.program,
            title="Community Feeding and Nutrition Seminar",
            activity_type=ProgramActivity.TYPE_FEEDING,
            starts_at=timezone.now() + timedelta(days=7),
            ends_at=timezone.now() + timedelta(days=7, hours=3),
            venue="Barangay Mabuhay Multi-Purpose Hall",
            status=ProgramActivity.STATUS_PLANNED,
            expected_attendance=120,
            created_by=cls.manager,
            updated_by=cls.manager,
        )
        cls.completed = ProgramActivity.objects.create(
            program=cls.program,
            title="Family Development Orientation",
            activity_type=ProgramActivity.TYPE_ORIENTATION,
            starts_at=timezone.now() - timedelta(days=14),
            venue="MSWD Conference Room",
            status=ProgramActivity.STATUS_COMPLETED,
            expected_attendance=60,
            actual_attendance=54,
            outcome_notes="Families completed the orientation and received referral materials.",
            created_by=cls.manager,
            updated_by=cls.delegated,
        )

    def test_all_mswd_employees_can_view_programs_and_aggregate_reach(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("social_welfare:program_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.program.name)
        self.assertContains(response, self.upcoming.title)
        self.assertContains(response, "54")
        self.assertFalse(response.context["can_manage_programs"])
        self.assertNotContains(response, "New program")

    def test_non_mswd_employee_is_forbidden_from_program_workspace(self):
        self.client.force_login(self.outsider)

        response = self.client.get(reverse("social_welfare:program_list"))

        self.assertEqual(response.status_code, 403)

    def test_department_head_can_manage_programs(self):
        self.assertTrue(can_manage_social_welfare(self.manager))
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("social_welfare:program_create"),
            {
                "name": "Senior Citizens Wellness Program",
                "code": "MSWD-SC-01",
                "program_type": SocialWelfareProgram.TYPE_OUTREACH,
                "description": "Community wellness services.",
                "status": SocialWelfareProgram.STATUS_ACTIVE,
                "coordinator": self.viewer.pk,
                "start_date": timezone.localdate().isoformat(),
                "end_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
            },
        )

        created = SocialWelfareProgram.objects.get(code="MSWD-SC-01")
        self.assertRedirects(response, created.get_absolute_url())
        self.assertEqual(created.department, self.mswd)
        self.assertEqual(created.created_by, self.manager)
        self.assertEqual(created.updated_by, self.manager)

    def test_dedicated_permission_allows_mswd_employee_to_manage(self):
        self.assertTrue(can_manage_social_welfare(self.delegated))
        self.client.force_login(self.delegated)

        response = self.client.post(
            reverse("social_welfare:activity_create", args=(self.program.pk,)),
            {
                "title": "Parent Effectiveness Seminar",
                "activity_type": ProgramActivity.TYPE_SEMINAR,
                "starts_at": (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M"),
                "ends_at": (timezone.now() + timedelta(days=10, hours=2)).strftime("%Y-%m-%dT%H:%M"),
                "venue": "Municipal Training Hall",
                "status": ProgramActivity.STATUS_PLANNED,
                "expected_attendance": 80,
                "actual_attendance": "",
                "outcome_notes": "",
            },
        )

        activity = ProgramActivity.objects.get(title="Parent Effectiveness Seminar")
        self.assertRedirects(response, self.program.get_absolute_url())
        self.assertEqual(activity.created_by, self.delegated)
        self.assertEqual(activity.updated_by, self.delegated)

    def test_regular_mswd_employee_cannot_open_management_views(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("social_welfare:program_create"))

        self.assertEqual(response.status_code, 403)

    def test_outsider_with_permission_still_cannot_cross_department_boundary(self):
        self.outsider.user_permissions.add(
            Permission.objects.get(codename="manage_social_welfare_programs")
        )
        self.client.force_login(self.outsider)

        response = self.client.get(reverse("social_welfare:program_update", args=(self.program.pk,)))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(can_manage_social_welfare(self.outsider))

    def test_program_and_activity_reject_reversed_schedules(self):
        program = SocialWelfareProgram(
            department=self.mswd,
            name="Invalid",
            code="INVALID",
            program_type=SocialWelfareProgram.TYPE_OTHER,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() - timedelta(days=1),
            created_by=self.manager,
            updated_by=self.manager,
        )
        with self.assertRaises(ValidationError):
            program.full_clean()

        activity = ProgramActivity(
            program=self.program,
            title="Invalid schedule",
            activity_type=ProgramActivity.TYPE_OTHER,
            starts_at=timezone.now(),
            ends_at=timezone.now() - timedelta(hours=1),
            venue="Test venue",
            created_by=self.manager,
            updated_by=self.manager,
        )
        with self.assertRaises(ValidationError):
            activity.full_clean()

    def test_phase_two_stores_only_aggregate_attendance(self):
        field_names = {field.name for field in ProgramActivity._meta.get_fields()}

        self.assertIn("actual_attendance", field_names)
        self.assertNotIn("citizen", field_names)
        self.assertNotIn("participants", field_names)

    def test_mswd_dashboard_activates_programs_and_shows_real_upcoming_activity(self):
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("department_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open Programs Workspace")
        self.assertContains(response, "View Activity Schedule")
        self.assertContains(response, reverse("social_welfare:program_list"))
        self.assertContains(response, self.upcoming.title)
        programs_section = response.context["dashboard_sections"][1]
        summary = {item["label"]: item["value"] for item in programs_section["summary_items"]}
        self.assertEqual(
            summary,
            {"Active programs": 1, "Upcoming": 1, "Completed activities": 1},
        )

    def test_program_detail_records_outcome_and_audit_metadata(self):
        self.client.force_login(self.viewer)

        response = self.client.get(self.program.get_absolute_url())

        self.assertContains(response, self.completed.outcome_notes)
        self.assertContains(response, "54 actual")
        self.assertContains(response, self.program.updated_by.get_full_name())
