from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from departments.models import Department

from .handoffs import HandoffError, attach_recipient_code, confirm_handoff, start_scan_session
from .models import PacketCheckpoint, PacketItemMove, PacketScanSession, TrackedPacket
from .credentials import issue_daily_credential
from .services import (
    add_checkpoint,
    add_packet_item,
    create_packet,
    rebundle_packet_items,
    split_packet_items,
)


class TracePointBatchAndCheckpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.origin = Department.objects.create(name="MSWD Batch Origin", slug="batch-mswd")
        cls.accounting = Department.objects.create(name="Accounting Repeat Target", slug="batch-accounting")
        cls.budget = Department.objects.create(name="Budget Intermediate", slug="batch-budget")
        users = get_user_model()
        cls.preparer = users.objects.create_user(
            "batch-preparer", email="batch-preparer@example.gov", password="test-password",
        )
        cls.accounting_receiver = users.objects.create_user(
            "batch-accounting-receiver", email="batch-accounting@example.gov", password="test-password",
        )
        cls.budget_receiver = users.objects.create_user(
            "batch-budget-receiver", email="batch-budget@example.gov", password="test-password",
        )
        for user, department in (
            (cls.preparer, cls.origin),
            (cls.accounting_receiver, cls.accounting),
            (cls.budget_receiver, cls.budget),
        ):
            user.employeeprofile.assigned_department = department
            user.employeeprofile.save(update_fields=("assigned_department",))
        cls.preparer.user_permissions.add(Permission.objects.get(codename="prepare_tracked_packets"))

    def setUp(self):
        self.tokens = {}

    def _packet(self, title="Voucher batch"):
        return create_packet(
            actor=self.preparer,
            title=title,
            contents_manifest="Three independently identified vouchers and attachments",
            final_destination_department=self.accounting,
            final_destination_employee=self.accounting_receiver,
        )

    def _token(self, employee):
        if employee.pk not in self.tokens:
            self.tokens[employee.pk] = issue_daily_credential(employee=employee).token
        return self.tokens[employee.pk]

    def _receive(self, packet, receiver, key, *, checkpoint=None, terminal=False):
        session = start_scan_session(packet=packet, operator=receiver, idempotency_key=key)
        attach_recipient_code(session=session, operator=receiver, token=self._token(receiver))
        handoff = confirm_handoff(
            session=session,
            operator=receiver,
            checkpoint=checkpoint,
            terminal_delivery=terminal,
        )
        packet.refresh_from_db()
        return handoff

    def _activate(self, packet):
        return self._receive(packet, self.preparer, "batch-activation")

    def test_destination_can_be_visited_for_signature_then_left_and_received_terminally_later(self):
        packet = self._packet()
        signature = add_checkpoint(
            packet=packet,
            actor=self.preparer,
            department=self.accounting,
            employee=self.accounting_receiver,
            purpose=PacketCheckpoint.SIGNATURE,
            label="Accounting signature",
        )
        budget_review = add_checkpoint(
            packet=packet,
            actor=self.preparer,
            department=self.budget,
            employee=self.budget_receiver,
            purpose=PacketCheckpoint.REVIEW,
            label="Budget review",
        )
        final_return = add_checkpoint(
            packet=packet,
            actor=self.preparer,
            department=self.accounting,
            employee=self.accounting_receiver,
            purpose=PacketCheckpoint.CERTIFICATION,
            label="Final accounting return",
        )
        self._activate(packet)

        first_accounting = self._receive(
            packet,
            self.accounting_receiver,
            "first-accounting-visit",
            checkpoint=signature,
        )
        self.assertEqual(first_accounting.status_after, TrackedPacket.ACTIVE)
        self.assertFalse(first_accounting.is_terminal_receipt)
        self.assertEqual(packet.status, TrackedPacket.ACTIVE)
        self.assertIsNone(packet.delivered_at)

        self._receive(packet, self.budget_receiver, "budget-review", checkpoint=budget_review)
        terminal = self._receive(
            packet,
            self.accounting_receiver,
            "accounting-terminal-return",
            checkpoint=final_return,
            terminal=True,
        )

        self.assertTrue(terminal.is_terminal_receipt)
        self.assertEqual(packet.status, TrackedPacket.DELIVERED)
        self.assertIsNotNone(packet.delivered_at)
        self.assertEqual(packet.handoffs.filter(to_department=self.accounting).count(), 2)
        self.assertEqual(packet.checkpoints.filter(status=PacketCheckpoint.COMPLETED).count(), 3)

    def test_terminal_confirmation_is_rejected_while_required_route_work_remains(self):
        packet = self._packet()
        signature = add_checkpoint(
            packet=packet,
            actor=self.preparer,
            department=self.accounting,
            purpose=PacketCheckpoint.SIGNATURE,
            label="Initial signature",
        )
        add_checkpoint(
            packet=packet,
            actor=self.preparer,
            department=self.budget,
            purpose=PacketCheckpoint.REVIEW,
            label="Required budget review",
        )
        self._activate(packet)
        session = start_scan_session(packet=packet, operator=self.accounting_receiver, idempotency_key="premature-terminal")
        attach_recipient_code(session=session, operator=self.accounting_receiver, token=self._token(self.accounting_receiver))

        with self.assertRaisesMessage(HandoffError, "required checkpoint"):
            confirm_handoff(
                session=session,
                operator=self.accounting_receiver,
                checkpoint=signature,
                terminal_delivery=True,
            )
        packet.refresh_from_db()
        signature.refresh_from_db()
        self.assertEqual(packet.status, TrackedPacket.ACTIVE)
        self.assertEqual(signature.status, PacketCheckpoint.PENDING)

    def test_vouchers_keep_stable_lineage_across_split_and_rebundle(self):
        packet = self._packet()
        add_checkpoint(
            packet=packet,
            actor=self.preparer,
            department=self.budget,
            purpose=PacketCheckpoint.REVIEW,
            label="Shared pending budget review",
        )
        items = [
            add_packet_item(
                packet=packet,
                actor=self.preparer,
                title=f"Voucher {number}",
                expected_attachment_count=2,
            )
            for number in (1, 2, 3)
        ]

        child = split_packet_items(
            packet=packet,
            items=items[:2],
            actor=self.preparer,
            title="Two vouchers routed separately",
            note="Separate signatories required",
        )
        for item in items:
            item.refresh_from_db()
        self.assertEqual(child.parent_packet, packet)
        self.assertEqual(child.checkpoints.get().label, "Shared pending budget review")
        self.assertEqual(packet.voucher_items.count(), 1)
        self.assertEqual(child.voucher_items.count(), 2)
        self.assertEqual(items[0].current_packet, child)

        rebundle_packet_items(
            source_packet=child,
            target_packet=packet,
            items=[items[0]],
            actor=self.preparer,
            note="First voucher now shares the original route",
        )
        items[0].refresh_from_db()
        self.assertEqual(items[0].current_packet, packet)
        self.assertEqual(
            list(items[0].moves.values_list("action", flat=True)),
            [PacketItemMove.REGISTERED, PacketItemMove.SPLIT, PacketItemMove.REBUNDLED],
        )
        self.assertEqual(packet.voucher_items.count(), 2)
        self.assertEqual(child.voucher_items.count(), 1)

    def test_active_split_keeps_same_custody_and_invalidates_stale_scans(self):
        packet = self._packet("Active split batch")
        items = [
            add_packet_item(packet=packet, actor=self.preparer, title=f"Active voucher {number}")
            for number in (1, 2, 3)
        ]
        add_checkpoint(
            packet=packet,
            actor=self.preparer,
            department=self.budget,
            purpose=PacketCheckpoint.REVIEW,
            label="Pending review inherited by both physical bundles",
        )
        self._activate(packet)
        open_scan = start_scan_session(packet=packet, operator=self.preparer, idempotency_key="stale-before-split")

        child = split_packet_items(
            packet=packet,
            items=items[:2],
            actor=self.preparer,
            title="Active child batch",
            note="Courier capacity required two bundles",
        )
        packet.refresh_from_db()
        open_scan.refresh_from_db()

        self.assertEqual(packet.status, TrackedPacket.ACTIVE)
        self.assertEqual(child.status, TrackedPacket.ACTIVE)
        self.assertEqual(child.current_holder, self.preparer)
        self.assertEqual(child.current_department, self.origin)
        self.assertEqual(child.checkpoints.filter(status=PacketCheckpoint.PENDING).count(), 1)
        self.assertEqual(open_scan.status, PacketScanSession.CANCELLED)
        self.assertEqual(packet.state_version, child.state_version)
