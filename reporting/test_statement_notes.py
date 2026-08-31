from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from departments.services.internal_howto_seed import ACCOUNTING_GUIDES
from vouchers.roles import FINANCE_ROLE_PERMISSIONS

from .models import (
    FinanceStatementNoteSet, ReportDefinition, ReportReferenceComparison, ReportRun,
    ReportTemplateVersion,
)
from .statement_services import (
    create_note_set, review_note_set, review_reference_comparison, submit_note_set,
    submit_reference_comparison,
)


STATEMENT_MEDIA_ROOT = tempfile.mkdtemp(prefix="grand-statement-notes-tests-")


@override_settings(MEDIA_ROOT=STATEMENT_MEDIA_ROOT)
class StatementNotesAndReferenceComparisonTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(
            name="Municipal Accounting Office", slug="f94-accounting",
        )
        cls.outside_department = Department.objects.create(
            name="Municipal Budget Office", slug="f94-budget",
        )
        cls.preparer = cls.employee(
            cls.department, "f94.notes.preparer",
            "view_reporting_workspace", "view_department_reports",
            "prepare_statement_notes", "prepare_reference_comparisons",
            "export_statement_packages",
        )
        cls.reviewer = cls.employee(
            cls.department, "f94.notes.reviewer",
            "view_reporting_workspace", "view_department_reports",
            "review_statement_notes", "review_reference_comparisons",
            "export_statement_packages",
        )
        cls.outsider = cls.employee(
            cls.outside_department, "f94.outsider", "view_reporting_workspace",
            "prepare_statement_notes", "prepare_reference_comparisons",
            "export_statement_packages",
        )
        cls.department.deptHead_or_oic = cls.reviewer
        cls.department.save(update_fields=("deptHead_or_oic",))

        cls.position_definition = cls.definition(
            "Management Statement of Financial Position", "f94-position",
            "finance_statement_position", cls.preparer,
        )
        cls.performance_definition = cls.definition(
            "Management Statement of Financial Performance", "f94-performance",
            "finance_statement_performance", cls.preparer,
        )
        cls.position_run = cls.statement_run(
            cls.position_definition, cls.preparer, cls.reviewer,
            {
                "assets": "1250.00", "liabilities": "0.00", "equity": "0.00",
                "unclosed_operating_result": "1250.00", "equation_difference": "0.00",
            },
            (("cash", "Cash and cash equivalents"), ("equity", "Accumulated surplus")),
        )
        cls.performance_run = cls.statement_run(
            cls.performance_definition, cls.preparer, cls.reviewer,
            {"revenue": "1250.00", "expense": "0.00", "operating_result": "1250.00"},
            (("revenue", "Revenue"), ("expense", "Expense")),
        )

    @classmethod
    def employee(cls, department, username, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="statement-test",
        )
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="reporting", codename__in=permissions,
        ))
        return user

    @classmethod
    def definition(cls, name, slug, dataset_key, actor):
        definition = ReportDefinition.objects.create(
            department=cls.department, name=name, slug=slug,
            description="Synthetic governed statement for F9.4 tests.",
            dataset_key=dataset_key, selected_fields=["line_title", "amount"],
            totals=["amount"], default_format=ReportDefinition.FORMAT_XLSX,
            applicability_status=ReportDefinition.APPLICABILITY_CONFIRMED,
            authority_reference="Synthetic reviewed COA/local statement authority.",
            local_acceptance_note="Accepted for synthetic test by named Accounting owner.",
            created_by=actor, updated_by=actor,
        )
        now = timezone.now()
        ReportTemplateVersion.objects.create(
            definition=definition, version=1, title=f"{name} synthetic accepted template",
            render_mode=ReportTemplateVersion.RENDER_NATIVE,
            fidelity_status=ReportTemplateVersion.OFFICIAL,
            fidelity_notes="Synthetic signed-reference and layout comparison passed.",
            fidelity_validated_by=actor, fidelity_validated_at=now,
            is_active=True, created_by=actor, approved_by=actor, approved_at=now,
        )
        return definition

    @classmethod
    def statement_run(cls, definition, preparer, reviewer, totals, lines):
        now = timezone.now()
        return ReportRun.objects.create(
            definition=definition, template_version=definition.current_template,
            idempotency_key=f"f94:{definition.slug}", status=ReportRun.APPROVED,
            output_format=ReportDefinition.FORMAT_XLSX,
            period_start=date(2027, 1, 1), period_end=date(2027, 12, 31),
            parameters={
                "_definition_snapshot": {
                    "dataset_key": definition.dataset_key,
                    "applicability_status": ReportDefinition.APPLICABILITY_CONFIRMED,
                },
                "_statement_mapping_snapshot": {
                    "version": 1, "status": "active",
                    "lines": [
                        {"line_code": code, "line_title": title} for code, title in lines
                    ],
                },
            },
            checksum="1" * 64, dataset_checksum="2" * 64,
            control_totals=totals, control_checksum="3" * 64,
            control_status=ReportRun.CONTROL_RECONCILED, control_gate_required=True,
            reproduction_key="4" * 64, created_by=preparer,
            reviewed_by=reviewer, reviewed_at=now, approved_by=reviewer,
            approved_at=now, generated_at=now,
        )

    def make_note_set(self, *, confirmed=False):
        note_set = create_note_set(
            department=self.department, position_run=self.position_run,
            performance_run=self.performance_run, actor=self.preparer,
            data={
                "title": "Synthetic FY 2027 notes",
                "applicability_status": (
                    FinanceStatementNoteSet.CONFIRMED if confirmed else FinanceStatementNoteSet.CANDIDATE
                ),
                "preparation_note": "Prepared from retained synthetic schedules.",
                "authority_reference": "Synthetic reviewed COA/local note authority." if confirmed else "",
                "local_acceptance_note": "Accepted by named synthetic Accounting owner." if confirmed else "",
            },
        )
        for item in note_set.notes.all():
            item.disclosure_text = f"Synthetic disclosure for {item.title}."
            item.source_reference = "F94-SYNTHETIC-SCHEDULE"
            item.authority_basis = "Candidate topic; applicability reviewed for synthetic UAT."
            item.save()
        return note_set

    def comparison(self, *, mismatch=False):
        values = {
            "assets": "1251.00" if mismatch else "1250.00",
            "liabilities": "0.00", "equity": "0.00",
            "unclosed_operating_result": "1250.00", "equation_difference": "0.00",
        }
        return ReportReferenceComparison.objects.create(
            run=self.position_run, version=(2 if mismatch else 1),
            reference_label=("Mismatched signed copy" if mismatch else "Redacted signed FY 2027 position statement"),
            reference_kind=ReportReferenceComparison.REFERENCE_PDF,
            reference_file=SimpleUploadedFile(
                "signed-reference.pdf", b"%PDF-1.4\nsynthetic redacted signed comparison\n%%EOF",
                content_type="application/pdf",
            ),
            signed_copy=True, redaction_confirmed=True,
            authority_reference="Synthetic reviewed statement authority.",
            local_acceptance_note="Named Accounting owner retained the redacted signed comparison.",
            reference_values=values, created_by=self.preparer,
        )

    def test_candidate_note_topics_require_completion_and_independent_working_review(self):
        note_set = create_note_set(
            department=self.department, position_run=self.position_run,
            performance_run=self.performance_run, actor=self.preparer,
            data={"title": "Candidate FY 2027 notes", "applicability_status": FinanceStatementNoteSet.CANDIDATE},
        )
        self.assertEqual(note_set.notes.count(), 11)
        with self.assertRaisesMessage(ValidationError, "disclosure"):
            submit_note_set(note_set, self.preparer)
        for item in note_set.notes.all():
            item.disclosure_text = f"Synthetic working disclosure for {item.title}."
            item.save()
        submit_note_set(note_set, self.preparer)
        note_set.refresh_from_db()
        self.assertEqual(len(note_set.snapshot_checksum), 64)
        self.assertEqual(note_set.source_snapshot["position_run"]["reproduction_key"], "4" * 64)
        with self.assertRaisesMessage(ValidationError, "preparer or submitter"):
            review_note_set(note_set, self.preparer, action="accept_working")
        review_note_set(note_set, self.reviewer, action="accept_working", note="Working disclosures checked.")
        note_set.refresh_from_db()
        self.assertEqual(note_set.status, FinanceStatementNoteSet.REVIEWED)
        note = note_set.notes.first()
        note.disclosure_text = "Silent rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            note.save()

    def test_locally_confirmed_notes_require_official_runs_and_detect_post_submit_drift(self):
        note_set = self.make_note_set(confirmed=True)
        submit_note_set(note_set, self.preparer)
        note_set.notes.filter(topic_code="revenue").update(disclosure_text="Database drift after submission")
        with self.assertRaisesMessage(ValidationError, "changed after submission"):
            review_note_set(note_set, self.reviewer, action="approve")

        successor = self.make_note_set(confirmed=True)
        submit_note_set(successor, self.preparer)
        review_note_set(successor, self.reviewer, action="approve", note="Official synthetic note package checked.")
        successor.refresh_from_db()
        self.assertEqual(successor.status, FinanceStatementNoteSet.APPROVED)
        self.assertTrue(successor.position_run.is_official_output)
        self.assertEqual(successor.reviewed_by, self.reviewer)

    def test_signed_reference_comparison_reconciles_exact_controls_and_rejects_difference(self):
        comparison = self.comparison()
        submit_reference_comparison(comparison, self.preparer)
        comparison.refresh_from_db()
        self.assertEqual(comparison.comparison_result, ReportReferenceComparison.RESULT_RECONCILED)
        self.assertEqual(comparison.differences["assets"], "0.00")
        self.assertEqual(len(comparison.reference_file_checksum), 64)
        self.assertEqual(len(comparison.snapshot_checksum), 64)
        with self.assertRaisesMessage(ValidationError, "preparer or submitter"):
            review_reference_comparison(comparison, self.preparer, approve=True)
        review_reference_comparison(
            comparison, self.reviewer, approve=True, note="Exact totals and checksums checked independently.",
        )
        comparison.refresh_from_db()
        self.assertEqual(comparison.status, ReportReferenceComparison.RECONCILED)
        comparison.reference_label = "Silent rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            comparison.save()

        mismatch = self.comparison(mismatch=True)
        submit_reference_comparison(mismatch, self.preparer)
        mismatch.refresh_from_db()
        self.assertEqual(mismatch.comparison_result, ReportReferenceComparison.RESULT_EXCEPTION)
        self.assertEqual(mismatch.differences["assets"], "1.00")
        with self.assertRaisesMessage(ValidationError, "zero-difference"):
            review_reference_comparison(mismatch, self.reviewer, approve=True)
        review_reference_comparison(
            mismatch, self.reviewer, approve=False, note="Reference assets differ by 1.00.",
        )
        mismatch.refresh_from_db()
        self.assertEqual(mismatch.status, ReportReferenceComparison.RETURNED)

    def test_department_scoped_workspace_howto_and_tracesync_exports(self):
        note_set = self.make_note_set()
        submit_note_set(note_set, self.preparer)
        review_note_set(note_set, self.reviewer, action="accept_working")
        comparison = self.comparison()
        submit_reference_comparison(comparison, self.preparer)
        review_reference_comparison(comparison, self.reviewer, approve=True)
        comparison.refresh_from_db()

        self.client.force_login(self.preparer)
        workspace = self.client.get(reverse("reporting:workspace"))
        self.assertEqual(workspace.status_code, 200)
        self.assertContains(workspace, "Statement notes")
        notes_list = self.client.get(reverse("reporting:statement_note_set_list"))
        self.assertContains(notes_list, "How to prepare statement notes")
        self.assertEqual(self.client.get(reverse("reporting:statement_note_set_create")).status_code, 200)
        comparison_form = self.client.get(reverse(
            "reporting:reference_comparison_create", args=(self.position_run.public_id,),
        ))
        self.assertContains(comparison_form, "Reference total — Assets")
        note_page = self.client.get(note_set.get_absolute_url())
        self.assertEqual(note_page.status_code, 200)
        self.assertContains(note_page, "Pinned statements")
        comparison_page = self.client.get(comparison.get_absolute_url())
        self.assertContains(comparison_page, "Exact control comparison")

        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=Path(export_root)):
            note_export = self.client.get(reverse("reporting:statement_note_set_export", args=(note_set.public_id,)))
            comparison_export = self.client.get(reverse("reporting:reference_comparison_export", args=(comparison.public_id,)))
            self.assertEqual(note_export["X-GRAND-Export-Archived"], "true")
            self.assertEqual(comparison_export["X-GRAND-Export-Archived"], "true")
            parsed = json.loads(comparison_export.content)
            self.assertEqual(parsed["integrity"]["comparison_sha256"], comparison.snapshot_checksum)
            root = Path(export_root)
            self.assertTrue((root / "GRAND_EXPORT_ROOT.json").exists())
            self.assertEqual(len(list(root.rglob("*.manifest.json"))), 2)

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(note_set.get_absolute_url()).status_code, 403)
        self.assertEqual(self.client.get(comparison.get_absolute_url()).status_code, 403)

    def test_finance_roles_keep_note_and_comparison_duties_separated(self):
        preparer = FINANCE_ROLE_PERMISSIONS["Accounting DV Preparer"]
        reviewer = FINANCE_ROLE_PERMISSIONS["Accounting Reviewer"]
        self.assertIn("reporting.prepare_statement_notes", preparer)
        self.assertIn("reporting.prepare_reference_comparisons", preparer)
        self.assertNotIn("reporting.review_statement_notes", preparer)
        self.assertIn("reporting.review_statement_notes", reviewer)
        self.assertIn("reporting.review_reference_comparisons", reviewer)
        self.assertNotIn("reporting.prepare_statement_notes", reviewer)
        guide = next(item for item in ACCOUNTING_GUIDES if item["slug"] == "finance-accountability-reporting-accounting")
        self.assertEqual(guide["version"], 4)
        self.assertIn("Prepare the statement notes", {step[0] for step in guide["steps"]})
        self.assertIn("Compare a signed reference safely", {step[0] for step in guide["steps"]})


def tearDownModule():
    shutil.rmtree(STATEMENT_MEDIA_ROOT, ignore_errors=True)
