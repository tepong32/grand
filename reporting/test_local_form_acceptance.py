from __future__ import annotations

import csv
import io
import json
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
from django.utils.text import slugify

from departments.models import Department
from finance.models import FinanceConfigurationRelease, FinanceTemplateVersion
from finance.services import build_finance_starter_workbook, preflight_finance_template
from vouchers.roles import FINANCE_ROLE_PERMISSIONS

from .form_acceptance_services import (
    checksum, create_local_form_from_starter, create_local_form_successor,
    file_checksum, form_snapshot, local_form_export_manifest, record_test_attempt,
    review_local_form, review_test_attempt, source_snapshot, submit_local_form,
    validate_local_form,
)
from .forms import FinanceLocalFormSectionForm
from .local_form_starters import DBM_FORM_STARTERS
from .models import (
    FinanceLocalFormAcceptance, FinanceLocalFormEvent, FinanceLocalFormSection,
    FinanceLocalFormTestAttempt,
    ReportDefinition, ReportRun, ReportTemplatePromotion, ReportTemplateVersion,
)
from .template_services import template_snapshot


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="grand-local-form-media-")
TEST_EXPORT_ROOT = tempfile.mkdtemp(prefix="grand-local-form-export-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT, GRAND_EXPORT_ROOT=TEST_EXPORT_ROOT)
class FinanceLocalFormAcceptanceTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.department = Department.objects.create(name="Municipal Accounting Office", slug="f102-accounting")
        cls.other_department = Department.objects.create(name="Municipal Budget Office", slug="f102-budget")
        cls.preparer = cls.employee(
            cls.department, "f102.form.preparer", "view_reporting_workspace",
            "manage_local_form_acceptance", "export_local_form_acceptance",
        )
        cls.witness = cls.employee(
            cls.department, "f102.form.witness", "view_reporting_workspace",
            "witness_local_form_tests", "review_local_form_acceptance",
            "export_local_form_acceptance",
        )
        cls.outsider = cls.employee(
            cls.other_department, "f102.form.outsider", "view_reporting_workspace",
            "manage_local_form_acceptance", "export_local_form_acceptance",
        )
        cls.preparer.user_permissions.add(Permission.objects.get(
            content_type__app_label="finance", codename="manage_finance_templates",
        ))
        cls.definition = ReportDefinition.objects.create(
            department=cls.department, name="Locally Reviewed Annual Statement",
            slug="f102-annual-statement", dataset_key="synthetic_f102",
            selected_fields=["reference", "amount"], totals=["amount"],
            default_format=ReportDefinition.FORMAT_PDF,
            applicability_status=ReportDefinition.APPLICABILITY_CONFIRMED,
            authority_reference="Synthetic reviewed local authority.",
            local_acceptance_note="Synthetic named-office acceptance.",
            created_by=cls.preparer, updated_by=cls.preparer,
        )
        now = timezone.now()
        cls.template = ReportTemplateVersion.objects.create(
            definition=cls.definition, version=1, title="Exact annual statement layout",
            fidelity_status=ReportTemplateVersion.OFFICIAL,
            fidelity_notes="Synthetic exact-layout comparison.",
            fidelity_validated_by=cls.witness, fidelity_validated_at=now,
            is_active=True, created_by=cls.preparer,
            approved_by=cls.witness, approved_at=now,
        )
        cls.preview_run = ReportRun.objects.create(
            definition=cls.definition, template_version=cls.template,
            idempotency_key="f102-preview", status=ReportRun.APPROVED,
            output_format=ReportDefinition.FORMAT_PDF,
            period_start=date(2027, 1, 1), period_end=date(2027, 12, 31),
            checksum="1" * 64, dataset_checksum="2" * 64,
            control_checksum="3" * 64, reproduction_key="4" * 64,
            control_status=ReportRun.CONTROL_RECONCILED,
            created_by=cls.preparer, reviewed_by=cls.witness,
            approved_by=cls.witness, generated_at=now, reviewed_at=now, approved_at=now,
        )
        snapshot = template_snapshot(cls.template)
        cls.promotion = ReportTemplatePromotion.objects.create(
            candidate_template=cls.template, preview_run=cls.preview_run,
            status=ReportTemplatePromotion.ACTIVATED,
            change_reason="Match the exact retained local form.",
            comparison_note="Synthetic side-by-side form and printer comparison.",
            template_snapshot=snapshot, template_checksum=checksum(snapshot),
            mapping_diff=[], impact_snapshot={},
            golden_result=ReportTemplatePromotion.GOLDEN_MATCHED,
            golden_snapshot={"all_checks_passed": True}, submission_checksum="6" * 64,
            created_by=cls.preparer, submitted_by=cls.preparer, submitted_at=now,
            reviewed_by=cls.witness, reviewed_at=now, review_note="Independently reviewed.",
            activated_by=cls.witness, activated_at=now,
        )

    @classmethod
    def employee(cls, department, username, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="f102-test",
        )
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="reporting", codename__in=permissions,
        ))
        return user

    def local_form(self, code="annual-statement"):
        item = FinanceLocalFormAcceptance.objects.create(
            department=self.department, code=code, version=1,
            name="Annual Financial Statement Form", form_number="Local Form A-1",
            purpose="Prepare the annual signed Accounting statement packet.",
            source_type=FinanceLocalFormAcceptance.SOURCE_REPORT,
            report_template=self.template,
            authority_reference="Synthetic current COA/local procedure reference.",
            local_acceptance_note="Synthetic Accountant and Records acceptance record F102-001.",
            reference_kind="pdf",
            reference_file=SimpleUploadedFile(
                f"{code}.pdf", b"%PDF-1.4\nsynthetic safely redacted blank form\n%%EOF",
                content_type="application/pdf",
            ),
            delivery_mode=FinanceLocalFormAcceptance.DELIVERY_BOTH,
            signatory_instructions="Prepared by, reviewed by, and approved by named roles in that order.",
            default_copy_count=3,
            recipient_instructions="Accounting original, Records copy, and management copy with receipt.",
            deadline_instructions="Complete under the retained locally reviewed annual reporting calendar.",
            retention_instructions="Retain under the Accounting/Records file plan with restricted signed copies.",
            paper_size="A4", orientation="Portrait",
            form_stock="Plain white A4, 80 gsm.",
            printer_instructions="Office laser printer, A4 tray, actual size, simplex.",
            pagination_instructions="Number every page and repeat the statement heading on continuation pages.",
            overflow_instructions="Move excess lines to a numbered continuation page without shrinking text.",
            accessibility_instructions="Use readable labels/order and provide an accessible PDF download.",
            created_by=self.preparer,
        )
        FinanceLocalFormSection.objects.create(
            form=item, position=10, code="statement-lines", label="Statement line items",
            requirement_type=FinanceLocalFormSection.REPEATING,
            row_instructions="Use up to 30 rows per page, then a numbered continuation page.",
        )
        FinanceLocalFormSection.objects.create(
            form=item, position=20, code="supplemental-disclosure", label="Supplemental disclosure",
            requirement_type=FinanceLocalFormSection.CONDITIONAL,
            applicability_instructions="The Municipal Accountant decides from the retained disclosure checklist.",
        )
        return item

    def pass_all_tests(self, item):
        attempts = []
        for index, (category, _label) in enumerate(FinanceLocalFormTestAttempt.CATEGORY_CHOICES, start=1):
            attempt = record_test_attempt(
                item, self.preparer, category=category,
                test_steps=f"Performed the actual {category} test with a redacted annual sample.",
                expected_result="The exact accepted form behavior is reproduced without control differences.",
                observed_result="Observed result matched the retained comparison and readable procedure.",
                environment="Windows workstation, supported browser, PDF, office printer and A4 stock where applicable.",
                evidence_reference=f"Retained redacted F102 test packet category {index}.",
                evidence_checksum=f"{index:x}" * 64,
            )
            review_test_attempt(
                attempt, self.witness, action="pass",
                note="Independently witnessed the steps, output, and retained evidence hash.",
            )
            attempts.append(attempt)
        return attempts

    def test_full_acceptance_export_successor_and_historical_reproduction(self):
        item = self.local_form()
        self.pass_all_tests(item)
        submit_local_form(item, self.preparer)
        with self.assertRaisesMessage(ValidationError, "preparer or submitter"):
            review_local_form(item, self.preparer, approve=True, note="Self acceptance.")
        review_local_form(
            item, self.witness, approve=True,
            note="Exact template, blank form, practical tests, routing, and custody independently accepted.",
        )
        item.refresh_from_db()
        self.assertEqual(item.status, FinanceLocalFormAcceptance.ACCEPTED)
        self.assertEqual(len(item.submission_checksum), 64)
        item.status = FinanceLocalFormAcceptance.DRAFT
        with self.assertRaisesMessage(ValidationError, "cannot move"):
            item.save()
        item.refresh_from_db()
        packet = local_form_export_manifest(item)
        self.assertEqual(packet["schema_version"], 2)
        self.assertEqual(packet["integrity"]["submission_sha256"], item.submission_checksum)
        self.assertEqual(len(packet["form"]["latest_witnessed_tests"]), 7)

        self.client.force_login(self.preparer)
        response = self.client.get(reverse("reporting:local_form_export", args=(item.public_id,)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-GRAND-Export-Archived"], "true")
        self.assertTrue(list(Path(TEST_EXPORT_ROOT).rglob("*local-form_annual-statement_v1*.json")))
        packet_after_export = local_form_export_manifest(item)
        self.assertEqual(packet, packet_after_export)

        successor = create_local_form_successor(
            item, self.preparer, reason="The accepted form added a locally approved continuation section.",
        )
        self.assertEqual(successor.version, 2)
        self.assertEqual(successor.sections.count(), 2)
        self.assertEqual(successor.test_attempts.count(), 0)
        with self.assertRaisesMessage(ValidationError, "record and independently witness"):
            submit_local_form(successor, self.preparer)
        self.pass_all_tests(successor)
        submit_local_form(successor, self.preparer)
        review_local_form(successor, self.witness, approve=True, note="Successor independently retested and accepted.")
        item.refresh_from_db()
        successor.refresh_from_db()
        self.assertEqual(item.status, FinanceLocalFormAcceptance.SUPERSEDED)
        self.assertEqual(successor.status, FinanceLocalFormAcceptance.ACCEPTED)
        self.assertEqual(local_form_export_manifest(item)["workflow"]["status"], "superseded")

    def test_dbm_starter_catalog_is_complete_and_source_anchored(self):
        self.assertEqual(len(DBM_FORM_STARTERS), 31)
        self.assertEqual(len({item["key"] for item in DBM_FORM_STARTERS}), 31)
        self.assertEqual(
            {item["family"] for item in DBM_FORM_STARTERS},
            {"LBP", "LBA", "LBR", "LBE", "LBAc"},
        )
        self.assertEqual(sum(len(item["sections"]) for item in DBM_FORM_STARTERS), 77)
        for starter in DBM_FORM_STARTERS:
            self.assertTrue(starter["manual_pages"])
            self.assertTrue(starter["pdf_pages"])
            self.assertTrue(starter["sections"])
            for section in starter["sections"]:
                self.assertTrue(section["field_instructions"])
                self.assertTrue(section["source_instructions"])
                self.assertTrue(section["control_instructions"])
                self.assertTrue(section["owner_instructions"])
                self.assertTrue(section["print_instructions"])

    def test_dbm_starter_creates_only_unmapped_unconfirmed_editable_candidate(self):
        item = create_local_form_from_starter(
            self.department, self.preparer, starter_key="lbp-form-4",
        )
        self.assertEqual(item.status, FinanceLocalFormAcceptance.DRAFT)
        self.assertEqual(item.source_type, FinanceLocalFormAcceptance.SOURCE_UNMAPPED)
        self.assertEqual(item.delivery_mode, FinanceLocalFormAcceptance.DELIVERY_UNCONFIRMED)
        self.assertFalse(item.reference_file)
        self.assertIsNone(item.report_template)
        self.assertIsNone(item.finance_template)
        self.assertEqual(item.sections.count(), 4)
        self.assertEqual(item.test_attempts.count(), 0)
        self.assertFalse(item.submission_checksum)
        self.assertFalse(item.local_acceptance_note)
        self.assertFalse(item.sections.exclude(
            confirmation_status=FinanceLocalFormSection.STARTER_CANDIDATE,
        ).exists())
        event = item.events.get(action="candidate_starter_created")
        self.assertEqual(event.snapshot["starter_key"], "lbp-form-4")
        self.assertFalse(event.snapshot["tests_created"])

        errors = validate_local_form(item)["errors"]
        self.assertTrue(any("confirm whether" in message for message in errors))
        self.assertTrue(any("inventory-only" in message for message in errors))
        self.assertTrue(any("Upload the exact blank" in message for message in errors))
        self.assertTrue(any("compare this candidate starter row" in message for message in errors))
        self.assertTrue(any("record and independently witness" in message for message in errors))

    def test_local_form_triage_and_register_are_synchronized_and_department_scoped(self):
        candidate = create_local_form_from_starter(
            self.department, self.preparer, starter_key="lbp-form-4",
        )
        FinanceLocalFormAcceptance.objects.filter(pk=candidate.pk).update(
            name="=LBP candidate must remain spreadsheet text",
        )
        candidate.refresh_from_db()
        completed_record = self.local_form("separate-local-form")
        outsider_record = create_local_form_from_starter(
            self.other_department, self.outsider, starter_key="lbp-form-4",
        )
        query = {
            "attention": "candidate_sections", "source_type": "unmapped",
            "delivery_mode": "unconfirmed", "q": "LBP candidate",
        }

        self.client.force_login(self.preparer)
        workspace = self.client.get(reverse("reporting:local_form_workspace"), query)
        self.assertEqual(workspace.status_code, 200)
        self.assertContains(workspace, candidate.get_absolute_url())
        self.assertNotContains(workspace, completed_record.get_absolute_url())
        self.assertNotContains(workspace, outsider_record.get_absolute_url())
        self.assertContains(workspace, "Link the exact governed report template or Finance workbook")
        self.assertContains(workspace, "Export these 1 forms")
        self.assertContains(workspace, "A register row does not make a candidate official")

        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            response = self.client.get(reverse("reporting:local_form_register_export"), query)
            self.assertEqual(response.status_code, 200)
            rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["form_public_id"], str(candidate.public_id))
            self.assertEqual(rows[0]["name"], "'=LBP candidate must remain spreadsheet text")
            self.assertEqual(rows[0]["section_count"], str(candidate.sections.count()))
            self.assertEqual(rows[0]["candidate_section_count"], str(candidate.sections.count()))
            self.assertEqual(rows[0]["missing_test_count"], "7")
            self.assertEqual(rows[0]["source_checksum"], "")
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            relative_path = response["X-GRAND-Export-Relative-Path"]
            self.assertIn(
                f"{self.department.slug}/{slugify(self.preparer.username)}/finance-local-form-register/",
                relative_path,
            )
            artifact = Path(export_root, *relative_path.split("/"))
            self.assertEqual(artifact.read_bytes(), response.content)
            manifest = json.loads(Path(str(artifact) + ".manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["metadata"]["form_count"], 1)
            self.assertEqual(manifest["sha256"], response["X-GRAND-Export-SHA256"])
            self.assertTrue(FinanceLocalFormEvent.objects.filter(
                form=candidate, actor=self.preparer, action="register_exported",
            ).exists())

            all_visible = self.client.get(reverse("reporting:local_form_register_export"))
            all_visible_text = all_visible.content.decode("utf-8-sig")
            self.assertIn(str(candidate.public_id), all_visible_text)
            self.assertIn(str(completed_record.public_id), all_visible_text)
            self.assertNotIn(str(outsider_record.public_id), all_visible_text)
            invalid = self.client.get(
                reverse("reporting:local_form_register_export"), {"attention": "unknown"},
            )
            self.assertEqual(
                len(list(csv.reader(io.StringIO(invalid.content.decode("utf-8-sig"))))), 1,
            )

        self.preparer.user_permissions.remove(Permission.objects.get(
            content_type__app_label="reporting", codename="export_local_form_acceptance",
        ))
        self.preparer = get_user_model().objects.get(pk=self.preparer.pk)
        self.client.force_login(self.preparer)
        self.assertEqual(
            self.client.get(reverse("reporting:local_form_register_export")).status_code, 403,
        )

    def test_dbm_starter_duplicate_and_department_boundaries(self):
        first = create_local_form_from_starter(
            self.department, self.preparer, starter_key="lbe-form-2",
        )
        with self.assertRaisesMessage(ValidationError, "already has a current"):
            create_local_form_from_starter(
                self.department, self.preparer, starter_key="lbe-form-2",
            )
        self.assertEqual(FinanceLocalFormAcceptance.objects.filter(
            department=self.department, code="lbe-form-2",
        ).count(), 1)
        with self.assertRaisesMessage(ValidationError, "actor's assigned department"):
            create_local_form_from_starter(
                self.other_department, self.preparer, starter_key="lbe-form-2",
            )
        other = create_local_form_from_starter(
            self.other_department, self.outsider, starter_key="lbe-form-2",
        )
        self.assertNotEqual(first.department, other.department)
        with self.assertRaisesMessage(ValidationError, "recognized DBM"):
            create_local_form_from_starter(
                self.department, self.preparer, starter_key="not-a-db-form",
            )

    def test_dbm_starter_catalog_views_and_permissions(self):
        catalog_url = reverse("reporting:local_form_starter_catalog")
        self.client.force_login(self.preparer)
        response = self.client.get(catalog_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "31 editable candidates")
        self.assertContains(response, "LBP Form No. 4")
        self.assertContains(response, "Manual pp. 89")

        create_url = reverse(
            "reporting:local_form_starter_create", args=("lbac-form-1",),
        )
        response = self.client.post(create_url)
        created = FinanceLocalFormAcceptance.objects.get(
            department=self.department, code="lbac-form-1",
        )
        self.assertRedirects(response, created.get_absolute_url())
        duplicate = self.client.post(create_url, follow=True)
        self.assertContains(duplicate, "already has a current local-form record")

        self.client.force_login(self.witness)
        self.assertEqual(self.client.get(catalog_url).status_code, 403)
        self.assertEqual(self.client.post(create_url).status_code, 403)

    def test_candidate_section_requires_attributable_local_resolution(self):
        item = create_local_form_from_starter(
            self.department, self.preparer, starter_key="lbp-form-1",
        )
        section = item.sections.first()
        starter_form = FinanceLocalFormSectionForm(instance=section, local_form=item)
        self.assertEqual(
            {value for value, _label in starter_form.fields["confirmation_status"].choices},
            {
                FinanceLocalFormSection.STARTER_CANDIDATE,
                FinanceLocalFormSection.STARTER_CONFIRMED,
                FinanceLocalFormSection.STARTER_NOT_APPLICABLE,
            },
        )
        section.confirmation_status = FinanceLocalFormSection.LOCAL_ENTRY
        with self.assertRaisesMessage(ValidationError, "starter row cannot be treated as a manual local entry"):
            section.full_clean()
        section.confirmation_status = FinanceLocalFormSection.STARTER_CONFIRMED
        with self.assertRaisesMessage(ValidationError, "Cite the retained local form"):
            section.full_clean()
        section.local_confirmation_reference = (
            "Compared with retained Municipal Budget Office blank LBP Form No. 1, page 1, "
            "comparison record MBO-2026-017."
        )
        section.save()
        snapshot = form_snapshot(item)
        self.assertEqual(snapshot["schema_version"], 2)
        mapped = snapshot["sections"][0]
        self.assertEqual(mapped["confirmation_status"], FinanceLocalFormSection.STARTER_CONFIRMED)
        self.assertIn("DBM BOM 2023", mapped["starter_reference"])
        self.assertIn("comparison record", mapped["local_confirmation_reference"])
        self.assertTrue(mapped["field_instructions"])

        manual_form = FinanceLocalFormSectionForm(local_form=item)
        self.assertEqual(manual_form.fields["confirmation_status"].widget.input_type, "hidden")
        self.assertEqual(
            list(manual_form.fields["confirmation_status"].choices),
            [(FinanceLocalFormSection.LOCAL_ENTRY, "Entered from the current local form")],
        )
        self.client.force_login(self.preparer)
        manual_response = self.client.get(reverse(
            "reporting:local_form_section_create", args=(item.public_id,),
        ))
        self.assertEqual(manual_response.status_code, 200)
        self.assertNotContains(manual_response, "Candidate starter source")
        self.assertNotContains(manual_response, "Local comparison status")

    def test_legacy_schema_one_acceptance_packet_remains_reproducible(self):
        item = self.local_form("legacy-schema-one")
        self.pass_all_tests(item)
        pinned_source = source_snapshot(item)
        pinned_reference = file_checksum(item.reference_file)
        legacy_snapshot = form_snapshot(
            item,
            pinned_source=pinned_source,
            pinned_reference_checksum=pinned_reference,
            schema_version=1,
        )
        now = timezone.now()
        FinanceLocalFormAcceptance.objects.filter(pk=item.pk).update(
            status=FinanceLocalFormAcceptance.ACCEPTED,
            reference_checksum=pinned_reference,
            source_snapshot=pinned_source,
            source_checksum=checksum(pinned_source),
            submission_snapshot=legacy_snapshot,
            submission_checksum=checksum(legacy_snapshot),
            submitted_by=self.preparer,
            submitted_at=now,
            reviewed_by=self.witness,
            reviewed_at=now,
            review_note="Synthetic retained schema-one independent acceptance.",
        )
        item.refresh_from_db()
        packet = local_form_export_manifest(item)
        self.assertEqual(packet["schema_version"], 1)
        self.assertNotIn("field_instructions", packet["form"]["sections"][0])

    def test_test_attempt_separation_failure_and_reasoned_retry(self):
        item = self.local_form("test-lineage")
        first = record_test_attempt(
            item, self.preparer, category=FinanceLocalFormTestAttempt.OVERFLOW_PAGINATION,
            test_steps="Printed a long redacted schedule.", expected_result="Continuation headings repeat.",
            observed_result="Heading was missing on page two.", environment="PDF and office printer.",
            evidence_reference="Retained failed overflow sample.", evidence_checksum="a" * 64,
        )
        with self.assertRaisesMessage(ValidationError, "cannot witness"):
            review_test_attempt(first, self.preparer, action="pass", note="Self witness.")
        review_test_attempt(first, self.witness, action="fail", note="Page-two heading is missing.")
        with self.assertRaisesMessage(ValidationError, "another attempt"):
            record_test_attempt(
                item, self.preparer, category=FinanceLocalFormTestAttempt.OVERFLOW_PAGINATION,
                test_steps="Retest.", expected_result="Pass.", observed_result="Pass.",
                environment="PDF.", evidence_reference="Retest.", evidence_checksum="b" * 64,
            )
        second = record_test_attempt(
            item, self.preparer, category=FinanceLocalFormTestAttempt.OVERFLOW_PAGINATION,
            test_steps="Retested the corrected continuation output.", expected_result="Heading repeats.",
            observed_result="Heading and page number now repeat.", environment="PDF and office printer.",
            evidence_reference="Retained corrected overflow sample.", evidence_checksum="b" * 64,
            change_reason="Corrected the missing continuation-page heading.",
        )
        review_test_attempt(second, self.witness, action="pass", note="Corrected output independently witnessed.")
        self.assertEqual(second.supersedes, first)
        self.assertEqual(item.test_attempts.count(), 2)

    def test_reference_type_and_printer_not_applicable_rules(self):
        item = self.local_form("physical-test-rules")
        item.reference_kind = "image"
        with self.assertRaisesMessage(ValidationError, "must match the selected"):
            item.full_clean()
        item.reference_kind = "pdf"

        attempt = record_test_attempt(
            item, self.preparer, category=FinanceLocalFormTestAttempt.PRINTER_STOCK,
            test_steps="Checked the actual office printer and retained sample.",
            expected_result="A4 stock prints at actual size.",
            observed_result="A4 stock printed at actual size.",
            environment="Office laser printer, A4 tray.",
            evidence_reference="Retained physical print sample.", evidence_checksum="c" * 64,
        )
        with self.assertRaisesMessage(ValidationError, "digital-only"):
            review_test_attempt(
                attempt, self.witness, action="not-applicable",
                note="Incorrectly treated a physical trial as not applicable.",
            )

    def test_inventory_only_and_template_drift_block_acceptance(self):
        inventory = self.local_form("inventory-pending")
        inventory.source_type = FinanceLocalFormAcceptance.SOURCE_UNMAPPED
        inventory.report_template = None
        inventory.save()
        with self.assertRaisesMessage(ValidationError, "inventory-only"):
            submit_local_form(inventory, self.preparer)

        item = self.local_form("tamper-check")
        self.pass_all_tests(item)
        submit_local_form(item, self.preparer)
        ReportTemplateVersion.objects.filter(pk=self.template.pk).update(title="Altered after submission")
        self.template.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "no longer matches its activated promotion evidence"):
            review_local_form(item, self.witness, approve=True, note="Should not accept drift.")

    def test_form_change_after_tests_requires_reasoned_retesting(self):
        item = self.local_form("test-basis-drift")
        self.pass_all_tests(item)
        item.signatory_instructions = "Changed signatory order after the practical tests were witnessed."
        item.save()
        with self.assertRaisesMessage(ValidationError, "changed since this test"):
            submit_local_form(item, self.preparer)

    def test_active_preflighted_finance_workbook_is_supported_source(self):
        release = FinanceConfigurationRelease.objects.create(
            department=self.department, code="f102-workbook-release", version=1,
            title="Synthetic active workbook release", fiscal_year=2027, status="active",
            effective_from=date(2027, 1, 1), created_by=self.preparer,
            approved_by=self.witness, approved_at=timezone.now(),
            activated_by=self.witness, activated_at=timezone.now(),
        )
        payload = build_finance_starter_workbook({
            "lgu_name": "Municipality of Synthetic",
            "finance_office_name": "Accounting Office", "form_title": "DISBURSEMENT VOUCHER",
            "form_reference": "Synthetic locally reviewed DV", "paper_size": "a4",
            "orientation": "portrait", "particulars_rows": 8, "default_copy_count": 3,
            "prepared_label": "Prepared by", "certified_label": "Certified by",
            "approved_label": "Approved by", "footer_note": "Synthetic test only",
        })
        template = FinanceTemplateVersion.objects.create(
            department=self.department, release=release, document_type="disbursement-voucher",
            version=1, title="Accepted DV workbook", form_reference="Local DV F102",
            authority_reference="Synthetic reviewed authority.",
            comparison_reference="Synthetic blank/redacted side-by-side acceptance record.",
            form_status=FinanceTemplateVersion.LOCALLY_ACCEPTED,
            paper_size="a4", orientation="portrait", default_copy_count=3,
            printer_instructions="Office printer, A4 stock, actual size.",
            controlled_print_required=True,
            workbook=SimpleUploadedFile(
                "accepted-dv.xlsx", payload,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            effective_from=date(2027, 1, 1), created_by=self.preparer,
        )
        preflight_finance_template(template, self.preparer)
        template.status = "active"
        template.full_clean()
        template.save(update_fields=("status",))

        item = self.local_form("finance-workbook-source")
        item.source_type = FinanceLocalFormAcceptance.SOURCE_FINANCE
        item.report_template = None
        item.finance_template = template
        item.save()
        self.pass_all_tests(item)
        submit_local_form(item, self.preparer)
        item.refresh_from_db()
        self.assertEqual(item.source_snapshot["kind"], FinanceLocalFormAcceptance.SOURCE_FINANCE)
        self.assertEqual(item.source_snapshot["workbook_checksum"], template.workbook_checksum)

    def test_department_boundary_views_and_role_separation(self):
        item = self.local_form("department-boundary")
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(item.get_absolute_url()).status_code, 200)
        self.assertContains(self.client.get(item.get_absolute_url()), "Practical acceptance tests")
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(item.get_absolute_url()).status_code, 404)

        manager = FINANCE_ROLE_PERMISSIONS["Finance Configuration Manager"]
        approver = FINANCE_ROLE_PERMISSIONS["Finance Configuration Approver"]
        self.assertIn("reporting.manage_local_form_acceptance", manager)
        self.assertNotIn("reporting.review_local_form_acceptance", manager)
        self.assertIn("reporting.witness_local_form_tests", approver)
        self.assertIn("reporting.review_local_form_acceptance", approver)
        self.assertNotIn("reporting.manage_local_form_acceptance", approver)
