"""Retained checksums, current attachments and fresh native Records ownership."""
import hashlib
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.http import FileResponse
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceRequest, AssistanceType, RequestDocument
from departments.models import Department
from finance.models import FinanceConfigurationRelease, FinanceTemplateVersion
from reporting.models import ReportDefinition, ReportRun, ReportTemplateVersion
from vouchers.models import VoucherCase, VoucherOutput
from . import test_file_integrity
from .models import RecordEvent
from .services import create_record, file_approved_report


class RecordSourceDownloadTests(TestCase):
    databases = {"default", "finance"}
    payload = b"%PDF-synthetic linked source"

    @classmethod
    def setUpTestData(cls):
        test_file_integrity.RecordFileIntegrityTests.setUpTestData.__func__(cls)
        cls.office, _ = Department.objects.get_or_create(slug="mswd", defaults={"name": "Municipal Social Welfare"})
        for actor in (cls.clerk, cls.reader):
            actor.employeeprofile.assigned_department = cls.office
            actor.employeeprofile.save(update_fields=("assigned_department",))
        cls.release = FinanceConfigurationRelease.objects.create(
            department=cls.office, code="records-source-fixture", title="Synthetic setup",
            fiscal_year=2026, effective_from=timezone.localdate(), created_by=cls.clerk)
        cls.template = FinanceTemplateVersion.objects.create(
            department=cls.office, release=cls.release, title="Synthetic fixture only",
            effective_from=timezone.localdate(), created_by=cls.clerk)

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.storage = FileSystemStorage(location=directory.name)
        for model, name in ((ReportRun, "output_file"), (VoucherOutput, "file"), (RequestDocument, "file")):
            replacement = patch.object(model._meta.get_field(name), "storage", self.storage)
            replacement.start()
            self.addCleanup(replacement.stop)
        definition = ReportDefinition.objects.create(
            department=self.office, name="Retained report source", slug="records-source-report",
            dataset_key="mswd_assistance_volume", selected_fields=["request_count"],
            created_by=self.clerk, updated_by=self.clerk)
        template = ReportTemplateVersion.objects.create(
            definition=definition, version=1, title="Synthetic official-report fixture",
            approved_by=self.clerk, approved_at=timezone.now(), fidelity_status="official",
            fidelity_notes="Synthetic fixture; no real acceptance.",
            fidelity_validated_by=self.clerk, fidelity_validated_at=timezone.now(), created_by=self.clerk)
        self.report = ReportRun.objects.create(
            definition=definition, template_version=template, idempotency_key="records-source-run",
            status=ReportRun.APPROVED, output_format="pdf", period_start=timezone.localdate(),
            period_end=timezone.localdate(), output_file=self.upload("report.pdf"),
            checksum=hashlib.sha256(self.payload).hexdigest(), created_by=self.clerk,
            generated_at=timezone.now(), reviewed_by=self.clerk, approved_by=self.clerk)
        report_record, _ = file_approved_report(self.report, self.clerk)
        case = VoucherCase.objects.create(
            reference_code="RECORDS-SOURCE-CASE", requesting_department=self.office,
            current_department=self.office, configuration_release=self.release,
            payee_name="Synthetic payee", particulars="Fixture only", created_by=self.clerk)
        self.output = VoucherOutput.objects.create(
            case=case, output_type="disbursement-voucher", version=1, template=self.template,
            file=self.upload("voucher.pdf"), checksum=hashlib.sha256(self.payload).hexdigest(),
            status=VoucherOutput.OFFICIAL, generated_by=self.clerk)
        output_record = create_record(department=self.office, actor=self.clerk,
                                      title="Retained voucher source", sources=(self.output,))
        kind = AssistanceType.objects.create(name="Records source assistance")
        request = AssistanceRequest.objects.create(assistance_type=kind, full_name="Synthetic source citizen",
            email="record-source@example.test", phone="09123456780", status="submitted")
        self.document = RequestDocument.objects.create(request=request, document_type="others", file=self.upload("attachment.pdf"))
        document_record = create_record(department=self.office, actor=self.clerk,
                                        title="Current assistance context", sources=(self.document,))
        self.sources = [(self.report, "output_file", report_record.associations.get()),
                        (self.output, "file", output_record.associations.get()),
                        (self.document, "file", document_record.associations.get())]
        self.client.force_login(self.clerk)

    def upload(self, name):
        return SimpleUploadedFile(name, self.payload, content_type="application/pdf")

    def url(self, association):
        return reverse("records:download_source", args=(association.record.public_id, association.pk))

    def assert_unavailable(self, association):
        before = association.record.events.count()
        response = self.client.get(self.url(association))
        try:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(association.record.events.count(), before)
        finally:
            if response.streaming:
                for _ in response.streaming_content:
                    pass

    def test_all_three_sources_stream_one_open_handle_with_explicit_integrity_and_audit(self):
        for source, name, association in self.sources:
            with self.subTest(source=type(source).__name__):
                with patch.object(self.storage, "open", wraps=self.storage.open) as opened, \
                        patch("records.views.FileResponse", wraps=FileResponse) as responding, \
                        CaptureQueriesContext(connections["finance"]) as finance:
                    response = self.client.get(self.url(association))
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(opened.call_count, 1)
                    handle = responding.call_args.args[0]
                    self.assertEqual(handle.tell(), 0)
                    self.assertEqual(b"".join(response.streaming_content), self.payload)
                    self.assertTrue(handle.closed)
                self.assertEqual(len(finance), 0)
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assertEqual(int(response["Content-Length"]), len(self.payload))
                self.assertIn(getattr(source, name).name.rsplit("/", 1)[-1], response["Content-Disposition"])
                checksum = None if source == self.document else source.checksum
                self.assertEqual(response["X-GRAND-File-Integrity"], "sha256-verified" if checksum else "not-recorded")
                event = association.record.events.get(action="downloaded_source")
                self.assertEqual(event.actor, self.clerk)
                self.assertEqual(event.metadata, {"association_id": association.pk, "checksum": checksum})

    def test_checksum_bearing_sources_reject_same_size_corruption(self):
        for source, name, association in self.sources[:2]:
            Path(getattr(source, name).path).write_bytes(b"X" * len(self.payload))
            self.assert_unavailable(association)

    def test_missing_checksum_is_not_silently_treated_as_legacy(self):
        for source, _, association in self.sources[:2]:
            type(source).objects.filter(pk=source.pk).update(checksum="")
            self.assert_unavailable(association)

    def test_filed_report_retains_its_original_checksum_even_if_source_metadata_drifts(self):
        content = b"%PDF-source changed together with metadata"
        Path(self.report.output_file.path).write_bytes(content)
        ReportRun.objects.filter(pk=self.report.pk).update(checksum=hashlib.sha256(content).hexdigest())
        self.assert_unavailable(self.sources[0][2])

    def test_missing_or_ambiguous_report_filing_evidence_is_rejected(self):
        association = self.sources[0][2]
        event = association.record.events.get(action="filed_official_report")
        RecordEvent.objects.create(record=association.record, actor=self.clerk, action=event.action,
                                  metadata=event.metadata)
        self.assert_unavailable(association)
        association.record.events.filter(action=event.action).delete()
        self.assert_unavailable(association)

    def test_current_assistance_attachment_is_not_misrepresented_as_an_immutable_copy(self):
        Path(self.document.file.path).write_bytes(b"replacement currently held by Assistance")
        association = self.sources[2][2]
        response = self.client.get(self.url(association))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-GRAND-File-Integrity"], "not-recorded")
        self.assertEqual(b"".join(response.streaming_content), b"replacement currently held by Assistance")
        self.assertContains(self.client.get(association.record.get_absolute_url()),
                            "Current attachment from Assistance; it may be replaced there.")

    def test_missing_and_removed_sources_have_no_success_event(self):
        for source, name, association in self.sources:
            Path(getattr(source, name).path).unlink()
            self.assert_unavailable(association)
        RequestDocument.objects.filter(pk=self.document.pk).update(is_removed=True)
        self.assert_unavailable(self.sources[2][2])

    def test_unsafe_and_wrong_namespace_paths_fail_before_open(self):
        for source, field, association in self.sources:
            original = getattr(source, field)
            for name in (original.path, "../outside.pdf", original.name.replace("/", "\\"), "unrelated/source.pdf"):
                with self.subTest(source=type(source).__name__, name=name):
                    type(source).objects.filter(pk=source.pk).update(**{field: name})
                    with patch.object(self.storage, "open", wraps=self.storage.open) as opened:
                        self.assert_unavailable(association)
                    self.assertEqual(opened.call_count, 0)

    def test_voucher_file_cannot_cross_its_case_type_or_version_namespace(self):
        original = Path(self.output.file.path)
        other = original.parent.parent / "v2" / original.name
        other.parent.mkdir()
        other.write_bytes(self.payload)
        VoucherOutput.objects.filter(pk=self.output.pk).update(file=other.relative_to(self.storage.location).as_posix())
        self.assert_unavailable(self.sources[1][2])

    def test_redirected_source_directories_are_rejected(self):
        for source, name, association in self.sources:
            original = Path(getattr(source, name).path).parent
            moved = original.with_name(original.name + "-moved")
            original.rename(moved)
            try:
                if os.name == "nt":
                    subprocess.run(["cmd", "/c", "mklink", "/J", str(original), str(moved)], check=True, capture_output=True)
                else:
                    original.symlink_to(moved, target_is_directory=True)
                self.assert_unavailable(association)
            finally:
                if os.name == "nt":
                    original.rmdir()
                else:
                    original.unlink()
                moved.rename(original)

    def test_current_source_ownership_precedes_open_and_hides_foreign_details(self):
        ReportDefinition.objects.filter(pk=self.report.definition_id).update(department=self.other, name="FOREIGN-PRIVATE-SOURCE")
        FinanceConfigurationRelease.objects.filter(pk=self.release.pk).update(department=self.other)
        for _, _, association in self.sources[:2]:
            with patch.object(self.storage, "open", wraps=self.storage.open) as opened:
                self.assert_unavailable(association)
            self.assertEqual(opened.call_count, 0)
            response = self.client.get(association.record.get_absolute_url())
            self.assertNotContains(response, "FOREIGN-PRIVATE-SOURCE")
            self.assertContains(response, "Linked source unavailable in this department.")
            self.assertNotContains(response, self.url(association))

    def test_retained_superseded_outputs_remain_available_but_shadow_outputs_do_not(self):
        ReportRun.objects.filter(pk=self.report.pk).update(status=ReportRun.SUPERSEDED)
        VoucherOutput.objects.filter(pk=self.output.pk).update(status=VoucherOutput.SUPERSEDED)
        for _, _, association in self.sources[:2]:
            response = self.client.get(self.url(association))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), self.payload)
        VoucherOutput.objects.filter(pk=self.output.pk).update(status=VoucherOutput.SHADOW)
        self.assert_unavailable(self.sources[1][2])

    def test_native_workspace_download_office_and_disposition_scope_remains(self):
        for actor, status in ((None, 302), (self.reader, 403), (self.outsider, 404)):
            self.client.logout()
            if actor:
                self.client.force_login(actor)
            for _, _, association in self.sources:
                with patch.object(self.storage, "open", wraps=self.storage.open) as opened:
                    self.assertEqual(self.client.get(self.url(association)).status_code, status)
                self.assertEqual(opened.call_count, 0)
        self.client.force_login(self.clerk)
        association = self.sources[0][2]
        type(association.record).objects.filter(pk=association.record.pk).update(status="disposed")
        self.assertEqual(self.client.get(self.url(association)).status_code, 403)

    def test_current_office_restricted_record_and_association_identity_are_rechecked(self):
        self.clerk.employeeprofile.assigned_department = self.other
        self.clerk.employeeprofile.save(update_fields=("assigned_department",))
        for _, _, association in self.sources:
            self.assert_unavailable(association)
        self.clerk.employeeprofile.assigned_department = self.office
        self.clerk.employeeprofile.save(update_fields=("assigned_department",))
        association = self.sources[0][2]
        type(association.record).objects.filter(pk=association.record.pk).update(confidentiality="restricted")
        self.assert_unavailable(association)
        other_record = self.sources[1][2].record
        wrong_url = reverse("records:download_source", args=(other_record.public_id, association.pk))
        with patch.object(self.storage, "open", wraps=self.storage.open) as opened:
            self.assertEqual(self.client.get(wrong_url).status_code, 404)
        self.assertEqual(opened.call_count, 0)

    def test_missing_voucher_owner_or_removed_assistance_is_not_a_downloadable_source(self):
        VoucherCase.objects.filter(pk=self.output.case_id).update(configuration_release=None)
        RequestDocument.objects.filter(pk=self.document.pk).update(is_removed=True)
        for _, _, association in self.sources[1:]:
            self.assert_unavailable(association)
            self.assertNotContains(self.client.get(association.record.get_absolute_url()), self.url(association))

    def test_report_slug_renames_preserve_original_bytes_and_filing_evidence(self):
        ReportDefinition.objects.filter(pk=self.report.definition_id).update(slug="renamed-source-report")
        # Report ownership is explicit; the stored historical folder is not a grant.
        response = self.client.get(self.url(self.sources[0][2]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.payload)

    def test_audit_failure_closes_all_three_open_sources(self):
        for _, _, association in self.sources:
            handles = []
            original = self.storage.open
            def observe(*args, **kwargs):
                source = original(*args, **kwargs)
                handles.append(source)
                return source
            with patch.object(self.storage, "open", side_effect=observe), \
                    patch.object(RecordEvent.objects, "create", side_effect=RuntimeError("synthetic source audit failure")):
                with self.assertRaisesMessage(RuntimeError, "synthetic source audit failure"):
                    self.client.get(self.url(association))
            self.assertEqual(len(handles), 1)
            self.assertTrue(handles[0].closed)
