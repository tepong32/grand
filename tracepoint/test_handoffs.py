from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from departments.models import Department

from .credentials import issue_daily_credential, revoke_daily_credential
from .handoffs import HandoffError, attach_recipient_code, confirm_handoff, start_scan_session
from .models import PacketHandoff, PacketScanSession, TrackedPacket
from .services import create_packet


class TracePointHandoffTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mswd = Department.objects.create(name="MSWD Handoff", slug="mswd-handoff")
        cls.accounting = Department.objects.create(name="Accounting Handoff", slug="accounting-handoff")
        users = get_user_model()
        cls.preparer = users.objects.create_user(
            username="handoff-preparer", email="handoff-preparer@example.gov", password="test-password",
            first_name="Maria", last_name="Preparer",
        )
        cls.receiver = users.objects.create_user(
            username="handoff-receiver", email="handoff-receiver@example.gov", password="test-password",
            first_name="Ramon", last_name="Receiver",
        )
        cls.station_operator = users.objects.create_user(
            username="handoff-station", email="handoff-station@example.gov", password="test-password",
            first_name="Lina", last_name="Station",
        )
        cls.other_operator = users.objects.create_user(
            username="handoff-other-station", email="handoff-other@example.gov", password="test-password",
        )
        for user, department, position in (
            (cls.preparer, cls.mswd, "Social Welfare Officer"),
            (cls.receiver, cls.accounting, "Accounting Clerk"),
            (cls.station_operator, cls.accounting, "Receiving Officer"),
            (cls.other_operator, cls.mswd, "Administrative Aide"),
        ):
            user.employeeprofile.assigned_department = department
            user.employeeprofile.position_title = position
            user.employeeprofile.save(update_fields=("assigned_department", "position_title"))
        cls.preparer.user_permissions.add(Permission.objects.get(codename="prepare_tracked_packets"))

    def _packet(self):
        return create_packet(
            actor=self.preparer,
            title="Synthetic voucher handoff",
            contents_manifest="Twelve voucher folders with synthetic attachments",
            final_destination_department=self.accounting,
            final_destination_employee=self.receiver,
        )

    def _ready_activation(self, packet, key="activate-packet-001"):
        issued = issue_daily_credential(employee=self.preparer)
        session = start_scan_session(packet=packet, operator=self.preparer, idempotency_key=key)
        attach_recipient_code(session=session, operator=self.preparer, token=issued.token)
        return session, issued

    def _activate(self, packet):
        session, _issued = self._ready_activation(packet)
        return confirm_handoff(session=session, operator=self.preparer, receipt_note="Label attached and packet activated")

    def test_scans_do_not_change_custody_until_confirmation(self):
        packet = self._packet()
        session, _issued = self._ready_activation(packet)
        packet.refresh_from_db()

        self.assertEqual(session.status, PacketScanSession.READY)
        self.assertEqual(packet.status, TrackedPacket.DRAFT)
        self.assertIsNone(packet.current_holder)
        self.assertEqual(packet.handoffs.count(), 0)

    def test_preparer_confirmation_activates_and_snapshots_first_receipt(self):
        packet = self._packet()
        handoff = self._activate(packet)
        packet.refresh_from_db()

        self.assertEqual(handoff.sequence, 1)
        self.assertEqual(handoff.transfer_type, PacketHandoff.ACTIVATION)
        self.assertIsNone(handoff.from_holder)
        self.assertEqual(handoff.to_holder, self.preparer)
        self.assertEqual(handoff.to_employee_name, "Maria Preparer")
        self.assertEqual(handoff.to_position_title, "Social Welfare Officer")
        self.assertEqual(packet.status, TrackedPacket.ACTIVE)
        self.assertIsNone(packet.delivered_at)
        self.assertEqual(packet.current_holder, self.preparer)
        self.assertEqual(packet.current_department, self.mswd)
        self.assertEqual(packet.state_version, 1)
        self.assertIsNotNone(packet.activated_at)

    def test_non_preparer_cannot_activate_draft(self):
        packet = self._packet()
        receiver_code = issue_daily_credential(employee=self.receiver)
        session = start_scan_session(packet=packet, operator=self.station_operator, idempotency_key="wrong-activation")
        with self.assertRaisesMessage(HandoffError, "preparer"):
            attach_recipient_code(session=session, operator=self.station_operator, token=receiver_code.token)

    def test_confirmed_transfer_is_atomic_sequenced_and_idempotent(self):
        packet = self._packet()
        self._activate(packet)
        receiver_code = issue_daily_credential(employee=self.receiver)
        session = start_scan_session(packet=packet, operator=self.station_operator, idempotency_key="receipt-accounting-001")
        attach_recipient_code(session=session, operator=self.station_operator, token=receiver_code.token)

        receipt = confirm_handoff(
            session=session,
            operator=self.station_operator,
            receipt_note="Received at Accounting counter",
            terminal_delivery=True,
        )
        repeated = confirm_handoff(session=session, operator=self.station_operator, receipt_note="Duplicate click")
        packet.refresh_from_db()
        receiver_code.credential.refresh_from_db()

        self.assertEqual(receipt.pk, repeated.pk)
        self.assertEqual(packet.handoffs.count(), 2)
        self.assertEqual(receipt.sequence, 2)
        self.assertEqual(receipt.from_holder, self.preparer)
        self.assertEqual(receipt.to_holder, self.receiver)
        self.assertEqual(receipt.from_department_name, self.mswd.name)
        self.assertEqual(receipt.to_department_name, self.accounting.name)
        self.assertEqual(packet.current_holder, self.receiver)
        self.assertEqual(packet.current_department, self.accounting)
        self.assertEqual(packet.status, TrackedPacket.DELIVERED)
        self.assertIsNotNone(packet.delivered_at)
        self.assertEqual(packet.state_version, 2)
        self.assertEqual(receiver_code.credential.use_count, 1)
        self.assertEqual(packet.events.filter(action="custody_transferred").count(), 1)
        self.assertEqual(packet.events.filter(action="delivered").count(), 1)

    def test_open_session_blocks_a_competing_station(self):
        packet = self._packet()
        first = start_scan_session(packet=packet, operator=self.preparer, idempotency_key="station-one")
        repeated = start_scan_session(packet=packet, operator=self.preparer, idempotency_key="station-one")
        self.assertEqual(first.pk, repeated.pk)

        with self.assertRaisesMessage(HandoffError, "Another receiving station"):
            start_scan_session(packet=packet, operator=self.other_operator, idempotency_key="station-two")

    def test_stale_packet_version_rejects_confirmation_without_a_receipt(self):
        packet = self._packet()
        session, _issued = self._ready_activation(packet, key="stale-activation")
        TrackedPacket.objects.filter(pk=packet.pk).update(state_version=1)

        with self.assertRaisesMessage(HandoffError, "changed at another station"):
            confirm_handoff(session=session, operator=self.preparer)
        self.assertFalse(PacketHandoff.objects.filter(scan_session=session).exists())
        packet.refresh_from_db()
        self.assertEqual(packet.status, TrackedPacket.DRAFT)

    def test_revoked_code_between_scan_and_confirm_is_rejected(self):
        packet = self._packet()
        session, issued = self._ready_activation(packet, key="revoked-before-confirm")
        revoke_daily_credential(credential=issued.credential, actor=self.preparer, reason="Code was exposed")

        with self.assertRaisesMessage(HandoffError, "expired, was replaced"):
            confirm_handoff(session=session, operator=self.preparer)
        self.assertEqual(packet.handoffs.count(), 0)

    def test_expired_session_and_self_transfer_are_rejected(self):
        packet = self._packet()
        self._activate(packet)
        session = start_scan_session(packet=packet, operator=self.preparer, idempotency_key="self-transfer")
        replacement = issue_daily_credential(employee=self.preparer, replace=True)
        with self.assertRaisesMessage(HandoffError, "themselves"):
            attach_recipient_code(session=session, operator=self.preparer, token=replacement.token)

        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save(update_fields=("expires_at",))
        receiver_code = issue_daily_credential(employee=self.receiver)
        with self.assertRaisesMessage(HandoffError, "expired"):
            attach_recipient_code(session=session, operator=self.preparer, token=receiver_code.token)
        session.refresh_from_db()
        self.assertEqual(session.status, PacketScanSession.EXPIRED)

    def test_confirmed_receipt_cannot_be_edited_or_deleted(self):
        packet = self._packet()
        receipt = self._activate(packet)
        receipt.receipt_note = "Rewritten history"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            receipt.save()
        with self.assertRaisesMessage(ValidationError, "cannot be deleted"):
            receipt.delete()
