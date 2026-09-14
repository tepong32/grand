"""Verify cancelled, never released advance instruments without rewriting their sources."""
from django.core.exceptions import ValidationError
from .models import PaymentInstrument


def evidence(case, day, *, instrument_ids=None, exclude_request=None, correction=None):
    from .cancelled_corrections import cancellation_evidence, retired_instruments
    instruments = case.payment_instruments.all()
    if instrument_ids is None:
        instruments = instruments.exclude(public_id__in=retired_instruments(case, exclude_request=exclude_request))
    else:
        instruments = instruments.filter(public_id__in=instrument_ids)
    if (instruments.exclude(status__in=(PaymentInstrument.CANCELLED, PaymentInstrument.BANK_RETURNED)).exists()
            or instruments.filter(status=PaymentInstrument.CANCELLED, released_at__isnull=False).exists()):
        raise ValidationError('Cancel every unreleased advance check and reconcile its payment cycle before correcting recognition.')
    rows = []
    for instrument in instruments.order_by('pk'):
        if instrument.status == PaymentInstrument.BANK_RETURNED:
            from .advance_returned_cycles import evidence as returned_evidence
            rows.append(returned_evidence(instrument, day, correction=correction))
        else:
            rows.extend(cancellation_evidence(case, None, day, instrument_ids=[instrument.public_id]))
    return rows
