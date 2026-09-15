from datetime import date
from decimal import Decimal
from unittest import skipUnless
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connections
from django.test import TestCase, TransactionTestCase
from accounting.models import JournalLine
from finance.models import FinanceTransactionVariant, FinancePostingRule as Rule, FinancePostingRuleLine as Line
from . import test_cheque_returns as fixtures
from . import cheque_redemptions as redemption
from . import cheque_clearing as clearing
from .collection_corrections import propose as correct
from .models import TreasuryCollectionSource as Source


class RedemptionTests(TestCase):
    databases = {'default','finance'}
    setUpTestData = classmethod(fixtures.ReturnTests.setUpTestData.__func__)
    employee = classmethod(fixtures.ReturnTests.employee.__func__)
    cheque_receipt = fixtures.ReturnTests.cheque_receipt
    post_source = fixtures.ReturnTests.post_source
    sources = fixtures.ReturnTests.sources
    bank_return = fixtures.ReturnTests.bank_return

    def deposit(self,receipt,value,reference):
        from .collections import record_deposit
        return record_deposit(actor=self.treasury_user,variant=self.transaction_variant,deposited_on=receipt.source_date,
            fund_code='general-fund',deposit_reference=reference,receiving_bank_id=self.bank_item.public_id,
            allocations=[{'receipt':str(receipt.public_id),'amount':value}],evidence_reference='Actual dated synthetic deposit')

    def setUp(self):
        fixtures.ReturnTests.setUp(self)
        self.redemption_type = FinanceTransactionVariant.objects.create(department=self.accounting,release=self.release,
            code='cheque-redemption',label='Redeem returned cheque principal',kind='other',description='Synthetic principal receipt',
            authority_reference='Synthetic reviewed applicability',effective_from=date(2026,1,1),status='active',created_by=self.preparer)
        rule = Rule.objects.create(variant=self.redemption_type,code='redemption',title='Original principal receipt',
            event_kind=Rule.COLLECTION,recognition_point=Rule.COLLECTION_RECEIPT,description='Synthetic receipt',
            authority_reference='Synthetic reviewed receivable settlement',created_by=self.preparer)
        for sequence,side,account_source,code,purpose in [(1,Line.DEBIT,Line.FIXED_ACCOUNT,self.collection_cash.code,'op_services'),
                (2,Line.CREDIT,Line.RETURN_RECEIVABLE,'','')]:
            Line.objects.create(rule=rule,sequence=sequence,label='Synthetic principal',side=side,account_source=account_source,
                ledger_account_code=code,amount_source=Line.EVENT_AMOUNT,cash_flow_category=purpose)

    def returned_source(self):
        receipt,deposit = self.sources()
        source = self.bank_return(receipt,deposit)
        self.post_source(source); source.refresh_from_db()
        return source

    def redeem(self, source, **changes):
        values = dict(original_return=source,actor=self.treasury_user,variant=self.redemption_type,
            received_on=date(2026,9,15),received_amount='100',receipt_book='REDEMPTION',receipt_number='001',
            evidence_reference='Actual synthetic principal received',old_receipt_disposition='surrendered',
            old_receipt_evidence='Original OR physically surrendered; synthetic retained reference')
        values.update(changes)
        return redemption.capture(**values)

    def test_cash_principal_posts_once_without_revenue_recognition(self):
        original = self.returned_source()
        receipt = self.redeem(original)
        with self.assertRaises(ValidationError): self.redeem(original,receipt_number='002')
        entry = self.post_source(receipt)
        self.assertEqual(entry.lines.get(account=self.receivable).credit,Decimal('100'))
        self.assertFalse(entry.lines.filter(account=self.collection_revenue).exists())
        receipt.refresh_from_db()
        self.assertEqual(redemption.settlement(receipt)['status'],'Principal received in cash')
        self.post_source(self.deposit(receipt,'100','REDEEM-DEP'))
        rows = JournalLine.objects.filter(entry__status='posted',account=self.receivable)
        self.assertEqual(sum(row.debit-row.credit for row in rows),Decimal('0'))

    def test_wrong_amount_date_and_ordinary_cheque_are_rejected(self):
        original = self.returned_source()
        for changes in ({'received_amount':'99'},{'received_on':date(2026,9,13)},
                {'old_receipt_evidence':''}, {'cheque':{'kind':'ordinary'}}):
            with self.assertRaises(ValidationError): self.redeem(original,**changes)
        with self.assertRaises(PermissionDenied): self.redeem(original,actor=self.validator)

    def test_web_receipt_review_and_immutable_source_copies(self):
        from django.urls import reverse
        from .collection_outputs import generate,content
        original = self.returned_source()
        before = generate(source=original,actor=self.validator); frozen = content(before,self.validator)
        self.client.force_login(self.treasury_user)
        response = self.client.post(reverse('vouchers:cheque_redemption_create',args=[original.public_id]),{
            'variant':self.redemption_type.pk,'received_on':'2026-09-15','received_amount':'100',
            'receipt_book':'WEB-REDEEM','receipt_number':'001','evidence_reference':'Actual cash received',
            'old_receipt_disposition':'loss_affidavit','old_receipt_evidence':'Synthetic affidavit reference','method':'cash'})
        self.assertEqual(response.status_code,302)
        receipt = Source.objects.get(book_reference='WEB-REDEEM')
        self.assertContains(self.client.get(response.url),'Original bank return')
        self.post_source(receipt); receipt.refresh_from_db()
        self.assertIn(b'Returned-cheque principal receipt',content(generate(source=receipt,actor=self.validator),self.validator))
        self.assertEqual(content(before,self.validator),frozen)
        self.assertIn(b'WEB-REDEEM',content(generate(source=original,actor=self.validator),self.validator))

    def test_uat_cannot_capture_and_changed_cash_account_is_rejected(self):
        from django.contrib.auth.models import Group
        from .roles import FINANCE_UAT_VIEWER_GROUP
        from .collection_posting import review_source
        from .remittances import _digest
        original = self.returned_source(); receipt = self.redeem(original)
        proposal = dict(receipt.proposal,cash_account_id=self.deposit_bank.pk)
        Source.objects.filter(pk=receipt.pk).update(proposal=proposal,proposal_checksum=_digest(proposal))
        with self.assertRaises(ValidationError):
            review_source(source=receipt,actor=self.validator,approve=True,reason='Changed source')
        self.treasury_user.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied): self.redeem(original,receipt_number='UAT')

    def test_source_correction_releases_principal_only_after_reconciliation(self):
        original = self.returned_source(); receipt = self.redeem(original)
        self.post_source(receipt); receipt.refresh_from_db()
        with self.assertRaises(ValidationError):
            correct(original=original,actor=self.treasury_user,corrected_on=date(2026,9,15),reason='Wrong return')
        correction = correct(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,15),reason='Wrong redemption attribution')
        with self.assertRaises(ValidationError): self.redeem(original,receipt_number='002')
        self.post_source(correction); receipt.refresh_from_db()
        self.assertFalse(receipt.redemption_active)
        self.assertEqual(receipt.status,Source.POSTED)
        replacement = self.redeem(original,receipt_number='002')
        self.assertEqual(replacement.redemption_return_id,original.pk)

    def test_later_redemption_correction_cannot_authorize_earlier_return_correction(self):
        original = self.returned_source(); receipt = self.redeem(original)
        self.post_source(receipt)
        correction = correct(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,15),reason='Wrong principal receipt')
        self.post_source(correction)
        with self.assertRaises(ValidationError):
            correct(original=original,actor=self.treasury_user,corrected_on=date(2026,9,14),reason='Earlier bank correction')
        final = correct(original=original,actor=self.treasury_user,corrected_on=date(2026,9,15),reason='Dated bank correction')
        self.post_source(final); original.refresh_from_db()
        self.assertEqual(original.status,Source.CORRECTED)

    def test_replacement_cheque_requires_clearing_and_repeated_return_uses_new_obligation(self):
        original = self.returned_source()
        receipt = self.redeem(original,cheque={'kind':'manager','bank':'Synthetic bank','drawer_account':'Manager account',
            'number':'MC-001','drawer':'Synthetic bank','date':'2026-09-15'})
        self.post_source(receipt); receipt.refresh_from_db()
        self.assertIn('clearing pending',redemption.settlement(receipt)['status'])
        from .collections import record_deposit
        deposit = record_deposit(actor=self.treasury_user,variant=self.transaction_variant,deposited_on=date(2026,9,15),
            fund_code='general-fund',deposit_reference='MC-DEP',receiving_bank_id=self.bank_item.public_id,
            allocations=[{'receipt':str(receipt.public_id),'amount':'100'}],evidence_reference='Actual manager cheque deposit')
        self.post_source(deposit); deposit.refresh_from_db()
        row = clearing.propose(receipt=receipt,deposit=deposit,actor=self.treasury_user,cleared_on=date(2026,9,15),
            bank_reference='MC-CLEAR',evidence_reference='Actual bank confirmation')
        clearing.review(clearance=row,actor=self.validator,approve=True,reason='Independent bank evidence')
        self.assertIn('clearing confirmed',redemption.settlement(receipt)['status'])
        later = self.bank_return(receipt,deposit,bank_reference='MC-RETURN',debited_on=date(2026,9,15))
        self.post_source(later); later.refresh_from_db()
        self.assertIn('Replacement cheque return',redemption.settlement(receipt)['status'])
        with self.assertRaises(ValidationError): self.redeem(original,receipt_number='OLD-AGAIN')
        self.post_source(self.redeem(later,receipt_number='SUCCESSOR'))
        rows = JournalLine.objects.filter(entry__status='posted',account=self.receivable)
        self.assertEqual(sum(row.debit-row.credit for row in rows),Decimal('0'))


@skipUnless(connections['finance'].vendor == 'mysql','Requires native MySQL row locks')
class RedemptionConcurrencyTests(TransactionTestCase):
    databases = {'default','finance'}
    employee = classmethod(RedemptionTests.employee.__func__)
    cheque_receipt = RedemptionTests.cheque_receipt
    deposit = RedemptionTests.deposit
    post_source = RedemptionTests.post_source
    sources = RedemptionTests.sources
    bank_return = RedemptionTests.bank_return
    redeem = RedemptionTests.redeem
    returned_source = RedemptionTests.returned_source
    race = fixtures.ReturnConcurrencyTests.race

    def setUp(self):
        RedemptionTests.setUpTestData.__func__(type(self))
        RedemptionTests.setUp(self)

    def test_competing_redemptions_reserve_principal_once(self):
        original = self.returned_source()
        def compete(number):
            self.redeem(original,receipt_number=str(number))
            return 'accepted'
        result = self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)

    def test_redemption_and_return_correction_share_original_source_lock(self):
        original = self.returned_source()
        def compete(number):
            if number == 1: self.redeem(original)
            else: correct(original=original,actor=self.treasury_user,corrected_on=date(2026,9,15),reason='Wrong original return')
            return 'accepted'
        result = self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)
