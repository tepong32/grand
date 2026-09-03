import json
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceRequest, AssistanceType
from departments.models import Department
from departments.services.internal_howto_seed import ACCOUNTING_GUIDES, BUDGET_GUIDES
from vouchers.roles import FINANCE_ROLE_PERMISSIONS

from .models import (
    ReportDefinition, ReportRun, ReportSchedule, ReportTemplatePromotion,
    ReportTemplateVersion,
)
from .services import create_manual_run, transition_run
from .template_services import (
    activate_template_promotion, create_template_promotion, review_template_promotion,
    rollback_template_promotion, submit_template_promotion,
)


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="grand-template-promotion-media-")
TEST_EXPORT_ROOT = tempfile.mkdtemp(prefix="grand-template-promotion-export-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, GRAND_EXPORT_ROOT=TEST_EXPORT_ROOT)
class ReportTemplatePromotionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(
            name="Municipal Social Welfare and Development Office",
            slug="mswd",
        )
        users = get_user_model()
        cls.manager = users.objects.create_user(username="layout-manager", email="layout-manager@example.test", password="test-password")
        cls.preparer = users.objects.create_user(username="layout-preparer", email="layout-preparer@example.test", password="test-password")
        cls.reviewer = users.objects.create_user(username="layout-reviewer", email="layout-reviewer@example.test", password="test-password")
        cls.outsider_department = Department.objects.create(name="Other Office", slug="template-other")
        cls.outsider = users.objects.create_user(username="layout-outsider", email="layout-outsider@example.test", password="test-password")
        for user in (cls.manager, cls.preparer, cls.reviewer):
            user.employeeprofile.assigned_department = cls.department
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.outsider.employeeprofile.assigned_department = cls.outsider_department
        cls.outsider.employeeprofile.save(update_fields=("assigned_department",))
        cls.department.deptHead_or_oic = cls.manager
        cls.department.save(update_fields=("deptHead_or_oic",))
        cls.preparer.user_permissions.add(*Permission.objects.filter(codename__in=(
            "view_reporting_workspace", "prepare_template_promotions", "download_reports",
        )))
        cls.reviewer.user_permissions.add(*Permission.objects.filter(codename__in=(
            "view_reporting_workspace", "approve_template_promotions", "approve_reports",
        )))
        cls.outsider.user_permissions.add(Permission.objects.get(codename="view_reporting_workspace"))

        assistance_type = AssistanceType.objects.create(
            name="Template comparison assistance", description="Synthetic", requirements="Synthetic",
        )
        AssistanceRequest.objects.create(
            assistance_type=assistance_type, full_name="Synthetic Template Citizen",
            email="template@example.test", phone="09123456789", status="submitted",
        )
        cls.definition = ReportDefinition.objects.create(
            department=cls.department,
            name="Assistance Template Control",
            slug="assistance-template-control",
            dataset_key="mswd_assistance_volume",
            selected_fields=["assistance_type", "status", "request_count"],
            totals=["request_count"],
            default_format=ReportDefinition.FORMAT_PDF,
            created_by=cls.manager,
            updated_by=cls.manager,
        )
        accepted_at = timezone.now()
        cls.baseline_template = ReportTemplateVersion.objects.create(
            definition=cls.definition,
            version=1,
            title="Accepted assistance form",
            header_text="MSWD",
            fidelity_status=ReportTemplateVersion.OFFICIAL,
            fidelity_notes="Accepted synthetic reference.",
            fidelity_validated_by=cls.reviewer,
            fidelity_validated_at=accepted_at,
            is_active=True,
            created_by=cls.preparer,
            approved_by=cls.reviewer,
            approved_at=accepted_at,
        )

    def setUp(self):
        self.start = timezone.localdate() - timedelta(days=7)
        self.end = timezone.localdate()
        self.baseline_run = create_manual_run(
            self.definition, self.baseline_template, "pdf",
            self.start, self.end, {}, self.preparer,
        )
        transition_run(self.baseline_run, "review", self.reviewer, "Accepted sample checked.")
        transition_run(self.baseline_run, "approve", self.reviewer, "Accepted golden output.")
        self.candidate = ReportTemplateVersion.objects.create(
            definition=self.definition,
            version=2,
            title="Plain-language revised assistance form",
            header_text="Municipal Social Welfare and Development Office",
            footer_text="Controlled output",
            document_control_prefix="MSWD-LAYOUT",
            is_active=False,
            created_by=self.preparer,
            approved_by=self.reviewer,
            approved_at=timezone.now(),
        )

    def _promotion(self, update_schedules=False):
        return create_template_promotion(
            template=self.candidate,
            actor=self.preparer,
            period_start=self.start,
            period_end=self.end,
            output_format="pdf",
            change_reason="Match the office's familiar signed layout without changing report data.",
            comparison_note=(
                "Compared headings, totals, signatories, page count, overflow, A4 stock, and office printer "
                "alignment with the retained redacted sample."
            ),
            baseline_run=self.baseline_run,
            update_compatible_schedules=update_schedules,
        )

    def test_golden_preview_submission_maker_checker_activation_and_rollback(self):
        schedule = ReportSchedule.objects.create(
            definition=self.definition,
            template_version=self.baseline_template,
            name="Monthly accepted assistance report",
            frequency=ReportSchedule.MONTHLY,
            output_format="pdf",
            next_run_at=timezone.now() + timedelta(days=2),
            created_by=self.manager,
        )
        promotion = self._promotion(update_schedules=True)
        self.assertEqual(promotion.golden_result, ReportTemplatePromotion.GOLDEN_MATCHED)
        self.assertTrue(promotion.golden_snapshot["all_checks_passed"])
        self.assertTrue(promotion.mapping_diff)
        self.assertEqual(promotion.impact_snapshot["compatible_schedule_ids"], [schedule.pk])
        submit_template_promotion(promotion, self.preparer)
        with self.assertRaisesMessage(ValueError, "cannot review"):
            review_template_promotion(promotion, self.preparer, "approve", "Self approval.")
        review_template_promotion(
            promotion, self.reviewer, "approve",
            "Automatic controls agree and the retained print comparison is complete.",
        )
        activate_template_promotion(promotion, self.manager)
        promotion.refresh_from_db()
        self.candidate.refresh_from_db()
        self.baseline_template.refresh_from_db()
        schedule.refresh_from_db()
        self.assertEqual(promotion.status, ReportTemplatePromotion.ACTIVATED)
        self.assertTrue(self.candidate.is_official_ready)
        self.assertTrue(self.candidate.is_active)
        self.assertFalse(self.baseline_template.is_active)
        self.assertEqual(schedule.template_version, self.candidate)
        self.assertEqual(self.definition.current_template, self.candidate)
        rollback_template_promotion(
            promotion, self.manager,
            "Printer trial exposed a margin issue; restore the accepted version while a successor is prepared.",
        )
        promotion.refresh_from_db()
        schedule.refresh_from_db()
        self.baseline_template.refresh_from_db()
        self.assertEqual(promotion.status, ReportTemplatePromotion.ROLLED_BACK)
        self.assertTrue(self.baseline_template.is_active)
        self.assertEqual(schedule.template_version, self.baseline_template)
        self.assertEqual(
            list(promotion.events.order_by("created_at", "pk").values_list("action", flat=True)),
            ["preview_created", "submitted", "approve", "activated", "rolled_back"],
        )

    def test_candidate_drift_and_unconfirmed_applicability_block_submission(self):
        promotion = self._promotion()
        ReportTemplateVersion.objects.filter(pk=self.candidate.pk).update(title="Changed after preview")
        self.candidate.refresh_from_db()
        promotion.refresh_from_db()
        with self.assertRaisesMessage(ValueError, "changed after preview"):
            submit_template_promotion(promotion, self.preparer)

        self.candidate.title = promotion.template_snapshot["title"]
        ReportTemplateVersion.objects.filter(pk=self.candidate.pk).update(title=self.candidate.title)
        self.definition.applicability_status = ReportDefinition.APPLICABILITY_CANDIDATE
        self.definition.save(update_fields=("applicability_status",))
        promotion.refresh_from_db()
        with self.assertRaisesMessage(ValueError, "local applicability"):
            submit_template_promotion(promotion, self.preparer)

    def test_first_layout_requires_reference_or_existing_golden_output(self):
        first_definition = ReportDefinition.objects.create(
            department=self.department,
            name="First controlled layout",
            slug="first-controlled-layout",
            dataset_key="mswd_assistance_volume",
            selected_fields=["assistance_type", "status", "request_count"],
            default_format="pdf",
            created_by=self.manager,
            updated_by=self.manager,
        )
        first = ReportTemplateVersion.objects.create(
            definition=first_definition, version=1, title="First layout",
            is_active=False, created_by=self.preparer,
            approved_by=self.reviewer, approved_at=timezone.now(),
        )
        with self.assertRaisesMessage(ValueError, "retained blank or redacted reference"):
            create_template_promotion(
                first, self.preparer, self.start, self.end, "pdf",
                "First official layout.", "Compared with local form.",
            )

    def test_department_views_and_tracesync_receipt(self):
        promotion = self._promotion()
        self.client.force_login(self.preparer)
        detail = self.client.get(promotion.get_absolute_url())
        self.assertContains(detail, "Preview and golden checks")
        self.assertContains(detail, "Activation impact")
        export = self.client.get(reverse("reporting:template_promotion_export", args=(promotion.public_id,)))
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export["X-GRAND-Export-Archived"], "true")
        receipt = json.loads(export.content)
        self.assertEqual(receipt["template_checksum"], promotion.template_checksum)
        self.assertTrue(list(Path(TEST_EXPORT_ROOT).rglob("*template-v2_promotion.json")))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(promotion.get_absolute_url()).status_code, 404)

    def test_template_creation_and_direct_validation_keep_candidate_inactive(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse("reporting:template_validate_fidelity", args=(self.candidate.pk,)),
            {"fidelity_notes": "This shortcut is retired."},
        )
        self.assertRedirects(
            response, reverse("reporting:template_promotion_create", args=(self.candidate.pk,)),
            fetch_redirect_response=False,
        )
        self.candidate.refresh_from_db()
        self.assertFalse(self.candidate.is_official_ready)
        self.assertFalse(self.candidate.is_active)

    def test_finance_roles_and_department_guides_separate_promotion_duties(self):
        budget_preparer = FINANCE_ROLE_PERMISSIONS["Budget Review and Consolidation Officer"]
        budget_approver = FINANCE_ROLE_PERMISSIONS["Budget Appropriation Authorizer"]
        config_manager = FINANCE_ROLE_PERMISSIONS["Finance Configuration Manager"]
        config_approver = FINANCE_ROLE_PERMISSIONS["Finance Configuration Approver"]
        self.assertIn("reporting.prepare_template_promotions", budget_preparer)
        self.assertIn("reporting.activate_template_promotions", budget_preparer)
        self.assertNotIn("reporting.approve_template_promotions", budget_preparer)
        self.assertIn("reporting.approve_template_promotions", budget_approver)
        self.assertIn("reporting.prepare_template_promotions", config_manager)
        self.assertIn("reporting.activate_template_promotions", config_manager)
        self.assertIn("reporting.approve_template_promotions", config_approver)
        accounting = next(item for item in ACCOUNTING_GUIDES if item["slug"] == "finance-accountability-reporting-accounting")
        budget = next(item for item in BUDGET_GUIDES if item["slug"] == "finance-accountability-reporting-budget")
        self.assertEqual(accounting["version"], 10)
        self.assertEqual(budget["version"], 6)
        self.assertIn("Promote a checked layout", {step[0] for step in accounting["steps"]})
        self.assertIn("Compare and promote the editable layout", {step[0] for step in budget["steps"]})
        self.assertIn("Accept the actual local form", {step[0] for step in accounting["steps"]})
        self.assertIn("Record local form acceptance", {step[0] for step in budget["steps"]})
