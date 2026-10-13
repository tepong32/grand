"""Officer cheque refund settlement facts, separate from dated application holds."""
from django.core.exceptions import ValidationError

from .models import TreasuryCollectionSource as Source
from .remittances import _digest


def settlement(source):
    if not source.proposal.get('advance_refund') or not source.proposal.get('cheque'):
        return None
    if _digest(source.proposal) != source.proposal_checksum:
        raise ValidationError('The retained officer cheque refund changed.')
    if source.status in (Source.REJECTED, Source.WITHDRAWN):
        return {'status': 'Receipt rejected or withdrawn; consult the retained decision', 'date': ''}
    if source.corrections.filter(status=Source.POSTED).exists():
        from .collection_corrections import corrected_sources
        from django.utils import timezone
        if source.pk in corrected_sources(source.treasury_department_id, timezone.localdate()):
            return {'status': 'Receipt corrected; reservation released from the correction date', 'date': ''}
    if source.status != Source.POSTED:
        return {'status': 'Cheque amount reserved; receipt posting and bank clearing pending', 'date': ''}
    from .collections import posted_receipt
    posted_receipt(source)
    bank_return = source.cheque_returns.filter(status__in=(Source.PROPOSED,Source.APPROVED,Source.POSTED)).first()
    if bank_return:
        if bank_return.status != Source.POSTED:
            return {'status':'Bank return under review; cheque amount remains reserved','date':''}
        from .collection_corrections import original_journal
        original_journal(bank_return)
        return {'status':'Bank returned cheque; original advance adjusted','date':bank_return.source_date.isoformat()}
    if source.corrections.filter(status__in=(Source.PROPOSED, Source.APPROVED)).exists():
        return {'status': 'Receipt correction pending; cheque amount remains reserved', 'date': ''}
    from .cheque_clearing import verify
    clearance = source.cheque_clearances.filter(status='approved').first()
    if clearance is None:
        return {'status': 'Cheque amount reserved; bank clearing pending', 'date': ''}
    verify(clearance)
    return {'status': 'Officer refund cheque clearing confirmed', 'date': clearance.cleared_on.isoformat()}
