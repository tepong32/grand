from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from departments.models import Department

from .credentials import issue_daily_credential
from .handoffs import attach_recipient_code, confirm_handoff, start_scan_session
from .models import PacketCheckpoint, PacketHandoff, PacketItem, PacketScanSession, TrackedPacket
from .services import create_packet


class TracePointOperatorViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mswd = Department.objects.create(name="Municipal Social Welfare and Development Office", slug="view-mswd")
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="view-accounting")
        cls.hr = Department.objects.create(name="Human Resources Office", slug="view-hr")
        users = get_user_model()
        cls.preparer = users.objects.create_user("view-preparer", email="view-preparer@example.gov", password="test-password")
        cls.receiver = users.objects.create_user("view-receiver", email="view-receiver@example.gov", password="test-password")
        cls.station = users.objects.create_user("view-station", email="view-station@example.gov", password="test-password")
        cls.outsider = users.objects.create_user("view-outsider", email="view-outsider@example.gov", password="test-password")
        cls.unassigned = users.objects.create_user("view-unassigned", email="view-unassigned@example.gov", password="test-password")
        for user, department in (
            (cls.preparer, cls.mswd),
            (cls.receiver, cls.accounting),
            (cls.station, cls.accounting),
            (cls.outsider, cls.hr),
        ):
            user.employeeprofile.assigned_department = department
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.unassigned.employeeprofile.assigned_department = None
        cls.unassigned.employeeprofile.save(update_fields=("assigned_department",))
        cls.preparer.user_permissions.add(*Permission.objects.filter(codename__in=(
            "view_tracepoint_workspace", "prepare_tracked_packets", "print_packet_labels",
        )))
        cls.receiver.user_permissions.add(Permission.objects.get(codename="view_tracepoint_workspace"))

    def setUp(self):
        self.client.force_login(self.preparer)

    def _packet(self, **overrides):
        values = {
            "actor": self.preparer,
            "title": "Assistance voucher bundle",
            "contents_manifest": "Twelve vouchers with supporting documents.",
            "final_destination_department": self.accounting,
            "final_destination_employee": self.receiver,
        }
        values.update(overrides)
        return create_packet(**values)

    def test_workspace_requires_an_assigned_authorized_employee(self):
        response = self.client.get(reverse("tracepoint:workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Physical document custody")
        self.assertContains(response, "Prepare a packet")

        for user in (self.outsider, self.unassigned):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("tracepoint:workspace")).status_code, 403)

    def test_department_dashboard_and_navigation_expose_tracepoint_by_permission(self):
        response = self.client.get(reverse("department_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TracePoint Physical Custody")
        self.assertContains(response, reverse("tracepoint:workspace"))

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("department_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "TracePoint Physical Custody")

    def test_workspace_filters_department_scope_and_restricted_packets(self):
        visible = self._packet()
        restricted = self._packet(title="Restricted payroll bundle", confidentiality=TrackedPacket.RESTRICTED)
        self.client.force_login(self.receiver)
        response = self.client.get(reverse("tracepoint:workspace"))
        self.assertContains(response, visible.tracking_number)
        self.assertContains(response, restricted.tracking_number)  # named destination remains a direct participant

        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(visible.get_absolute_url()).status_code, 404)

    def test_packet_form_creates_a_draft_with_declared_destination(self):
        response = self.client.post(reverse("tracepoint:packet_create"), {
            "title": "July voucher packet",
            "contents_manifest": "One control sheet and five voucher folders.",
            "expected_document_count": 6,
            "expected_page_count": 30,
            "confidentiality": TrackedPacket.INTERNAL,
            "final_destination_department": self.accounting.pk,
            "final_destination_employee": self.receiver.pk,
            "department_record": "",
            "report_run": "",
        })
        packet = TrackedPacket.objects.get(title="July voucher packet")
        self.assertRedirects(response, packet.get_absolute_url())
        self.assertEqual(packet.origin_department, self.mswd)
        self.assertEqual(packet.status, TrackedPacket.DRAFT)

    def test_label_and_qr_require_print_permission(self):
        packet = self._packet()
        self.assertEqual(self.client.get(reverse("tracepoint:packet_label", args=(packet.public_id,))).status_code, 200)
        qr = self.client.get(reverse("tracepoint:packet_label_qr", args=(packet.public_id,)))
        self.assertEqual(qr.status_code, 200)
        self.assertEqual(qr["Content-Type"], "image/png")
        self.assertTrue(qr.content.startswith(b"\x89PNG"))

        self.client.force_login(self.receiver)
        self.assertEqual(self.client.get(reverse("tracepoint:packet_label", args=(packet.public_id,))).status_code, 403)

    def test_daily_code_is_generated_replaced_and_revoked_without_storing_raw_token(self):
        url = reverse("tracepoint:daily_code")
        response = self.client.post(url)
        self.assertRedirects(response, url)
        token = self.client.session["tracepoint_daily_token"]
        self.assertNotIn(token, str(self.preparer.tracepoint_daily_credentials.first().__dict__))
        image = self.client.get(reverse("tracepoint:daily_code_image"))
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image["Content-Type"], "image/png")

        previous = self.preparer.tracepoint_daily_credentials.get(revoked_at__isnull=True)
        self.client.post(url)
        previous.refresh_from_db()
        self.assertIsNotNone(previous.revoked_at)
        self.client.post(reverse("tracepoint:daily_code_revoke"))
        self.assertNotIn("tracepoint_daily_token", self.client.session)

    def test_scanning_only_transfers_after_explicit_confirmation(self):
        packet = self._packet()
        issued = issue_daily_credential(employee=self.preparer, actor=self.preparer)
        self.client.force_login(self.station)
        start_url = reverse("tracepoint:packet_scan", args=(packet.public_id,))
        self.assertEqual(self.client.get(start_url).status_code, 200)
        packet.refresh_from_db()
        self.assertEqual(packet.status, TrackedPacket.DRAFT)

        response = self.client.post(start_url)
        scan = PacketScanSession.objects.get(packet=packet)
        self.assertRedirects(response, reverse("tracepoint:scan_session", args=(scan.public_id,)))
        response = self.client.post(reverse("tracepoint:scan_session", args=(scan.public_id,)), {
            "employee_code": issued.token,
        })
        self.assertRedirects(response, reverse("tracepoint:scan_session", args=(scan.public_id,)))
        scan.refresh_from_db()
        packet.refresh_from_db()
        self.assertEqual(scan.status, PacketScanSession.READY)
        self.assertEqual(packet.status, TrackedPacket.DRAFT)
        self.assertFalse(PacketHandoff.objects.filter(packet=packet).exists())

        response = self.client.post(reverse("tracepoint:scan_confirm", args=(scan.public_id,)), {
            "receipt_note": "Bundle counted and accepted.",
        })
        packet.refresh_from_db()
        self.assertRedirects(response, packet.get_absolute_url())
        self.assertEqual(packet.status, TrackedPacket.ACTIVE)
        self.assertEqual(packet.current_holder, self.preparer)
        self.assertEqual(packet.handoffs.get().receipt_note, "Bundle counted and accepted.")

    def test_state_changing_routes_reject_get(self):
        packet = self._packet()
        self.assertEqual(self.client.get(reverse("tracepoint:daily_code_revoke")).status_code, 405)
        self.assertEqual(self.client.get(reverse("tracepoint:packet_action", args=(packet.public_id, "cancel"))).status_code, 405)
        self.assertEqual(self.client.get(reverse("tracepoint:discrepancy_report", args=(packet.public_id,))).status_code, 405)

    def test_preparer_builds_individual_voucher_manifest_and_repeatable_route(self):
        packet = self._packet()
        item_response = self.client.post(reverse("tracepoint:packet_item_add", args=(packet.public_id,)), {
            "title": "Voucher 2026-001",
            "description": "Synthetic disbursement voucher with attachments",
            "expected_attachment_count": 4,
            "expected_page_count": 12,
        })
        self.assertRedirects(item_response, packet.get_absolute_url())
        self.assertEqual(PacketItem.objects.get(current_packet=packet).expected_attachment_count, 4)

        for label, purpose in (("Accounting signature", PacketCheckpoint.SIGNATURE), ("Final accounting return", PacketCheckpoint.CERTIFICATION)):
            response = self.client.post(reverse("tracepoint:checkpoint_add", args=(packet.public_id,)), {
                "department": self.accounting.pk,
                "employee": self.receiver.pk,
                "purpose": purpose,
                "label": label,
                "instructions": "Receive and verify the physical papers.",
                "required": "on",
            })
            self.assertRedirects(response, packet.get_absolute_url())

        detail = self.client.get(packet.get_absolute_url())
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Voucher manifest")
        self.assertContains(detail, "Voucher 2026-001")
        self.assertContains(detail, "Accounting signature")
        self.assertContains(detail, "Final accounting return")
        self.assertEqual(packet.checkpoints.filter(department=self.accounting).count(), 2)

    def test_destination_confirmation_defaults_to_temporary_and_requires_explicit_terminal_choice(self):
        packet = self._packet()
        preparer_code = issue_daily_credential(employee=self.preparer)
        activation = start_scan_session(packet=packet, operator=self.preparer, idempotency_key="view-terminal-activate")
        attach_recipient_code(session=activation, operator=self.preparer, token=preparer_code.token)
        confirm_handoff(session=activation, operator=self.preparer)
        packet.refresh_from_db()

        receiver_code = issue_daily_credential(employee=self.receiver)
        receipt = start_scan_session(packet=packet, operator=self.station, idempotency_key="view-terminal-review")
        attach_recipient_code(session=receipt, operator=self.station, token=receiver_code.token)
        self.client.force_login(self.station)
        review = self.client.get(reverse("tracepoint:scan_session", args=(receipt.public_id,)))

        self.assertContains(review, "This is the final, terminal delivery")
        self.assertContains(review, "Leave this unchecked when the papers are here only for signing")
        response = self.client.post(reverse("tracepoint:scan_confirm", args=(receipt.public_id,)), {
            "checkpoint": "",
            "receipt_note": "Received for signature only.",
        })
        self.assertRedirects(response, packet.get_absolute_url())
        packet.refresh_from_db()
        self.assertEqual(packet.status, TrackedPacket.ACTIVE)
        self.assertIsNone(packet.delivered_at)
