"""Retire an unposted return approval without erasing the actual receipt history."""
from django.core.exceptions import ValidationError
from django.db import transaction

from accounting.models import JournalEntry
from accounting.posted_evidence import verify_source_link
from .models import RemittanceReturn, RemittancePostingRequest, TreasuryRemittanceBatch
from .remittances import _require, require_remittance_review_scope, _digest, _event


@transaction.atomic
def withdraw_return(*, item, actor, reason):
    _require(actor, 'vouchers.approve_remittances')
    batch = TreasuryRemittanceBatch.objects.select_for_update().get(pk=item.batch_id)
    item = RemittanceReturn.objects.select_for_update().get(pk=item.pk)
    require_remittance_review_scope(actor, batch)
    if item.prepared_by_id == actor.pk:
        raise ValidationError('The receipt preparer cannot withdraw its independent approval.')
    reason = str(reason or '').strip()
    if not reason:
        raise ValidationError('Record why the approved receipt must be replaced before posting.')
    if item.status == item.WITHDRAWN:
        return item
    if item.status != item.APPROVED or not item.posting_request_id:
        raise ValidationError('Only an approved, unposted return can be withdrawn here.')
    if _digest(item.proposal) != item.proposal_checksum:
        raise ValidationError('The retained receipt proposal no longer reproduces.')
    sources = list(batch.posting_requests.select_for_update().filter(
        payload__remittance_return__return=str(item.public_id)).order_by('pk'))
    if not sources or item.posting_request_id not in {source.pk for source in sources}:
        raise ValidationError('The approved receipt is missing its retained posting chain.')
    if any(source.status == source.POSTED or _digest(source.payload) != source.payload_checksum for source in sources):
        raise ValidationError('A posted or inconsistent receipt needs a separate Accounting correction.')
    by_reference = {str(source.public_id): source for source in sources}
    with transaction.atomic(using='finance'):
        # Materialization uses this same batch -> original journal order. Posting
        # locks the actual return entry, so a posting race is observed here.
        JournalEntry.objects.select_for_update().get(public_id=item.proposal['original_entry'])
        entries = list(JournalEntry.objects.select_for_update().filter(source_type='remittance',
            source_reference__in=by_reference).order_by('pk'))
        for entry in entries:
            verify_source_link(by_reference[entry.source_reference], entry, source_type='remittance')
            if entry.status != entry.VOIDED:
                raise ValidationError('Discard the unposted receipt JEV first. A posted receipt requires a separate correction.')
        for source in sources:
            if source.accounting_entry_public_id and not any(entry.public_id == source.accounting_entry_public_id for entry in entries):
                raise ValidationError('Investigate the missing retained receipt JEV before withdrawing its approval.')
        current = next(source for source in sources if source.pk == item.posting_request_id)
        current.status, current.failure_reason = current.CANCELLED, f'Approval withdrawn before posting: {reason}'
        current.save(update_fields=('status', 'failure_reason'))
        item.status = item.WITHDRAWN
        item.save(update_fields=('status',))
        batch.state_version += 1
        batch.save(update_fields=('state_version', 'updated_at'))
        _event(batch, actor, 'remittance_return_withdrawn', batch.status, reason,
            {'return': str(item.public_id), 'proposal_checksum': item.proposal_checksum,
             'posting_requests': list(by_reference), 'original_reviewed_by': item.reviewed_by_id,
             'discarded_entries': [str(entry.public_id) for entry in entries]})
    return item
