from django.contrib.auth import get_user_model
from django.utils import timezone

from accounting.models import JournalEntry
from accounting.services import submit_entry, post_entry
from . import test_cancelled_correction_concurrency as cancelled, test_returned_check_corrections as returned
from . import test_deduction_corrections as fixtures
from .models import ReturnedInstrumentReview
from .deduction_corrections import request_correction
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .advice import decide_returned_instrument


class ReturnedCorrectionConcurrencyTests(cancelled.CancelledCorrectionConcurrencyTests):
    pay = fixtures.DeductionCorrectionTests.pay
    acknowledge_advice = fixtures.DeductionCorrectionTests.acknowledge_advice
    resolved_before_correction = returned.ReturnedCheckCorrectionTests.resolved_before_correction

    def cancel_before_correction(self):
        return self.resolved_before_correction(issuance=False)

    def test_stale_return_decision_and_correction_completion_use_case_first(self):
        self.resolved_before_correction(issuance=False)
        request_correction(case=self.case, actor=self.preparer, correction_date=timezone.localdate(),
            reason="Correct returned DV", expected_version=self.case.state_version, idempotency_key="returned-correction-race")
        request = next(r for r in self.case.posting_requests.all() if r.payload.get("deduction_correction"))
        entry, _ = materialize_voucher_journal(request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        def compete(number):
            actor = get_user_model().objects.get(pk=self.validator.pk)
            if number == 1:
                reconcile_posted_voucher_entry(JournalEntry.objects.get(pk=entry.pk), actor)
                return "completed"
            review = ReturnedInstrumentReview.objects.get(pk=self.review.pk)
            decide_returned_instrument(review=review, actor=actor, approve=True,
                outcome=ReturnedInstrumentReview.REISSUE, decision_reason="Stale decision attempt",
                evidence_reference="Must retain the existing review", expected_version=review.state_version)
            return "unexpected decision"
        results = self.race(compete)
        self.assertEqual(results.count("completed"), 1, results)
        self.assertNotIn("unexpected decision", results)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReturnedInstrumentReview.CLOSED)
