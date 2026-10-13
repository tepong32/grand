from datetime import date
from decimal import Decimal
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from accounting.models import LedgerAccount
from finance.models import FinanceTransactionVariant, FinancePostingRule as Rule, FinancePostingRuleLine as Line
from . import test_collection_workflow as fixtures
from .collections import record_receipt, remaining_receipts
from .collection_posting import review_source, materialize
from .collection_corrections import propose
from .collection_outputs import generate, content


class CollectionChargeTests(fixtures.CollectionWorkflowTests):
    def setUp(self):
        super().setUp()
        self.second_revenue=LedgerAccount.objects.create(department_id=self.accounting.pk,
            department_label=self.accounting.name,code='COL-SECOND',title='Second synthetic charge',
            account_type='revenue',normal_balance='credit')
        self.second_type=FinanceTransactionVariant.objects.create(department=self.accounting,release=self.release,
            code='second-collection',label='Second collection charge',kind='other',description='Synthetic second charge',
            authority_reference='Synthetic reviewed type',effective_from=date(2026,1,1),status='active',created_by=self.preparer)
        self.second_rule=Rule.objects.create(variant=self.second_type,code='second-receipt',title='Second receipt recipe',
            event_kind=Rule.COLLECTION,recognition_point=Rule.COLLECTION_RECEIPT,description='Synthetic recipe',
            authority_reference='Synthetic reviewed rule',created_by=self.preparer)
        for sequence,side,code,purpose in [(1,Line.DEBIT,self.collection_cash.code,'op_services'),(2,Line.CREDIT,self.second_revenue.code,'')]:
            Line.objects.create(rule=self.second_rule,sequence=sequence,label='Synthetic charge line',side=side,
                account_source=Line.FIXED_ACCOUNT,amount_source=Line.EVENT_AMOUNT,ledger_account_code=code,cash_flow_category=purpose)
        for user in (self.validator,self.treasury_user):
            user.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers',codename='view_collection_register'),
                Permission.objects.get(content_type__app_label='finance',codename='export_finance_work'))

    def capture_charges(self,total='100',first='60',second='40'):
        return record_receipt(actor=self.treasury_user,variant=self.transaction_variant,received_on=date(2026,9,12),
            fund_code='general-fund',receipt_book='CHARGES',receipt_number='001',payer_reference='Synthetic payer',
            received_amount=total,evidence_reference='One payment for two charges',charges=[
                {'variant':str(self.transaction_variant.public_id),'amount':first},
                {'variant':str(self.second_type.public_id),'amount':second}])

    def test_receipt_deposits_corrections_replacement_and_retained_copy(self):
        receipt=self.capture_charges(); entry=self.post_source(receipt)
        self.assertEqual(entry.lines.get(account=self.collection_cash).debit,Decimal('100'))
        self.assertEqual(entry.lines.get(account=self.collection_revenue).credit,Decimal('60'))
        self.assertEqual(entry.lines.get(account=self.second_revenue).credit,Decimal('40'))
        receipt.refresh_from_db(); output=generate(source=receipt,actor=self.validator)
        original_copy=content(output,self.validator)
        self.assertIn(b'Second collection charge',original_copy)
        first=self.deposit(receipt,'40','MULTI-DEP-1');self.post_source(first)
        second=self.deposit(receipt,'60','MULTI-DEP-2');self.post_source(second)
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('0'))
        with self.assertRaises(ValidationError):
            propose(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Correct receipt')
        for deposit in (first,second):
            deposit.refresh_from_db()
            self.post_source(propose(original=deposit,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Correct deposit'))
        fixed=self.post_source(propose(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Correct charge amount'))
        self.assertEqual(fixed.lines.get(account=self.second_revenue).debit,Decimal('40'))
        replacement=self.capture_charges('90','60','30'); revised=self.post_source(replacement)
        self.assertEqual(replacement.supersedes_id,receipt.pk)
        self.assertEqual(revised.lines.get(account=self.second_revenue).credit,Decimal('30'))
        self.assertEqual(content(output,self.validator),original_copy)

    def test_charge_total_and_incompatible_cash_account_are_rejected(self):
        with self.assertRaises(ValidationError):self.capture_charges(total='99')
        Line.objects.filter(rule=self.second_rule,side=Line.DEBIT).update(ledger_account_code=self.deposit_bank.code)
        with self.assertRaises(ValidationError):self.capture_charges()

    def test_review_detects_recipe_change_and_posting_pins_approved_recipe(self):
        receipt=self.capture_charges()
        line=Line.objects.get(rule=self.second_rule,side=Line.CREDIT)
        Line.objects.filter(pk=line.pk).update(ledger_account_code=self.collection_revenue.code)
        with self.assertRaises(ValidationError):
            review_source(source=receipt,actor=self.validator,approve=True,reason='Review charge breakdown')
        Line.objects.filter(pk=line.pk).update(ledger_account_code=self.second_revenue.code)
        review_source(source=receipt,actor=self.validator,approve=True,reason='Independent charge review')
        Line.objects.filter(pk=line.pk).update(ledger_account_code=self.collection_revenue.code)
        entry,_=materialize(receipt.posting_requests.get(),self.preparer)
        self.assertEqual(entry.lines.get(account=self.second_revenue).credit,Decimal('40'))

    def test_http_charge_entry_and_review_detail(self):
        self.client.force_login(self.treasury_user)
        url=reverse('vouchers:collection_create')
        self.assertContains(self.client.get(url),'One receipt covering several charge types')
        response=self.client.post(url,{'variant':self.transaction_variant.pk,'received_on':'2026-09-12',
            'fund_code':'general-fund','receipt_book':'HTTP-CHARGES','receipt_number':'001','payer_reference':'Synthetic payer',
            'received_amount':'100','evidence_reference':'Two actual charges','charges-TOTAL_FORMS':'2','charges-INITIAL_FORMS':'0',
            'charges-0-variant':str(self.transaction_variant.public_id),'charges-0-amount':'60',
            'charges-1-variant':str(self.second_type.public_id),'charges-1-amount':'40'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Second collection charge')


    def test_mixed_cash_purposes_keep_their_amounts_through_deposit(self):
        Line.objects.filter(rule=self.second_rule,side=Line.DEBIT).update(cash_flow_category='op_taxes')
        receipt=self.capture_charges(); entry=self.post_source(receipt)
        self.assertEqual(set(entry.lines.filter(account=self.collection_cash).values_list('cash_flow_category','debit')),
            {('op_services',Decimal('60')),('op_taxes',Decimal('40'))})
        deposit=self.post_source(self.deposit(receipt,'100','MIXED-PURPOSE-DEP'))
        self.assertEqual(deposit.lines.get(account=self.collection_cash).credit,Decimal('100'))
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('0'))
