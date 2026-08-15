import hashlib
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceRequest, AssistanceType, CitizenProfile
from departments.models import Department
from departments.services.dashboard_service import get_department_dashboard_context
from reporting.models import ReportDefinition, ReportRun, ReportTemplateVersion
from social_welfare.models import SocialWelfareProgram

from .models import DepartmentRecord, RecordAssociation, RecordEvent
from .access import can_view_records
from .services import RecordWorkflowError, add_association, create_record, file_approved_report, transition_record


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="grand-records-tests-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DepartmentRecordsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mswd = Department.objects.create(name="Municipal Social Welfare and Development Office", slug="mswd")
        cls.hr = Department.objects.create(name="Human Resources", slug="hr")
        users = get_user_model()
        cls.head = users.objects.create_user(username="records-head", email="records-head@example.gov", password="test-password", first_name="Mara", last_name="Santos")
        cls.manager = users.objects.create_user(username="records-manager", email="records-manager@example.gov", password="test-password")
        cls.reviewer = users.objects.create_user(username="records-reviewer", email="records-reviewer@example.gov", password="test-password")
        cls.viewer = users.objects.create_user(username="records-viewer", email="records-viewer@example.gov", password="test-password")
        cls.outsider = users.objects.create_user(username="hr-records", email="hr-records@example.gov", password="test-password")
        for user in (cls.head, cls.manager, cls.reviewer, cls.viewer):
            user.employeeprofile.assigned_department = cls.mswd
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.outsider.employeeprofile.assigned_department = cls.hr
        cls.outsider.employeeprofile.save(update_fields=("assigned_department",))
        cls.mswd.deptHead_or_oic = cls.head
        cls.mswd.save(update_fields=("deptHead_or_oic",))
        cls.manager.user_permissions.add(*Permission.objects.filter(codename__in=(
            "view_records_workspace", "manage_department_records", "download_department_records",
        )))
        cls.reviewer.user_permissions.add(*Permission.objects.filter(codename__in=(
            "view_records_workspace", "review_department_records", "approve_department_records",
            "manage_record_retention", "download_department_records", "view_restricted_records",
        )))
        cls.viewer.user_permissions.add(Permission.objects.get(codename="view_records_workspace"))
        cls.outsider.user_permissions.add(*Permission.objects.filter(codename__in=(
            "view_records_workspace", "manage_department_records", "view_restricted_records",
        )))
        cls.assistance_type = AssistanceType.objects.create(name="Medical assistance", description="Support", requirements="Documents")
        cls.request = AssistanceRequest.objects.create(
            assistance_type=cls.assistance_type, full_name="Synthetic Citizen", email="citizen@example.test",
            phone="09123456789", status="submitted",
        )
        cls.program = SocialWelfareProgram.objects.create(
            department=cls.mswd, name="Community Nutrition", code="MSWD-NUT-01", program_type="feeding",
            status="active", created_by=cls.head, updated_by=cls.head,
        )

    def _file(self, name="record.txt", content=b"controlled record"):
        return SimpleUploadedFile(name, content, content_type="text/plain")

    def _draft(self, **kwargs):
        defaults = dict(department=self.mswd, actor=self.head, title="Program accomplishment file")
        defaults.update(kwargs)
        return create_record(**defaults)

    def _official_report(self, official=True):
        definition = ReportDefinition.objects.create(
            department=self.mswd, name="Workload report", slug=f"workload-{ReportDefinition.objects.count()}",
            dataset_key="mswd_assistance_volume", selected_fields=["assistance_type", "request_count"],
            created_by=self.head, updated_by=self.head,
        )
        validated_at = timezone.now() if official else None
        template = ReportTemplateVersion.objects.create(
            definition=definition, version=1, title="Workload", approved_by=self.head,
            approved_at=timezone.now(), fidelity_status="official" if official else "pilot",
            fidelity_notes="Compared with the current form." if official else "",
            fidelity_validated_by=self.head if official else None, fidelity_validated_at=validated_at,
            created_by=self.head,
        )
        return ReportRun.objects.create(
            definition=definition, template_version=template, idempotency_key=f"records-test-{definition.pk}",
            status=ReportRun.APPROVED, output_format="pdf", period_start=timezone.localdate() - timedelta(days=30),
            period_end=timezone.localdate(), output_file=SimpleUploadedFile("official.pdf", b"%PDF synthetic"),
            checksum=hashlib.sha256(b"%PDF synthetic").hexdigest(), created_by=self.head,
            reviewed_by=self.head, reviewed_at=timezone.now(), approved_by=self.head, approved_at=timezone.now(),
        )

    def test_head_and_delegated_employee_can_access_workspace(self):
        for user in (self.head, self.manager):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("records:workspace")).status_code, 200)
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("records:workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Register a record")

    def test_department_boundary_is_enforced_for_direct_access_and_associations(self):
        record = self._draft(sources=(self.program,))
        self.assertFalse(can_view_records(self.outsider, self.mswd))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(record.get_absolute_url()).status_code, 404)
        hr_record = create_record(department=self.hr, actor=self.outsider, title="HR file")
        with self.assertRaises(RecordWorkflowError):
            add_association(hr_record, self.program, self.outsider)

    def test_restricted_records_require_separate_permission_and_do_not_leak_in_search(self):
        record = self._draft(title="Sensitive household assessment", confidentiality=DepartmentRecord.CONFIDENTIALITY_CONFIDENTIAL)
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("records:workspace"), {"q": "Sensitive"})
        self.assertNotContains(response, record.title)
        self.assertEqual(self.client.get(record.get_absolute_url()).status_code, 404)
        self.client.force_login(self.reviewer)
        self.assertContains(self.client.get(record.get_absolute_url()), record.record_number)

    def test_upload_records_checksum_and_audit_event(self):
        payload = b"controlled record"
        record = self._draft(uploaded_file=self._file(content=payload), uploaded_description="Signed accomplishment note")
        item = record.files.get()
        self.assertEqual(item.checksum, hashlib.sha256(payload).hexdigest())
        self.assertEqual(item.size_bytes, len(payload))
        self.assertEqual(set(record.events.values_list("action", flat=True)), {"created", "file_added"})

    def test_review_approval_and_post_approval_immutability(self):
        record = self._draft(uploaded_file=self._file())
        transition_record(record, "submit", self.head, "Ready for checking.")
        transition_record(record, "approve", self.reviewer, "Checked against source.")
        self.assertEqual(record.status, DepartmentRecord.APPROVED)
        self.assertEqual(record.approved_by, self.reviewer)
        record.title = "Silently changed title"
        with self.assertRaises(ValidationError):
            record.full_clean()
        with self.assertRaises((RecordWorkflowError, ValidationError)):
            add_association(record, self.program, self.head)

    def test_empty_record_cannot_be_approved(self):
        record = self._draft()
        transition_record(record, "submit", self.head)
        with self.assertRaises(RecordWorkflowError):
            transition_record(record, "approve", self.reviewer)

    def test_retention_due_date_legal_hold_and_disposition(self):
        record = self._draft(uploaded_file=self._file(), retention_years=1)
        transition_record(record, "submit", self.head)
        transition_record(record, "approve", self.reviewer)
        self.assertEqual(record.disposition_due_date, record.retention_start_date + timedelta(days=365))
        transition_record(record, "archive", self.reviewer)
        record.retention_start_date = timezone.localdate() - timedelta(days=730)
        record.disposition_due_date = timezone.localdate() - timedelta(days=1)
        record.legal_hold = True
        record.save(update_fields=("retention_start_date", "disposition_due_date", "legal_hold"))
        with self.assertRaises(RecordWorkflowError):
            transition_record(record, "dispose", self.reviewer)
        record.legal_hold = False
        record.save(update_fields=("legal_hold",))
        transition_record(record, "dispose", self.reviewer)
        self.assertEqual(record.status, DepartmentRecord.DISPOSED)
        record.retention_notes = "changed"
        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_supersession_preserves_both_records_and_links_replacement(self):
        old = self._draft(title="Old procedure", uploaded_file=self._file("old.txt"))
        replacement = self._draft(title="Updated procedure", uploaded_file=self._file("new.txt"))
        for record in (old, replacement):
            transition_record(record, "submit", self.head)
            transition_record(record, "approve", self.reviewer)
        transition_record(old, "supersede", self.reviewer, replacement=replacement)
        self.assertEqual(old.status, DepartmentRecord.SUPERSEDED)
        self.assertEqual(old.superseded_by, replacement)
        self.assertTrue(old.files.exists())

    def test_controlled_download_requires_permission_and_is_audited(self):
        record = self._draft(uploaded_file=self._file())
        item = record.files.get()
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("records:download_file", args=[record.public_id, item.pk])).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.get(reverse("records:download_file", args=[record.public_id, item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(RecordEvent.objects.filter(record=record, action="downloaded_file", actor=self.manager).exists())

    def test_approved_report_is_filed_once_without_copying_output(self):
        run = self._official_report()
        record, created = file_approved_report(run, self.head)
        again, created_again = file_approved_report(run, self.head)
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(again, record)
        self.assertEqual(record.status, DepartmentRecord.APPROVED)
        self.assertFalse(record.files.exists())
        association = record.associations.get(role="official_source")
        self.assertEqual(association.content_object, run)
        self.assertEqual(record.events.get(action="filed_official_report").metadata["output_checksum"], run.checksum)

    def test_pilot_approved_report_cannot_become_official_record(self):
        run = self._official_report(official=False)
        with self.assertRaises(RecordWorkflowError):
            file_approved_report(run, self.head)

    def test_contextual_source_creation_links_program_and_confidential_assistance(self):
        self.client.force_login(self.head)
        response = self.client.post(reverse("records:record_create"), {
            "source_type": "program", "source_id": self.program.pk, "title": "Nutrition program file",
            "description": "", "classification": "program", "confidentiality": "internal",
            "custodian": "", "retention_years": "", "retention_notes": "", "file_description": "",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DepartmentRecord.objects.get(title="Nutrition program file").associations.get().content_object, self.program)
        assistance_form = self.client.get(reverse("records:record_create"), {"source_type": "assistance", "source_id": self.request.pk})
        self.assertContains(assistance_form, "Assistance request")
        self.assertEqual(assistance_form.context["form"].initial["confidentiality"], "confidential")

    def test_records_dashboard_section_does_not_replace_hr_employee_records(self):
        context = get_department_dashboard_context(self.hr, self.outsider)
        titles = [section["title"] for section in context["dashboard_sections"]]
        self.assertIn("Employee records", titles)
        self.assertIn("Records and Documents", titles)

    def test_employee_logo_opens_public_portal_and_footer_preserves_dev_zone(self):
        self.client.force_login(self.head)
        response = self.client.get(reverse("department_dashboard"))
        self.assertContains(response, f'href="{reverse("unauthedhome")}" class="navbar-brand')
        self.assertContains(response, "Dev Zone")
        self.assertContains(response, "https://github.com/tepong32")
        template_source = Path("templates/components/footer_links.html").read_text(encoding="utf-8")
        self.assertIn("Preserve this Dev Zone card", template_source)
