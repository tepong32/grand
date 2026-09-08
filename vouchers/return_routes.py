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


def return_route_blocker(case, target_stage):
    if target_stage not in RETURN_TARGETS.get(case.current_stage, ()):
        return INVALID_RETURN
    if target_stage == VoucherCase.PAYABLE_PREPARATION:
        if hasattr(case, "disbursement_voucher") or case.payment_instruments.exists():
            return "A DV or check already exists; use the later voucher/payment correction route instead of reopening payable allocations."
    if target_stage in {VoucherCase.ACCOUNTING_PREPARATION, VoucherCase.ACCOUNTING_VALIDATION}:
        if case.posting_requests.filter(status=VoucherPostingRequest.POSTED).exists():
            return "This voucher already has a posted JEV. Use an adjusting/reversal entry and a replacement case instead of rewriting it."
        if case.posting_requests.filter(status=VoucherPostingRequest.MATERIALIZED).exists():
            return "Discard the draft GRAND JEV before returning this voucher for correction."
    return ""


def return_route_options(case):
    choices, blockers = [], []
    if case is not None:
        for target in RETURN_TARGETS.get(case.current_stage, ()):
            reason = return_route_blocker(case, target)
            if reason:
                blockers.append({"stage": target, "label": RETURN_LABELS[target], "reason": reason})
            else:
                choices.append((target, RETURN_LABELS[target]))
    return choices, blockers
