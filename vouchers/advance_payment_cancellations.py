"""Pin an advance payment before its governed cancellation or bank return posts."""
from django.core.exceptions import ValidationError
from accounting.posted_evidence import verify_source_link
from .models import VoucherPostingRequest as Request

KEY = 'advance_payment_cancellation'
RETURN_KEY = 'advance_payment_return'


def source_key(payload):
    keys = [key for key in (KEY, RETURN_KEY) if payload.get(key)]
    if len(keys) != 1:
        raise ValidationError('Retain one explicit advance payment reversal purpose.')
    return keys[0]


def payload_evidence(case, rule, trigger):
    from finance.models import FinancePostingRule as Rule
    if rule.accounting_effect != Rule.JOURNAL_ENTRY:
        return {}
    if rule.event_kind == Rule.CANCELLATION:
        key = KEY
    elif rule.event_kind == Rule.REVERSAL and trigger.get('type') == 'payment_instrument_returned_by_bank':
        key = RETURN_KEY
    else:
        return {}
    recognition = case.posting_requests.filter(kind=Request.RECOGNITION, status=Request.POSTED).order_by('-pk').first()
    if recognition is None or not recognition.payload.get('advance_recognition'):
        return {}
    from .prior_payables import original_payment
    from .advance_sources import posted_request
    original = original_payment(case, trigger)
    entry = posted_request(original)
    return {key: {'original_request':str(original.public_id), 'original_entry':str(entry.public_id),
                  'original_checksum':original.payload_checksum, 'original_rule_checksum':original.posting_rule_checksum}}


def source(request):
    from .advance_sources import posted_request
    data = request.payload[source_key(request.payload)]
    original = Request.objects.get(case_id=request.case_id, public_id=data['original_request'])
    entry = posted_request(original, allow_reversal_reference=request.public_id)
    if (original.kind not in (Request.PAYMENT, Request.REPLACEMENT)
            or str(entry.public_id) != data['original_entry']
            or original.payload_checksum != data['original_checksum']
            or original.posting_rule_checksum != data['original_rule_checksum']
            or request.payload.get('trigger', {}).get('source_payment_request', str(original.public_id)) != str(original.public_id)
            or original.payload.get('trigger', {}).get('instrument_public_id') != request.payload.get('trigger', {}).get('instrument_public_id')):
        raise ValidationError('Retain the exact advance payment source for cancellation or return.')
    return entry


def validate(entry):
    from accounting.claim_attributions import _exact_reversal
    from finance.models import FinancePostingRule as Rule
    request = Request.objects.select_related('case').get(public_id=entry.source_reference)
    verify_source_link(request, entry, source_type='voucher')
    original = source(request)
    key = source_key(request.payload)
    kind = Request.CANCELLATION if key == KEY else Request.REVERSAL
    point = Rule.PAYMENT_CANCELLATION if key == KEY else Rule.PAYMENT_RETURN
    trigger = 'payment_instrument_cancelled' if key == KEY else 'payment_instrument_returned_by_bank'
    if (request.kind != kind or entry.source_snapshot.get(key) != request.payload[key]
            or source_key(entry.source_snapshot) != key
            or request.posting_rule_snapshot.get('recognition_point') != point
            or request.payload.get('trigger', {}).get('type') != trigger
            or not _exact_reversal(entry, original) or entry.entry_date < original.entry_date):
        raise ValidationError('The advance cancellation or return must exactly reverse its retained payment.')
    if list(entry.lines.order_by('sequence').values_list('cash_flow_category', flat=True)) != list(
            original.lines.order_by('sequence').values_list('cash_flow_category', flat=True)):
        raise ValidationError('Retain each original cash-flow purpose in the advance payment reversal.')
    fields = ('category', 'reference_key', 'reference_label', 'source_code', 'debit', 'credit')
    expected = sorted((*row[:4], row[5], row[4]) for row in original.subsidiary_lines.values_list(*fields))
    if sorted(entry.subsidiary_lines.values_list(*fields)) != expected:
        raise ValidationError('Retain the original payable subsidiary in the advance cancellation.')
    return request


def released_payment(request, instrument):
    """Verify a later exact return while retaining the original dated release source."""
    from .advance_sources import posted_request
    from .models import ReturnedInstrumentReview as Review, PaymentInstrument, PaymentInstrumentException
    reviews = [review for review in instrument.returned_accounting_reviews.select_related('posting_request', 'exception')
        .filter(original_payment_request=request, posting_request__status=Request.POSTED)
        if review.posting_request.payload.get(RETURN_KEY)]
    if not reviews:
        return posted_request(request), None
    if len(reviews) != 1:
        raise ValidationError('Retain one independently posted return for the original advance payment.')
    review = reviews[0]
    returned = review.posting_request
    trigger = returned.payload.get('trigger', {})
    entry = posted_request(returned)
    validate(entry)
    if (review.status not in (Review.READY_FOR_TREASURY, Review.CLOSED)
            or instrument.status != PaymentInstrument.BANK_RETURNED
            or review.exception.kind != PaymentInstrumentException.RETURNED
            or review.exception.instrument_id != instrument.pk
            or review.case_id != request.case_id or returned.case_id != request.case_id
            or not review.reviewed_at or not review.reviewed_by_id
            or review.reviewed_by_id == review.prepared_by_id or returned.requested_by_id != review.reviewed_by_id
            or trigger.get('review_public_id') != str(review.public_id)
            or trigger.get('source_payment_request') != str(request.public_id)
            or trigger.get('outcome') != review.outcome
            or trigger.get('evidence_reference') != review.accounting_evidence_reference
            or entry.entry_date < review.exception.observed_on):
        raise ValidationError('Retain the independent advance bank-return review and actual source chronology.')
    return source(returned), {'review':str(review.public_id), 'request':str(returned.public_id),
        'entry':str(entry.public_id), 'posted_on':entry.entry_date.isoformat(), 'payload_checksum':returned.payload_checksum}
