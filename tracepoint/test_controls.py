from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase

from departments.models import Department

from .controls import (
    PacketControlError,
    cancel_packet,
    complete_packet,
    correct_current_custody,
    hold_packet,
    report_discrepancy,
    resolve_discrepancy,
    resume_packet,
    skip_checkpoint,
)
from .credentials import issue_daily_credential
from .handoffs import HandoffError, attach_recipient_code, confirm_handoff, start_scan_session
from .models import PacketCheckpoint, PacketDiscrepancy, PacketScanSession, TrackedPacket
from .services import add_checkpoint, create_packet


class TracePointDeliveryControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mswd = Department.objects.create(name="MSWD Controls", slug="mswd-controls")
        cls.budget = Department.objects.create(name="Budget Controls", slug="budget-controls")
        cls.accounting = Department.objects.create(name="Accounting Controls", slug="accounting-controls")
        cls.hr = Department.objects.create(name="HR Controls", slug="hr-controls")
        users = get_user_model()
        cls.preparer = users.objects.create_user(username="control-preparer", email="control-preparer@example.gov", password="test-password")
        cls.intermediary = users.objects.create_user(username="control-budget", email="control-budget@example.gov", password="test-password")
        cls.receiver = users.objects.create_user(username="control-receiver", email="control-receiver@example.gov", password="test-password")
        cls.finisher = users.objects.create_user(username="control-finisher", email="control-finisher@example.gov", password="test-password")
        cls.resolver = users.objects.create_user(username="control-resolver", email="control-resolver@example.gov", password="test-password")
        cls.outsider = users.objects.create_user(username="control-outsider", email="control-outsider@example.gov", password="test-password")
        for user, department in (
            (cls.preparer, cls.mswd),
            (cls.intermediary, cls.budget),
            (cls.receiver, cls.accounting),
            (cls.finisher, cls.accounting),
            (cls.resolver, cls.budget),
            (cls.outsider, cls.hr),
        ):
            user.employeeprofile.assigned_department = department
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.preparer.user_permissions.add(Permission.objects.get(codename="prepare_tracked_packets"))
        cls.finisher.user_permissions.add(Permission.objects.get(codename="complete_tracked_packets"))
        cls.resolver.user_permissions.add(Permission.objects.get(codename="resolve_tracepoint_exceptions"))

    def _packet(self, named_receiver=True):
        return create_packet(
            actor=self.preparer,
            title="Synthetic controlled packet",
            contents_manifest="Voucher and synthetic supporting pages",
            final_destination_department=self.accounting,
            final_destination_employee=self.receiver if named_receiver else None,
        )

    def _receive(self, packet, employee, operator, key, terminal_delivery=False):
        issued = issue_daily_credential(employee=employee)
        session = start_scan_session(packet=packet, operator=operator, idempotency_key=key)
        attach_recipient_code(session=session, operator=operator, token=issued.token)
        handoff = confirm_handoff(session=session, operator=operator, terminal_delivery=terminal_delivery)
        packet.refresh_from_db()
        return handoff

    def _activate(self, packet):
        return self._receive(packet, self.preparer, self.preparer, "controls-activate")

    def _to_intermediary(self, packet):
        self._activate(packet)
        return self._receive(packet, self.intermediary, self.intermediary, "controls-budget-receipt")

    def _deliver(self, packet):
        self._to_intermediary(packet)
        return self._receive(packet, self.receiver, self.finisher, "controls-final-receipt", terminal_delivery=True)

    def test_final_receipt_delivers_but_does_not_complete_work(self):
        packet = self._packet()
        receipt = self._deliver(packet)
        packet.refresh_from_db()

        self.assertEqual(receipt.status_after, TrackedPacket.DELIVERED)
        self.assertEqual(packet.status, TrackedPacket.DELIVERED)
        self.assertIsNotNone(packet.delivered_at)
        self.assertIsNone(packet.completed_at)
        with self.assertRaises(PacketControlError):
            complete_packet(packet=packet, actor=self.outsider)

        completed = complete_packet(packet=packet, actor=self.finisher, note="Accounting review completed")
        repeated = complete_packet(packet=completed, actor=self.finisher)
        self.assertEqual(completed.pk, repeated.pk)
        self.assertEqual(completed.status, TrackedPacket.COMPLETED)
        self.assertEqual(completed.completed_by, self.finisher)
        self.assertEqual(completed.events.filter(action="completed").count(), 1)

    def test_department_destination_is_delivered_to_any_employee_in_that_department(self):
        packet = self._packet(named_receiver=False)
        self._to_intermediary(packet)
        self._receive(packet, self.finisher, self.finisher, "controls-department-final", terminal_delivery=True)
        packet.refresh_from_db()
        self.assertEqual(packet.status, TrackedPacket.DELIVERED)
        self.assertEqual(packet.current_holder, self.finisher)

    def test_active_packet_can_be_held_and_resumed_with_open_scan_cancelled(self):
        packet = self._packet()
        self._to_intermediary(packet)
        open_scan = start_scan_session(packet=packet, operator=self.intermediary, idempotency_key="controls-open-before-hold")

        held = hold_packet(packet=packet, actor=self.intermediary, reason="Contents need recounting")
        open_scan.refresh_from_db()
        self.assertEqual(held.status, TrackedPacket.ON_HOLD)
        self.assertEqual(open_scan.status, PacketScanSession.CANCELLED)
        with self.assertRaises(HandoffError):
            start_scan_session(packet=held, operator=self.intermediary, idempotency_key="controls-held-scan")

        resumed = resume_packet(packet=held, actor=self.intermediary, note="Recount matched manifest")
        self.assertEqual(resumed.status, TrackedPacket.ACTIVE)
        self.assertEqual(resumed.hold_reason, "")
        self.assertEqual(resumed.events.filter(action="resumed").count(), 1)

    def test_preparer_can_cancel_draft_but_only_resolver_can_cancel_active(self):
        draft = self._packet()
        cancelled = cancel_packet(packet=draft, actor=self.preparer, reason="Bundle preparation withdrawn")
        self.assertEqual(cancelled.status, TrackedPacket.CANCELLED)
        self.assertIsNotNone(cancelled.cancelled_at)

        active = self._packet()
        self._to_intermediary(active)
        with self.assertRaises(PacketControlError):
            cancel_packet(packet=active, actor=self.intermediary, reason="Not authorized to cancel active tracking")
        cancelled = cancel_packet(packet=active, actor=self.resolver, reason="Physical packet was formally recalled")
        self.assertEqual(cancelled.status, TrackedPacket.CANCELLED)

    def test_discrepancy_report_is_immutable_and_resolution_is_audited(self):
        packet = self._packet()
        handoff = self._to_intermediary(packet)
        discrepancy = report_discrepancy(
            packet=packet,
            actor=self.intermediary,
            category=PacketDiscrepancy.MISSING_CONTENTS,
            description="One listed attachment was not present at recount.",
            related_handoff=handoff,
        )
        discrepancy.description = "Rewritten complaint"
        with self.assertRaises(ValidationError):
            discrepancy.full_clean()
        discrepancy.refresh_from_db()
        resolved = resolve_discrepancy(
            discrepancy=discrepancy,
            actor=self.resolver,
            resolution="Preparer supplied the omitted attachment and both employees recounted the bundle.",
        )
        self.assertEqual(resolved.status, PacketDiscrepancy.RESOLVED)
        self.assertEqual(packet.events.filter(action="discrepancy_resolved").count(), 1)
        resolved.resolution = "Rewritten resolution"
        with self.assertRaises(ValidationError):
            resolved.full_clean()

    def test_custody_correction_appends_evidence_without_rewriting_receipt(self):
        packet = self._packet()
        original_receipt = self._to_intermediary(packet)
        original_to = original_receipt.to_holder
        open_scan = start_scan_session(packet=packet, operator=self.intermediary, idempotency_key="controls-open-before-correction")

        correction = correct_current_custody(
            packet=packet,
            actor=self.resolver,
            corrected_holder=self.resolver,
            reason="Signed receiving log shows the budget resolver accepted the bundle after the scanner was closed.",
            related_handoff=original_receipt,
        )
        packet.refresh_from_db()
        original_receipt.refresh_from_db()
        open_scan.refresh_from_db()
        self.assertEqual(original_receipt.to_holder, original_to)
        self.assertEqual(packet.current_holder, self.resolver)
        self.assertEqual(correction.prior_holder, self.intermediary)
        self.assertEqual(open_scan.status, PacketScanSession.CANCELLED)
        correction.reason = "Rewritten correction"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            correction.save()

    def test_delivered_packet_cannot_be_administratively_reassigned(self):
        packet = self._packet()
        self._deliver(packet)
        packet.refresh_from_db()
        with self.assertRaises(PacketControlError):
            correct_current_custody(
                packet=packet,
                actor=self.finisher,
                corrected_holder=self.finisher,
                reason="Attempted reassignment after delivery",
            )

    def test_only_exception_resolver_can_skip_required_checkpoint_with_reason(self):
        packet = self._packet()
        checkpoint = add_checkpoint(
            packet=packet,
            actor=self.preparer,
            department=self.budget,
            purpose=PacketCheckpoint.APPROVAL,
            label="Budget approval",
        )
        self._to_intermediary(packet)
        with self.assertRaises(PacketControlError):
            skip_checkpoint(checkpoint=checkpoint, actor=self.intermediary, reason="Approver absent")

        skipped = skip_checkpoint(
            checkpoint=checkpoint,
            actor=self.resolver,
            reason="Formal written waiver attached by the authorized budget resolver.",
        )
        self.assertEqual(skipped.status, PacketCheckpoint.SKIPPED)
        self.assertEqual(skipped.skipped_by, self.resolver)
        self.assertEqual(packet.events.filter(action="checkpoint_skipped").count(), 1)
