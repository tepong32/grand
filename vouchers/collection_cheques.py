"""Actual incoming cheque identity; deposit shares retain the whole instrument."""
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import TreasuryCollectionSource as Source
from .remittances import _digest


def instrument_identity(values):
    return _digest({key: ' '.join(str(values.get(key) or '').casefold().split())
        for key in ('bank', 'drawer_account', 'number')})


def capture(treasury, day, supplied, *, bank=None, advance=None):
    if not supplied:
        return None
    if bank:
        raise ValidationError('Record the received cheque separately from a direct bank credit.')
    if advance is not None:
        raise ValidationError('Officer cheque refunds require the pending cheque-clearing workflow; do not record them as cash refunds.')
    fields = ('bank', 'drawer_account', 'number', 'drawer')
    values = {key: str(supplied.get(key) or '').strip() for key in fields}
    if any(not value or len(value) > 160 for value in values.values()):
        raise ValidationError('Retain the cheque bank, drawer account reference, number and drawer, up to 160 characters each.')
    issued_on = supplied.get('date')
    if isinstance(issued_on, str):
        try:
            issued_on = date.fromisoformat(issued_on)
        except ValueError:
            issued_on = None
    if not isinstance(issued_on, date) or issued_on > day:
        raise ValidationError('Record the cheque date; a future-dated instrument cannot be recorded as a current collection.')
    values['date'] = issued_on.isoformat()
    if supplied.get('kind'):
        if supplied['kind'] not in ('ordinary', 'manager', 'cashier'):
            raise ValidationError('Choose an ordinary, manager’s or cashier’s cheque explicitly.')
        values['kind'] = supplied['kind']
    values['identity'] = instrument_identity(values)
    # Caller holds the existing Treasury department lock across identity and source creation.
    from .collection_corrections import corrected_sources
    corrected = corrected_sources(treasury.pk, day)
    for prior in Source.objects.filter(treasury_department=treasury, kind=Source.RECEIPT,
            status__in=(Source.PROPOSED, Source.APPROVED, Source.POSTED)).exclude(pk__in=corrected):
        retained = prior.proposal.get('cheque')
        if retained and _digest(prior.proposal) != prior.proposal_checksum:
            raise ValidationError('The retained cheque source changed. Resolve its evidence before accepting another instrument.')
        # Recompute identity from retained fields without rewriting earlier dated digests.
        if retained and instrument_identity(retained) == values['identity']:
            raise ValidationError('This cheque already has an active collection receipt. Resolve its existing source first.')
    return values


def validate_deposit(receipt, value):
    if receipt.proposal.get('cheque') and Decimal(value) != receipt.amount:
        raise ValidationError('Deposit the whole cheque amount once; a cheque cannot be split between deposit slips.')
