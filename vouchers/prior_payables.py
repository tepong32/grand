"""Prior-claim DV settlement through the existing governed posting workflow."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.models import JournalEntry, JournalLine, PayableClaimReservation, PostingMapping
from accounting.payables import _reserve_claim, _release_unused_claim, reservation_evidence, verify_reservation
from accounting.claim_attributions import identity as claim_identity
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from finance.services import posting_rule_snapshot

from .models import AccountingValidation, PayableIntake, PaymentInstrument, VoucherPostingRequest


def requires_prior_claim(case):
    intake = getattr(case, "payable_intake", None)
    return intake is not None and intake.recognition_decision in (
        PayableIntake.ACCRUE_BEFORE_SETTLEMENT, PayableIntake.SETTLE_EXISTING_PAYABLE)


def current_evidence(case):
    validation = case.accounting_validations.filter(decision=AccountingValidation.ACCEPTED).order_by("-pk").first()
    evidence = validation.prior_payable_snapshot if validation else {}
    if not evidence:
        if requires_prior_claim(case):
            raise ValidationError("This prior-payable voucher has no retained claim reservation. Complete Accounting validation first.")
        return {}
    from accounting.claim_groups import resolve
    reservations = resolve(evidence, case_public_id=case.public_id)
    if evidence.get("schema") == 2:
        from .claim_allocations import verify_case
        verify_case(case, evidence)
    if sum(r.amount for r in reservations) != case.disbursement_voucher.gross_amount:
        raise ValidationError("The voucher differs from its retained prior-payable amount.")
    for reservation in reservations:
        if (not case.payee_id or claim_identity(reservation.source)[0] != f"finance-party:{case.payee.code}"
                or reservation.source.entry.department_id != case.configuration_release.department_id
                or set(case.obligation.allocation_lines.values_list("fund_code", flat=True)) != {reservation.source.entry.fund.code}):
            raise ValidationError("The voucher differs from its retained prior-payable source, payee, fund or amount.")
    return evidence


def current_reservations(case):
    from accounting.claim_groups import resolve
    return resolve(current_evidence(case), case_public_id=case.public_id)


def current_reservation(case):
    reservations = current_reservations(case)
    if len(reservations) > 1:
        raise ValidationError("This consolidated DV has several claim reservations; use the complete allocation.")
    return reservations[0] if reservations else None


def check_rule(snapshot, *, deduction=False, restoring=False, source=None, transaction_type=""):
    """Accept the explicit source or an existing mapping to the exact same control."""
    if snapshot.get("accounting_effect") != Rule.JOURNAL_ENTRY:
        raise ValidationError("Prior-payable settlement requires a governed journal-producing rule.")
    lines = snapshot.get("lines") or []
    if len(lines) != 2:
        raise ValidationError("A prior-payable rule needs exactly the claim application and its deduction or bank counterpart.")
    payable = [row for row in lines if row.get("account_source") in (Line.PRIOR_PAYABLE, Line.PAYABLE_MAPPING)]
    counterpart = [row for row in lines if row not in payable]
    if len(payable) != 1 or len(counterpart) != 1:
        raise ValidationError("The prior-payable rule must apply to exactly one original claim.")
    debit, credit = (Line.CREDIT, Line.DEBIT) if restoring else (Line.DEBIT, Line.CREDIT)
    amount = Line.TOTAL_DEDUCTIONS if deduction else Line.EVENT_AMOUNT
    other_source = Line.DEDUCTION_MAPPINGS if deduction else Line.BANK_MAPPING
    other_amount = Line.EACH_DEDUCTION if deduction else Line.EVENT_AMOUNT
    first, second = payable[0], counterpart[0]
    if (first.get("side") != debit or first.get("amount_source") != amount
            or second.get("side") != credit or second.get("account_source") != other_source
            or second.get("amount_source") != other_amount):
        raise ValidationError("The prior-payable rule must reduce the original liability against deductions or bank payment; it cannot recognize the expense again.")
    if source is not None and first["account_source"] == Line.PAYABLE_MAPPING:
        mappings = PostingMapping.objects.filter(department_id=source.entry.department_id,
            category=PostingMapping.PAYABLE, is_active=True)
        mapping = mappings.filter(source_code__iexact=first.get("mapping_code") or transaction_type).first()
        mapping = mapping or mappings.filter(source_code="*").first()
        if mapping is None or mapping.account_id != source.account_id:
            raise ValidationError("The payable mapping must match the original claim's liability account.")


def check_payment_policy(case, source):
    variant = case.configuration_release.transaction_variants.filter(code=case.transaction_type,
        status__in=("approved", "scheduled", "active", "superseded")).first()
    if variant is None:
        raise ValidationError("The pinned release has no governed transaction variant.")
    rules = {rule.event_kind: rule for rule in variant.posting_rules.all()}
    payment = rules.get(Rule.PAYMENT)
    if not payment or payment.recognition_point not in (Rule.PAYMENT_ISSUANCE, Rule.PAYMENT_RELEASE):
        raise ValidationError("Configure payment at issuance or release before validating a prior-payable DV.")
    for kind, point in ((Rule.PAYMENT, payment.recognition_point), (Rule.REVERSAL, Rule.PAYMENT_RETURN),
            (Rule.CANCELLATION, Rule.PAYMENT_CANCELLATION), (Rule.REPLACEMENT, Rule.PAYMENT_REPLACEMENT)):
        rule = rules.get(kind)
        if rule is None or rule.recognition_point != point:
            raise ValidationError("Prior-payable payment requires explicit payment, cancellation, return and replacement policies.")
        if kind in (Rule.CANCELLATION, Rule.REPLACEMENT) and payment.recognition_point == Rule.PAYMENT_RELEASE:
            if rule.accounting_effect != Rule.NO_ENTRY:
                raise ValidationError("Before-release cancellation/replacement must retain no-entry decisions for a release-time payment policy.")
        else:
            check_rule(posting_rule_snapshot(rule)[0], restoring=kind in (Rule.CANCELLATION, Rule.REVERSAL),
                source=source, transaction_type=case.transaction_type)
    return variant


def reserve_for_validation(case, actor, source_id, as_of):
    if not case.payee_id:
        raise ValidationError("Select a governed payee before linking a prior claim.")
    funds = set(case.obligation.allocation_lines.values_list("fund_code", flat=True))
    if len(funds) != 1:
        raise ValidationError("Prior-payable DV settlement currently requires one source claim and one fund.")
    generated = [r for r in case.posting_requests.filter(kind=Rule.RECOGNITION).exclude(status=VoucherPostingRequest.CANCELLED)
                 if r.payload.get("earlier_accrual")]
    if generated:
        if (len(generated) != 1 or generated[0].status != VoucherPostingRequest.POSTED
                or not JournalLine.objects.filter(pk=source_id, entry__public_id=generated[0].accounting_entry_public_id,
                    payable_claim_reference=generated[0].payload["earlier_accrual"]["claim_reference"]).exists()):
            raise ValidationError("Settle the posted original claim generated by this payable's earlier accrual.")
    return _reserve_claim(source_id=source_id, case_public_id=case.public_id,
        key=f"{case.public_id}:{case.state_version}", amount=case.disbursement_voucher.gross_amount,
        actor_id=actor.pk, department_id=case.configuration_release.department_id,
        fund_code=funds.pop(), party_key=f"finance-party:{case.payee.code}", as_of=as_of)


@transaction.atomic(using="finance")
def release_for_return(case, actor, reason):
    if case.payment_instruments.exclude(status=PaymentInstrument.CANCELLED).exists():
        raise ValidationError("Resolve payment instruments before releasing a prior-payable reservation.")
    reservations = list(PayableClaimReservation.objects.filter(case_public_id=case.public_id, released_at__isnull=True).order_by("source_id"))
    list(JournalLine.objects.select_for_update().filter(pk__in=[r.source_id for r in reservations]).order_by("pk"))
    for reservation in reservations:
        _release_unused_claim(reservation, actor_id=actor.pk, reason=reason)


def payload_evidence(case, *, trigger=None, amount=None):
    evidence = current_evidence(case)
    if not evidence:
        return {}
    from .claim_allocations import event_evidence
    return {"prior_payable": evidence, **(event_evidence(case, evidence, trigger, amount) if trigger else {})}


def original_payment(case, trigger):
    candidates = case.posting_requests.filter(kind__in=(Rule.PAYMENT, Rule.REPLACEMENT), status=VoucherPostingRequest.POSTED)
    matches = [request for request in candidates if request.payload.get("trigger", {}).get("instrument_public_id") == trigger.get("instrument_public_id")]
    if len(matches) != 1:
        raise ValidationError("An exact posted payment request is required before restoring this prior payable.")
    request = matches[0]
    if trigger.get("source_payment_request") and trigger["source_payment_request"] != str(request.public_id):
        raise ValidationError("The returned-instrument request does not match the original payment.")
    return request


@transaction.atomic(using="finance")
def retire_returned_claim(posting_request, review, actor):
    """Free only unused capacity after an independently posted close-without-reissue return."""
    evidence = posting_request.payload.get("prior_payable")
    if not evidence:
        return
    from accounting.posted_evidence import require_persisted_posting, verify_source_link
    from accounting.payables import _capacity
    if (posting_request.status != VoucherPostingRequest.POSTED
            or review.outcome != review.CLOSE_WITHOUT_REISSUE
            or posting_request.payload.get("trigger", {}).get("outcome") != review.CLOSE_WITHOUT_REISSUE
            or posting_request.payload.get("trigger", {}).get("review_public_id") != str(review.public_id)):
        raise ValidationError("Release returned-claim capacity only from its posted, independently reviewed closing decision.")
    if posting_request.case.posting_requests.filter(status__in=(VoucherPostingRequest.PENDING,
            VoucherPostingRequest.MATERIALIZED, VoucherPostingRequest.FAILED)).exclude(pk=posting_request.pk).exists():
        raise ValidationError("Resolve other pending voucher postings before closing this claim reservation.")
    entry = require_persisted_posting(JournalEntry.objects.get(public_id=posting_request.accounting_entry_public_id),
        actor, source_type="voucher")
    verify_source_link(posting_request, entry, source_type="voucher")
    if entry.reversal_of_id is None or entry.source_snapshot.get("prior_payable") != evidence:
        raise ValidationError("The closing return must retain its exact original payment and claim evidence.")
    from accounting.claim_groups import resolve
    reservations = resolve(evidence, case_public_id=review.case.public_id, lock=True, allow_released=True)
    if evidence.get("schema") == 2:
        from accounting.claim_groups import retire_return
        retire_return(reservations, entry, posting_request, review, actor)
        return
    for reservation in reservations:
        reason = f"Returned-item review {review.public_id}: closed without replacement after JEV {entry.reference}."
        if reservation.released_at:
            if reservation.release_reason != reason:
                raise ValidationError("This claim reservation was released by a different decision. Investigate before recovery.")
            continue
        verify_reservation(reservation)
        if reservation.applications.exclude(entry__status__in=(JournalEntry.POSTED, JournalEntry.VOIDED)).exists():
            raise ValidationError("Resolve pending claim applications before releasing remaining capacity.")
        _capacity(reservation.source)
        reservation.released_at = timezone.now()
        reservation.released_by_id = actor.pk
        reservation.release_reason = reason
        reservation._release_transition = True
        reservation.save(update_fields=("released_at", "released_by_id", "release_reason"))
