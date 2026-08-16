from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from departments.models import Department
from records.models import DepartmentRecord
from reporting.models import ReportDefinition, ReportRun, ReportTemplateVersion

from .access import can_receive_packets, packet_is_visible
from .models import PacketEvent, TrackedPacket
from .services import PacketWorkflowError, create_packet, update_draft_packet


class TracePointPacketFoundationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mswd = Department.objects.create(name="Municipal Social Welfare and Development Office", slug="mswd")
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="accounting")
        cls.hr = Department.objects.create(name="Human Resources Office", slug="hr")
        users = get_user_model()
        cls.preparer = users.objects.create_user(username="trace-preparer", email="preparer@example.gov", password="test-password")
        cls.origin_viewer = users.objects.create_user(username="trace-origin-viewer", email="origin-viewer@example.gov", password="test-password")
        cls.receiver = users.objects.create_user(username="trace-receiver", email="receiver@example.gov", password="test-password")
        cls.accounting_viewer = users.objects.create_user(username="trace-accounting-viewer", email="accounting-viewer@example.gov", password="test-password")
        cls.outsider = users.objects.create_user(username="trace-outsider", email="outsider@example.gov", password="test-password")
        cls.unassigned = users.objects.create_user(username="trace-unassigned", email="unassigned@example.gov", password="test-password")

        assignments = (
            (cls.preparer, cls.mswd),
            (cls.origin_viewer, cls.mswd),
            (cls.receiver, cls.accounting),
            (cls.accounting_viewer, cls.accounting),
            (cls.outsider, cls.hr),
        )
        for user, department in assignments:
            user.employeeprofile.assigned_department = department
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.unassigned.employeeprofile.assigned_department = None
        cls.unassigned.employeeprofile.save(update_fields=("assigned_department",))

        cls.preparer.user_permissions.add(*Permission.objects.filter(codename__in=(
            "view_tracepoint_workspace", "prepare_tracked_packets", "print_packet_labels",
        )))
        cls.origin_viewer.user_permissions.add(Permission.objects.get(codename="view_tracepoint_workspace"))
        cls.accounting_viewer.user_permissions.add(Permission.objects.get(codename="view_tracepoint_workspace"))

        cls.record = DepartmentRecord.objects.create(
            department=cls.mswd,
            record_number="MSWD-2026-001",
            title="Synthetic approved accomplishment record",
            confidentiality=DepartmentRecord.CONFIDENTIALITY_RESTRICTED,
            status=DepartmentRecord.APPROVED,
            created_by=cls.preparer,
            approved_by=cls.preparer,
            approved_at=timezone.now(),
        )
        cls.foreign_record = DepartmentRecord.objects.create(
            department=cls.hr,
            record_number="HR-2026-001",
            title="Synthetic HR record",
            status=DepartmentRecord.APPROVED,
            created_by=cls.outsider,
            approved_by=cls.outsider,
            approved_at=timezone.now(),
        )

    def _packet(self, **overrides):
        values = {
            "actor": self.preparer,
            "title": "Monthly assistance voucher bundle",
            "contents_manifest": "One summary report with twelve voucher folders and supporting attachments.",
            "final_destination_department": self.accounting,
            "final_destination_employee": self.receiver,
        }
        values.update(overrides)
        return create_packet(**values)

    def _official_report(self):
        definition = ReportDefinition.objects.create(
            department=self.mswd,
            name="Synthetic assistance summary",
            slug="synthetic-assistance-summary",
            dataset_key="assistance_requests",
            selected_fields=["status"],
            created_by=self.preparer,
            updated_by=self.preparer,
        )
        now = timezone.now()
        template = ReportTemplateVersion.objects.create(
            definition=definition,
            version=1,
            title="Validated synthetic layout",
            fidelity_status=ReportTemplateVersion.OFFICIAL,
            created_by=self.preparer,
            approved_by=self.preparer,
            approved_at=now,
            fidelity_validated_by=self.preparer,
            fidelity_validated_at=now,
        )
        return ReportRun.objects.create(
            definition=definition,
            template_version=template,
            idempotency_key="tracepoint-foundation-official-report",
            status=ReportRun.APPROVED,
            output_format=ReportDefinition.FORMAT_PDF,
            period_start=timezone.localdate(),
            period_end=timezone.localdate(),
            created_by=self.preparer,
            approved_by=self.preparer,
            approved_at=now,
        )

    def test_authorized_preparer_creates_audited_packet(self):
        packet = self._packet(expected_document_count=13, expected_page_count=85)

        self.assertEqual(packet.status, TrackedPacket.DRAFT)
        self.assertEqual(packet.origin_department, self.mswd)
        self.assertEqual(packet.final_destination_employee, self.receiver)
        self.assertRegex(packet.tracking_number, r"^TP-\d{8}-[0-9A-F]{6}$")
        event = PacketEvent.objects.get(packet=packet)
        self.assertEqual(event.action, "created")
        self.assertEqual(event.metadata["final_destination_department_id"], self.accounting.pk)

    def test_employee_without_preparation_permission_cannot_create(self):
        with self.assertRaisesMessage(PacketWorkflowError, "not allowed"):
            create_packet(
                actor=self.origin_viewer,
                title="Unauthorized packet",
                contents_manifest="Synthetic contents",
                final_destination_department=self.accounting,
            )

    def test_destination_employee_must_belong_to_destination_department(self):
        with self.assertRaises(ValidationError) as context:
            self._packet(final_destination_department=self.hr)
        self.assertIn("final_destination_employee", context.exception.message_dict)

    def test_sources_must_be_official_and_owned_by_origin_department(self):
        with self.assertRaises(ValidationError) as context:
            self._packet(department_record=self.foreign_record)
        self.assertIn("department_record", context.exception.message_dict)

        report = self._official_report()
        packet = self._packet(report_run=report)
        self.assertEqual(packet.report_run, report)
        report.status = ReportRun.GENERATED
        report.save(update_fields=("status",))
        with self.assertRaises(ValidationError) as context:
            self._packet(report_run=report)
        self.assertIn("report_run", context.exception.message_dict)

    def test_packet_cannot_weaken_linked_record_confidentiality(self):
        with self.assertRaises(ValidationError) as context:
            self._packet(department_record=self.record, confidentiality=TrackedPacket.INTERNAL)
        self.assertIn("confidentiality", context.exception.message_dict)

        packet = self._packet(department_record=self.record, confidentiality=TrackedPacket.RESTRICTED)
        self.assertEqual(packet.confidentiality, TrackedPacket.RESTRICTED)

    def test_visibility_honors_participation_department_and_restriction(self):
        internal = self._packet()
        restricted = self._packet(confidentiality=TrackedPacket.RESTRICTED)

        self.assertTrue(packet_is_visible(self.preparer, restricted))
        self.assertTrue(packet_is_visible(self.receiver, restricted))
        self.assertTrue(packet_is_visible(self.origin_viewer, internal))
        self.assertTrue(packet_is_visible(self.accounting_viewer, internal))
        self.assertFalse(packet_is_visible(self.origin_viewer, restricted))
        self.assertFalse(packet_is_visible(self.accounting_viewer, restricted))
        self.assertFalse(packet_is_visible(self.outsider, internal))

    def test_only_active_assigned_users_are_eligible_receivers(self):
        self.assertTrue(can_receive_packets(self.receiver))
        self.assertFalse(can_receive_packets(self.unassigned))
        self.receiver.is_active = False
        self.receiver.save(update_fields=("is_active",))
        self.assertFalse(can_receive_packets(self.receiver))

    def test_draft_updates_are_audited_and_activation_locks_identity(self):
        packet = self._packet()
        update_draft_packet(packet=packet, actor=self.preparer, title="Corrected voucher bundle")
        self.assertEqual(packet.title, "Corrected voucher bundle")
        update_event = packet.events.get(action="draft_updated")
        self.assertEqual(update_event.metadata["changed_fields"], ["title"])

        packet.status = TrackedPacket.ACTIVE
        packet.current_holder = self.preparer
        packet.current_department = self.mswd
        packet.activated_at = timezone.now()
        packet.full_clean()
        packet.save()
        packet.title = "Silently rewritten title"
        with self.assertRaises(ValidationError) as context:
            packet.full_clean()
        self.assertIn("status", context.exception.message_dict)
