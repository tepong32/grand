from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from finance.models import FinanceTransactionVariant, FinancePostingRule as Rule, FinancePostingRuleLine as Line
from vouchers import test_cheque_redemptions as fixtures
from vouchers.collection_outputs import generate,content
from vouchers.collection_corrections import propose as correct


class ComponentTests(TestCase):
    databases = {'default','finance'}
    setUpTestData = classmethod(fixtures.RedemptionTests.setUpTestData.__func__)
    employee = classmethod(fixtures.RedemptionTests.employee.__func__)
    cheque_receipt = fixtures.RedemptionTests.cheque_receipt
    post_source = fixtures.RedemptionTests.post_source
    deposit = fixtures.RedemptionTests.deposit
    bank_return = fixtures.RedemptionTests.bank_return
    redeem = fixtures.RedemptionTests.redeem

    def setUp(self):
        fixtures.RedemptionTests.setUp(self)
        self.second_type = FinanceTransactionVariant.objects.create(department=self.accounting,release=self.release,
            code='tax-component',label='Second original tax charge',kind='other',description='Synthetic second charge',
            authority_reference='Synthetic reviewed applicability',effective_from=date(2026,1,1),status='active',created_by=self.preparer)
        rule = Rule.objects.create(variant=self.second_type,code='tax',title='Tax component',
            event_kind=Rule.COLLECTION,recognition_point=Rule.COLLECTION_RECEIPT,
            description='Synthetic charge',authority_reference='Synthetic authority',created_by=self.preparer)
        for sequence,side,code,purpose in [(1,Line.DEBIT,self.collection_cash.code,'op_taxes'),
                (2,Line.CREDIT,self.collection_revenue.code,'')]:
            Line.objects.create(rule=rule,sequence=sequence,label='Synthetic charge',side=side,
                account_source=Line.FIXED_ACCOUNT,amount_source=Line.EVENT_AMOUNT,
                ledger_account_code=code,cash_flow_category=purpose)
        self.return_rule.lines.filter(side=Line.CREDIT).update(amount_source='original_cash_component')
        Line.objects.create(rule=self.return_rule,sequence=3,label='Original tax cash component',side=Line.CREDIT,
            account_source=Line.BANK_MAPPING,amount_source='original_cash_component',cash_flow_category='op_taxes')
        receipt_rule = self.redemption_type.posting_rules.get()
        receipt_rule.lines.filter(side=Line.DEBIT).update(amount_source='original_cash_component')
        Line.objects.create(rule=receipt_rule,sequence=3,label='Original tax cash component',side=Line.DEBIT,
            account_source=Line.FIXED_ACCOUNT,ledger_account_code=self.collection_cash.code,
            amount_source='original_cash_component',cash_flow_category='op_taxes')

    def sources(self):
        receipt = self.cheque_receipt(charges=[{'variant':str(self.transaction_variant.public_id),'amount':'60'},
            {'variant':str(self.second_type.public_id),'amount':'40'}])
        self.post_source(receipt)
        deposit = self.deposit(receipt,'100','COMPONENT-DEPOSIT'); self.post_source(deposit)
        receipt.refresh_from_db(); deposit.refresh_from_db()
        return receipt,deposit

    def test_original_components_survive_return_redemption_and_exact_correction(self):
        receipt,deposit = self.sources()
        original = self.bank_return(receipt,deposit); returned = self.post_source(original)
        original.refresh_from_db()
        self.assertEqual(set(returned.lines.filter(account=self.deposit_bank).values_list('cash_flow_category','credit')),
            {('op_services',Decimal('60')),('op_taxes',Decimal('40'))})
        frozen = generate(source=original,actor=self.validator); original_bytes = content(frozen,self.validator)
        redemption = self.redeem(original); entry = self.post_source(redemption)
        self.assertEqual(set(entry.lines.filter(account=self.collection_cash).values_list('cash_flow_category','debit')),
            {('op_services',Decimal('60')),('op_taxes',Decimal('40'))})
        self.assertEqual(entry.lines.get(account=self.receivable).credit,Decimal('100'))
        self.assertFalse(entry.lines.filter(account=self.collection_revenue).exists())
        redemption.refresh_from_db()
        self.assertIn(b'Returned-cheque principal receipt',content(generate(source=redemption,actor=self.validator),self.validator))
        correction = correct(original=redemption,actor=self.treasury_user,corrected_on=date(2026,9,15),reason='Actual source error')
        reversal = self.post_source(correction)
        self.assertEqual(set(reversal.lines.filter(account=self.collection_cash).values_list('cash_flow_category','credit')),
            {('op_services',Decimal('60')),('op_taxes',Decimal('40'))})
        self.assertEqual(content(frozen,self.validator),original_bytes)

    def test_incomplete_or_reclassified_component_recipe_is_rejected(self):
        receipt,deposit = self.sources()
        self.return_rule.lines.filter(cash_flow_category='op_taxes').update(cash_flow_category='op_other')
        with self.assertRaises(ValidationError): self.bank_return(receipt,deposit)

    def test_redemption_cannot_route_components_to_two_collection_assets(self):
        receipt,deposit = self.sources(); original = self.bank_return(receipt,deposit)
        self.post_source(original); original.refresh_from_db()
        self.redemption_type.posting_rules.get().lines.filter(cash_flow_category='op_taxes').update(ledger_account_code=self.deposit_bank.code)
        with self.assertRaises(ValidationError): self.redeem(original)

    def test_component_configuration_requires_the_correct_event_side_and_purpose(self):
        type(self.release).objects.filter(pk=self.release.pk).update(status='draft')
        line = Line.objects.get(rule=self.return_rule,cash_flow_category='op_taxes')
        line.full_clean()
        line.cash_flow_category = ''
        with self.assertRaises(ValidationError): line.full_clean()
        line.cash_flow_category = 'op_taxes'; line.mapping_code = 'another-bank'
        with self.assertRaises(ValidationError): line.full_clean()
        line.mapping_code = ''; line.side = Line.DEBIT
        with self.assertRaises(ValidationError): line.full_clean()

    def test_changed_component_evidence_cannot_be_approved(self):
        from copy import deepcopy
        from vouchers.models import TreasuryCollectionSource as Source
        from vouchers.remittances import _digest
        from vouchers.collection_posting import review_source
        receipt,deposit = self.sources(); source = self.bank_return(receipt,deposit)
        proposal = deepcopy(source.proposal)
        proposal['original_cheque']['cash_components'][0]['amount'] = '59.99'
        Source.objects.filter(pk=source.pk).update(proposal=proposal,proposal_checksum=_digest(proposal))
        source.refresh_from_db()
        with self.assertRaises(ValidationError):
            review_source(source=source,actor=self.validator,approve=True,reason='Changed retained component')
