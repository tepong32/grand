"""Existing return destinations and retained-source blockers, shared by form and service."""
from .models import VoucherCase, VoucherPostingRequest


RETURN_TARGETS = {
    VoucherCase.ACCOUNTING_PREPARATION: (VoucherCase.PAYABLE_PREPARATION,),
    VoucherCase.AWAITING_SIGNATURES: (VoucherCase.ACCOUNTING_PREPARATION,),
    VoucherCase.ACCOUNTING_VALIDATION: (VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.AWAITING_SIGNATURES),
    VoucherCase.ACCOUNTING_POSTING: (VoucherCase.ACCOUNTING_VALIDATION,),
    VoucherCase.TREASURY_CHECK_PREPARATION: (VoucherCase.ACCOUNTING_VALIDATION,),
    VoucherCase.ACCOUNTING_BANK_ADVICE: (VoucherCase.TREASURY_CHECK_PREPARATION,),
    VoucherCase.TREASURY_RELEASE: (VoucherCase.TREASURY_CHECK_PREPARATION, VoucherCase.ACCOUNTING_BANK_ADVICE),
}
RETURN_LABELS = {
    VoucherCase.PAYABLE_PREPARATION: "Requesting-office payable preparation",
    VoucherCase.ACCOUNTING_PREPARATION: "Accounting DV preparation",
    VoucherCase.AWAITING_SIGNATURES: "Wet signatures",
    VoucherCase.ACCOUNTING_VALIDATION: "Accounting validation",
    VoucherCase.TREASURY_CHECK_PREPARATION: "Treasury check preparation",
    VoucherCase.ACCOUNTING_BANK_ADVICE: "Accounting bank advice",
}
INVALID_RETURN = "Choose an allowed earlier stage and record the correction reason."


def return_targets(case):
    if (case.current_stage == VoucherCase.ACCOUNTING_POSTING
            and not hasattr(case, "disbursement_voucher")
            and any(r.payload.get("earlier_accrual") for r in case.posting_requests.all())):
        return (VoucherCase.PAYABLE_PREPARATION,)
    return RETURN_TARGETS.get(case.current_stage, ())


def return_route_blocker(case, target_stage):
    if target_stage not in return_targets(case):
        return INVALID_RETURN
    early = [r for r in case.posting_requests.all() if r.payload.get("earlier_accrual")]
    if early and target_stage == VoucherCase.PAYABLE_PREPARATION:
        from accounting.models import JournalEntry
        if (any(r.status == VoucherPostingRequest.POSTED for r in early)
                or JournalEntry.objects.filter(source_type="voucher",
                    source_reference__in=[str(r.public_id) for r in early]).exclude(status=JournalEntry.VOIDED).exists()):
            return "The earlier-accrual JEV is retained. Discard an unposted draft first; a posted claim requires governed correction, not rewritten payable evidence."
    if target_stage == VoucherCase.PAYABLE_PREPARATION:
        if hasattr(case, "disbursement_voucher") or case.payment_instruments.exists():
            return "A DV or check already exists; use the later voucher/payment correction route instead of reopening payable allocations."
    if target_stage in {VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.ACCOUNTING_VALIDATION}:
        if case.posting_requests.filter(status=VoucherPostingRequest.POSTED).exclude(pk__in=[r.pk for r in early]).exists():
            return "This voucher already has a posted JEV. Use an adjusting/reversal entry and a replacement case instead of rewriting it."
        if case.posting_requests.filter(status=VoucherPostingRequest.MATERIALIZED).exists():
            return "Discard the draft GRAND JEV before returning this voucher for correction."
    return ""


def return_route_options(case):
    choices, blockers = [], []
    if case is not None:
        for target in return_targets(case):
            reason = return_route_blocker(case, target)
            if reason:
                blockers.append({"stage": target, "label": RETURN_LABELS[target], "reason": reason})
            else:
                choices.append((target, RETURN_LABELS[target]))
    return choices, blockers
