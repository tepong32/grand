from __future__ import annotations

import secrets

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .access import can_prepare_packets, department_for_user
from .models import PacketCheckpoint, PacketEvent, PacketItem, PacketItemMove, PacketScanSession, TrackedPacket


class PacketWorkflowError(ValueError):
    pass


def _tracking_number():
    return f"TP-{timezone.localdate():%Y%m%d}-{secrets.token_hex(3).upper()}"


def _item_reference():
    return f"TPV-{timezone.localdate():%Y%m%d}-{secrets.token_hex(4).upper()}"


def create_packet(*, actor, title, contents_manifest, final_destination_department,
                  final_destination_employee=None, confidentiality=TrackedPacket.INTERNAL,
                  expected_document_count=None, expected_page_count=None,
                  department_record=None, report_run=None, parent_packet=None):
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
                parent_packet=parent_packet,
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


def _require_bundle_actor(packet, actor):
    if packet.status == TrackedPacket.DRAFT:
        allowed = actor.pk == packet.prepared_by_id and can_prepare_packets(actor, packet.origin_department)
    elif packet.status == TrackedPacket.ACTIVE:
        allowed = actor.pk == packet.current_holder_id
    else:
        allowed = False
    if not allowed:
        raise PacketWorkflowError("Only the draft preparer or current physical holder can change this bundle.")


def add_packet_item(*, packet, actor, title, description="", expected_attachment_count=0, expected_page_count=None):
    if packet.status != TrackedPacket.DRAFT:
        raise PacketWorkflowError("Register voucher items before the packet is activated.")
    _require_bundle_actor(packet, actor)
    with transaction.atomic():
        locked = TrackedPacket.objects.select_for_update().get(pk=packet.pk)
        if locked.status != TrackedPacket.DRAFT:
            raise PacketWorkflowError("Register voucher items before the packet is activated.")
        _require_bundle_actor(locked, actor)
        item = None
        for _attempt in range(5):
            candidate = PacketItem(
                reference_number=_item_reference(),
                origin_packet=locked,
                current_packet=locked,
                title=title.strip(),
                description=description.strip(),
                expected_attachment_count=expected_attachment_count or 0,
                expected_page_count=expected_page_count,
                created_by=actor,
            )
            candidate.full_clean()
            try:
                with transaction.atomic():
                    candidate.save(force_insert=True)
                item = candidate
                break
            except IntegrityError:
                continue
        if item is None:
            raise PacketWorkflowError("A unique voucher reference could not be created. Try again.")
        PacketItemMove.objects.create(
            item=item,
            action=PacketItemMove.REGISTERED,
            to_packet=locked,
            actor=actor,
            note="Registered in the preparer's voucher manifest.",
        )
        PacketEvent.objects.create(
            packet=locked,
            actor=actor,
            action="voucher_registered",
            from_status=locked.status,
            to_status=locked.status,
            note=item.title,
            metadata={"item_id": item.pk, "item_reference": item.reference_number},
        )
    return item


def add_checkpoint(*, packet, actor, department, purpose, label, employee=None, instructions="", required=True):
    if packet.status != TrackedPacket.DRAFT or actor.pk != packet.prepared_by_id:
        raise PacketWorkflowError("Only the preparer can define checkpoints before activation.")
    if not can_prepare_packets(actor, packet.origin_department):
        raise PacketWorkflowError("You are not allowed to define this route.")
    with transaction.atomic():
        locked = TrackedPacket.objects.select_for_update().get(pk=packet.pk)
        if locked.status != TrackedPacket.DRAFT or locked.prepared_by_id != actor.pk:
            raise PacketWorkflowError("Only the preparer can define checkpoints before activation.")
        sequence = (locked.checkpoints.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        checkpoint = PacketCheckpoint(
            packet=locked,
            sequence=sequence,
            department=department,
            employee=employee,
            purpose=purpose,
            label=label.strip(),
            instructions=instructions.strip(),
            required=required,
        )
        checkpoint.full_clean()
        checkpoint.save(force_insert=True)
        PacketEvent.objects.create(
            packet=locked,
            actor=actor,
            action="checkpoint_added",
            from_status=locked.status,
            to_status=locked.status,
            note=checkpoint.label,
            metadata={
                "checkpoint_id": checkpoint.pk,
                "sequence": checkpoint.sequence,
                "department_id": department.pk,
                "employee_id": getattr(employee, "pk", None),
                "purpose": purpose,
                "required": required,
            },
        )
    return checkpoint


def remove_checkpoint(*, checkpoint, actor):
    packet = checkpoint.packet
    if packet.status != TrackedPacket.DRAFT or actor.pk != packet.prepared_by_id:
        raise PacketWorkflowError("Checkpoint plans can only be edited by the preparer before activation.")
    with transaction.atomic():
        locked = PacketCheckpoint.objects.select_for_update().select_related("packet").get(pk=checkpoint.pk)
        locked_packet = TrackedPacket.objects.select_for_update().get(pk=locked.packet_id)
        if locked_packet.status != TrackedPacket.DRAFT or locked_packet.prepared_by_id != actor.pk:
            raise PacketWorkflowError("Checkpoint plans can only be edited by the preparer before activation.")
        metadata = {
            "checkpoint_id": locked.pk,
            "sequence": locked.sequence,
            "department_id": locked.department_id,
            "purpose": locked.purpose,
        }
        note = locked.label
        locked.delete()
        PacketEvent.objects.create(
            packet=locked_packet,
            actor=actor,
            action="checkpoint_removed",
            from_status=locked_packet.status,
            to_status=locked_packet.status,
            note=note,
            metadata=metadata,
        )


def split_packet_items(*, packet, items, actor, title, note=""):
    item_ids = [getattr(item, "pk", item) for item in items]
    if not item_ids:
        raise PacketWorkflowError("Choose at least one voucher to split.")
    _require_bundle_actor(packet, actor)
    with transaction.atomic():
        source = TrackedPacket.objects.select_for_update().select_related(
            "origin_department", "prepared_by", "current_holder", "current_department",
            "final_destination_department", "final_destination_employee",
        ).get(pk=packet.pk)
        _require_bundle_actor(source, actor)
        moving = list(PacketItem.objects.select_for_update().filter(pk__in=item_ids, current_packet=source))
        if len(moving) != len(set(item_ids)):
            raise PacketWorkflowError("One or more selected vouchers no longer belong to this bundle.")
        if len(moving) >= source.voucher_items.count():
            raise PacketWorkflowError("A split must leave at least one voucher in the original bundle.")

        child = None
        for _attempt in range(5):
            candidate = TrackedPacket(
                tracking_number=_tracking_number(),
                title=title.strip(),
                contents_manifest=f"Split from {source.tracking_number}: " + ", ".join(item.reference_number for item in moving),
                expected_document_count=len(moving),
                expected_page_count=sum(item.expected_page_count or 0 for item in moving) or None,
                confidentiality=source.confidentiality,
                status=source.status,
                origin_department=source.origin_department,
                prepared_by=source.prepared_by,
                final_destination_department=source.final_destination_department,
                final_destination_employee=source.final_destination_employee,
                current_holder=source.current_holder,
                current_department=source.current_department,
                parent_packet=source,
                state_version=source.state_version + (1 if source.status == TrackedPacket.ACTIVE else 0),
                activated_at=source.activated_at,
            )
            candidate.full_clean()
            try:
                with transaction.atomic():
                    candidate.save(force_insert=True)
                child = candidate
                break
            except IntegrityError:
                continue
        if child is None:
            raise PacketWorkflowError("A unique child packet reference could not be created. Try again.")

        inherited_checkpoints = []
        for planned in source.checkpoints.filter(status=PacketCheckpoint.PENDING).select_related("department", "employee"):
            inherited_checkpoints.append(PacketCheckpoint(
                packet=child,
                sequence=planned.sequence,
                department=planned.department,
                employee=planned.employee,
                purpose=planned.purpose,
                label=planned.label,
                instructions=planned.instructions,
                required=planned.required,
            ))
        for inherited in inherited_checkpoints:
            inherited.full_clean()
        PacketCheckpoint.objects.bulk_create(inherited_checkpoints)

        for item in moving:
            item.current_packet = child
            item.full_clean()
            item.save(update_fields=("current_packet", "updated_at"))
            PacketItemMove.objects.create(
                item=item,
                action=PacketItemMove.SPLIT,
                from_packet=source,
                to_packet=child,
                actor=actor,
                note=note.strip(),
            )
        PacketScanSession.objects.filter(packet=source, status__in=PacketScanSession.OPEN_STATUSES).update(
            status=PacketScanSession.CANCELLED,
        )
        source.state_version += 1
        source.save(update_fields=("state_version", "updated_at"))
        metadata = {
            "child_packet_id": child.pk,
            "child_tracking_number": child.tracking_number,
            "item_references": [item.reference_number for item in moving],
            "inherited_pending_checkpoints": len(inherited_checkpoints),
        }
        PacketEvent.objects.create(
            packet=source,
            actor=actor,
            action="bundle_split",
            from_status=source.status,
            to_status=source.status,
            note=note.strip(),
            metadata=metadata,
        )
        PacketEvent.objects.create(
            packet=child,
            actor=actor,
            action="split_packet_created",
            from_status="",
            to_status=child.status,
            note=f"Created from {source.tracking_number}. {note.strip()}".strip(),
            metadata={"parent_packet_id": source.pk, "item_references": metadata["item_references"]},
        )
    return child


def rebundle_packet_items(*, source_packet, target_packet, items, actor, note=""):
    item_ids = [getattr(item, "pk", item) for item in items]
    if not item_ids:
        raise PacketWorkflowError("Choose at least one voucher to rebundle.")
    if source_packet.pk == target_packet.pk:
        raise PacketWorkflowError("Choose a different destination bundle.")
    with transaction.atomic():
        locked_packets = {
            row.pk: row for row in TrackedPacket.objects.select_for_update().filter(
                pk__in=(source_packet.pk, target_packet.pk),
            ).select_related("origin_department", "current_holder", "current_department")
        }
        source = locked_packets[source_packet.pk]
        target = locked_packets[target_packet.pk]
        _require_bundle_actor(source, actor)
        _require_bundle_actor(target, actor)
        if source.status != target.status or source.origin_department_id != target.origin_department_id:
            raise PacketWorkflowError("Bundles must share the same origin and workflow state before rebundling.")
        if source.status == TrackedPacket.ACTIVE and source.current_holder_id != target.current_holder_id:
            raise PacketWorkflowError("Active bundles can only be combined while held by the same employee.")
        if TrackedPacket.CONFIDENTIALITY_RANK[target.confidentiality] < TrackedPacket.CONFIDENTIALITY_RANK[source.confidentiality]:
            raise PacketWorkflowError("The destination bundle cannot use weaker confidentiality handling.")
        moving = list(PacketItem.objects.select_for_update().filter(pk__in=item_ids, current_packet=source))
        if len(moving) != len(set(item_ids)):
            raise PacketWorkflowError("One or more selected vouchers no longer belong to the source bundle.")
        if len(moving) >= source.voucher_items.count():
            raise PacketWorkflowError("Rebundling must leave at least one voucher in the source bundle.")
        for item in moving:
            item.current_packet = target
            item.full_clean()
            item.save(update_fields=("current_packet", "updated_at"))
            PacketItemMove.objects.create(
                item=item,
                action=PacketItemMove.REBUNDLED,
                from_packet=source,
                to_packet=target,
                actor=actor,
                note=note.strip(),
            )
        PacketScanSession.objects.filter(
            packet__in=(source, target), status__in=PacketScanSession.OPEN_STATUSES,
        ).update(status=PacketScanSession.CANCELLED)
        TrackedPacket.objects.filter(pk__in=(source.pk, target.pk)).update(
            state_version=F("state_version") + 1,
            updated_at=timezone.now(),
        )
        metadata = {
            "other_packet_id": target.pk,
            "other_tracking_number": target.tracking_number,
            "item_references": [item.reference_number for item in moving],
        }
        PacketEvent.objects.create(
            packet=source, actor=actor, action="vouchers_rebundled_out",
            from_status=source.status, to_status=source.status, note=note.strip(), metadata=metadata,
        )
        PacketEvent.objects.create(
            packet=target, actor=actor, action="vouchers_rebundled_in",
            from_status=target.status, to_status=target.status, note=note.strip(),
            metadata={**metadata, "other_packet_id": source.pk, "other_tracking_number": source.tracking_number},
        )
    return target


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
