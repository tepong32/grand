"""Explicit advance recognition; liquidation must select original source evidence separately."""
from django.core.exceptions import ValidationError

from finance.models import FinanceParty, FinancePostingRule, FinancePostingRuleLine, FinanceTransactionVariant


def recognition_evidence(case, rule):
    lines = list(rule.lines.filter(account_source=FinancePostingRuleLine.ADVANCE_ACCOUNT))
    if not lines:
        return {}
    if (len(lines) != 1 or rule.variant.kind != FinanceTransactionVariant.CASH_ADVANCE
            or rule.event_kind != FinancePostingRule.RECOGNITION
            or rule.recognition_point != FinancePostingRule.DV_VALIDATION
            or lines[0].side != FinancePostingRuleLine.DEBIT
            or lines[0].amount_source != FinancePostingRuleLine.GROSS):
        raise ValidationError("Use one explicit gross advance debit at DV recognition on a cash-advance variant.")
    if not case.payee_id or case.payee.party_type != FinanceParty.EMPLOYEE:
        raise ValidationError("An advance requires a governed employee payee identifying the accountable officer.")
    if case.disbursement_voucher.total_deductions:
        raise ValidationError("This advance recognition route requires a gross advance without deductions.")
    other = list(rule.lines.exclude(pk=lines[0].pk))
    if (len(other) != 1 or other[0].account_source != FinancePostingRuleLine.PAYABLE_MAPPING
            or other[0].side != FinancePostingRuleLine.CREDIT
            or other[0].amount_source not in (FinancePostingRuleLine.GROSS, FinancePostingRuleLine.NET)):
        raise ValidationError("Advance recognition must pair the advance asset with one gross payable credit.")
    return {"advance_recognition": {
        "schema_version": 1,
        "party_id": case.payee_id,
        "party_version": case.payee.version,
        "party_code": case.payee.code,
        "party_type": case.payee.party_type,
        "variant_public_id": str(rule.variant.public_id),
        "variant_kind": rule.variant.kind,
        "basis": "recognized_asset_not_disbursement_or_liquidation_capacity",
    }}
