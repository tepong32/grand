from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from vouchers.roles import FINANCE_ROLE_PERMISSIONS

from .accountability_services import (
    create_package, create_package_successor, create_profile_successor,
    review_package, review_profile, select_source, submit_package, submit_profile,
)
from .models import (
    FinanceAccountabilityPackage, FinanceAccountabilityPackageProfile,
    FinanceAccountabilityPackageRequirement, FinanceAccountabilityPackageSelection,
    ReportDefinition, ReportRun, ReportTemplateVersion,
)


class FinanceAccountabilityPackageTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="f97-accounting")
        cls.budget = Department.objects.create(name="Municipal Budget Office", slug="f97-budget")
        cls.preparer = cls.employee(
            cls.accounting, "f97.package.preparer",
            "view_reporting_workspace", "prepare_accountability_packages",
            "export_accountability_packages",
        )
        cls.reviewer = cls.employee(
            cls.accounting, "f97.package.reviewer",
            "view_reporting_workspace", "review_accountability_packages",
            "export_accountability_packages",
        )
        cls.config_preparer = cls.employee(
            cls.accounting, "f97.profile.preparer",
            "view_reporting_workspace", "manage_accountability_package_profiles",
        )
        cls.config_approver = cls.employee(
            cls.accounting, "f97.profile.approver",
            "view_reporting_workspace", "approve_accountability_package_profiles",
        )
        cls.outsider = cls.employee(
            cls.budget, "f97.outsider", "view_reporting_workspace",
            "prepare_accountability_packages", "export_accountability_packages",
        )
        cls.definition = ReportDefinition.objects.create(
            department=cls.budget, name="Approved Budget Accountability Schedule",
            slug="f97-budget-accountability", dataset_key="synthetic_f97_budget",
            selected_fields=["reference", "amount"], totals=["amount"],
            default_format=ReportDefinition.FORMAT_PDF,
            applicability_status=ReportDefinition.APPLICABILITY_CONFIRMED,
            authority_reference="Synthetic reviewed DBM/COA authority.",
            local_acceptance_note="Accepted by named Budget and Accounting test owners.",
            created_by=cls.config_preparer, updated_by=cls.config_preparer,
        )
        now = timezone.now()
        cls.template = ReportTemplateVersion.objects.create(
            definition=cls.definition, version=1, title="Accepted budget schedule",
            render_mode=ReportTemplateVersion.RENDER_NATIVE,
            fidelity_status=ReportTemplateVersion.OFFICIAL,
            fidelity_notes="Synthetic layout accepted.", fidelity_validated_by=cls.config_approver,
            fidelity_validated_at=now, is_active=True, created_by=cls.config_preparer,
            approved_by=cls.config_approver, approved_at=now,
        )
        cls.run_one = cls.report_run("f97-budget-run-1", "1")
        cls.run_two = cls.report_run("f97-budget-run-2", "5")

    @classmethod
    def employee(cls, department, username, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="f97-test",
        )
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="reporting", codename__in=permissions,
        ))
        return user

    @classmethod
    def report_run(cls, key, seed):
        now = timezone.now()
        return ReportRun.objects.create(
            definition=cls.definition, template_version=cls.template, idempotency_key=key,
            status=ReportRun.APPROVED, output_format=ReportDefinition.FORMAT_PDF,
            period_start=date(2027, 1, 1), period_end=date(2027, 12, 31),
            checksum=seed * 64, dataset_checksum="2" * 64, control_checksum="3" * 64,
            control_status=ReportRun.CONTROL_RECONCILED, control_gate_required=True,
            reproduction_key=("4" if seed != "4" else "6") * 64,
            created_by=cls.config_preparer, reviewed_by=cls.config_approver,
            approved_by=cls.config_approver, generated_at=now, reviewed_at=now, approved_at=now,
        )

    def active_profile(self):
        profile = FinanceAccountabilityPackageProfile.objects.create(
            department=self.accounting, code="annual-accountability", version=1,
            name="Annual Finance Accountability Package",
            description="Synthetic human-editable annual evidence recipe.",
            authority_reference="Synthetic reviewed COA/DBM memorandum.",
            local_acceptance_note="Accepted by named Accounting and Budget test owners.",
            created_by=self.config_preparer,
        )
        FinanceAccountabilityPackageRequirement.objects.create(
            profile=profile, position=10, code="budget-schedule",
            label="Approved annual budget accountability schedule",
            evidence_kind=FinanceAccountabilityPackageRequirement.REPORT_RUN,
            source_department=self.budget, report_definition=self.definition,
            required=True, instructions="Choose the independently approved annual Budget schedule.",
        )
        submit_profile(profile, self.config_preparer)
        self.config_preparer.user_permissions.add(Permission.objects.get(codename="approve_accountability_package_profiles"))
        self.config_preparer = get_user_model().objects.get(pk=self.config_preparer.pk)
        with self.assertRaisesMessage(ValidationError, "preparer or submitter"):
            review_profile(profile, self.config_preparer, approve=True)
        review_profile(profile, self.config_approver, approve=True, note="Recipe independently checked.")
        profile.refresh_from_db()
        return profile

    def test_profile_successor_preserves_accepted_recipe_and_traceback(self):
        profile = self.active_profile()
        successor = create_profile_successor(
            profile, self.config_preparer, reason="Named office added a supplemental annual schedule.",
        )
        self.assertEqual(successor.version, 2)
        self.assertEqual(successor.supersedes, profile)
        self.assertEqual(successor.requirements.count(), 1)
        self.assertEqual(profile.status, FinanceAccountabilityPackageProfile.ACTIVE)
        self.assertEqual(successor.events.first().action, "successor_created")

    def test_package_replacement_approval_successor_and_tracesync_export(self):
        profile = self.active_profile()
        package = create_package(
            profile=profile, department=self.accounting, actor=self.preparer,
            title="FY 2027 Finance Accountability Package",
            period_start=date(2027, 1, 1), period_end=date(2027, 12, 31),
            preparation_note="Prepared from approved inter-office GRAND evidence.",
        )
        slot = package.slots.get()
        first = select_source(slot, self.preparer, source_public_id=self.run_one.public_id)
        with self.assertRaisesMessage(ValidationError, "Explain why"):
            select_source(slot, self.preparer, source_public_id=self.run_two.public_id)
        second = select_source(
            slot, self.preparer, source_public_id=self.run_two.public_id,
            reason="The first approved run used the earlier signed cover sheet.",
        )
        first.refresh_from_db()
        self.assertEqual(first.status, FinanceAccountabilityPackageSelection.SUPERSEDED)
        self.assertEqual(second.supersedes, first)
        self.assertEqual(second.version, 2)

        submit_package(package, self.preparer)
        self.preparer.user_permissions.add(Permission.objects.get(codename="review_accountability_packages"))
        self.preparer = get_user_model().objects.get(pk=self.preparer.pk)
        with self.assertRaisesMessage(ValidationError, "preparer or submitter"):
            review_package(package, self.preparer, approve=True)
        review_package(package, self.reviewer, approve=True, note="Every source and checksum independently checked.")
        package.refresh_from_db()
        self.assertEqual(package.status, FinanceAccountabilityPackage.APPROVED)
        self.assertEqual(len(package.package_checksum), 64)

        self.client.force_login(self.preparer)
        detail = self.client.get(package.get_absolute_url())
        self.assertContains(detail, "Audit and traceback")
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=Path(export_root)):
            response = self.client.get(reverse(
                "reporting:accountability_package_export", args=(package.public_id,),
            ))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            manifest = json.loads(response.content)
            self.assertEqual(manifest["integrity"]["package_sha256"], package.package_checksum)
            self.assertEqual(manifest["package"]["slots"][0]["selection"]["source_public_id"], str(self.run_two.public_id))
            self.assertTrue((Path(export_root) / "GRAND_EXPORT_ROOT.json").exists())

        successor = create_package_successor(
            package, self.preparer, reason="User selected the wrong signed cover-sheet run.",
        )
        self.assertEqual(successor.supersedes, package)
        self.assertEqual(successor.version, 2)
        self.assertEqual(successor.status, FinanceAccountabilityPackage.DRAFT)
        self.assertEqual(package.status, FinanceAccountabilityPackage.APPROVED)
        copied = successor.slots.get().current_selection
        self.assertEqual(copied.source_public_id, self.run_two.public_id)
        select_source(
            successor.slots.get(), self.preparer, source_public_id=self.run_one.public_id,
            reason="Corrected to the locally signed approved run.",
        )
        submit_package(successor, self.preparer)
        review_package(successor, self.reviewer, approve=True, note="Correction independently checked.")
        package.refresh_from_db()
        successor.refresh_from_db()
        self.assertEqual(package.status, FinanceAccountabilityPackage.SUPERSEDED)
        self.assertEqual(successor.status, FinanceAccountabilityPackage.APPROVED)
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=Path(export_root)):
            historical_export = self.client.get(reverse(
                "reporting:accountability_package_export", args=(package.public_id,),
            ))
            self.assertEqual(historical_export.status_code, 200)
            self.assertEqual(json.loads(historical_export.content)["workflow"]["status"], "superseded")

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(successor.get_absolute_url()).status_code, 404)

    def test_finance_roles_separate_profile_and_package_duties(self):
        config_preparer = FINANCE_ROLE_PERMISSIONS["Finance Configuration Manager"]
        config_approver = FINANCE_ROLE_PERMISSIONS["Finance Configuration Approver"]
        package_preparer = FINANCE_ROLE_PERMISSIONS["Accounting DV Preparer"]
        package_reviewer = FINANCE_ROLE_PERMISSIONS["Accounting Reviewer"]
        self.assertIn("reporting.manage_accountability_package_profiles", config_preparer)
        self.assertNotIn("reporting.approve_accountability_package_profiles", config_preparer)
        self.assertIn("reporting.approve_accountability_package_profiles", config_approver)
        self.assertIn("reporting.prepare_accountability_packages", package_preparer)
        self.assertNotIn("reporting.review_accountability_packages", package_preparer)
        self.assertIn("reporting.review_accountability_packages", package_reviewer)

    def _assert_profile_return_denied(self, actor):
        profile = self.active_profile()
        successor = create_profile_successor(profile, self.config_preparer, reason="Reviewed recipe correction")
        submit_profile(successor, self.config_preparer)
        before = successor.events.count()
        with self.assertRaises(PermissionDenied):
            review_profile(successor, actor, approve=False, note="Correction required")
        successor.refresh_from_db()
        self.assertEqual(successor.status, FinanceAccountabilityPackageProfile.SUBMITTED)
        self.assertEqual(successor.events.count(), before)

    def test_uat_cannot_review_accountability_profile(self):
        from django.contrib.auth.models import Group
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        # Build the submitted fixture before adding preview membership.
        profile = self.active_profile()
        successor = create_profile_successor(profile, self.config_preparer, reason="Recipe correction")
        submit_profile(successor, self.config_preparer)
        self.config_approver.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            review_profile(successor, self.config_approver, approve=False, note="Preview return")
        successor.refresh_from_db()
        self.assertEqual(successor.status, FinanceAccountabilityPackageProfile.SUBMITTED)

    def test_foreign_office_cannot_review_accountability_profile(self):
        self.outsider.user_permissions.add(Permission.objects.get(codename="approve_accountability_package_profiles"))
        self._assert_profile_return_denied(self.outsider)

    def test_accountability_mutations_use_stored_package_office(self):
        profile = self.active_profile()
        package = create_package(profile=profile, department=self.accounting, actor=self.preparer,
                                 title="Office-bound package", period_start=date(2027, 1, 1), period_end=date(2027, 12, 31))
        slot = package.slots.get()
        self.outsider.user_permissions.add(*Permission.objects.filter(codename__in=(
            "manage_accountability_package_profiles", "approve_accountability_package_profiles", "review_accountability_packages",
        )))
        profile.department = self.budget
        package.department = self.budget
        slot.package.department = self.budget
        calls = (
            lambda: submit_profile(profile, self.outsider),
            lambda: review_profile(profile, self.outsider, approve=False, note="Foreign review"),
            lambda: create_profile_successor(profile, self.outsider, reason="Foreign successor"),
            lambda: create_package(profile=profile, department=self.budget, actor=self.outsider,
                                   title="Foreign package", period_start=date(2027, 1, 1), period_end=date(2027, 12, 31)),
            lambda: select_source(slot, self.outsider, source_public_id=self.run_one.public_id),
            lambda: submit_package(package, self.outsider),
            lambda: review_package(package, self.outsider, approve=False, note="Foreign review"),
            lambda: create_package_successor(package, self.outsider, reason="Foreign successor"),
        )
        before = (profile.events.count(), package.events.count())
        for index, call in enumerate(calls):
            with self.subTest(entry_point=index), self.assertRaises(PermissionDenied):
                call()
        profile.refresh_from_db()
        package.refresh_from_db()
        self.assertEqual(profile.department, self.accounting)
        self.assertEqual(package.department, self.accounting)
        self.assertEqual((profile.events.count(), package.events.count()), before)
        self.assertFalse(slot.selections.exists())

    def test_ungranted_actor_cannot_review_accountability_profile(self):
        observer = self.employee(self.accounting, "package.observer", "view_reporting_workspace")
        self._assert_profile_return_denied(observer)

    def test_uat_package_pages_keep_read_export_and_hide_mutations(self):
        from django.contrib.auth.models import Group
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        profile = self.active_profile()
        package = create_package(profile=profile, department=self.accounting, actor=self.preparer,
                                 title="Preview package", period_start=date(2027, 1, 1), period_end=date(2027, 12, 31))
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.preparer)
        detail = self.client.get(reverse("reporting:accountability_package_detail", args=(package.public_id,)))
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.context["can_prepare"])
        self.assertFalse(detail.context["can_review"])
        self.assertTrue(detail.context["can_export"])
        self.assertEqual(self.client.post(reverse("reporting:accountability_package_submit", args=(package.public_id,))).status_code, 403)

    def test_uat_profile_manager_retains_workspace_navigation_without_export(self):
        from django.contrib.auth.models import Group
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        self.config_preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.config_preparer)
        response = self.client.get(reverse("reporting:workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["accountability_packages_enabled"])


    def work_rows(self, actor, record, view="ready"):
        from finance.work_tasks import finance_work_tasks
        kind = "profile" if isinstance(record, FinanceAccountabilityPackageProfile) else "package"
        return [row for row in finance_work_tasks(actor, view=view)["tasks"]
                if row["case_id"] == f"accountability-{kind}:{record.public_id}"]

    def test_profile_personal_handoffs_match_independent_source_lifecycle(self):
        from .accountability_register import accountability_action_queryset
        profile = create_profile_successor(self.active_profile(), self.config_preparer, reason="Reviewed recipe correction")
        self.assertEqual(len(self.work_rows(self.config_preparer, profile)), 1)
        submit_profile(profile, self.config_preparer)
        self.assertEqual(len(self.work_rows(self.config_preparer, profile, "waiting")), 1)
        self.assertFalse(accountability_action_queryset(self.config_preparer, "profile_review").filter(pk=profile.pk).exists())
        self.assertEqual(self.work_rows(self.config_preparer, profile), [])
        review_rows = self.work_rows(self.config_approver, profile)
        self.assertEqual(len(review_rows), 1)
        self.client.force_login(self.config_approver)
        self.assertEqual(self.client.get(review_rows[0]["url"]).status_code, 200)
        review_profile(profile, self.config_approver, approve=False, note="Clarify recipe wording.")
        self.assertEqual(self.work_rows(self.config_preparer, profile)[0]["state"], "Returned")
        self.assertEqual(self.work_rows(self.config_preparer, profile, "waiting"), [])
        submit_profile(profile, self.config_preparer)
        self.assertEqual(len(self.work_rows(self.config_preparer, profile, "completed")), 2)
        review_profile(profile, self.config_approver, approve=True, note="Recipe independently accepted.")
        self.assertEqual(self.work_rows(self.config_preparer, profile, "waiting"), [])
        self.assertEqual(len(self.work_rows(self.config_approver, profile, "completed")), 2)

    def test_package_personal_handoffs_preserve_cross_office_evidence_and_history(self):
        profile = self.active_profile()
        package = create_package(profile=profile, department=self.accounting, actor=self.preparer,
                                 title="Personal accountability package", period_start=date(2027, 1, 1), period_end=date(2027, 12, 31))
        self.assertEqual(self.work_rows(self.preparer, package)[0]["state"], "Exception")
        select_source(package.slots.get(), self.preparer, source_public_id=self.run_one.public_id)
        self.assertEqual(self.work_rows(self.preparer, package)[0]["state"], "Ready")
        submit_package(package, self.preparer)
        self.preparer.user_permissions.add(Permission.objects.get(codename="review_accountability_packages"))
        self.preparer = get_user_model().objects.get(pk=self.preparer.pk)
        self.assertEqual(self.work_rows(self.preparer, package), [])
        self.assertEqual(len(self.work_rows(self.preparer, package, "waiting")), 1)
        self.assertEqual(self.work_rows(self.reviewer, package, "waiting"), [])
        self.assertEqual(len(self.work_rows(self.reviewer, package)), 1)
        self.assertEqual(self.work_rows(self.outsider, package), [])
        review_package(package, self.reviewer, approve=False, note="Clarify the preparation note.")
        self.assertEqual(self.work_rows(self.preparer, package, "returned")[0]["state"], "Returned")
        submit_package(package, self.preparer)
        review_package(package, self.reviewer, approve=True, note="Cross-office approved evidence checked.")
        self.assertEqual(self.work_rows(self.preparer, package, "waiting"), [])
        prior_history = self.work_rows(self.preparer, package, "completed")
        self.assertEqual(len(prior_history), 2)
        successor = create_package_successor(package, self.preparer, reason="Corrected cover sheet")
        submit_package(successor, self.preparer)
        review_package(successor, self.reviewer, approve=True, note="Successor checked.")
        history = self.work_rows(self.preparer, package, "completed")
        self.assertEqual([row["task_id"] for row in history], [row["task_id"] for row in prior_history])
        self.assertNotEqual(history[0]["source_version"], prior_history[0]["source_version"])
        self.assertEqual(len(self.work_rows(self.reviewer, package, "completed")), 2)

    def test_accountability_work_views_recheck_read_scope_and_uat(self):
        from django.contrib.auth.models import Group
        from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
        profile = self.active_profile()
        package = create_package(profile=profile, department=self.accounting, actor=self.preparer,
                                 title="Scoped package", period_start=date(2027, 1, 1), period_end=date(2027, 12, 31))
        select_source(package.slots.get(), self.preparer, source_public_id=self.run_one.public_id)
        submit_package(package, self.preparer)
        group = Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0]
        self.preparer.groups.add(group)
        for view in ("ready", "waiting", "completed"):
            self.assertEqual(self.work_rows(self.preparer, package, view), [])
            self.assertEqual(self.work_rows(self.outsider, package, view), [])
        self.preparer.groups.remove(group)
        self.preparer.user_permissions.remove(Permission.objects.get(codename="view_reporting_workspace"))
        actor = get_user_model().objects.get(pk=self.preparer.pk)
        for view in ("ready", "waiting", "completed"):
            self.assertEqual(self.work_rows(actor, package, view), [])

    def test_package_review_task_explains_changed_pinned_evidence(self):
        profile = self.active_profile()
        package = create_package(profile=profile, department=self.accounting, actor=self.preparer,
                                 title="Drifted package", period_start=date(2027, 1, 1), period_end=date(2027, 12, 31))
        select_source(package.slots.get(), self.preparer, source_public_id=self.run_one.public_id)
        submit_package(package, self.preparer)
        before = self.work_rows(self.reviewer, package)[0]
        FinanceAccountabilityPackage.objects.filter(pk=package.pk).update(package_checksum="0" * 64)
        changed = self.work_rows(self.reviewer, package)[0]
        self.assertEqual(changed["task_id"], before["task_id"])
        self.assertNotEqual(changed["source_version"], before["source_version"])
        self.assertEqual(changed["state"], "Exception")
        with self.assertRaises(ValidationError):
            review_package(package, self.reviewer, approve=True, note="Must reject drift.")
        review_package(package, self.reviewer, approve=False, note="Return for evidence correction.")
