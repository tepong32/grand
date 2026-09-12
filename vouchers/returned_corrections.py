"""Use reviewed, posted bank-return evidence before correcting a prior-payable DV."""
from django.core.exceptions import ValidationError

from accounting.claim_attributions import _exact_reversal
from accounting.models import JournalEntry
from .models import PaymentInstrument, PaymentInstrumentException, ReturnedInstrumentReview as Review


def evidence(instrument, prior_evidence, correction_date):
    from .cancelled_corrections import _posted
    reviews = list(instrument.returned_accounting_reviews.filter(outcome=Review.REISSUE,
        status__in=(Review.READY_FOR_TREASURY, Review.CLOSED)).select_related(
            "posting_request", "original_payment_request", "exception").order_by("-version"))
    if len(reviews) != 1:
        raise ValidationError("Reconcile the returned check's independent replacement authorization and posted reversal first.")
    review = reviews[0]
    replacement = getattr(instrument, "replacement", None)
    if (review.case_id != instrument.case_id or not review.reviewed_at or not review.reviewed_by_id
            or review.reviewed_by_id == review.prepared_by_id or not review.original_payment_request_id
            or not review.posting_request_id or not instrument.released_at
            or (review.status == Review.CLOSED and (replacement is None
                or replacement.status not in (PaymentInstrument.CANCELLED, PaymentInstrument.BANK_RETURNED)))):
        raise ValidationError("Resolve the returned check and any replacement before correcting this DV.")
    payment, returned = review.original_payment_request, review.posting_request
    trigger = returned.payload.get("trigger", {})
    if (payment.status != payment.POSTED or returned.status != returned.POSTED
            or payment.case_id != instrument.case_id or returned.case_id != instrument.case_id
            or returned.requested_by_id != review.reviewed_by_id
            or trigger.get("type") != "payment_instrument_returned_by_bank"
            or trigger.get("review_public_id") != str(review.public_id)
            or trigger.get("instrument_public_id") != str(instrument.public_id)
            or trigger.get("source_payment_request") != str(payment.public_id)
            or trigger.get("outcome") != Review.REISSUE
            or trigger.get("evidence_reference") != review.accounting_evidence_reference
            or any(r.payload.get("prior_payable") != prior_evidence for r in (payment, returned))
            or correction_date < returned.jev_date or correction_date < review.exception.observed_on):
        raise ValidationError("The returned payment must retain this claim, review and actual correction chronology.")
    original, reversal = _posted(payment), _posted(returned)
    if not _exact_reversal(reversal, original) or reversal.reversal_entries.exclude(status=JournalEntry.VOIDED).exists():
        raise ValidationError("Retain the exact posted bank-return reversal before correcting deductions.")
    if review.status == Review.READY_FOR_TREASURY and review.exception.status != PaymentInstrumentException.OPEN:
        raise ValidationError("The current returned-item exception differs from its reviewed correction route.")
    return {"instrument": str(instrument.public_id), "status": instrument.status,
        "check_number": instrument.check_number, "bank_account": instrument.bank_account_code,
        "amount": str(instrument.amount), "released_at": instrument.released_at.isoformat(),
        "allocation": instrument.prior_payable_allocation,
        "bank_return": {"review": str(review.public_id), "version": review.version,
            "state_version": review.state_version, "status": review.status, "outcome": review.outcome,
            "reviewed_by": review.reviewed_by_id, "reviewed_at": review.reviewed_at.isoformat(),
            "decision": review.accounting_decision_reason, "evidence": review.accounting_evidence_reference,
            "exception": str(review.exception.public_id), "observed_on": review.exception.observed_on.isoformat()},
        "requests": [{"id": str(r.public_id), "payload_checksum": r.payload_checksum,
            "rule_checksum": r.posting_rule_checksum, "entry": str(r.accounting_entry_public_id)} for r in (payment, returned)]}


def close_reviews(request, actor):
    """Caller holds the case and default transaction; failed handoffs roll back together."""
    from django.utils import timezone
    from .cash_positions import resolve_instrument_exception
    rows = request.payload["deduction_correction"].get("resolved_instruments", [])
    for row in rows:
        retained = row.get("bank_return")
        if not retained or retained["status"] == Review.CLOSED:
            continue
        review = Review.objects.select_for_update().get(public_id=retained["review"], case_id=request.case_id)
        if review.status != Review.READY_FOR_TREASURY or review.state_version != retained["state_version"]:
            raise ValidationError("The bank-return authorization changed before correction completion.")
        review.status, review.closed_by, review.closed_at = Review.CLOSED, actor, timezone.now()
        review.state_version += 1
        review.save(update_fields=("status", "closed_by", "closed_at", "state_version"))
        resolve_instrument_exception(exception=review.exception, actor=actor, permission_required=False,
            resolution=f"Deduction correction {request.public_id} posted as {request.jev_number}; the old replacement authorization is retired. Prepare a newly validated DV and check.")
