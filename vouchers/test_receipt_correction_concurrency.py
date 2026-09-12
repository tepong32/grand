from datetime import date
from django.contrib.auth import get_user_model

from accounting.models import JournalEntry
from accounting.services import submit_entry, post_entry
from . import test_remittance_return_concurrency as concurrent
from . import test_remittance_returns as receipts
from . import test_receipt_corrections as scenarios
from .models import RemittanceReturn, RemittancePostingRequest, VoucherCase
from .receipt_corrections import propose_correction, review_correction
from .deduction_corrections import request_correction
from .remittances import materialize_remittance_journal


class ReceiptCorrectionConcurrencyTests(concurrent.RemittanceReturnConcurrencyTests):
    propose = receipts.RemittanceReturnTests.propose
    post_return = receipts.RemittanceReturnTests.post_return
    posted_receipt = scenarios.ReceiptCorrectionTests.posted_receipt
    correction = scenarios.ReceiptCorrectionTests.correction

    def test_receipt_and_deduction_corrections_cannot_consume_same_restored_withholding(self):
        self.posted_receipt(); self.batch.refresh_from_db(); self.case.refresh_from_db()
        def compete(number):
            if number == 1:
                propose_correction(receipt=RemittanceReturn.objects.get(pk=self.receipt.pk),
                    actor=get_user_model().objects.get(pk=self.treasury_user.pk), correction_date=date(2026, 9, 2),
                    reason='Concurrent receipt error', evidence_reference='Synthetic bank evidence', filing_basis='Agency basis',
                    expected_version=self.batch.state_version)
            else:
                request_correction(case=VoucherCase.objects.get(pk=self.case.pk),
                    actor=get_user_model().objects.get(pk=self.preparer.pk), correction_date=date(2026, 9, 2),
                    reason='Concurrent deduction correction', expected_version=self.case.state_version,
                    idempotency_key='receipt-versus-deduction')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)

    def test_duplicate_receipt_correction_materialization_keeps_one_reversal(self):
        self.posted_receipt(); item = self.correction()
        review_correction(item=item, actor=self.validator, approve=True, reason='Independent exact reversal review')
        item.refresh_from_db()
        def materialize(number):
            entry, created = materialize_remittance_journal(RemittancePostingRequest.objects.get(pk=item.posting_request_id),
                get_user_model().objects.get(pk=self.preparer.pk))
            return entry.pk, created
        results = self.race(materialize)
        self.assertTrue(all(isinstance(row, tuple) for row in results), results)
        self.assertEqual(len({row[0] for row in results}), 1)
        self.assertEqual(sorted(row[1] for row in results), [False, True])
        self.assertEqual(JournalEntry.objects.filter(reversal_of=self.incoming).count(), 1)

    def test_withdrawal_cannot_bypass_independent_correction_posting(self):
        from .receipt_corrections import withdraw_correction
        from .models import RemittanceReturnCorrection
        self.posted_receipt(); item = self.correction()
        review_correction(item=item, actor=self.validator, approve=True, reason='Independent exact reversal review')
        item.refresh_from_db()
        entry, _ = materialize_remittance_journal(item.posting_request, self.preparer)
        submit_entry(entry, self.preparer)
        def compete(number):
            actor = get_user_model().objects.get(pk=self.validator.pk)
            if number == 1:
                withdraw_correction(item=RemittanceReturnCorrection.objects.get(pk=item.pk), actor=actor, reason='Withdraw correction')
                return 'withdrawn'
            post_entry(JournalEntry.objects.get(pk=entry.pk), actor)
            return 'posted'
        results = self.race(compete)
        self.assertIn('posted', results); self.assertNotIn('withdrawn', results)
