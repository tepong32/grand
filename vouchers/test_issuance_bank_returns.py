"""Bank returns must use the actual issuance/replacement payment journal."""
from datetime import date
from decimal import Decimal

from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError

from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from accounting.payables import _capacity, claim_rows
from . import test_prior_payables as fixtures
from .models import VoucherCase, VoucherPostingRequest, TreasuryCashPolicy, PaymentInstrumentException, ReturnedInstrumentReview
from .services import issue_check, submit_checks_for_advice, finalize_bank_advice, release_check
from .cash_positions import open_instrument_exception
from .advice import decide_returned_instrument


class IssuanceBankReturnTests(fixtures.PriorPayableDVTests):
    def issuance_case(self):
        Rule.objects.filter(pk=self.payment_rule.pk).update(recognition_point=Rule.PAYMENT_ISSUANCE)
        for kind in (Rule.CANCELLATION, Rule.REPLACEMENT):
            rule = Rule.objects.get(variant=self.transaction_variant, event_kind=kind)
            Rule.objects.filter(pk=rule.pk).update(accounting_effect=Rule.JOURNAL_ENTRY)
            restoring = kind == Rule.CANCELLATION
            Line.objects.bulk_create([
                Line(rule=rule, sequence=1, label="Original payable", side=Line.CREDIT if restoring else Line.DEBIT,
                    account_source=Line.PRIOR_PAYABLE, amount_source=Line.EVENT_AMOUNT),
                Line(rule=rule, sequence=2, label="Bank", side=Line.DEBIT if restoring else Line.CREDIT,
                    account_source=Line.BANK_MAPPING, amount_source=Line.EVENT_AMOUNT, cash_flow_category="op_suppliers")])
        TreasuryCashPolicy.objects.create(configuration_release=self.release, treasury_department=self.treasury,
            bank_account_code="gf-lbp", fund_code="general-fund", mode=TreasuryCashPolicy.OBSERVE,
            minimum_reserve=0, position_max_age_days=35, unclaimed_after_days=30, stale_after_days=180,
            effective_from=date(2026, 1, 1), authority_reference="Synthetic policy", local_applicability_note="Synthetic",
            status=TreasuryCashPolicy.ACTIVE, created_by=self.treasury_user, submitted_by=self.treasury_user,
            submitted_at=timezone.now(), approved_by=self.validator, approved_at=timezone.now())
        case = self.case_for_validation(deductions=True)
        self.validate(case)
        self.post_request(case.posting_requests.get(kind=Rule.ADJUSTMENT))
        case.refresh_from_db()
        return case

    def issuance_release(self, case, suffix, replaces=None):
        case.refresh_from_db()
        instrument = issue_check(case=case, actor=self.treasury_user, bank_account_code="gf-lbp", fund_code="general-fund",
            check_number="ISSUANCE-RETURN-"+suffix, amount=900, replaces=replaces,
            expected_version=case.state_version, idempotency_key="issue-"+suffix)
        request = case.posting_requests.get(trigger_key=f"payment-instrument:{instrument.public_id}:issued")
        payment = self.post_request(request)
        case.refresh_from_db()
        submit_checks_for_advice(case=case, actor=self.treasury_user, expected_version=case.state_version, idempotency_key="advice-"+suffix)
        case.refresh_from_db()
        batch = finalize_bank_advice(case=case, actor=self.preparer, advice_number="ISSUANCE-ADVICE-"+suffix,
            advice_date=timezone.localdate(), expected_version=case.state_version, idempotency_key="finalize-"+suffix,
            preparation_note="Synthetic review", authority_reference="Synthetic reviewed procedure", local_applicability_note="Synthetic")
        self.acknowledge_advice(batch)
        case.refresh_from_db(); instrument.refresh_from_db()
        release_check(case=case, instrument=instrument, actor=self.treasury_user, claimant=self.claimant,
            receipt_reference="ISSUANCE-RECEIPT-"+suffix, expected_version=case.state_version, idempotency_key="release-"+suffix)
        case.refresh_from_db(); instrument.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
        self.assertFalse(case.posting_requests.filter(trigger_key=f"payment-instrument:{instrument.public_id}:released").exists())
        return instrument, request, payment

    def bank_return(self, instrument):
        exception = open_instrument_exception(instrument=instrument, actor=self.treasury_user,
            kind=PaymentInstrumentException.RETURNED, observed_on=timezone.localdate(), reason="Bank returned unpaid",
            evidence_reference="Synthetic bank return memorandum")
        return exception.accounting_reviews.get()

    def test_issuance_and_replacement_payments_can_each_be_returned(self):
        case = self.issuance_case()
        instrument, original_request, payment = self.issuance_release(case, "FIRST")
        original_lines = list(payment.lines.values("pk", "account_id", "debit", "credit"))
        review = self.bank_return(instrument)
        self.assertEqual(review.original_payment_request_id, original_request.pk)
        decide_returned_instrument(review=review, actor=self.validator, approve=True, outcome=ReturnedInstrumentReview.REISSUE,
            decision_reason="Restore the actual issued payment", evidence_reference="Synthetic reviewed return",
            expected_version=review.state_version)
        review.refresh_from_db()
        reversal = self.post_request(review.posting_request)
        self.assertEqual(reversal.reversal_of_id, payment.pk)
        self.assertEqual(_capacity(self.source), Decimal("500"))
        instrument.refresh_from_db()
        replacement, replacement_request, replacement_entry = self.issuance_release(case, "SECOND", replaces=instrument)
        next_review = self.bank_return(replacement)
        self.assertEqual(next_review.original_payment_request_id, replacement_request.pk)
        decide_returned_instrument(review=next_review, actor=self.validator, approve=True,
            outcome=ReturnedInstrumentReview.CLOSE_WITHOUT_REISSUE, decision_reason="Close the unpaid replacement",
            evidence_reference="Synthetic second bank return", expected_version=next_review.state_version)
        next_review.refresh_from_db()
        final_return = self.post_request(next_review.posting_request)
        self.assertEqual(final_return.reversal_of_id, replacement_entry.pk)
        self.assertEqual(list(payment.lines.values("pk", "account_id", "debit", "credit")), original_lines)
        self.assertEqual(_capacity(self.source), Decimal("1400"))
        self.assertEqual(claim_rows(self.accounting.pk, timezone.localdate())[0]["outstanding"], Decimal("1400"))
        self.client.force_login(self.validator)
        exported = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": timezone.localdate().isoformat()})
        self.assertEqual(exported.status_code, 200)
        self.assertIn(b"1500.00,100.00,1400.00", exported.content)

    def test_unreconciled_issuance_cannot_start_bank_return(self):
        case = self.issuance_case()
        instrument, request, _ = self.issuance_release(case, "UNRECONCILED")
        VoucherPostingRequest.objects.filter(pk=request.pk).update(status=VoucherPostingRequest.MATERIALIZED)
        with self.assertRaisesMessage(ValidationError, "Complete the governed payment Accounting decision"):
            self.bank_return(instrument)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
        self.assertFalse(instrument.returned_accounting_reviews.exists())
        self.assertFalse(instrument.exceptions.exists())

    def test_wrong_retained_journal_cannot_start_bank_return(self):
        case = self.issuance_case()
        instrument, request, _ = self.issuance_release(case, "WRONG-JOURNAL")
        VoucherPostingRequest.objects.filter(pk=request.pk).update(accounting_entry_public_id=self.original.public_id)
        with self.assertRaisesMessage(ValidationError, "immutable identity"):
            self.bank_return(instrument)
        self.assertFalse(instrument.returned_accounting_reviews.exists())
        self.assertFalse(instrument.exceptions.exists())
