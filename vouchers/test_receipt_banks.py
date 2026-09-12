from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse

from accounting.models import LedgerAccount, PostingMapping
from accounting.services import submit_entry, post_entry
from finance.models import FinanceConfigurationItem
from . import test_remittance_returns as fixtures
from .remittance_returns import propose_return, review_return
from .receipt_corrections import propose_correction, review_correction
from .remittances import materialize_remittance_journal, reconcile_posted_remittance_entry


class ReceiptBankTests(fixtures.RemittanceReturnTests):
    def receiving_bank(self):
        self.remitted = self.posted_remittance(); self.batch = self.remitted_source_batch()
        owner = {'department_id':self.accounting.pk, 'department_label':self.accounting.name}
        self.other_bank = LedgerAccount.objects.create(**owner, code='1-01-03', title='Synthetic second bank',
            account_type='asset', normal_balance='debit')
        self.bank_item = FinanceConfigurationItem.objects.create(department=self.accounting, release=self.release,
            category='bank_account', code='gf-other-bank', version=1, label='Synthetic receiving bank',
            status='active', effective_from=date(2026, 1, 1), created_by=self.preparer)
        self.bank_mapping = PostingMapping.objects.create(**owner, category=PostingMapping.BANK,
            source_code=self.bank_item.code, label='Explicit receiving bank mapping', account=self.other_bank)

    def propose_other(self):
        self.batch.refresh_from_db()
        return propose_return(batch=self.batch, actor=self.treasury_user, returned_on=date(2026, 9, 1),
            receipt_reference='Actual credit to other bank', reason='Agency refund into another authorized account',
            filing_basis='Synthetic retained agency basis',
            allocations=[{'source_detail':self.remitted.subsidiary_lines.get().pk, 'amount':'100.00'}],
            expected_version=self.batch.state_version, receiving_bank_id=self.bank_item.public_id)

    def test_http_bank_selection_posting_correction_and_exports(self):
        self.receiving_bank()
        for user in (self.treasury_user,self.validator):
            user.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename='view_remittance_workbench'))
        self.client.force_login(self.treasury_user)
        url = reverse('vouchers:remittance_return_prepare', args=[self.batch.public_id])
        self.assertContains(self.client.get(url), 'Synthetic receiving bank')
        self.assertEqual(self.client.post(url, {'returned_on':'2026-09-01', 'receipt_reference':'Actual receiving-bank credit',
            'reason':'Refund into authorized alternate account', 'filing_basis':'Agency evidence retained',
            'expected_version':self.batch.state_version, 'receiving_bank_id':str(self.bank_item.public_id),
            f'amount_{self.remitted.subsidiary_lines.get().pk}':'100.00'}).status_code,302)
        item = self.batch.returns.get()
        entry = self.post_return(item)
        self.assertEqual(entry.lines.get(debit__gt=0).account_id,self.other_bank.pk)
        self.assertEqual(entry.fund_id,self.remitted.fund_id)
        self.assertNotEqual(self.remitted.lines.get(credit__gt=0).account_id,self.other_bank.pk)
        self.client.force_login(self.validator)
        exported = self.client.get(reverse('vouchers:remittance_return_export',args=[self.batch.public_id]))
        self.assertContains(exported,'gf-other-bank')
        self.assertContains(exported,self.other_bank.code)
        self.assertContains(self.client.get(reverse('vouchers:remittance_detail',args=[self.batch.public_id])),'Synthetic receiving bank')
        item.refresh_from_db(); self.batch.refresh_from_db()
        correction = propose_correction(receipt=item, actor=self.treasury_user, correction_date=date(2026,9,2),
            reason='Incorrect receipt amount', evidence_reference='Synthetic receipt correction', filing_basis='Agency basis',
            expected_version=self.batch.state_version)
        review_correction(item=correction, actor=self.validator, approve=True, reason='Independent original-bank-line review')
        correction.refresh_from_db()
        reversed_entry,_ = materialize_remittance_journal(correction.posting_request,self.preparer)
        submit_entry(reversed_entry,self.preparer); post_entry(reversed_entry,self.validator)
        reconcile_posted_remittance_entry(reversed_entry,self.validator)
        self.assertEqual(reversed_entry.lines.get(credit__gt=0).account_id,self.other_bank.pk)
        self.assertEqual(reversed_entry.reversal_of_id,entry.pk)

    def test_changed_mapping_requires_fresh_proposal_before_review(self):
        self.receiving_bank(); item=self.propose_other()
        original=self.remitted.lines.get(credit__gt=0).account
        self.bank_mapping.account=original; self.bank_mapping.save()
        with self.assertRaisesMessage(ValidationError,'mapping changed'):
            review_return(item=item,actor=self.validator,approve=True,reason='Review observed bank')
        item.refresh_from_db(); self.assertEqual(item.status,item.PROPOSED)
        self.assertEqual(item.proposal['receiving_bank']['ledger_account_id'],self.other_bank.pk)

    def test_approved_bank_is_not_rerouted_by_later_mapping_changes(self):
        self.receiving_bank(); item=self.propose_other()
        review_return(item=item,actor=self.validator,approve=True,reason='Independent actual bank credit review')
        item.refresh_from_db()
        self.bank_mapping.account=self.remitted.lines.get(credit__gt=0).account; self.bank_mapping.save()
        entry,_=materialize_remittance_journal(item.posting_request,self.preparer)
        submit_entry(entry,self.preparer); post_entry(entry,self.validator)
        reconcile_posted_remittance_entry(entry,self.validator)
        self.assertEqual(entry.lines.get(debit__gt=0).account_id,self.other_bank.pk)

    def test_unmapped_or_inactive_bank_cannot_be_selected(self):
        self.receiving_bank()
        self.bank_mapping.is_active=False; self.bank_mapping.save()
        with self.assertRaisesMessage(ValidationError,'explicit active'):
            self.propose_other()
        self.bank_mapping.is_active=True; self.bank_mapping.save()
        FinanceConfigurationItem.objects.filter(pk=self.bank_item.pk).update(status='retired')
        with self.assertRaisesMessage(ValidationError,'active for this receipt date'):
            self.propose_other()
