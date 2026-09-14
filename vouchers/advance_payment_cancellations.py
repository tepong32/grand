"""Pin an advance's issuance payment before its governed cancellation is posted."""
from django.core.exceptions import ValidationError
from accounting.models import JournalEntry
from accounting.posted_evidence import verify_source_link
from .models import VoucherPostingRequest as Request

KEY = 'advance_payment_cancellation'


def payload_evidence(case, rule, trigger):
    from finance.models import FinancePostingRule as Rule
    if rule.event_kind != Rule.CANCELLATION or rule.accounting_effect != Rule.JOURNAL_ENTRY:
        return {}
    recognition = case.posting_requests.filter(kind=Request.RECOGNITION, status=Request.POSTED).order_by('-pk').first()
    if recognition is None or not recognition.payload.get('advance_recognition'):
        return {}
    from .prior_payables import original_payment
    from .advance_sources import posted_request
    original = original_payment(case, trigger)
    entry = posted_request(original)
    return {KEY: {'original_request':str(original.public_id), 'original_entry':str(entry.public_id),
                  'original_checksum':original.payload_checksum, 'original_rule_checksum':original.posting_rule_checksum}}


def source(request):
    from .advance_sources import posted_request
    data = request.payload[KEY]
    original = Request.objects.get(case_id=request.case_id, public_id=data['original_request'])
    entry = posted_request(original, allow_reversal_reference=request.public_id)
    if (original.kind not in (Request.PAYMENT, Request.REPLACEMENT)
            or str(entry.public_id) != data['original_entry']
            or original.payload_checksum != data['original_checksum']
            or original.posting_rule_checksum != data['original_rule_checksum']
            or original.payload.get('trigger', {}).get('instrument_public_id') != request.payload.get('trigger', {}).get('instrument_public_id')):
        raise ValidationError('Retain the exact advance payment source for cancellation.')
    return entry


def validate(entry):
    from accounting.claim_attributions import _exact_reversal
    request = Request.objects.select_related('case').get(public_id=entry.source_reference)
    verify_source_link(request, entry, source_type='voucher')
    original = source(request)
    if (request.kind != Request.CANCELLATION or entry.source_snapshot.get(KEY) != request.payload[KEY]
            or not _exact_reversal(entry, original) or entry.entry_date < original.entry_date):
        raise ValidationError('The advance cancellation must exactly reverse its retained payment.')
    fields = ('category', 'reference_key', 'reference_label', 'source_code', 'debit', 'credit')
    expected = sorted((*row[:4], row[5], row[4]) for row in original.subsidiary_lines.values_list(*fields))
    if sorted(entry.subsidiary_lines.values_list(*fields)) != expected:
        raise ValidationError('Retain the original payable subsidiary in the advance cancellation.')
    return request
