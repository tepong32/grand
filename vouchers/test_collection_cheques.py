from datetime import date
from django.core.exceptions import ValidationError
from django.urls import reverse
from . import test_collection_charges as fixtures
from .collections import record_receipt
from .collection_outputs import generate, content
from .models import TreasuryCollectionSource as Source


class CollectionChequeTests(fixtures.CollectionChargeTests):
    def cheque_receipt(self, **changes):
        values = dict(actor=self.treasury_user, variant=self.transaction_variant, received_on=date(2026,9,12),
            fund_code='general-fund', receipt_book='CHEQUE', receipt_number='001', payer_reference='Synthetic payer',
            received_amount='100', evidence_reference='Actual synthetic cheque received',
            cheque={'bank':'Synthetic drawee', 'drawer_account':'TEST-ACCOUNT', 'number':'000001',
                    'drawer':'Synthetic drawer', 'date':'2026-09-11'})
        values.update(changes)
        return record_receipt(**values)

    def test_whole_cheque_deposit_and_retained_receipt(self):
        source = self.cheque_receipt()
        self.post_source(source)
        output = generate(source=source, actor=self.treasury_user)
        retained = content(output, self.treasury_user)
        self.assertIn(b'000001', retained)
        with self.assertRaises(ValidationError):
            self.deposit(source, '40', 'PARTIAL-CHEQUE')
        self.post_source(self.deposit(source, '100', 'WHOLE-CHEQUE'))
        with self.assertRaises(ValidationError):
            self.deposit(source, '100', 'DUPLICATE-CHEQUE')
        self.assertEqual(content(output, self.treasury_user), retained)

    def test_duplicate_and_future_cheques_are_rejected(self):
        self.cheque_receipt()
        with self.assertRaises(ValidationError):
            self.cheque_receipt(receipt_number='002')
        with self.assertRaises(ValidationError):
            self.cheque_receipt(receipt_number='003', cheque={'bank':'Bank', 'drawer_account':'A',
                'number':'2','drawer':'Drawer','date':'2026-09-13'})
        with self.assertRaises(ValidationError):
            self.cheque_receipt(receipt_number='004', receiving_bank_id=self.bank_item.public_id,
                bank_transaction_reference='Not a bank credit')

    def test_web_cheque_capture(self):
        self.client.force_login(self.treasury_user)
        response = self.client.post(reverse('vouchers:collection_create'), {
            'variant':self.transaction_variant.pk,'received_on':'2026-09-12','fund_code':'general-fund',
            'receipt_book':'WEB-CHEQUE','receipt_number':'001','payer_reference':'Payer','received_amount':'100',
            'evidence_reference':'Actual synthetic cheque','cheque_bank':'Bank','cheque_drawer_account':'Account',
            'cheque_number':'123','cheque_drawer':'Drawer','cheque_date':'2026-09-11'})
        self.assertEqual(response.status_code, 302)
        source = Source.objects.get(book_reference='WEB-CHEQUE')
        self.assertEqual(source.proposal['cheque']['number'], '123')
        self.assertContains(self.client.get(response.url), 'Cheque received')
        self.assertContains(self.client.get(reverse('vouchers:collection_export')), 'Cheque number')

    def test_changed_issue_date_cannot_duplicate_the_same_instrument(self):
        self.cheque_receipt()
        with self.assertRaises(ValidationError):
            self.cheque_receipt(receipt_number='002', cheque={'bank':'Synthetic drawee',
                'drawer_account':'TEST-ACCOUNT', 'number':'000001', 'drawer':'Synthetic drawer',
                'date':'2026-09-10'})


from . import test_collection_concurrency as concurrency


class CollectionChequeConcurrencyTests(concurrency.CollectionConcurrencyTests):
    cheque_receipt = CollectionChequeTests.cheque_receipt

    def test_duplicate_cheque_capture_serializes_on_treasury(self):
        from django.contrib.auth import get_user_model
        def compete(number):
            self.cheque_receipt(actor=get_user_model().objects.get(pk=self.treasury_user.pk),
                receipt_number=str(number))
            return 'accepted'
        outcomes = self.race(compete)
        self.assertEqual(outcomes.count('accepted'), 1, outcomes)
        self.assertEqual(Source.objects.filter(kind=Source.RECEIPT).count(), 1)
