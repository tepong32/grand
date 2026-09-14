"""Native case-lock boundaries for returned advance correction and replacement."""
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounting.models import JournalEntry, JournalSubsidiaryLine
from accounting.services import submit_entry, post_entry
from . import test_advance_concurrency as fixtures
from . import test_returned_advance_corrections as returned, test_prior_payables as payments
from .models import VoucherPostingRequest as Request, ReturnedInstrumentReview as Review, VoucherCase, PaymentInstrument
from .advance_recognition_corrections import prepare
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .services import issue_check
from .advice import decide_returned_instrument


class ReturnedAdvanceConcurrencyTests(fixtures.AdvanceConcurrencyTests):
    post_request = payments.PriorPayableDVTests.post_request
    pay = payments.PriorPayableDVTests.pay
    prepare_released_advance = returned.ReturnedAdvanceCorrectionTests.prepare_released_advance
    review_bank_return = returned.ReturnedAdvanceCorrectionTests.review_bank_return

    def returned_source(self):
        self.enable_payment_event_rules('op_suppliers')
        self.case = self.ready_for_treasury()
        self.prepare_released_advance(self.case)
        self.review_bank_return(self.case)
        self.detail = JournalSubsidiaryLine.objects.get(
            entry__public_id=self.case.posting_requests.get(kind=Request.RECOGNITION).accounting_entry_public_id,
            category=JournalSubsidiaryLine.ADVANCE)

    def posted_correction(self):
        self.returned_source()
        request = prepare(detail=self.detail, actor=self.preparer, day=timezone.localdate(),
            reason='Correct returned original advance', key='RETURN-RACE')
        entry, _ = materialize_voucher_journal(request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        return request, entry

    def test_returned_advance_correction_and_replacement_are_exclusive(self):
        self.returned_source()
        version = self.case.state_version
        def compete(number):
            if number == 1:
                prepare(detail=JournalSubsidiaryLine.objects.get(pk=self.detail.pk),
                    actor=get_user_model().objects.get(pk=self.preparer.pk), day=timezone.localdate(),
                    reason='Correct returned source instead of reissuing it', key='RETURN-COMPETING')
            else:
                issue_check(case=VoucherCase.objects.get(pk=self.case.pk),
                    actor=get_user_model().objects.get(pk=self.treasury_user.pk), bank_account_code='gf-lbp',
                    fund_code='general-fund', check_number='RETURN-RACING-REPLACEMENT', amount='1000',
                    replaces=PaymentInstrument.objects.get(pk=self.returned.pk),
                    expected_version=version, idempotency_key='return-racing-replacement')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)
        pending = self.case.posting_requests.filter(payload__has_key='advance_recognition_correction').exists()
        replacement = self.case.payment_instruments.filter(replaces=self.returned).exists()
        self.assertNotEqual(pending, replacement)

    def test_stale_return_decision_cannot_race_original_correction_closure(self):
        request, entry = self.posted_correction()
        def compete(number):
            actor = get_user_model().objects.get(pk=self.validator.pk)
            if number == 1:
                reconcile_posted_voucher_entry(JournalEntry.objects.get(pk=entry.pk), actor)
                return 'completed'
            review = Review.objects.get(pk=self.review.pk)
            decide_returned_instrument(review=review, actor=actor, approve=True, outcome=Review.REISSUE,
                decision_reason='Stale review must not reopen replacement', evidence_reference='Stale decision',
                expected_version=review.state_version)
            return 'unexpected decision'
        results = self.race(compete)
        self.assertEqual(results.count('completed'), 1, results)
        self.assertNotIn('unexpected decision', results)
        self.review.refresh_from_db(); request.refresh_from_db()
        self.assertEqual(self.review.status, Review.CLOSED)
        self.assertEqual(request.status, Request.POSTED)

    def test_duplicate_reconciliation_retires_return_once(self):
        request, entry = self.posted_correction()
        self.review.refresh_from_db()
        version = self.review.state_version
        def compete(number):
            reconcile_posted_voucher_entry(JournalEntry.objects.get(pk=entry.pk),
                get_user_model().objects.get(pk=self.validator.pk))
            return 'completed'
        self.assertEqual(self.race(compete).count('completed'), 2)
        self.review.refresh_from_db()
        self.assertEqual(self.review.state_version, version + 1)
        self.assertEqual(self.case.events.filter(action='advance_return_retired').count(), 1)
