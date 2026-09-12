from datetime import date

from django.utils import timezone
from django.core.exceptions import ValidationError
from unittest.mock import patch

from accounting.models import JournalEntry, PayableClaimReservation
from accounting.services import submit_entry, post_entry
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry

from . import test_cancelled_check_corrections as cancelled, test_issuance_bank_returns as issuance
from .models import TreasuryCashPolicy, PaymentInstrument, PaymentInstrumentException, ReturnedInstrumentReview
from .cash_positions import open_instrument_exception
from .advice import decide_returned_instrument


class ReturnedCheckCorrectionTests(cancelled.CancelledCheckCorrectionTests):
    issuance_release = issuance.IssuanceBankReturnTests.issuance_release

    def resolved_before_correction(self, *, issuance):
        TreasuryCashPolicy.objects.create(configuration_release=self.release, treasury_department=self.treasury,
            bank_account_code="gf-lbp", fund_code="general-fund", mode=TreasuryCashPolicy.OBSERVE,
            minimum_reserve=0, position_max_age_days=35, unclaimed_after_days=30, stale_after_days=180,
            effective_from=date(2026, 1, 1), authority_reference="Synthetic policy", local_applicability_note="Synthetic",
            status=TreasuryCashPolicy.ACTIVE, created_by=self.treasury_user, submitted_by=self.treasury_user,
            submitted_at=timezone.now(), approved_by=self.validator, approved_at=timezone.now())
        if issuance:
            instrument, _, _ = self.issuance_release(self.case, "BEFORE-CORRECTION")
        else:
            instrument, _ = self.pay(self.case, "-before-correction")
        instrument.refresh_from_db()
        exception = open_instrument_exception(instrument=instrument, actor=self.treasury_user,
            kind=PaymentInstrumentException.RETURNED, observed_on=timezone.localdate(), reason="Bank returned unpaid",
            evidence_reference="Synthetic return for correction")
        review = exception.accounting_reviews.get()
        decide_returned_instrument(review=review, actor=self.validator, approve=True, outcome=ReturnedInstrumentReview.REISSUE,
            decision_reason="Reverse unpaid payment before further settlement", evidence_reference="Synthetic independent return review",
            expected_version=review.state_version)
        review.refresh_from_db()
        self.post_request(review.posting_request)
        self.case.refresh_from_db(); instrument.refresh_from_db()
        self.assertEqual(instrument.status, PaymentInstrument.BANK_RETURNED)
        self.review = review
        return instrument

    def test_reviewed_bank_return_can_request_deduction_correction(self):
        self.resolved_before_correction(issuance=False)
        self.request(correction_date=timezone.localdate())

    def assert_cancelled_correction(self, *, issuance):
        super().assert_cancelled_correction(issuance=issuance)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReturnedInstrumentReview.CLOSED)
        self.assertEqual(self.review.outcome, ReturnedInstrumentReview.REISSUE)
        self.assertEqual(self.review.closed_by_id, self.validator.pk)
        self.assertEqual(self.review.exception.status, PaymentInstrumentException.RESOLVED)
        self.assertIn("old replacement authorization is retired", self.review.exception.resolution)

    def test_returned_correction_recovers_after_finance_commit(self):
        self.resolved_before_correction(issuance=False)
        self.request(correction_date=timezone.localdate())
        request = next(r for r in self.case.posting_requests.all() if r.payload.get("deduction_correction"))
        entry, _ = materialize_voucher_journal(request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        with patch("vouchers.returned_corrections.close_reviews", side_effect=RuntimeError("Interrupted review closure")), self.assertRaises(RuntimeError):
            reconcile_posted_voucher_entry(entry, self.validator)
        self.assertTrue(PayableClaimReservation.objects.get().released_at)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReturnedInstrumentReview.READY_FOR_TREASURY)
        reconcile_posted_voucher_entry(entry, self.validator)
        reconcile_posted_voucher_entry(entry, self.validator)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReturnedInstrumentReview.CLOSED)
        self.assertEqual(JournalEntry.objects.filter(source_reference=str(request.public_id)).count(), 1)

    def test_changed_bank_review_blocks_correction_materialization(self):
        self.resolved_before_correction(issuance=False)
        self.request(correction_date=timezone.localdate())
        request = next(r for r in self.case.posting_requests.all() if r.payload.get("deduction_correction"))
        ReturnedInstrumentReview.objects.filter(pk=self.review.pk).update(accounting_decision_reason="Changed after correction proposal")
        with self.assertRaisesMessage(ValidationError, "differ from the retained correction"):
            materialize_voucher_journal(request, self.preparer)
