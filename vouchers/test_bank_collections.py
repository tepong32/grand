from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from accounting.models import PostingMapping
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line
from . import test_collection_charges as fixtures
from .collections import record_receipt, remaining_receipts
from .collection_posting import review_source, materialize
from .collection_corrections import propose
from .collection_outputs import generate, content


class BankCollectionTests(fixtures.CollectionChargeTests):
    def bank_recipe(self):
        type(self.release).objects.filter(pk=self.release.pk).update(status='draft')
        Line.objects.filter(rule__variant__in=[self.transaction_variant, self.second_type],
            rule__event_kind=Rule.COLLECTION, side=Line.DEBIT).update(
                account_source=Line.BANK_MAPPING, ledger_account_code='')
        for line in Line.objects.filter(rule__variant__in=[self.transaction_variant, self.second_type],
                rule__event_kind=Rule.COLLECTION):
            line.full_clean()
        type(self.release).objects.filter(pk=self.release.pk).update(status='active')

    def bank_receipt(self, **changes):
        values = dict(actor=self.treasury_user, variant=self.transaction_variant,
            received_on=date(2026,9,12), fund_code='general-fund', receipt_book='BANK',
            receipt_number='001', payer_reference='Synthetic payer', received_amount='100',
            evidence_reference='Synthetic confirmed incoming bank credit',
            receiving_bank_id=self.bank_item.public_id, bank_transaction_reference='BANK-CREDIT-001')
        values.update(changes)
        return record_receipt(**values)

    def test_bank_credit_correction_successor_and_retained_copy(self):
        self.bank_recipe()
        source = self.bank_receipt()
        entry = self.post_source(source)
        self.assertEqual(entry.lines.get(account=self.deposit_bank).debit, Decimal('100'))
        self.assertFalse(entry.lines.filter(account=self.collection_cash).exists())
        self.assertNotIn(str(source.public_id), remaining_receipts(self.treasury.pk))
        with self.assertRaises(ValidationError):
            self.deposit(source, '100', 'DUPLICATE-DEPOSIT')
        output = generate(source=source, actor=self.treasury_user)
        original = content(output, self.treasury_user)
        self.assertIn(b'BANK-CREDIT-001', original)
        correction = propose(original=source, actor=self.treasury_user,
            corrected_on=date(2026,9,13), reason='Correct synthetic source amount')
        reversal = self.post_source(correction)
        self.assertEqual(reversal.reversal_of_id, entry.pk)
        successor = self.bank_receipt(received_on=date(2026,9,13), received_amount='90')
        self.post_source(successor)
        self.assertEqual(successor.supersedes_id, source.pk)
        self.assertEqual(content(output, self.treasury_user), original)
        self.assertNotIn(str(successor.public_id), remaining_receipts(self.treasury.pk))

    def test_bank_mapping_is_reviewed_then_pinned(self):
        self.bank_recipe()
        source = self.bank_receipt()
        mapping = PostingMapping.objects.get(department_id=self.accounting.pk,
            category=PostingMapping.BANK, source_code='gf-lbp')
        mapping.account = self.collection_cash
        mapping.save()
        with self.assertRaises(ValidationError):
            review_source(source=source, actor=self.validator, approve=True, reason='Changed mapping')
        mapping.account = self.deposit_bank
        mapping.save()
        review_source(source=source, actor=self.validator, approve=True, reason='Verified bank credit')
        mapping.account = self.collection_cash
        mapping.save()
        entry, _ = materialize(source.posting_requests.get(), self.preparer)
        self.assertEqual(entry.lines.get(account=self.deposit_bank).debit, Decimal('100'))

    def test_bank_receipt_requires_actual_reference_and_bank_recipe(self):
        with self.assertRaises(ValidationError):
            self.bank_receipt()
        self.bank_recipe()
        with self.assertRaises(ValidationError):
            self.bank_receipt(bank_transaction_reference='')
        with self.assertRaises(ValidationError):
            self.bank_receipt(receiving_bank_id=None)
        with self.assertRaises(ValidationError):
            self.bank_receipt(receiving_bank_id=None, bank_transaction_reference='')

    def test_multi_charge_bank_receipt_preserves_cash_purposes(self):
        self.bank_recipe()
        Line.objects.filter(rule=self.second_rule, side=Line.DEBIT).update(cash_flow_category='op_taxes')
        source = self.bank_receipt(charges=[
            {'variant':str(self.transaction_variant.public_id), 'amount':'60'},
            {'variant':str(self.second_type.public_id), 'amount':'40'}])
        entry = self.post_source(source)
        self.assertEqual(entry.lines.get(account=self.deposit_bank, cash_flow_category='op_services').debit, Decimal('60'))
        self.assertEqual(entry.lines.get(account=self.deposit_bank, cash_flow_category='op_taxes').debit, Decimal('40'))
        self.assertNotIn(str(source.public_id), remaining_receipts(self.treasury.pk))

    def test_web_bank_capture_export_and_deposit_selection(self):
        from django.urls import reverse
        from .models import TreasuryCollectionSource as Source
        from .collection_views import DepositShareForm
        self.bank_recipe()
        self.client.force_login(self.treasury_user)
        response = self.client.post(reverse('vouchers:collection_create'), {
            'variant':self.transaction_variant.pk, 'received_on':'2026-09-12',
            'fund_code':'general-fund', 'receipt_book':'WEB-BANK', 'receipt_number':'001',
            'payer_reference':'Synthetic payer', 'received_amount':'100',
            'evidence_reference':'Actual synthetic bank credit',
            'receiving_bank_id':str(self.bank_item.public_id), 'bank_transaction_reference':'WEB-BANK-001'})
        self.assertEqual(response.status_code, 302)
        source = Source.objects.get(book_reference='WEB-BANK')
        self.post_source(source)
        self.assertContains(self.client.get(response.url), 'WEB-BANK-001')
        self.assertContains(self.client.get(reverse('vouchers:collection_export')), 'WEB-BANK-001')
        self.assertFalse(DepositShareForm(user=self.treasury_user).fields['receipt'].queryset.filter(pk=source.pk).exists())

    def test_interrupted_bank_receipt_recovers_one_posting(self):
        from unittest.mock import patch
        self.bank_recipe()
        with patch.object(self, 'capture', self.bank_receipt):
            self.test_interrupted_receipt_handoff_recovers_one_finance_journal()


from . import test_advance_refunds as refund_fixtures


class BankAdvanceRefundTests(refund_fixtures.AdvanceRefundTests):
    def test_bank_refund_preserves_officer_capacity_and_exact_correction(self):
        from django.utils import timezone
        from finance.models import FinanceConfigurationItem
        from .advance_applications import prepare
        from .advance_refunds import movements
        detail, cash = self.refund_setup()
        bank = FinanceConfigurationItem.objects.get(release=self.release, category='bank_account', code='gf-lbp')
        Line.objects.filter(rule__variant=self.transaction_variant, rule__event_kind=Rule.COLLECTION,
            side=Line.DEBIT).update(account_source=Line.BANK_MAPPING, ledger_account_code='')
        refund = record_receipt(actor=self.treasury_user, advance_detail=detail,
            variant=self.transaction_variant, received_on=timezone.localdate(), fund_code='general-fund',
            receipt_book='BANK-REFUND', receipt_number='001', payer_reference='', received_amount='400',
            evidence_reference='Confirmed officer bank refund', receiving_bank_id=bank.public_id,
            bank_transaction_reference='OFFICER-REFUND-001')
        entry = self.post_refund_source(refund)
        self.assertEqual(entry.subsidiary_lines.get().credit, Decimal('400'))
        self.assertFalse(entry.lines.filter(account=cash).exists())
        self.assertNotIn(str(refund.public_id), remaining_receipts(self.treasury.pk))
        rule = self.liquidation_rule()
        def expense(value, key):
            return prepare(detail=detail, actor=self.preparer, rule=rule, day=timezone.localdate(),
                expenses=[{'account_code':'5-02-03', 'amount':value, 'document_reference':key}],
                evidence_reference=key, key=key)
        with self.assertRaises(ValidationError):
            expense('600.01', 'over-bank-refund')
        correction = propose(original=refund, actor=self.treasury_user,
            corrected_on=timezone.localdate(), reason='Incorrect refund source')
        reversal = self.post_refund_source(correction)
        self.assertEqual(reversal.reversal_of_id, entry.pk)
        self.assertEqual(reversal.subsidiary_lines.get().debit, Decimal('400'))
        self.assertEqual(sum(value for day, value in movements(detail)), Decimal('0'))
        self.assertEqual(expense('1000', 'after-bank-correction').payload['advance_application']['amount'], '1000.00')
