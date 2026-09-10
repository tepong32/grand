"""Reviewed pre-DV accruals using the existing immutable posting handoff."""
from datetime import date
from decimal import Decimal
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db.models import Max
from django.utils import timezone

from accounting.models import AccountingPeriod, JournalEntry
from accounting.access import department_for_user
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from finance.services import posting_rule_snapshot
from .models import PayableIntake, VoucherCase, VoucherPostingRequest


def check_rule(snapshot):
    expected = {(Line.DEBIT, Line.ALLOCATION_ACCOUNTS, Line.EACH_ALLOCATION),
                (Line.CREDIT, Line.PAYABLE_MAPPING, Line.GROSS)}
    rows = snapshot.get("lines") or []
    actual = {(r.get("side"), r.get("account_source"), r.get("amount_source")) for r in rows}
    if (snapshot.get("event_kind") != Rule.RECOGNITION
            or snapshot.get("accounting_effect") != Rule.JOURNAL_ENTRY
            or snapshot.get("recognition_point") not in (Rule.DELIVERY_ACCEPTANCE, Rule.BILLING_VALIDATION)
            or len(rows) != 2 or actual != expected):
        raise ValidationError("Earlier accrual requires a reviewed delivery/acceptance or billing-validation recognition rule: debit each allocation and credit the gross payable.")


def queue_accrual(case, actor, recognition_date, recognition_reference, summary, documents):
    # Caller holds the default case lock and has independently reviewed the intake.
    from .services import _consume_sequence_number
    if department_for_user(actor).pk != case.configuration_release.department_id:
        raise ValidationError("Only the pinned Accounting office may request the earlier accrual.")
    if not isinstance(recognition_date, date) or recognition_date > timezone.localdate():
        raise ValidationError("Record the actual recognition date, no later than today.")
    reference = (recognition_reference or "").strip()
    if not reference or len(reference) > 240:
        raise ValidationError("Record the recognition evidence reference (up to 240 characters).")
    if not case.payee_id or not case.payable_intake.claim_reference.strip():
        raise ValidationError("Earlier accrual requires a governed payee and a claim reference.")
    if len(case.payable_intake.claim_reference) > 120:
        raise ValidationError("The original payable claim reference must fit within 120 characters.")
    variant = case.configuration_release.transaction_variants.filter(code=case.transaction_type,
        status__in=("approved", "scheduled", "active", "superseded")).first()
    rule = variant.posting_rules.filter(event_kind=Rule.RECOGNITION).first() if variant else None
    if rule is None:
        raise ValidationError("Configure and review the earlier-recognition posting rule first.")
    snapshot, rule_checksum = posting_rule_snapshot(rule)
    check_rule(snapshot)
    if not AccountingPeriod.objects.filter(department_id=case.configuration_release.department_id,
            status=AccountingPeriod.OPEN, starts_on__lte=recognition_date, ends_on__gte=recognition_date).exists():
        raise ValidationError("The actual recognition date must be in an open Accounting period.")
    previous = list(case.posting_requests.filter(kind=Rule.RECOGNITION))
    if any(r.status != VoucherPostingRequest.CANCELLED for r in previous):
        raise ValidationError("Resolve the existing recognition request before reviewing another accrual.")
    if JournalEntry.objects.filter(source_type="voucher", source_reference__in=[str(r.public_id) for r in previous]).exclude(status=JournalEntry.VOIDED).exists():
        raise ValidationError("The retained recognition JEV must be discarded before changing the payable.")
    allocations = [{"fund_code": r.fund_code, "responsibility_center_code": r.responsibility_center_code,
        "account_code": r.account_code, "amount": str(r.amount)} for r in case.obligation.allocation_lines.order_by("pk")]
    intake = case.payable_intake
    if (len({r["fund_code"] for r in allocations}) != 1
            or sum((Decimal(r["amount"]) for r in allocations), Decimal("0")) != intake.claim_amount):
        raise ValidationError("Earlier accrual requires the full reviewed claim allocated within one fund.")
    version = (case.posting_requests.filter(kind=Rule.RECOGNITION).aggregate(value=Max("version"))["value"] or 0) + 1
    number = _consume_sequence_number(case, actor, "journal-entry", f"journal-entry-recognition-{version}")
    evidence = {
        "claim_reference": intake.claim_reference, "invoice_number": intake.invoice_number,
        "invoice_date": intake.invoice_date.isoformat() if intake.invoice_date else "", "claim_amount": str(intake.claim_amount),
        "delivery_reference": intake.delivery_reference,
        "inspection_acceptance_reference": intake.inspection_acceptance_reference,
        "evidence_reference": intake.evidence_reference,
        "recognition_date": recognition_date.isoformat(), "recognition_reference": reference,
        "recognition_point": rule.recognition_point, "recognition_basis": intake.recognition_basis,
        "reviewed_by": actor.pk, "review_reason": intake.decision_reason,
        "obligations": [{"allocation": str(r.public_id), "obligation": str(r.obligation.public_id),
            "checksum": r.obligation_checksum_snapshot, "amount": str(r.allocated_amount)} for r in summary["allocations"]],
        "documents": [{"rule": str(r.source_rule_id), "status": r.status,
            "reference": r.evidence_reference} for r in documents],
    }
    payload = {"schema_version": 5, "earlier_accrual": evidence,
        "voucher_case_public_id": str(case.public_id), "voucher_reference": case.reference_code,
        "dv_number": "", "transaction_type": case.transaction_type,
        "recognition_decision": PayableIntake.ACCRUE_BEFORE_SETTLEMENT,
        "posting_rule_public_id": str(rule.public_id), "posting_rule_checksum": rule_checksum,
        "payee_key": f"finance-party:{case.payee.code}", "payee_code": case.payee.code,
        "payee_name": case.payee_name, "particulars": case.particulars,
        "gross_amount": str(intake.claim_amount), "net_amount": str(intake.claim_amount),
        "total_deductions": "0.00", "event_amount": str(intake.claim_amount),
        "allocations": allocations, "deductions": [], "jev_number": number,
        "jev_date": recognition_date.isoformat()}
    request = VoucherPostingRequest(case=case, kind=Rule.RECOGNITION, version=version,
        jev_number=number, jev_date=recognition_date, origin_stage=case.current_stage,
        resume_stage=VoucherCase.ACCOUNTING_PREPARATION, finance_department_id=case.configuration_release.department_id,
        finance_department_label=case.configuration_release.department.name, posting_rule=rule,
        posting_rule_public_id_snapshot=str(rule.public_id), posting_rule_snapshot=snapshot,
        posting_rule_checksum=rule_checksum, payload=payload,
        payload_checksum=hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
        requested_by=actor)
    request.full_clean()
    request.save()
    return request
