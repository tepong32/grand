from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from accounting.models import LedgerAccount
from accounting.services import submit_entry, post_entry
from . import test_remittance_returns as return_fixtures
from .remittance_returns import propose_return, review_return, export_returns
from .receipt_corrections import propose_correction, review_correction
from .remittances import materialize_remittance_journal, reconcile_posted_remittance_entry
from django.test import SimpleTestCase


class ReceiptFeeInputTests(SimpleTestCase):
    def test_oversized_fee_is_a_controlled_validation_error(self):
        from .receipt_fees import snapshot
        for value in ('1E+100', 'NaN', 'Infinity', '-1', '0.001'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                snapshot(None, value, None, '', Decimal('100'))
        self.assertIsNone(snapshot(None, '0', None, '', Decimal('100')))


class ReceiptFeeTests(return_fixtures.RemittanceReturnTests):
    def fee_setup(self):
        self.remitted = self.posted_remittance()
        self.batch = self.remitted_source_batch()
        self.fee_account = LedgerAccount.objects.create(department_id=self.accounting.pk,
            department_label=self.accounting.name, code='5-fee', title='Synthetic bank charge',
            account_type='expense', normal_balance='debit')

    def fee_proposal(self, amount='5.00'):
        self.batch.refresh_from_db()
        return propose_return(batch=self.batch, actor=self.treasury_user,
            returned_on=date(2026,9,1), receipt_reference='Bank credit 95; gross refund 100',
            reason='Refund less documented bank charge', filing_basis='Agency refund basis',
            allocations=[{'source_detail':self.remitted.subsidiary_lines.get().pk,'amount':'100.00'}],
            expected_version=self.batch.state_version, fee_amount=amount,
            fee_account_id=self.fee_account.pk, fee_reference='Bank charge advice 5')

    def test_netted_receipt_and_exact_correction_preserve_gross_fee_net(self):
        self.fee_setup()
        receipt = self.fee_proposal()
        entry = self.post_return(receipt)
        self.assertEqual(entry.totals,(Decimal('100'),Decimal('100')))
        self.assertEqual(entry.lines.get(account=self.fee_account).debit,Decimal('5'))
        self.assertEqual(entry.lines.get(account__account_type='asset').debit,Decimal('95'))
        self.assertEqual(entry.subsidiary_lines.get().credit,Decimal('100'))
        receipt.refresh_from_db(); self.batch.refresh_from_db()
        correction = propose_correction(receipt=receipt,actor=self.treasury_user,
            correction_date=date(2026,9,2),reason='Wrong bank advice',evidence_reference='Corrected advice',
            filing_basis='Retained agency basis',expected_version=self.batch.state_version)
        review_correction(item=correction,actor=self.validator,approve=True,reason='Independent correction review')
        correction.refresh_from_db()
        reverse,_ = materialize_remittance_journal(correction.posting_request,self.preparer)
        submit_entry(reverse,self.preparer); post_entry(reverse,self.validator)
        reconcile_posted_remittance_entry(reverse,self.validator)
        self.assertEqual(reverse.lines.get(account=self.fee_account).credit,Decimal('5'))
        self.assertEqual(reverse.lines.get(account__account_type='asset').credit,Decimal('95'))
        self.assertEqual(self.remitted.lines.get(credit__gt=0).credit,Decimal('100'))

    def test_fee_cannot_exceed_receipt_or_use_nonexpense_account(self):
        self.fee_setup()
        for amount in ('-1','100','101','NaN','0.001'):
            with self.assertRaises(ValidationError): self.fee_proposal(amount)
        self.fee_account=self.remitted.lines.get(credit__gt=0).account
        with self.assertRaises(ValidationError): self.fee_proposal()

    def test_review_and_posting_reject_changed_fee_evidence(self):
        self.fee_setup()
        receipt=self.fee_proposal()
        LedgerAccount.objects.filter(pk=self.fee_account.pk).update(title='Changed expense')
        with self.assertRaisesMessage(ValidationError,'fee account changed'):
            review_return(item=receipt,actor=self.validator,approve=True,reason='Independent review')
        LedgerAccount.objects.filter(pk=self.fee_account.pk).update(title=self.fee_account.title)
        review_return(item=receipt,actor=self.validator,approve=True,reason='Independent review')
        receipt.refresh_from_db()
        entry,_=materialize_remittance_journal(receipt.posting_request,self.preparer)
        cash=entry.lines.get(account__account_type='asset'); expense=entry.lines.get(account=self.fee_account)
        entry.lines.filter(pk=cash.pk).update(debit=Decimal('94'))
        entry.lines.filter(pk=expense.pk).update(debit=Decimal('6'))
        with self.assertRaisesMessage(ValidationError,'approved gross allocations'):
            submit_entry(entry,self.preparer)

    def test_http_fee_entry_and_retained_gross_net_export(self):
        from django.contrib.auth.models import Permission
        from django.urls import reverse
        self.fee_setup()
        for user in (self.treasury_user,self.validator):
            user.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers',codename='view_remittance_workbench'))
        self.client.force_login(self.treasury_user)
        url=reverse('vouchers:remittance_return_prepare',args=[self.batch.public_id])
        self.assertContains(self.client.get(url),'Bank fee deducted from refund')
        response=self.client.post(url,{'returned_on':'2026-09-01','receipt_reference':'Actual credit 95',
            'reason':'Refund less bank fee','filing_basis':'Agency refund evidence','expected_version':self.batch.state_version,
            'fee_amount':'5.00','fee_account_id':self.fee_account.pk,'fee_reference':'Bank advice',
            f'amount_{self.remitted.subsidiary_lines.get().pk}':'100.00'})
        self.assertEqual(response.status_code,302)
        receipt=self.batch.returns.get(); self.post_return(receipt)
        self.client.force_login(self.validator)
        self.assertContains(self.client.get(reverse('vouchers:remittance_detail',args=[self.batch.public_id])),'Net bank credit 95.00')
        exported=self.client.get(reverse('vouchers:remittance_return_export',args=[self.batch.public_id]))
        self.assertContains(exported,'gross_refund,deducted_bank_fee,net_bank_credit')
        self.assertContains(exported,'100.00,5.00,95.00,5-fee,Bank advice')


from . import test_returned_remittance_settlement as settlement_fixtures


class ReceiptFeeSettlementTests(settlement_fixtures.ReturnedRemittanceSettlementTests):
    def propose_netted(self, amount, day=1):
        self.fee_account = LedgerAccount.objects.create(department_id=self.accounting.pk,
            department_label=self.accounting.name, code='5-settlement-fee',
            title='Synthetic returned-remittance bank fee', account_type='expense', normal_balance='debit')
        self.batch.refresh_from_db()
        return propose_return(batch=self.batch, actor=self.treasury_user,
            returned_on=date(2026,9,day), receipt_reference='Gross 100 less bank charge 5',
            reason='Agency refund with documented bank fee', filing_basis='Retained independent agency basis',
            allocations=[{'source_detail':self.remitted.subsidiary_lines.get().pk,'amount':amount}],
            expected_version=self.batch.state_version,fee_amount='5.00',fee_account_id=self.fee_account.pk,
            fee_reference='Synthetic bank advice 5')

    def test_actual_return_corrected_dv_payment_and_retained_outputs(self):
        from unittest.mock import patch
        with patch.object(self, "propose", self.propose_netted):
            super().test_actual_return_corrected_dv_payment_and_retained_outputs()
        receipt=self.batch.returns.get()
        from accounting.models import JournalEntry
        incoming=JournalEntry.objects.get(public_id=receipt.posting_request.accounting_entry_public_id)
        self.assertEqual(incoming.lines.get(account=self.fee_account).debit,Decimal('5'))
        self.assertEqual(incoming.lines.get(account__account_type='asset').debit,Decimal('95'))
        self.assertEqual(incoming.subsidiary_lines.get().credit,Decimal('100'))
        self.assertFalse(incoming.reversal_entries.exists())
        content,_=export_returns(self.batch,self.validator)
        self.assertIn('100.00,5.00,95.00,5-settlement-fee',content.decode('utf-8-sig'))
