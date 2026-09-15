from datetime import date
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import patch
import tempfile

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from accounting.models import LedgerAccount, JournalEntry, PostingMapping
from accounting.services import submit_entry, post_entry
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from . import test_cheque_clearing as fixtures
from . import test_collection_workflow as workflow
from . import cheque_returns as returns
from . import cheque_clearing as clearing
from .collection_posting import review_source, materialize, reconcile
from .collection_corrections import propose as correct
from .collection_outputs import generate, content
from .collections import record_deposit, remaining_receipts
from .models import TreasuryCollectionSource as Source, CollectionPostingRequest as Request


class ReturnTests(TestCase):
    databases = {'default','finance'}
    setUpTestData = classmethod(fixtures.ChequeClearingTests.setUpTestData.__func__)
    employee = classmethod(fixtures.ChequeClearingTests.employee.__func__)
    cheque_receipt = fixtures.ChequeClearingTests.cheque_receipt
    deposit = fixtures.ChequeClearingTests.deposit
    post_source = fixtures.ChequeClearingTests.post_source
    sources = fixtures.ChequeClearingTests.sources
    propose_clearing = fixtures.ChequeClearingTests.propose_clearing

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='grand-return-tests-')
        self.addCleanup(tmp.cleanup)
        settings = override_settings(MEDIA_ROOT=tmp.name, GRAND_EXPORT_ROOT=tmp.name)
        settings.enable(); self.addCleanup(settings.disable)
        workflow.CollectionWorkflowTests.setUp(self)
        from django.contrib.auth.models import Permission
        for user in (self.validator, self.treasury_user):
            user.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers',codename='view_collection_register'),
                Permission.objects.get(content_type__app_label='finance',codename='export_finance_work'))
        self.receivable = LedgerAccount.objects.create(department_id=self.accounting.pk,
            department_label=self.accounting.name, code='TEST-RETURN', title='Synthetic reviewed cheque debtor',
            account_type='asset', normal_balance='debit')
        self.return_rule = Rule.objects.create(variant=self.transaction_variant, code='cheque-return',
            title='Synthetic receivable treatment', event_kind=Rule.CHEQUE_RETURN,
            recognition_point=Rule.COLLECTION_RETURN, description='Synthetic whole principal return',
            authority_reference='Synthetic applicable category; not an LGU prescription', created_by=self.preparer)
        for sequence, side, account_source, code, purpose in [
                (1,Line.DEBIT,Line.FIXED_ACCOUNT,self.receivable.code,''),
                (2,Line.CREDIT,Line.BANK_MAPPING,'','op_services')]:
            Line.objects.create(rule=self.return_rule, sequence=sequence, label='Synthetic return line',
                side=side, account_source=account_source, ledger_account_code=code,
                amount_source=Line.EVENT_AMOUNT, cash_flow_category=purpose)

    def bank_return(self, receipt, deposit, **changes):
        values = dict(receipt=receipt, deposit=deposit, actor=self.treasury_user,
            variant=self.transaction_variant, debited_on=date(2026,9,14), debit_amount='100',
            bank_reference='DEBIT-001', reason='Actual bank dishonour', evidence_reference='Synthetic bank debit memo',
            applicability_reference='Synthetic reviewed debtor treatment for all original components')
        values.update(changes)
        return returns.capture(**values)

    def test_return_posts_only_own_share_of_combined_deposit_and_preserves_copies(self):
        receipt = self.cheque_receipt(); self.post_source(receipt)
        other = self.cheque_receipt(receipt_number='002', received_amount='200',
            cheque={'bank':'Bank','drawer_account':'Account','number':'OTHER','drawer':'Other','date':'2026-09-11'})
        self.post_source(other)
        deposit = record_deposit(actor=self.treasury_user, variant=self.transaction_variant,
            deposited_on=date(2026,9,12), fund_code='general-fund', deposit_reference='COMBINED',
            receiving_bank_id=self.bank_item.public_id, evidence_reference='Combined bank slip',
            allocations=[{'receipt':str(receipt.public_id),'amount':'100'}, {'receipt':str(other.public_id),'amount':'200'}])
        self.post_source(deposit); receipt.refresh_from_db(); deposit.refresh_from_db()
        output = generate(source=receipt,actor=self.validator); frozen = content(output,self.validator)
        clearance = self.propose_clearing(receipt,deposit)
        clearing.review(clearance=clearance,actor=self.validator,approve=True,reason='Actually cleared earlier')
        source = self.bank_return(receipt,deposit)
        entry = self.post_source(source)
        self.assertEqual(entry.lines.get(account=self.deposit_bank).credit,Decimal('100'))
        self.assertEqual(entry.lines.get(account=self.receivable).debit,Decimal('100'))
        self.assertIsNone(entry.reversal_of_id)
        self.assertFalse(entry.lines.filter(account=self.collection_revenue).exists())
        self.assertEqual(content(output,self.validator),frozen)
        self.assertIn(b'DEBIT-001',content(generate(source=receipt,actor=self.validator),self.validator))
        source.refresh_from_db()
        self.assertIn(b'Original returned cheque',content(generate(source=source,actor=self.validator),self.validator))
        clearance.refresh_from_db(); self.assertEqual(clearance.status,'approved')
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(other.public_id)],Decimal('0'))

    def test_duplicate_partial_wrong_date_and_source_correction_are_blocked(self):
        receipt,deposit = self.sources()
        for changes in ({'debit_amount':'99'}, {'debited_on':date(2026,9,11)}, {'bank_reference':''}):
            with self.assertRaises(ValidationError): self.bank_return(receipt,deposit,**changes)
        source = self.bank_return(receipt,deposit)
        with self.assertRaises(ValidationError): self.bank_return(receipt,deposit,bank_reference='SECOND')
        with self.assertRaises(ValidationError): self.propose_clearing(receipt,deposit)
        for original in (receipt,deposit):
            with self.assertRaises(ValidationError):
                correct(original=original,actor=self.treasury_user,corrected_on=date(2026,9,14),reason='Wrong source')
        review_source(source=source,actor=self.validator,approve=False,reason='Wrong debit attribution')
        self.assertIsNotNone(self.bank_return(receipt,deposit,bank_reference='REVISED').pk)

    def test_return_error_correction_retires_only_after_independent_posting(self):
        receipt,deposit = self.sources(); source = self.bank_return(receipt,deposit)
        original_entry = self.post_source(source); source.refresh_from_db()
        fix = correct(original=source,actor=self.treasury_user,corrected_on=date(2026,9,15),reason='Debit attributed to wrong cheque')
        with self.assertRaises(ValidationError): self.bank_return(receipt,deposit,bank_reference='NEW')
        reversal = self.post_source(fix)
        self.assertEqual(reversal.reversal_of_id,original_entry.pk)
        source.refresh_from_db(); self.assertEqual(source.status,Source.CORRECTED)
        with self.assertRaises(ValidationError):
            self.bank_return(receipt,deposit,bank_reference='EARLY',debited_on=date(2026,9,14))
        self.assertIsNotNone(self.bank_return(receipt,deposit,bank_reference='NEW',debited_on=date(2026,9,15)).pk)

    def test_changed_recipe_detected_and_approved_original_bank_is_pinned(self):
        receipt,deposit = self.sources(); source = self.bank_return(receipt,deposit)
        line = self.return_rule.lines.get(side=Line.DEBIT)
        Line.objects.filter(pk=line.pk).update(ledger_account_code=self.collection_cash.code)
        with self.assertRaises(ValidationError):
            review_source(source=source,actor=self.validator,approve=True,reason='Changed recipe')
        Line.objects.filter(pk=line.pk).update(ledger_account_code=self.receivable.code)
        review_source(source=source,actor=self.validator,approve=True,reason='Original recipe')
        PostingMapping.objects.filter(account=self.deposit_bank).update(account=self.collection_cash)
        entry,_ = materialize(source.posting_requests.get(),self.preparer)
        self.assertTrue(entry.lines.filter(account=self.deposit_bank,credit=100).exists())

    def test_interrupted_handoff_recovers_one_return_journal(self):
        receipt,deposit = self.sources(); source = self.bank_return(receipt,deposit)
        review_source(source=source,actor=self.validator,approve=True,reason='Bank debit verified')
        request = source.posting_requests.get(); save = Request.save
        def fail(row,*args,**kwargs):
            if row.status == row.MATERIALIZED: raise RuntimeError('Interrupted default link')
            return save(row,*args,**kwargs)
        with patch.object(Request,'save',fail), self.assertRaises(RuntimeError): materialize(request,self.preparer)
        entry,created = materialize(request,self.preparer)
        self.assertFalse(created)
        submit_entry(entry,self.preparer); post_entry(entry,self.validator); reconcile(entry,self.validator)
        self.assertEqual(JournalEntry.objects.filter(source_type='cheque_return').count(),1)

    def test_web_capture_review_and_uat_denial(self):
        from django.contrib.auth.models import Group
        from .roles import FINANCE_UAT_VIEWER_GROUP
        receipt,deposit = self.sources()
        self.client.force_login(self.treasury_user)
        response = self.client.post(reverse('vouchers:cheque_return_create',args=[receipt.public_id]),
            {'deposit':deposit.pk,'variant':self.transaction_variant.pk,'debited_on':'2026-09-14','debit_amount':'100',
             'bank_reference':'WEB-DEBIT','reason':'Bank returned cheque','evidence_reference':'Bank memo',
             'applicability_reference':'Reviewed synthetic category'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Original returned cheque')
        source = Source.objects.get(kind=Source.CHEQUE_RETURN)
        with self.assertRaises((PermissionDenied,ValidationError)):
            review_source(source=source,actor=self.treasury_user,approve=True,reason='Self')
        self.validator.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            review_source(source=source,actor=self.validator,approve=True,reason='UAT')

    def test_known_collection_cash_is_not_a_return_receivable(self):
        receipt,deposit = self.sources()
        self.return_rule.lines.filter(side=Line.DEBIT).update(ledger_account_code=self.collection_cash.code)
        with self.assertRaises(ValidationError): self.bank_return(receipt,deposit)

    def test_return_cannot_reclassify_the_original_cash_purpose(self):
        Line.objects.filter(rule__variant=self.transaction_variant,rule__event_kind=Rule.COLLECTION,
            side=Line.DEBIT).update(cash_flow_category='op_taxes')
        receipt,deposit = self.sources()
        with self.assertRaises(ValidationError): self.bank_return(receipt,deposit)

    def test_multicharge_return_retains_original_component_amounts(self):
        from finance.models import FinanceTransactionVariant
        from .collections import record_receipt
        variant = FinanceTransactionVariant.objects.create(department=self.accounting,release=self.release,
            code='second-return-charge',label='Second original charge',kind='other',description='Synthetic charge',
            authority_reference='Synthetic category',effective_from=date(2026,1,1),status='active',created_by=self.preparer)
        rule = Rule.objects.create(variant=variant,code='second',title='Synthetic charge',event_kind=Rule.COLLECTION,
            recognition_point=Rule.COLLECTION_RECEIPT,description='Synthetic category',authority_reference='Synthetic',created_by=self.preparer)
        for sequence,side,code,purpose in [(1,Line.DEBIT,self.collection_cash.code,'op_services'),
                (2,Line.CREDIT,self.collection_revenue.code,'')]:
            Line.objects.create(rule=rule,sequence=sequence,label='Synthetic',side=side,account_source=Line.FIXED_ACCOUNT,
                amount_source=Line.EVENT_AMOUNT,ledger_account_code=code,cash_flow_category=purpose)
        receipt = self.cheque_receipt(charges=[{'variant':str(self.transaction_variant.public_id),'amount':'60'},
            {'variant':str(variant.public_id),'amount':'40'}])
        self.post_source(receipt)
        deposit = self.deposit(receipt,'100','MULTI'); self.post_source(deposit)
        receipt.refresh_from_db(); deposit.refresh_from_db()
        source = self.bank_return(receipt,deposit)
        entry = self.post_source(source)
        self.assertEqual(source.proposal['original_cheque']['charges'],receipt.proposal['charges'])
        self.assertEqual(entry.lines.get(account=self.deposit_bank).credit,Decimal('100'))


@skipUnless(connections['finance'].vendor == 'mysql','Requires native MySQL row locks')
class ReturnConcurrencyTests(TransactionTestCase):
    databases = {'default','finance'}
    employee = classmethod(ReturnTests.employee.__func__)
    cheque_receipt = ReturnTests.cheque_receipt
    deposit = ReturnTests.deposit
    post_source = ReturnTests.post_source
    sources = ReturnTests.sources
    bank_return = ReturnTests.bank_return
    race = fixtures.ChequeClearingConcurrencyTests.race

    def setUp(self):
        ReturnTests.setUpTestData.__func__(type(self))
        ReturnTests.setUp(self)

    def test_competing_returns_keep_one_active_source(self):
        receipt,deposit = self.sources()
        def compete(number):
            self.bank_return(receipt,deposit,bank_reference=f'RACE-{number}')
            return 'accepted'
        result = self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)

    def test_return_and_deposit_correction_share_source_lock(self):
        receipt,deposit = self.sources()
        def compete(number):
            if number == 1: self.bank_return(receipt,deposit)
            else: correct(original=deposit,actor=self.treasury_user,corrected_on=date(2026,9,14),reason='Wrong deposit')
            return 'accepted'
        result = self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)

    def test_return_and_clearing_proposal_share_source_lock(self):
        receipt,deposit = self.sources()
        def compete(number):
            if number == 1: self.bank_return(receipt,deposit)
            else: fixtures.ChequeClearingTests.propose_clearing(self,receipt,deposit)
            return 'accepted'
        result = self.race(compete)
        self.assertEqual(result.count('accepted'),1,result)

    def test_competing_materialization_recovers_one_return_journal(self):
        from django.contrib.auth import get_user_model
        receipt,deposit = self.sources(); source = self.bank_return(receipt,deposit)
        review_source(source=source,actor=self.validator,approve=True,reason='Independent bank debit review')
        request = source.posting_requests.get()
        def compete(number):
            entry,created = materialize(Request.objects.get(pk=request.pk),get_user_model().objects.get(pk=self.preparer.pk))
            return entry.pk,created
        result = self.race(compete)
        self.assertTrue(all(isinstance(item,tuple) for item in result),result)
        self.assertEqual(len({item[0] for item in result}),1,result)
        self.assertEqual(sum(item[1] for item in result),1,result)
