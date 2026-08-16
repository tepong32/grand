from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .access import can_receive_packets, department_for_user
from .credentials import CredentialError, resolve_daily_credential
from .models import (
    DailyEmployeeCredential,
    PacketEvent,
    PacketHandoff,
    PacketScanSession,
    TrackedPacket,
)


SCAN_LIFETIME = timedelta(minutes=5)


class HandoffError(ValueError):
    pass


def _employee_snapshot(user):
    profile = getattr(user, "employeeprofile", None)
    department = getattr(profile, "assigned_department", None)
    return {
        "name": user.get_full_name() or user.username,
        "position": getattr(profile, "position_title", "") or "",
        "department": department,
        "department_name": getattr(department, "name", "") or "",
    }


def _require_operator(operator):
    if not can_receive_packets(operator):
        raise HandoffError("The receiving station requires an active employee account with a department assignment.")


def _require_session_operator(session, operator):
    _require_operator(operator)
    if session.initiated_by_id != operator.pk:
        raise HandoffError("Continue this scan at the employee station where it was started.")


def start_scan_session(*, packet, operator, idempotency_key):
    _require_operator(operator)
    idempotency_key = idempotency_key.strip()
    if not idempotency_key or len(idempotency_key) > 64:
        raise HandoffError("A valid scan idempotency key is required.")

    with transaction.atomic():
        locked_packet = TrackedPacket.objects.select_for_update().get(pk=packet.pk)
        if locked_packet.status not in (TrackedPacket.DRAFT, TrackedPacket.ACTIVE):
            raise HandoffError("Only draft or active packets can enter the receipt scanner.")

        repeated = PacketScanSession.objects.filter(idempotency_key=idempotency_key).first()
        if repeated:
            if repeated.packet_id != locked_packet.pk or repeated.initiated_by_id != operator.pk:
                raise HandoffError("This scan key already belongs to a different operation.")
            return repeated

        open_session = PacketScanSession.objects.select_for_update().filter(
            packet=locked_packet,
            status__in=PacketScanSession.OPEN_STATUSES,
        ).first()
        if open_session and open_session.is_expired:
            open_session.status = PacketScanSession.EXPIRED
            open_session.save(update_fields=("status",))
            open_session = None
        if open_session:
            if open_session.initiated_by_id == operator.pk:
                return open_session
            raise HandoffError("Another receiving station already has an open scan for this packet.")

        return PacketScanSession.objects.create(
            packet=locked_packet,
            initiated_by=operator,
            packet_state_version=locked_packet.state_version,
            idempotency_key=idempotency_key,
            expires_at=timezone.now() + SCAN_LIFETIME,
        )


def attach_recipient_code(*, session, operator, token):
    _require_session_operator(session, operator)
    if session.status not in PacketScanSession.OPEN_STATUSES:
        raise HandoffError("This scan is no longer open.")
    if session.is_expired:
        session.status = PacketScanSession.EXPIRED
        session.save(update_fields=("status",))
        raise HandoffError("This scan expired. Scan the packet again.")
    try:
        credential = resolve_daily_credential(token)
    except CredentialError as error:
        raise HandoffError(str(error)) from error

    packet = session.packet
    receiver = credential.employee
    if packet.status == TrackedPacket.DRAFT and receiver.pk != packet.prepared_by_id:
        raise HandoffError("The preparer must use their own daily code to activate this packet.")
    if packet.status == TrackedPacket.ACTIVE and receiver.pk == packet.current_holder_id:
        raise HandoffError("The current holder cannot receive the packet from themselves.")

    session.recipient_credential = credential
    session.recipient = receiver
    session.status = PacketScanSession.READY
    session.full_clean()
    session.save(update_fields=("recipient_credential", "recipient", "status"))
    return session


def confirm_handoff(*, session, operator, receipt_note=""):
    _require_session_operator(session, operator)
    with transaction.atomic():
        locked_session = PacketScanSession.objects.select_for_update().select_related(
            "recipient_credential", "recipient", "packet"
        ).get(pk=session.pk)
        existing = PacketHandoff.objects.filter(scan_session=locked_session).first()
        if existing:
            return existing
        if locked_session.status != PacketScanSession.READY:
            raise HandoffError("Scan the receiving employee's daily code before confirming receipt.")
        if locked_session.is_expired:
            raise HandoffError("This scan expired before confirmation. Scan the packet again.")

        packet = TrackedPacket.objects.select_for_update().get(pk=locked_session.packet_id)
        if packet.state_version != locked_session.packet_state_version:
            raise HandoffError("Packet custody changed at another station. Scan the packet again.")
        credential = DailyEmployeeCredential.objects.select_for_update().select_related(
            "employee", "employee__employeeprofile", "employee__employeeprofile__assigned_department"
        ).get(pk=locked_session.recipient_credential_id)
        if not credential.is_valid or credential.employee_id != locked_session.recipient_id:
            raise HandoffError("The receiving employee code expired, was replaced, or is no longer eligible.")

        receiver = credential.employee
        receiver_snapshot = _employee_snapshot(receiver)
        sender = packet.current_holder
        sender_snapshot = _employee_snapshot(sender) if sender else {
            "name": "", "position": "", "department": None, "department_name": "",
        }
        if packet.status == TrackedPacket.DRAFT:
            if receiver.pk != packet.prepared_by_id:
                raise HandoffError("Only the preparer can activate this packet.")
            transfer_type = PacketHandoff.ACTIVATION
            normal_status_after = TrackedPacket.ACTIVE
        elif packet.status == TrackedPacket.ACTIVE:
            if not sender or sender.pk == receiver.pk:
                raise HandoffError("A custody receipt must move the packet to another employee.")
            transfer_type = PacketHandoff.RECEIPT
            normal_status_after = TrackedPacket.ACTIVE
        else:
            raise HandoffError("This packet can no longer be transferred through the standard scanner.")

        reached_destination = (
            receiver.pk == packet.final_destination_employee_id
            if packet.final_destination_employee_id
            else receiver_snapshot["department"].pk == packet.final_destination_department_id
        )
        status_after = TrackedPacket.DELIVERED if reached_destination else normal_status_after

        status_before = packet.status
        sequence = (packet.handoffs.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        handoff = PacketHandoff(
            packet=packet,
            sequence=sequence,
            scan_session=locked_session,
            idempotency_key=locked_session.idempotency_key,
            transfer_type=transfer_type,
            from_holder=sender,
            to_holder=receiver,
            from_department=sender_snapshot["department"],
            to_department=receiver_snapshot["department"],
            from_employee_name=sender_snapshot["name"],
            from_position_title=sender_snapshot["position"],
            from_department_name=sender_snapshot["department_name"],
            to_employee_name=receiver_snapshot["name"],
            to_position_title=receiver_snapshot["position"],
            to_department_name=receiver_snapshot["department_name"],
            status_before=status_before,
            status_after=status_after,
            receipt_note=receipt_note.strip(),
            confirmed_by=operator,
            confirmed_at=timezone.now(),
        )
        handoff.full_clean()
        handoff.save(force_insert=True)

        packet.current_holder = receiver
        packet.current_department = receiver_snapshot["department"]
        packet.status = status_after
        packet.state_version += 1
        if transfer_type == PacketHandoff.ACTIVATION:
            packet.activated_at = handoff.confirmed_at
        if reached_destination:
            packet.delivered_at = handoff.confirmed_at
        packet.full_clean()
        packet.save(update_fields=(
            "current_holder", "current_department", "status", "state_version", "activated_at", "delivered_at", "updated_at",
        ))

        DailyEmployeeCredential.objects.filter(pk=credential.pk).update(
            last_used_at=handoff.confirmed_at,
            use_count=F("use_count") + 1,
        )
        locked_session.status = PacketScanSession.CONFIRMED
        locked_session.confirmed_at = handoff.confirmed_at
        locked_session.full_clean()
        locked_session.save(update_fields=("status", "confirmed_at"))
        PacketEvent.objects.create(
            packet=packet,
            actor=operator,
            action="activated" if transfer_type == PacketHandoff.ACTIVATION else "custody_transferred",
            from_status=status_before,
            to_status=status_after,
            note=handoff.receipt_note,
            metadata={
                "handoff_id": handoff.pk,
                "sequence": handoff.sequence,
                "from_employee_id": getattr(sender, "pk", None),
                "to_employee_id": receiver.pk,
                "to_department_id": receiver_snapshot["department"].pk,
                "scan_session_id": str(locked_session.public_id),
            },
        )
        if reached_destination:
            PacketEvent.objects.create(
                packet=packet,
                actor=operator,
                action="delivered",
                from_status=status_before,
                to_status=TrackedPacket.DELIVERED,
                note="Received by the declared final destination.",
                metadata={"handoff_id": handoff.pk, "sequence": handoff.sequence},
            )
    return handoff


def cancel_scan_session(*, session, operator):
    _require_session_operator(session, operator)
    if session.status not in PacketScanSession.OPEN_STATUSES:
        return session
    session.status = PacketScanSession.CANCELLED
    session.save(update_fields=("status",))
    return session
