"""Retained original advance and dated actual disbursement evidence."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.utils import timezone

from accounting.models import JournalEntry, JournalSubsidiaryLine
from accounting.posted_evidence import verify_source_link
from finance.models import FinancePostingRule as Rule
from .models import VoucherPostingRequest as Request, PaymentInstrumentException


def posted_request(request):
    entry = JournalEntry.objects.filter(public_id=request.accounting_entry_public_id).first()
    if request.status != Request.POSTED or entry is None:
        raise ValidationError("Reconcile the independently posted source journal first.")
    verify_source_link(request, entry, source_type="voucher")
    event = entry.audit_events.filter(action="posted").first()
    debit, credit = entry.totals
    try:
        recorded = (Decimal(event.snapshot["debit"]), Decimal(event.snapshot["credit"])) if event else None
        if recorded is not None and not all(value.is_finite() for value in recorded):
            recorded = None
    except (KeyError, TypeError, InvalidOperation):
        recorded = None
    if (entry.status != JournalEntry.POSTED or not entry.posted_at or not entry.posted_by_id
            or entry.posted_by_id in (entry.created_by_id, entry.submitted_by_id)
            or event is None or event.actor_id != entry.posted_by_id
            or event.department_id != entry.department_id or debit <= 0 or debit != credit
            or recorded != (debit, credit)):
        raise ValidationError("The source must retain independent posting attribution and exact audited totals.")
    if entry.reversal_entries.exclude(status=JournalEntry.VOIDED).exists():
        raise ValidationError("Resolve the source journal's reversal before using this advance.")
    return entry


def original(detail):
    detail = JournalSubsidiaryLine.objects.select_related("entry", "journal_line__account").get(pk=detail.pk)
    if detail.category != JournalSubsidiaryLine.ADVANCE or detail.debit <= 0 or detail.credit:
        raise ValidationError("Select an original recognized officer advance debit.")
    request = Request.objects.select_related("case").filter(public_id=detail.source_reference).first()
    if request is None or request.kind != Request.RECOGNITION:
        raise ValidationError("The advance needs its original governed DV recognition source.")
    entry = posted_request(request)
    case_sources = [str(value) for value in request.case.posting_requests.filter(kind=Request.RECOGNITION)
                    .values_list("public_id", flat=True)]
    if JournalSubsidiaryLine.objects.filter(category=JournalSubsidiaryLine.ADVANCE, debit__gt=0,
            entry__status=JournalEntry.POSTED, entry__source_type="voucher", entry__source_reference__in=case_sources).count() != 1:
        raise ValidationError("Resolve the case's ambiguous original advance recognitions before allocating its payments.")
    evidence = request.payload.get("advance_recognition")
    lines = list(entry.lines.select_related("account").order_by("sequence", "pk"))
    others = [line for line in lines if line.pk != detail.journal_line_id]
    instruction = [line for line in request.posting_rule_snapshot.get("lines", [])
                   if line.get("account_source") == "advance_account"]
    if (entry.pk != detail.entry_id or len(others) != 1 or len(instruction) != 1
            or not evidence or detail.source_snapshot.get("advance_recognition") != evidence
            or evidence.get("party_type") != "employee" or evidence.get("variant_kind") != "cash_advance"
            or detail.reference_key != request.payload.get("payee_key")
            or detail.reference_label != request.payload.get("payee_name")
            or detail.reference_key != f"finance-party:{evidence.get('party_code')}"
            or detail.journal_line.account.code != instruction[0].get("ledger_account_code")
            or detail.journal_line.account.account_type != "asset"
            or detail.journal_line.account.normal_balance != "debit"
            or detail.journal_line.debit != detail.debit or detail.journal_line.credit
            or str(detail.debit) != request.payload.get("gross_amount")
            or others[0].credit != detail.debit or others[0].debit
            or others[0].account.account_type != "liability"):
        raise ValidationError("The original officer, advance asset and payable must reproduce the retained recognition.")
    return detail, request, others[0]


def disbursement(detail, as_of):
    """Read actual releases; callers must serialize the case before reserving an application.

    This is evidence, not an authorization or reservation. Returns are withheld from
    their observed date, including pending Accounting resolution; replacement releases
    contribute separately only with their own reconciled source.
    """
    detail, recognition, payable = original(detail)
    if as_of > timezone.localdate():
        raise ValidationError("Choose an actual advance reporting date.")
    if detail.entry.entry_date > as_of:
        return {"recognized": Decimal("0"), "released": Decimal("0"), "withheld_returns": Decimal("0"),
                "released_net": Decimal("0"), "sources": []}
    released = Decimal("0")
    withheld = Decimal("0")
    sources = []
    for instrument in recognition.case.payment_instruments.order_by("pk"):
        if instrument.released_at is None or timezone.localdate(instrument.released_at) > as_of:
            continue
        day = timezone.localdate(instrument.released_at)
        requests = list(recognition.case.posting_requests.filter(kind=Request.PAYMENT,
            trigger_key=f"payment-instrument:{instrument.public_id}:released"))
        if len(requests) != 1:
            raise ValidationError("The released advance instrument needs one retained release posting decision.")
        request = requests[0]
        if request.status != Request.POSTED:
            raise ValidationError("Post and reconcile the advance payment before applying its release.")
        payment = posted_request(request)
        trigger = request.payload.get("trigger", {})
        lines = list(payment.lines.select_related("account"))
        debits = [line for line in lines if line.debit]
        credits = [line for line in lines if line.credit]
        if (payment.fund_id != detail.entry.fund_id or payment.entry_date != day
                or request.posting_rule_snapshot.get("recognition_point") != Rule.PAYMENT_RELEASE
                or request.payload.get("payee_key") != detail.reference_key
                or request.payload.get("event_amount") != str(instrument.amount)
                or trigger.get("instrument_public_id") != str(instrument.public_id)
                or trigger.get("receipt_reference") != instrument.receipt_reference
                or not instrument.receipt_reference or not instrument.released_by_id
                or trigger.get("claimant_id") != instrument.released_to_claimant_id
                or len(lines) != 2 or len(debits) != 1 or len(credits) != 1
                or debits[0].account_id != payable.account_id or debits[0].debit != instrument.amount
                or credits[0].credit != instrument.amount or credits[0].account.account_type != "asset"
                or credits[0].account_id == detail.journal_line.account_id):
            raise ValidationError("The actual released check, receipt and payable-to-bank journal must agree.")
        returned = list(instrument.exceptions.filter(kind=PaymentInstrumentException.RETURNED,
            observed_on__lte=as_of).order_by("observed_on", "pk"))
        released += instrument.amount
        if returned:
            withheld += instrument.amount
        sources.append({"instrument": str(instrument.public_id), "check_number": instrument.check_number,
            "released_on": day.isoformat(), "receipt_reference": instrument.receipt_reference,
            "request": str(request.public_id), "entry": str(payment.public_id),
            "payload_checksum": request.payload_checksum, "amount": str(instrument.amount),
            "returns": [{"exception": str(item.public_id), "observed_on": item.observed_on.isoformat()}
                        for item in returned]})
    if released - withheld > detail.debit:
        raise ValidationError("Net released instruments exceed the original advance; resolve the payment chain.")
    return {"recognized": detail.debit, "released": released, "withheld_returns": withheld,
            "released_net": released - withheld, "sources": sources}
