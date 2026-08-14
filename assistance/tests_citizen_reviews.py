from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department

from assistance.access import (
    can_access_citizen_reviews,
    can_review_citizen_profiles,
    can_view_citizen_pii,
)
from assistance.models import AssistanceRequest, AssistanceType, CitizenProfile, CitizenReviewLog
from assistance.services import AssistanceRequestService
from assistance.services.citizen_service import CitizenProfileService


class CitizenProfileReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mswd = Department.objects.create(
            name="Municipal Social Welfare and Development Office", slug="mswd"
        )
        cls.hr = Department.objects.create(name="Human Resources", slug="hr")
        user_model = get_user_model()
        cls.head = user_model.objects.create_user(
            username="citizen-review-head",
            email="citizen-review-head@example.gov",
            password="test-password",
            first_name="Mara",
            last_name="Santos",
        )
        cls.masked_viewer = user_model.objects.create_user(
            username="citizen-masked-viewer",
            email="citizen-masked@example.gov",
            password="test-password",
        )
        cls.reviewer = user_model.objects.create_user(
            username="citizen-reviewer",
            email="citizen-reviewer@example.gov",
            password="test-password",
            first_name="Ana",
            last_name="Reyes",
        )
        cls.outsider = user_model.objects.create_user(
            username="citizen-review-outsider",
            email="citizen-review-outsider@example.gov",
            password="test-password",
        )
        for user in (cls.head, cls.masked_viewer, cls.reviewer):
            user.employeeprofile.assigned_department = cls.mswd
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.outsider.employeeprofile.assigned_department = cls.hr
        cls.outsider.employeeprofile.save(update_fields=("assigned_department",))
        cls.mswd.deptHead_or_oic = cls.head
        cls.mswd.save(update_fields=("deptHead_or_oic",))

        permissions = {
            permission.codename: permission
            for permission in Permission.objects.filter(
                codename__in=(
                    "view_citizen_review_workspace",
                    "review_citizen_profiles",
                    "view_citizen_profile_pii",
                )
            )
        }
        cls.masked_viewer.user_permissions.add(permissions["view_citizen_review_workspace"])
        cls.reviewer.user_permissions.add(
            permissions["view_citizen_review_workspace"],
            permissions["review_citizen_profiles"],
            permissions["view_citizen_profile_pii"],
        )
        cls.outsider.user_permissions.add(*permissions.values())

        cls.assistance_type = AssistanceType.objects.create(
            name="Educational Assistance",
            description="Student and family support.",
            requirements="Approved supporting documents.",
        )
        cls.profile = CitizenProfile.objects.create(
            full_name="Maria Dela Cruz",
            email="Maria@example.com",
            phone="0917-123-4567",
        )
        for index, status in enumerate(("submitted", "approved", "review"), start=1):
            AssistanceRequest.objects.create(
                reference_code=f"CITIZEN-TEST-{index}",
                assistance_type=cls.assistance_type,
                full_name="Maria Dela Cruz",
                email="Maria@example.com",
                phone="0917-123-4567",
                status=status,
                citizen=cls.profile,
            )
        CitizenProfileService.increment_request_count(cls.profile)

    def test_access_requires_both_mswd_boundary_and_explicit_role(self):
        self.assertTrue(can_access_citizen_reviews(self.head))
        self.assertTrue(can_review_citizen_profiles(self.head))
        self.assertTrue(can_view_citizen_pii(self.head))
        self.assertTrue(can_access_citizen_reviews(self.masked_viewer))
        self.assertFalse(can_review_citizen_profiles(self.masked_viewer))
        self.assertFalse(can_view_citizen_pii(self.masked_viewer))
        self.assertFalse(can_access_citizen_reviews(self.outsider))

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("assistance:citizen_profile_list"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_access_redirects_to_login(self):
        response = self.client.get(reverse("assistance:citizen_profile_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_masked_workspace_shows_usage_but_hides_pii_and_review_controls(self):
        self.profile.review_notes = "Confidential reviewer-only note."
        self.profile.save(update_fields=("review_notes", "updated_at"))
        CitizenReviewLog.objects.create(
            profile=self.profile,
            actor=self.reviewer,
            previous_status="unreviewed",
            new_status="in_review",
            note="Confidential audit explanation.",
        )
        self.client.force_login(self.masked_viewer)
        response = self.client.get(reverse("assistance:citizen_profile_list"), {"sort": "requests"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "M*** D*** C***")
        self.assertNotContains(response, "Maria@example.com")
        self.assertNotContains(response, "0917-123-4567")
        self.assertContains(response, ">3<", html=False)

        detail = self.client.get(
            reverse("assistance:citizen_profile_detail", args=[self.profile.pk])
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Frequency is shown for workload")
        self.assertNotContains(detail, "Save review")
        self.assertNotContains(detail, "Maria@example.com")
        self.assertContains(detail, "Restricted to authorized reviewers")
        self.assertNotContains(detail, "Confidential reviewer-only note")
        self.assertNotContains(detail, "Confidential audit explanation")

    def test_pii_permission_enables_search_and_identity_fields(self):
        self.client.force_login(self.reviewer)
        response = self.client.get(
            reverse("assistance:citizen_profile_list"), {"q": "Maria@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maria Dela Cruz")
        self.assertContains(response, "Maria@example.com")
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_reviewer_updates_state_assignment_notes_and_audit_history(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse("assistance:citizen_profile_detail", args=[self.profile.pk]),
            {
                "review_status": "verified",
                "assigned_reviewer": self.reviewer.pk,
                "review_notes": "Contact details matched the submitted records.",
            },
        )

        self.assertRedirects(
            response, reverse("assistance:citizen_profile_detail", args=[self.profile.pk])
        )
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.review_status, "verified")
        self.assertEqual(self.profile.assigned_reviewer, self.reviewer)
        self.assertEqual(self.profile.reviewed_by, self.reviewer)
        self.assertIsNotNone(self.profile.reviewed_at)
        log = CitizenReviewLog.objects.get(profile=self.profile)
        self.assertEqual(log.actor, self.reviewer)
        self.assertEqual(log.previous_status, "unreviewed")
        self.assertEqual(log.new_status, "verified")
        self.assertIn("Contact details matched", log.note)

        unchanged = self.client.post(
            reverse("assistance:citizen_profile_detail", args=[self.profile.pk]),
            {
                "review_status": "verified",
                "assigned_reviewer": self.reviewer.pk,
                "review_notes": "Contact details matched the submitted records.",
            },
        )
        self.assertEqual(unchanged.status_code, 302)
        self.assertEqual(CitizenReviewLog.objects.filter(profile=self.profile).count(), 1)

    def test_needs_update_requires_an_explanation(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse("assistance:citizen_profile_detail", args=[self.profile.pk]),
            {"review_status": "needs_update", "assigned_reviewer": "", "review_notes": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explain what information needs to be updated")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.review_status, "unreviewed")
        self.assertFalse(CitizenReviewLog.objects.filter(profile=self.profile).exists())

    def test_view_only_user_cannot_submit_review(self):
        self.client.force_login(self.masked_viewer)
        response = self.client.post(
            reverse("assistance:citizen_profile_detail", args=[self.profile.pk]),
            {"review_status": "verified", "assigned_reviewer": "", "review_notes": ""},
        )
        self.assertEqual(response.status_code, 403)

    def test_exact_normalized_identifier_duplicates_are_cued_not_merged(self):
        duplicate = CitizenProfile.objects.create(
            full_name="Maria D. Cruz",
            email="maria@EXAMPLE.com",
            phone="09171234567",
        )
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("assistance:citizen_profile_list"))

        self.assertContains(response, "Possible duplicate identifiers", count=2)
        detail = self.client.get(
            reverse("assistance:citizen_profile_detail", args=[self.profile.pk])
        )
        self.assertContains(detail, duplicate.full_name)
        self.assertContains(detail, "No records have been merged automatically")

    def test_conflicting_identifiers_never_silently_merge_two_profiles(self):
        first = CitizenProfile.objects.create(
            full_name="First Citizen", email="first@example.com", phone="09170000001"
        )
        second = CitizenProfile.objects.create(
            full_name="Second Citizen", email="second@example.com", phone="09170000002"
        )

        resolved = CitizenProfileService.get_or_create_citizen(
            full_name="Submitted Identity",
            email=second.email,
            phone=first.phone,
        )

        self.assertNotEqual(resolved.pk, first.pk)
        self.assertNotEqual(resolved.pk, second.pk)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.full_name, "First Citizen")
        self.assertEqual(second.full_name, "Second Citizen")

    def test_request_submission_keeps_factual_count_in_sync(self):
        request_obj = AssistanceRequestService.submit_request(
            assistance_type=self.assistance_type,
            period="2026-2027",
            semester="1st",
            full_name="New Resident",
            email="resident@example.com",
            phone="09179998888",
        )
        request_obj.citizen.refresh_from_db()
        self.assertEqual(request_obj.citizen.total_requests, 1)
        self.assertEqual(request_obj.citizen.normalized_email, "resident@example.com")
        self.assertEqual(request_obj.citizen.normalized_phone, "09179998888")

    def test_authorized_navigation_and_request_detail_link_to_profile(self):
        self.client.force_login(self.head)
        dashboard = self.client.get(reverse("assistance:mswd_dashboard"))
        self.assertContains(dashboard, "Citizen profile review")
        self.assertContains(
            dashboard,
            reverse("assistance:citizen_profile_detail", args=[self.profile.pk]),
        )
        request_obj = self.profile.requests.first()
        detail = self.client.get(
            reverse("assistance:mswd_request_detail", args=[request_obj.reference_code])
        )
        self.assertContains(detail, "Review service history")
