from django.contrib.auth import get_user_model
from django.utils import timezone

from .test_advance_concurrency import AdvanceConcurrencyTests
from .test_advance_refunds import AdvanceRefundTests
from .advance_applications import prepare
from .collections import record_receipt
from .models import TreasuryCollectionSource


class AdvanceRefundConcurrencyTests(AdvanceConcurrencyTests):
    refund_setup = AdvanceRefundTests.refund_setup

    def test_refund_and_expense_cannot_consume_the_same_original_advance(self):
        detail, _ = self.refund_setup()
        rule = self.liquidation_rule()
        def compete(number):
            if number == 1:
                record_receipt(actor=get_user_model().objects.get(pk=self.treasury_user.pk), advance_detail=detail,
                    variant=self.transaction_variant, received_on=timezone.localdate(), fund_code='general-fund',
                    receipt_book='RACE', receipt_number='001', payer_reference='', received_amount='600',
                    evidence_reference='Synthetic actual cash refund')
            else:
                prepare(detail=detail, actor=get_user_model().objects.get(pk=self.preparer.pk), rule=rule,
                    day=timezone.localdate(), expenses=[{'account_code':'5-02-03','amount':'600','document_reference':'RACE'}],
                    evidence_reference='RACE-EXPENSE', key='race-expense')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)

    def test_two_refunds_cannot_reserve_the_same_released_balance(self):
        detail, _ = self.refund_setup()
        def compete(number):
            record_receipt(actor=get_user_model().objects.get(pk=self.treasury_user.pk), advance_detail=detail,
                variant=self.transaction_variant, received_on=timezone.localdate(), fund_code='general-fund',
                receipt_book='RACE', receipt_number=str(number), payer_reference='', received_amount='600',
                evidence_reference='Synthetic actual cash refund')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'), 1, results)
        self.assertEqual(TreasuryCollectionSource.objects.filter(proposal__advance_refund__original_detail=detail.pk).count(), 1)
