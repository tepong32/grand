"""Retain and retire reviewed bank-return routes during original advance correction."""
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import ReturnedInstrumentReview as Review, PaymentInstrumentException as ExceptionRecord


def evidence(instrument, day, *, correction=None):
    from .advance_payment_cancellations import released_payment
    from .advance_corrected_applications import journal_evidence
    from .advance_sources import posted_request
    reviews = list(instrument.returned_accounting_reviews.filter(outcome=Review.REISSUE,
        status__in=(Review.READY_FOR_TREASURY, Review.CLOSED)).select_related('original_payment_request', 'exception'))
    if len(reviews) != 1 or getattr(instrument, 'replacement', None) is not None:
        raise ValidationError('Resolve the returned advance and its replacement before correcting recognition.')
    review = reviews[0]
    if review.original_payment_request is None or not instrument.released_at:
        raise ValidationError('Retain the released advance and original payment review.')
    payment, proof = released_payment(review.original_payment_request, instrument)
    if proof is None or day < review.posting_request.jev_date or day < review.exception.observed_on:
        raise ValidationError('Post the exact advance bank return before correcting its recognition.')
    retained = None
    if correction:
        retained = next((row.get('advance_bank_return') for row in
            correction.payload['advance_recognition_correction'].get('cancelled_instruments', [])
            if row['instrument'] == str(instrument.public_id)), None)
    if review.status == Review.CLOSED:
        event = correction.case.events.filter(action='advance_return_retired',
            metadata__correction=str(correction.public_id), metadata__review=str(review.public_id)).first() if correction else None
        if (not retained or not event or correction.status != correction.POSTED
                or event.metadata != {'correction': str(correction.public_id), 'review': str(review.public_id),
                    'from_version': retained['state_version'], 'to_version': review.state_version}
                or review.state_version != retained['state_version'] + 1
                or not review.closed_at or event.actor_id != review.closed_by_id
                or review.exception.status != ExceptionRecord.RESOLVED
                or review.exception.resolved_by_id != event.actor_id
                or review.exception.resolution != resolution(correction)):
            raise ValidationError('Retain the exact posted advance correction that retired this return authorization.')
    elif review.exception.status != ExceptionRecord.OPEN:
        raise ValidationError('Retain the open reviewed advance bank-return exception.')
    return {'instrument': str(instrument.public_id), 'check_number': instrument.check_number,
        'bank_account': instrument.bank_account_code, 'amount': str(instrument.amount),
        'released_at': instrument.released_at.isoformat(),
        'payment_journal': journal_evidence(review.original_payment_request, payment),
        'return_journal': journal_evidence(review.posting_request, posted_request(review.posting_request)),
        'advance_bank_return': {'review': str(review.public_id), 'version': review.version,
            'state_version': review.state_version, 'status': review.status,
            'prepared_by': review.prepared_by_id, 'reviewed_by': review.reviewed_by_id,
            'reviewed_at': review.reviewed_at.isoformat(), 'decision': review.accounting_decision_reason,
            'evidence': review.accounting_evidence_reference, 'treasury_evidence': review.treasury_evidence_reference,
            'treasury_note': review.treasury_note, 'exception': str(review.exception.public_id),
            'observed_on': review.exception.observed_on.isoformat(), 'return': proof},
        'requests': [{'id': str(request.public_id), 'payload_checksum': request.payload_checksum,
            'rule_checksum': request.posting_rule_checksum, 'entry': str(request.accounting_entry_public_id)}
            for request in (review.original_payment_request, review.posting_request)]}


def matches(current, retained):
    """Compare immutable evidence separately from an explicitly verified closure."""
    if 'advance_bank_return' not in retained:
        return current == retained
    before, after = retained['advance_bank_return'], current.get('advance_bank_return', {})
    if before.get('status') != Review.READY_FOR_TREASURY:
        return False
    if after.get('status') == Review.READY_FOR_TREASURY:
        return current == retained
    return (after.get('status') == Review.CLOSED
        and {k: v for k, v in current.items() if k != 'advance_bank_return'} ==
            {k: v for k, v in retained.items() if k != 'advance_bank_return'}
        and {k: v for k, v in after.items() if k not in ('status', 'state_version')} ==
            {k: v for k, v in before.items() if k not in ('status', 'state_version')})


def resolution(request):
    return f'Original advance correction {request.public_id} posted as {request.jev_number}; old replacement authorization retired.'


def close_reviews(request, actor):
    """Called inside the case-locked reconciliation transaction after source validation."""
    from .cash_positions import resolve_instrument_exception
    from .services import _event
    for row in request.payload['advance_recognition_correction'].get('cancelled_instruments', []):
        retained = row.get('advance_bank_return')
        if not retained:
            continue
        review = Review.objects.select_for_update().get(public_id=retained['review'], case_id=request.case_id)
        if review.status != Review.READY_FOR_TREASURY or review.state_version != retained['state_version']:
            raise ValidationError('The advance return authorization changed before correction reconciliation.')
        review.status, review.closed_by, review.closed_at = Review.CLOSED, actor, timezone.now()
        review.state_version += 1
        review.save(update_fields=('status', 'closed_by', 'closed_at', 'state_version'))
        resolve_instrument_exception(exception=review.exception, actor=actor, permission_required=False,
            resolution=resolution(request))
        _event(request.case, actor, 'advance_return_retired', request.case.current_stage, resolution(request),
            {'correction': str(request.public_id), 'review': str(review.public_id),
             'from_version': retained['state_version'], 'to_version': review.state_version},
            f'advance-return-retired:{request.public_id}:{review.public_id}')
