from __future__ import annotations

import secrets

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .access import can_prepare_packets, department_for_user
from .models import PacketEvent, TrackedPacket


class PacketWorkflowError(ValueError):
    pass


def _tracking_number():
    return f"TP-{timezone.localdate():%Y%m%d}-{secrets.token_hex(3).upper()}"


def create_packet(*, actor, title, contents_manifest, final_destination_department,
                  final_destination_employee=None, confidentiality=TrackedPacket.INTERNAL,
                  expected_document_count=None, expected_page_count=None,
                  department_record=None, report_run=None):
    origin_department = department_for_user(actor)
    if not origin_department or not can_prepare_packets(actor, origin_department):
        raise PacketWorkflowError("You are not allowed to prepare packets for this department.")

    with transaction.atomic():
        packet = None
        for _attempt in range(5):
            candidate = TrackedPacket(
                tracking_number=_tracking_number(),
                title=title,
                contents_manifest=contents_manifest,
                expected_document_count=expected_document_count,
                expected_page_count=expected_page_count,
                confidentiality=confidentiality,
                origin_department=origin_department,
                prepared_by=actor,
                final_destination_department=final_destination_department,
                final_destination_employee=final_destination_employee,
                department_record=department_record,
                report_run=report_run,
            )
            candidate.full_clean()
            try:
                with transaction.atomic():
                    candidate.save(force_insert=True)
                packet = candidate
                break
            except IntegrityError:
                continue
        if packet is None:
            raise PacketWorkflowError("A unique tracking reference could not be created. Try again.")
        PacketEvent.objects.create(
            packet=packet,
            actor=actor,
            action="created",
            to_status=packet.status,
            metadata={
                "origin_department_id": origin_department.pk,
                "final_destination_department_id": final_destination_department.pk,
                "final_destination_employee_id": getattr(final_destination_employee, "pk", None),
                "department_record_id": getattr(department_record, "pk", None),
                "report_run_id": getattr(report_run, "pk", None),
            },
        )
    return packet


def update_draft_packet(*, packet, actor, **changes):
    if packet.status != packet.DRAFT:
        raise PacketWorkflowError("Only draft packet details can be changed.")
    if packet.origin_department != department_for_user(actor) or not can_prepare_packets(actor, packet.origin_department):
        raise PacketWorkflowError("You are not allowed to update this packet.")

    allowed = {
        "title", "contents_manifest", "expected_document_count", "expected_page_count",
        "confidentiality", "final_destination_department", "final_destination_employee",
        "department_record", "report_run",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ValidationError(f"Unsupported packet fields: {', '.join(sorted(unknown))}")

    before = {field: getattr(packet, field) for field in changes}
    for field, value in changes.items():
        setattr(packet, field, value)
    packet.full_clean()
    packet.save(update_fields=tuple(changes) + ("updated_at",))
    PacketEvent.objects.create(
        packet=packet,
        actor=actor,
        action="draft_updated",
        from_status=packet.status,
        to_status=packet.status,
        metadata={"changed_fields": sorted(field for field in changes if before[field] != getattr(packet, field))},
    )
    return packet
