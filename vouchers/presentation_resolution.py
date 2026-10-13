"""Close a bank finding only against an existing governed financial disposition."""
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError

from accounting.models import JournalEntry
from accounting.posted_evidence import require_persisted_posting, verify_source_link
from .models import VoucherPostingRequest as Request, ReturnedInstrumentReview, PaymentInstrument
from .remittances import _digest


def payment_sources(instrument):
    sources = instrument.case.posting_requests.filter(
        payload__trigger__instrument_public_id=str(instrument.public_id)).exclude(status=Request.CANCELLED)
    released = sources.filter(kind=Request.PAYMENT, payload__trigger__type='payment_instrument_released')
    if released.exists():
        return released
    # A no-entry replacement issuance must not stand in for an unfinished release JEV.
    return sources.filter(kind=Request.REPLACEMENT if instrument.replaces_id else Request.PAYMENT,
        status=Request.POSTED, payload__trigger__type='payment_instrument_issued',
        posting_rule_snapshot__recognition_point='payment_replacement' if instrument.replaces_id else 'payment_issuance')


def completed_request(request, instrument, actor):
    if (request.case_id != instrument.case_id or request.finance_department_id != instrument.case.configuration_release.department_id
            or request.payload.get('trigger', {}).get('instrument_public_id') != str(instrument.public_id)
            or request.payload.get('bank_account_code') != instrument.bank_account_code
            or Decimal(request.payload.get('event_amount', '0')) != instrument.amount
            or _digest(request.payload) != request.payload_checksum
            or _digest(request.posting_rule_snapshot) != request.posting_rule_checksum):
        raise ValidationError('The disposition must reproduce this instrument and its original governed source.')
    result = {'request': str(request.public_id), 'payload_checksum': request.payload_checksum,
              'rule_checksum': request.posting_rule_checksum}
    if request.status == Request.NOT_REQUIRED:
        if request.posting_rule_snapshot.get('accounting_effect') != 'no_entry' or request.accounting_entry_public_id:
            raise ValidationError('Retain an explicit governed no-entry decision.')
        result['effect'] = 'no_entry'
    elif request.status == Request.POSTED:
        try:
            entry = JournalEntry.objects.get(public_id=request.accounting_entry_public_id)
        except JournalEntry.DoesNotExist:
            raise ValidationError('The reconciled financial source journal is missing.')
        entry = require_persisted_posting(entry, actor, source_type='voucher')
        verify_source_link(request, entry, source_type='voucher')
        if entry.reversal_entries.exclude(status=JournalEntry.VOIDED).exists():
            raise ValidationError('Resolve the financial source reversal before linking this disposition.')
        result.update(effect='posted', entry=str(entry.public_id), number=entry.reference)
    else:
        raise ValidationError('Complete independent posting and source reconciliation before closing this finding.')
    return result


def evidence(report, actor, outcome, reference):
    try:
        public_id = UUID(str(reference))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Select the exact completed source disposition.')
    instrument = report.instrument
    if outcome == 'paid_reconciled':
        if instrument.status != PaymentInstrument.RELEASED or not instrument.released_at or not instrument.receipt_reference:
            raise ValidationError('Actual release evidence is missing. Resolve the external release discrepancy first.')
        request = payment_sources(instrument).filter(public_id=public_id).first()
        if request is None:
            raise ValidationError('Choose the original instrument payment source, not recognition or cancellation.')
        return completed_request(request, instrument, actor)
    review = ReturnedInstrumentReview.objects.select_related('posting_request', 'original_payment_request', 'exception').filter(
        public_id=public_id, instrument=instrument, case=instrument.case,
        status__in=(ReturnedInstrumentReview.READY_FOR_TREASURY, ReturnedInstrumentReview.CLOSED)).first()
    if (review is None or not review.reviewed_by_id or not review.reviewed_at or not review.posting_request_id
            or review.exception.instrument_id != instrument.pk or instrument.status != PaymentInstrument.BANK_RETURNED
            or not review.original_payment_request_id
            or review.posting_request.kind != Request.REVERSAL
            or review.posting_request.posting_rule_snapshot.get('recognition_point') != 'payment_return'
            or review.posting_request.payload.get('trigger', {}).get('source_payment_request') != str(review.original_payment_request.public_id)
            or review.posting_request.payload.get('trigger', {}).get('review_public_id') != str(review.public_id)):
        raise ValidationError('Choose the completed governed Accounting review of this returned instrument.')
    result = completed_request(review.posting_request, instrument, actor)
    result.update(returned_review=str(review.public_id), outcome=review.outcome,
                  reviewed_by=review.reviewed_by_id, reviewed_at=review.reviewed_at.isoformat())
    return result
