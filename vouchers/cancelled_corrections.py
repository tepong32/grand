"""Retained cancellation evidence for reopening a prior-payable DV."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from accounting.claim_attributions import _exact_reversal
from accounting.models import JournalEntry
from accounting.posted_evidence import verify_source_link
from finance.models import FinancePostingRule as Rule
from .models import PaymentInstrument, VoucherPostingRequest


def _posted(request):
    entry = JournalEntry.objects.filter(public_id=request.accounting_entry_public_id).first()
    if entry is None:
        raise ValidationError("The retained payment-cycle journal cannot be found.")
    verify_source_link(request, entry, source_type="voucher")
    audit = entry.audit_events.filter(action="posted", actor_id=entry.posted_by_id,
        department_id=entry.department_id).first()
    debit, credit = entry.totals
    if (entry.status != JournalEntry.POSTED or not entry.posted_at or not entry.posted_by_id
            or entry.posted_by_id == entry.created_by_id or not audit or debit <= 0 or debit != credit
            or Decimal(str(audit.snapshot.get("debit", "0"))) != debit
            or Decimal(str(audit.snapshot.get("credit", "0"))) != credit):
        raise ValidationError("Retain the independent posting decision and balanced payment-cycle totals.")
    return entry


def retired_instruments(case, *, exclude_request=None):
    """Only an independently posted correction retires an old check's route."""
    from .deduction_corrections import digest
    retired = set()
    for request in case.posting_requests.filter(status=VoucherPostingRequest.POSTED, kind=Rule.REVERSAL):
        if request.pk == exclude_request:
            continue
        correction = request.payload.get("deduction_correction", {})
        rows = correction.get("cancelled_instruments", [])
        if not rows:
            continue
        entry = _posted(request)
        if (entry.status != JournalEntry.POSTED or not entry.posted_by_id
                or entry.source_snapshot.get("deduction_correction") != correction
                or not entry.reversal_of_id or str(entry.reversal_of.public_id) != correction.get("original_entry")
                or not _exact_reversal(entry, entry.reversal_of)
                or digest(request.payload) != request.payload_checksum):
            raise ValidationError("The retired check correction no longer reproduces its posted evidence.")
        retired.update(row["instrument"] for row in rows)
    return retired


def has_unretired_instruments(case):
    return case.payment_instruments.exclude(public_id__in=retired_instruments(case)).exists()


def cancellation_evidence(case, prior_evidence, correction_date, *, exclude_request=None):
    """Caller holds the case lock shared by issue/cancel/release and corrections."""
    from .deduction_corrections import digest
    rows = []
    retired = retired_instruments(case, exclude_request=exclude_request)
    for instrument in case.payment_instruments.exclude(public_id__in=retired).order_by("pk"):
        if (instrument.status != PaymentInstrument.CANCELLED or instrument.released_at
                or not instrument.cancelled_at or not instrument.cancelled_by_id or not instrument.cancellation_reason):
            raise ValidationError("A payment instrument already exists. Cancel every unreleased check and reconcile its posting before correcting deductions.")
        if correction_date < timezone.localdate(instrument.cancelled_at):
            raise ValidationError("The deduction correction cannot predate the check cancellation.")
        requests = [r for r in case.posting_requests.all()
            if r.payload.get("trigger", {}).get("instrument_public_id") == str(instrument.public_id)]
        cancellations = [r for r in requests if r.kind == Rule.CANCELLATION and r.status != r.CANCELLED]
        if len(cancellations) != 1:
            raise ValidationError("Reconcile the check's one governed cancellation decision first.")
        cancellation = cancellations[0]
        if (cancellation.payload.get("trigger", {}).get("type") != "payment_instrument_cancelled"
                or cancellation.payload.get("trigger", {}).get("check_number") != instrument.check_number
                or cancellation.posting_rule_snapshot.get("recognition_point") != Rule.PAYMENT_CANCELLATION
                or cancellation.jev_date != timezone.localdate(instrument.cancelled_at)):
            raise ValidationError("The cancellation decision must match this check and its actual cancellation date.")
        for request in requests:
            if (digest(request.payload) != request.payload_checksum
                    or digest(request.posting_rule_snapshot) != request.posting_rule_checksum
                    or request.payload.get("prior_payable") != prior_evidence
                    or Decimal(request.payload["event_amount"]) != instrument.amount
                    or request.jev_date > correction_date):
                raise ValidationError("The cancelled payment cycle differs from the retained claim, amount or correction date.")
            if request.status not in (request.POSTED, request.NOT_REQUIRED):
                # Discarded/superseded payment requests require separate reconciliation.
                raise ValidationError("Resolve every payment-cycle posting before correcting deductions.")
        if cancellation.status == cancellation.NOT_REQUIRED:
            if (cancellation.posting_rule_snapshot.get("accounting_effect") != Rule.NO_ENTRY
                    or any(r.status != r.NOT_REQUIRED for r in requests)
                    or JournalEntry.objects.filter(source_type="voucher",
                        source_reference__in=[str(r.public_id) for r in requests]).exists()):
                raise ValidationError("The no-entry cancellation must have no financial payment journal.")
        elif cancellation.status == cancellation.POSTED:
            payments = [r for r in requests if r.kind in (Rule.PAYMENT, Rule.REPLACEMENT) and r.status == r.POSTED]
            if len(payments) != 1 or len([r for r in requests if r.status == r.POSTED]) != 2:
                raise ValidationError("The cancellation must reverse exactly one posted payment.")
            payment = payments[0]
            original = _posted(payment)
            reversal = _posted(cancellation)
            if (reversal.status != JournalEntry.POSTED or not reversal.posted_by_id
                    or not original.posted_by_id or not _exact_reversal(reversal, original)
                    or reversal.reversal_entries.exclude(status=JournalEntry.VOIDED).exists()):
                raise ValidationError("Retain the exact independently posted cancellation of the original payment.")
        else:
            raise ValidationError("Post and reconcile the check cancellation before correcting deductions.")
        rows.append({"instrument": str(instrument.public_id), "check_number": instrument.check_number,
            "bank_account": instrument.bank_account_code, "amount": str(instrument.amount),
            "cancelled_at": instrument.cancelled_at.isoformat(), "cancelled_by": instrument.cancelled_by_id,
            "reason": instrument.cancellation_reason,
            "requests": [{"id": str(r.public_id), "payload_checksum": r.payload_checksum,
                "rule_checksum": r.posting_rule_checksum, "entry": str(r.accounting_entry_public_id or "")}
                for r in sorted(requests, key=lambda r: r.pk)]})
    return rows
