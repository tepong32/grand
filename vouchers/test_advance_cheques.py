from datetime import date, datetime, timezone as utc
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from accounting.models import JournalEntry
from finance.models import FinanceConfigurationItem
from . import test_advance_refunds as fixtures, test_advance_concurrency as concurrent
from . import cheque_clearing as clearing
from .advance_applications import capacity, prepare
from .advance_cheques import settlement
from .advance_refunds import movements
from .collections import record_receipt, record_deposit
from .collection_outputs import generate, content
from .models import TreasuryCollectionSource as Source


class OfficerChequeTests(fixtures.AdvanceRefundTests):
    def cheque(self, detail, **changes):
        values = dict(actor=self.treasury_user, advance_detail=detail, variant=self.transaction_variant,
            received_on=timezone.localdate(), fund_code='general-fund', receipt_book='OFFICER-CHEQUE',
            receipt_number='001', payer_reference='', received_amount='400', evidence_reference='Actual synthetic instrument',
            cheque={'bank':'Synthetic drawee', 'drawer_account':'Synthetic account', 'number':'0001',
                'drawer':'Synthetic officer', 'date':'2026-09-11'})
        values.update(changes)
        return record_receipt(**values)

    def deposited(self, receipt):
        self.post_refund_source(receipt)
        bank = FinanceConfigurationItem.objects.get(release=self.release, category='bank_account', code='gf-lbp')
        deposit = record_deposit(actor=self.treasury_user, variant=self.transaction_variant,
            deposited_on=receipt.source_date, fund_code='general-fund', deposit_reference='OFFICER-DEP',
            receiving_bank_id=bank.public_id, allocations=[{'receipt':str(receipt.public_id),'amount':str(receipt.amount)}],
            evidence_reference='Actual synthetic whole deposit')
        self.post_refund_source(deposit)
        return deposit

    def clearance(self, receipt, deposit):
        return clearing.propose(receipt=receipt, deposit=deposit, actor=self.treasury_user,
            cleared_on=timezone.localdate(), bank_reference='OFFICER-CLEAR', evidence_reference='Bank confirmation')

    def test_pending_and_cleared_refund_keep_one_hold_and_immutable_prior_copy(self):
        detail, _ = self.refund_setup()
        receipt = self.cheque(detail)
        self.assertIn('posting and bank clearing pending', settlement(receipt)['status'])
        with self.assertRaises(ValidationError): capacity(detail, receipt.source_date, Decimal('600.01'))
        deposit = self.deposited(receipt)
        self.treasury_user.user_permissions.add(Permission.objects.get(content_type__app_label='finance',codename='export_finance_work'))
        before = generate(source=receipt,actor=self.treasury_user)
        frozen = content(before,self.treasury_user)
        self.assertIn(b'Officer advance cheque refund',frozen)
        self.assertIn(b'bank clearing pending',frozen)
        original_journals = list(JournalEntry.objects.values_list('pk',flat=True))
        row = self.clearance(receipt,deposit)
        clearing.review(clearance=row,actor=self.validator,approve=True,reason='Independent bank evidence')
        self.assertIn('clearing confirmed',settlement(receipt)['status'])
        self.assertEqual(movements(detail),[(receipt.source_date,Decimal('400'))])
        self.assertEqual(list(JournalEntry.objects.values_list('pk',flat=True)),original_journals)
        capacity(detail,receipt.source_date,Decimal('600'))
        with self.assertRaises(ValidationError): capacity(detail,receipt.source_date,Decimal('600.01'))
        self.assertEqual(content(before,self.treasury_user),frozen)
        self.assertIn(b'clearing confirmed',content(generate(source=receipt,actor=self.treasury_user),self.treasury_user))

    def test_clearing_withdrawal_preserves_hold_and_exact_correction_releases_it(self):
        from .collection_corrections import propose
        detail, _ = self.refund_setup()
        receipt = self.cheque(detail)
        deposit = self.deposited(receipt)
        row = self.clearance(receipt,deposit)
        clearing.review(clearance=row,actor=self.validator,approve=True,reason='Independent evidence')
        with self.assertRaises(ValidationError):
            propose(original=deposit,actor=self.treasury_user,corrected_on=timezone.localdate(),reason='Source error')
        clearing.withdraw(clearance=row,actor=self.validator,reason='Confirmation attributed incorrectly')
        self.assertIn('bank clearing pending',settlement(receipt)['status'])
        self.assertEqual(movements(detail),[(receipt.source_date,Decimal('400'))])
        self.post_refund_source(propose(original=deposit,actor=self.treasury_user,corrected_on=timezone.localdate(),reason='Wrong deposit'))
        self.post_refund_source(propose(original=receipt,actor=self.treasury_user,corrected_on=timezone.localdate(),reason='Wrong receipt'))
        self.assertIn('reservation released from the correction date',settlement(receipt)['status'])
        self.assertEqual(sum(value for day,value in movements(detail)),0)

    def test_future_refund_hold_blocks_earlier_over_application(self):
        with patch('django.utils.timezone.now',return_value=datetime(2026,9,11,3,tzinfo=utc.utc)):
            detail, _ = self.refund_setup()
        receipt = self.cheque(detail,received_on=date(2026,9,13),received_amount='600')
        with self.assertRaises(ValidationError): capacity(detail,date(2026,9,12),Decimal('500'))
        capacity(detail,date(2026,9,12),Decimal('400'))
        self.assertEqual(movements(detail),[(receipt.source_date,Decimal('600'))])

    def test_duplicate_mixed_method_uat_and_premature_clearing_are_rejected(self):
        detail, _ = self.refund_setup()
        receipt = self.cheque(detail)
        with self.assertRaises(ValidationError): self.cheque(detail,receipt_number='duplicate')
        bank = FinanceConfigurationItem.objects.get(release=self.release,category='bank_account',code='gf-lbp')
        with self.assertRaises(ValidationError):
            self.cheque(detail,receiving_bank_id=bank.public_id,bank_transaction_reference='Credit and instrument')
        with self.assertRaises(ValidationError): self.clearance(receipt,receipt)
        self.treasury_user.groups.add(Group.objects.get_or_create(name='Finance UAT Viewer')[0])
        with self.assertRaises(PermissionDenied): self.cheque(detail,receipt_number='uat')

    def test_actual_bank_return_remains_blocked_without_dated_advance_adapter(self):
        from .cheque_returns import original_evidence
        detail, _ = self.refund_setup()
        receipt = self.cheque(detail)
        deposit = self.deposited(receipt)
        with self.assertRaisesMessage(ValidationError,'dependent dated-capacity adapter'):
            original_evidence(receipt,deposit,timezone.localdate())
        self.assertEqual(movements(detail),[(receipt.source_date,Decimal('400'))])

    def test_web_capture_shows_pending_officer_cheque_without_claiming_cash(self):
        detail, _ = self.refund_setup()
        self.client.force_login(self.treasury_user)
        response = self.client.post(reverse('vouchers:collection_create'),{
            'advance_detail':detail.pk,'variant':self.transaction_variant.pk,'received_on':timezone.localdate().isoformat(),
            'fund_code':'general-fund','receipt_book':'WEB-OFFICER-CHEQUE','receipt_number':'001','received_amount':'400',
            'evidence_reference':'Synthetic instrument','cheque_bank':'Bank','cheque_drawer_account':'Account',
            'cheque_number':'007','cheque_drawer':'Officer','cheque_date':'2026-09-11'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Cheque amount reserved; receipt posting and bank clearing pending')


class OfficerChequeConcurrencyTests(concurrent.AdvanceConcurrencyTests):
    refund_setup = fixtures.AdvanceRefundTests.refund_setup
    cheque = OfficerChequeTests.cheque
    deposited = OfficerChequeTests.deposited
    clearance = OfficerChequeTests.clearance
    post_refund_source = fixtures.AdvanceRefundTests.post_refund_source

    def test_pending_cheque_and_expense_share_original_case_lock(self):
        detail, _ = self.refund_setup()
        rule = self.liquidation_rule()
        def compete(number):
            if number == 1:
                self.cheque(detail,received_amount='600')
            else:
                prepare(detail=detail,actor=self.preparer,rule=rule,day=timezone.localdate(),
                    expenses=[{'account_code':'5-02-03','amount':'600','document_reference':'RACE'}],
                    evidence_reference='Actual expense',key='cheque-expense-race')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'),1,results)

    def test_clearing_withdrawal_and_expense_keep_refund_reserved(self):
        detail, _ = self.refund_setup()
        receipt = self.cheque(detail,received_amount='600')
        deposit = self.deposited(receipt)
        row = self.clearance(receipt,deposit)
        clearing.review(clearance=row,actor=self.validator,approve=True,reason='Bank confirmed')
        rule = self.liquidation_rule()
        def compete(number):
            if number == 1:
                clearing.withdraw(clearance=row,actor=self.validator,reason='Incorrect clearing reference')
                return 'withdrawn'
            prepare(detail=detail,actor=self.preparer,rule=rule,day=timezone.localdate(),
                expenses=[{'account_code':'5-02-03','amount':'500','document_reference':'RACE'}],
                evidence_reference='Expense evidence',key='clearing-withdrawal-expense')
            return 'accepted'
        results = self.race(compete)
        self.assertIn('withdrawn',results)
        self.assertTrue(any('exceeds the released' in item for item in results),results)
        self.assertEqual(movements(detail),[(receipt.source_date,Decimal('600'))])
