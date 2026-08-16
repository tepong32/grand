from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .access import (
    can_complete_packets,
    can_receive_packets,
    can_resolve_exceptions,
    department_for_user,
    packet_is_visible,
)
from .handoffs import _employee_snapshot
from .models import (
    PacketCorrection,
    PacketDiscrepancy,
    PacketEvent,
    PacketScanSession,
    TrackedPacket,
)


class PacketControlError(ValueError):
    pass


def _participant_departments(packet):
    return {
        packet.origin_department_id,
        packet.current_department_id,
        packet.final_destination_department_id,
    }


def _can_resolve_packet(actor, packet):
    department = department_for_user(actor)
    return bool(
        department
        and department.pk in _participant_departments(packet)
        and can_resolve_exceptions(actor, department)
    )


def _cancel_open_scans(packet):
    PacketScanSession.objects.filter(
        packet=packet,
        status__in=PacketScanSession.OPEN_STATUSES,
    ).update(status=PacketScanSession.CANCELLED)


def complete_packet(*, packet, actor, note=""):
    if department_for_user(actor) != packet.final_destination_department or not can_complete_packets(actor, packet.final_destination_department):
        raise PacketControlError("Only authorized employees at the final destination can complete this packet.")
    with transaction.atomic():
        locked = TrackedPacket.objects.select_for_update().get(pk=packet.pk)
        if locked.status == TrackedPacket.COMPLETED:
            return locked
        if locked.status != TrackedPacket.DELIVERED:
            raise PacketControlError("A packet must be delivered before its work can be completed.")
        now = timezone.now()
        locked.status = TrackedPacket.COMPLETED
        locked.completed_at = now
        locked.completed_by = actor
        locked.state_version += 1
        locked.full_clean()
        locked.save(update_fields=("status", "completed_at", "completed_by", "state_version", "updated_at"))
        PacketEvent.objects.create(
            packet=locked, actor=actor, action="completed", from_status=TrackedPacket.DELIVERED,
            to_status=TrackedPacket.COMPLETED, note=note.strip(),
        )
    return locked


def hold_packet(*, packet, actor, reason):
    reason = reason.strip()
    if not reason:
        raise PacketControlError("Explain why the packet is being placed on hold.")
    if actor.pk != packet.current_holder_id and not _can_resolve_packet(actor, packet):
        raise PacketControlError("Only the current holder or an authorized exception resolver can place this packet on hold.")
    with transaction.atomic():
        locked = TrackedPacket.objects.select_for_update().get(pk=packet.pk)
        if locked.status != TrackedPacket.ACTIVE:
            raise PacketControlError("Only an active packet can be placed on hold.")
        _cancel_open_scans(locked)
        locked.status = TrackedPacket.ON_HOLD
        locked.held_at = timezone.now()
        locked.hold_reason = reason
        locked.state_version += 1
        locked.full_clean()
        locked.save(update_fields=("status", "held_at", "hold_reason", "state_version", "updated_at"))
        PacketEvent.objects.create(
            packet=locked, actor=actor, action="placed_on_hold", from_status=TrackedPacket.ACTIVE,
            to_status=TrackedPacket.ON_HOLD, note=reason,
        )
    return locked


def resume_packet(*, packet, actor, note=""):
    if actor.pk != packet.current_holder_id and not _can_resolve_packet(actor, packet):
        raise PacketControlError("Only the current holder or an authorized exception resolver can resume this packet.")
    with transaction.atomic():
        locked = TrackedPacket.objects.select_for_update().get(pk=packet.pk)
        if locked.status != TrackedPacket.ON_HOLD:
            raise PacketControlError("Only an on-hold packet can be resumed.")
        prior_reason = locked.hold_reason
        locked.status = TrackedPacket.ACTIVE
        locked.held_at = None
        locked.hold_reason = ""
        locked.state_version += 1
        locked.full_clean()
        locked.save(update_fields=("status", "held_at", "hold_reason", "state_version", "updated_at"))
        PacketEvent.objects.create(
            packet=locked, actor=actor, action="resumed", from_status=TrackedPacket.ON_HOLD,
            to_status=TrackedPacket.ACTIVE, note=note.strip(), metadata={"hold_reason": prior_reason},
        )
    return locked


def cancel_packet(*, packet, actor, reason):
    reason = reason.strip()
    if not reason:
        raise PacketControlError("Explain why tracking is being cancelled.")
    allowed = packet.status == TrackedPacket.DRAFT and actor.pk == packet.prepared_by_id
    allowed = allowed or _can_resolve_packet(actor, packet)
    if not allowed:
        raise PacketControlError("You are not allowed to cancel this packet.")
    with transaction.atomic():
        locked = TrackedPacket.objects.select_for_update().get(pk=packet.pk)
        if locked.status not in (TrackedPacket.DRAFT, TrackedPacket.ACTIVE, TrackedPacket.ON_HOLD):
            raise PacketControlError("Delivered, completed, or already cancelled packets cannot be cancelled.")
        from_status = locked.status
        _cancel_open_scans(locked)
        locked.status = TrackedPacket.CANCELLED
        locked.cancelled_at = timezone.now()
        locked.cancellation_reason = reason
        locked.state_version += 1
        locked.full_clean()
        locked.save(update_fields=("status", "cancelled_at", "cancellation_reason", "state_version", "updated_at"))
        PacketEvent.objects.create(
            packet=locked, actor=actor, action="cancelled", from_status=from_status,
            to_status=TrackedPacket.CANCELLED, note=reason,
        )
    return locked


def report_discrepancy(*, packet, actor, category, description, related_handoff=None):
    description = description.strip()
    if not packet_is_visible(actor, packet):
        raise PacketControlError("You cannot report a discrepancy for a packet outside your work.")
    if not description:
        raise PacketControlError("Describe the discrepancy in plain language.")
    discrepancy = PacketDiscrepancy(
        packet=packet,
        related_handoff=related_handoff,
        category=category,
        description=description,
        reported_by=actor,
    )
    discrepancy.full_clean()
    discrepancy.save()
    PacketEvent.objects.create(
        packet=packet, actor=actor, action="discrepancy_reported", from_status=packet.status,
        to_status=packet.status, note=description,
        metadata={"discrepancy_id": discrepancy.pk, "category": category, "handoff_id": getattr(related_handoff, "pk", None)},
    )
    return discrepancy


def resolve_discrepancy(*, discrepancy, actor, resolution):
    resolution = resolution.strip()
    if not _can_resolve_packet(actor, discrepancy.packet):
        raise PacketControlError("Only an authorized exception resolver can close this discrepancy.")
    if not resolution:
        raise PacketControlError("Record how the discrepancy was resolved.")
    if discrepancy.status == PacketDiscrepancy.RESOLVED:
        return discrepancy
    discrepancy.status = PacketDiscrepancy.RESOLVED
    discrepancy.resolved_by = actor
    discrepancy.resolution = resolution
    discrepancy.resolved_at = timezone.now()
    discrepancy.full_clean()
    discrepancy.save(update_fields=("status", "resolved_by", "resolution", "resolved_at"))
    PacketEvent.objects.create(
        packet=discrepancy.packet, actor=actor, action="discrepancy_resolved",
        from_status=discrepancy.packet.status, to_status=discrepancy.packet.status,
        note=resolution, metadata={"discrepancy_id": discrepancy.pk},
    )
    return discrepancy


def correct_current_custody(*, packet, actor, corrected_holder, reason, related_handoff=None):
    reason = reason.strip()
    if not _can_resolve_packet(actor, packet):
        raise PacketControlError("Only an authorized exception resolver can correct current custody.")
    if not can_receive_packets(corrected_holder):
        raise PacketControlError("The corrected holder must be an active employee with a department assignment.")
    if not reason:
        raise PacketControlError("Explain the evidence for this custody correction.")
    with transaction.atomic():
        locked = TrackedPacket.objects.select_for_update().select_related("current_holder").get(pk=packet.pk)
        if locked.status not in (TrackedPacket.ACTIVE, TrackedPacket.ON_HOLD):
            raise PacketControlError("Only active or on-hold custody can be corrected administratively.")
        if locked.current_holder_id == corrected_holder.pk:
            raise PacketControlError("The corrected holder is already the recorded holder.")
        prior = _employee_snapshot(locked.current_holder) if locked.current_holder else {
            "name": "", "department_name": "",
        }
        corrected = _employee_snapshot(corrected_holder)
        correction = PacketCorrection(
            packet=locked,
            related_handoff=related_handoff,
            prior_holder=locked.current_holder,
            corrected_holder=corrected_holder,
            prior_holder_name=prior["name"],
            corrected_holder_name=corrected["name"],
            prior_department_name=prior["department_name"],
            corrected_department_name=corrected["department_name"],
            reason=reason,
            created_by=actor,
        )
        correction.full_clean()
        correction.save(force_insert=True)
        _cancel_open_scans(locked)
        locked.current_holder = corrected_holder
        locked.current_department = corrected["department"]
        locked.state_version += 1
        locked.full_clean()
        locked.save(update_fields=("current_holder", "current_department", "state_version", "updated_at"))
        PacketEvent.objects.create(
            packet=locked, actor=actor, action="custody_corrected", from_status=locked.status,
            to_status=locked.status, note=reason,
            metadata={"correction_id": correction.pk, "related_handoff_id": getattr(related_handoff, "pk", None)},
        )
    return correction
