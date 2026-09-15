"""Finance source associations over TracePoint's existing physical item history."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from departments.models import Department
from tracepoint.access import packet_is_visible, can_resolve_exceptions
from tracepoint.models import PacketItem, TrackedPacket
from .models import TreasuryCollectionSource as Source, CollectionChequeCustodyLink as Link
from .collections import require
from .remittances import _digest


def locked_item(item_id):
    candidate = PacketItem.objects.get(pk=item_id)
    packet = TrackedPacket.objects.select_for_update().get(pk=candidate.current_packet_id)
    item = PacketItem.objects.select_for_update().get(pk=item_id)
    if item.current_packet_id != packet.pk:
        raise ValidationError('The item moved while its custody link was being reviewed. Reload its current packet.')
    return item,packet


def identity(source,item):
    return {'source':str(source.public_id),'source_checksum':source.proposal_checksum,
        'item':str(item.public_id),'item_reference':item.reference_number,
        'origin_packet':str(item.origin_packet.public_id)}


def verify(link):
    if (_digest(link.snapshot) != link.checksum
            or _digest(link.source.proposal) != link.source.proposal_checksum
            or any(link.snapshot.get(key) != value for key,value in identity(link.source,link.item).items())):
        raise ValidationError('The retained cheque-to-custody item association changed.')


@transaction.atomic
def link(*,source,item,actor,evidence_reference):
    office = require(actor,'vouchers.link_collection_custody')
    if office.pk != source.treasury_department_id:
        raise PermissionDenied
    Department.objects.select_for_update().get(pk=office.pk)
    source = Source.objects.select_for_update().get(pk=source.pk)
    if source.kind != Source.CHEQUE_RETURN or source.status not in (Source.PROPOSED,Source.APPROVED,Source.POSTED):
        raise ValidationError('Choose the retained incoming cheque bank return.')
    from .cheque_returns import validate
    validate(source)
    item,packet = locked_item(item.pk)
    if not packet_is_visible(actor,packet):
        raise PermissionDenied
    authorized = (packet.status == packet.DRAFT and packet.prepared_by_id == actor.pk
        or packet.status in (packet.ACTIVE,packet.ON_HOLD) and packet.current_holder_id == actor.pk)
    if not authorized or hasattr(item,'voucher_case'):
        raise ValidationError('Choose your draft or currently held TracePoint item, not an item assigned to another financial source.')
    evidence_reference = str(evidence_reference or '').strip()
    if not evidence_reference or len(evidence_reference) > 4000:
        raise ValidationError('Retain the actual cheque/item identification evidence, up to 4,000 characters.')
    snapshot = dict(identity(source,item),evidence_reference=evidence_reference)
    current = source.custody_links.filter(withdrawn_at__isnull=True).first()
    if current:
        verify(current)
        if current.item_id == item.pk and current.linked_by_id == actor.pk and current.snapshot == snapshot:
            return current
        raise ValidationError('Independently withdraw the existing association before linking a different custody item.')
    if item.cheque_custody_links.filter(withdrawn_at__isnull=True).exists():
        raise ValidationError('This physical item already has an active cheque source association.')
    return Link.objects.create(source=source,item=item,
        version=(source.custody_links.aggregate(v=Max('version'))['v'] or 0)+1,
        snapshot=snapshot,checksum=_digest(snapshot),linked_by=actor)


@transaction.atomic
def withdraw(*,link,actor,reason):
    office = require(actor,'vouchers.link_collection_custody')
    if office.pk != link.source.treasury_department_id or not can_resolve_exceptions(actor,office):
        raise PermissionDenied
    Department.objects.select_for_update().get(pk=office.pk)
    Source.objects.select_for_update().get(pk=link.source_id)
    item,packet = locked_item(link.item_id)
    row = Link.objects.select_for_update().get(pk=link.pk)
    if not packet_is_visible(actor,packet):
        raise PermissionDenied
    if row.withdrawn_at or row.linked_by_id == actor.pk or not str(reason or '').strip():
        raise ValidationError('An independent authorized custody reviewer must retain the reason for withdrawing this association.')
    verify(row)
    row.withdrawn_by,row.withdrawn_at,row.withdrawal_reason = actor,timezone.now(),reason.strip()
    row.save(update_fields=('withdrawn_by','withdrawn_at','withdrawal_reason'))
    return row


@transaction.atomic
def evidence(source,actor):
    from .collection_views import visible_sources
    if not visible_sources(actor).filter(pk=source.pk).exists():
        raise PermissionDenied
    Department.objects.select_for_update().get(pk=source.treasury_department_id)
    Source.objects.select_for_update().get(pk=source.pk)
    row = source.custody_links.filter(withdrawn_at__isnull=True).select_related('source','item__origin_packet').first()
    if not row:
        return None
    item,packet = locked_item(row.item_id)
    if not packet_is_visible(actor,packet):
        raise PermissionDenied
    verify(row)
    handoffs = [{'sequence':h.sequence,'from':h.from_employee_name,'to':h.to_employee_name,
        'confirmed_at':h.confirmed_at.isoformat(),'reference':h.pk,'terminal_receipt':h.is_terminal_receipt}
        for h in packet.handoffs.order_by('sequence')]
    moves = [{'reference':move.pk,'action':move.get_action_display(),
        'from_packet':move.from_packet_id,'to_packet':move.to_packet_id,'recorded_at':move.created_at.isoformat()}
        for move in item.moves.order_by('pk')]
    return {'link_version':row.version,'link_checksum':row.checksum,'item':str(item.public_id),
        'item_reference':item.reference_number,'packet':str(packet.public_id),'tracking_number':packet.tracking_number,
        'packet_version':packet.state_version,'status':packet.get_status_display(),
        'holder':packet.current_holder.get_full_name() or packet.current_holder.username if packet.current_holder_id else '',
        'physical_confirmation':bool(handoffs and packet.current_holder_id), 'handoffs':handoffs,'item_moves':moves,
        'evidence_reference':row.snapshot['evidence_reference']}


def require_output_access(snapshot,actor):
    proof = snapshot.get('cheque_custody')
    if not proof:
        return
    packet = TrackedPacket.objects.get(public_id=proof['packet'])
    item = PacketItem.objects.select_related('current_packet').get(public_id=proof['item'])
    if not packet_is_visible(actor,packet) or not packet_is_visible(actor,item.current_packet):
        raise PermissionDenied
