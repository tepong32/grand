from datetime import date

from django.contrib.auth import get_user_model

from . import test_deduction_correction_concurrency as concurrent
from . import test_dated_withholding_corrections as fixtures
from . import test_remittance_returns as returns
from .models import TreasuryRemittanceBatch, RemittanceReturn
from .remittance_returns import propose_return, review_return


class RemittanceReturnConcurrencyTests(concurrent.DeductionCorrectionConcurrencyTests):
    posted_remittance = fixtures.DatedWithholdingCorrectionTests.posted_remittance
    remitted_source_batch = returns.RemittanceReturnTests.remitted_source_batch

    def test_competing_actual_returns_cannot_allocate_the_same_original_amount(self):
        self.remitted = self.posted_remittance()
        batch = self.remitted_source_batch()
        source = self.remitted.subsidiary_lines.get().pk
        def compete(number):
            actor = get_user_model().objects.get(pk=self.treasury_user.pk)
            propose_return(batch=TreasuryRemittanceBatch.objects.get(pk=batch.pk), actor=actor,
                returned_on=date(2026, 9, 1), receipt_reference=f'Concurrent receipt {number}',
                reason='Actual receipt', filing_basis='Retained agency disposition',
                allocations=[{'source_detail': source, 'amount': '100.00'}], expected_version=batch.state_version)
            return 'accepted'
        result = self.race(compete)
        self.assertEqual(result.count('accepted'), 1, result)
        self.assertEqual(batch.returns.count(), 1)

    def test_competing_review_decisions_retain_one_posting_request(self):
        self.remitted = self.posted_remittance()
        batch = self.remitted_source_batch()
        item = propose_return(batch=batch, actor=self.treasury_user, returned_on=date(2026, 9, 1),
            receipt_reference='Actual credit', reason='Actual return', filing_basis='Agency disposition',
            allocations=[{'source_detail': self.remitted.subsidiary_lines.get().pk, 'amount': '100'}],
            expected_version=batch.state_version)
        def compete(number):
            review_return(item=RemittanceReturn.objects.get(pk=item.pk),
                actor=get_user_model().objects.get(pk=self.validator.pk), approve=True, reason=f'Review {number}')
            return 'approved'
        result = self.race(compete)
        self.assertEqual(result.count('approved'), 1, result)
        self.assertEqual(batch.posting_requests.count(), 2)
