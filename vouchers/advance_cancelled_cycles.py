"""Verify cancelled, never released advance instruments without rewriting their sources."""
from django.core.exceptions import ValidationError
from .models import PaymentInstrument


def evidence(case, day, *, instrument_ids=None, exclude_request=None):
    from .cancelled_corrections import cancellation_evidence, retired_instruments
    instruments = case.payment_instruments.all()
    if instrument_ids is None:
        instruments = instruments.exclude(public_id__in=retired_instruments(case, exclude_request=exclude_request))
    else:
        instruments = instruments.filter(public_id__in=instrument_ids)
    if instruments.exclude(status=PaymentInstrument.CANCELLED).exists() or instruments.filter(released_at__isnull=False).exists():
        raise ValidationError('Cancel every unreleased advance check and reconcile its payment cycle before correcting recognition.')
    ids = list(instruments.values_list('public_id', flat=True))
    return cancellation_evidence(case, None, day, instrument_ids=ids)
