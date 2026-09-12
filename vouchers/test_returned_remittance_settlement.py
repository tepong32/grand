from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.urls import reverse

from accounting.payables import claim_rows
from accounting.services import submit_entry, post_entry
from finance.models import FinancePostingRule as Rule
from . import test_remittance_returns as fixtures
from .models import VoucherCase
from .remittances import (withholding_availability, create_batch, add_line, submit_batch,
    review_batch, release_batch, materialize_remittance_journal, reconcile_posted_remittance_entry)
from .services import prepare_voucher, validate_accounting


class ReturnedRemittanceSettlementTests(fixtures.RemittanceReturnTests):
    def test_actual_return_corrected_dv_payment_and_retained_outputs(self):
        self.remitted = self.posted_remittance()
        self.batch = self.remitted_source_batch()
        original = list(self.remitted.lines.values('account_id', 'debit', 'credit'))
        receipt = self.propose('100.00', day=1)
        incoming = self.post_return(receipt)
        self.request(correction_date=date(2026, 9, 2))
        correction = self.case.posting_requests.get(kind=Rule.REVERSAL)
        reversal = self.post_request(correction)
        self.assertEqual(reversal.reversal_of_id, self.adjustment.pk)
        self.case.refresh_from_db()
        self.assertEqual(self.case.current_stage, VoucherCase.ACCOUNTING_PREPARATION)
        prepare_voucher(case=self.case, actor=self.preparer, voucher_date=date(2026, 9, 3),
            gross_amount=Decimal('1000'),
            deductions=[{'code': 'ewt', 'description': 'Corrected deduction', 'amount': Decimal('50')}],
            line_description='Corrected invoice after actual agency refund',
            line_account_code=self.expense_account.code, document_codes=['invoice'],
            expected_version=self.case.state_version, idempotency_key='returned-remittance-corrected-dv')
        self.return_signatures(self.case)
        validate_accounting(case=self.case, actor=self.validator, jev_number='RETURN-CORRECTED-DEDUCTIONS',
            jev_date=date(2026, 9, 3), note='Independent corrected deduction review',
            prior_payable_line_id=self.source.pk, expected_version=self.case.state_version,
            idempotency_key='returned-remittance-corrected-validation')
        self.post_request(self.case.posting_requests.get(kind=Rule.ADJUSTMENT, version=2))
        self.pay(self.case)
        rows = withholding_availability(finance_department_id=self.accounting.pk,
            transaction_type=self.transaction_variant.code, as_of_date=date(2026, 9, 30), include_nonpositive=True)
        self.assertEqual(rows[0]['ledger_balance'], Decimal('50'))
        self.assertEqual(rows[0]['available'], Decimal('50'))
        self.assertEqual(claim_rows(self.accounting.pk, date(2026, 9, 30))[0]['outstanding'], Decimal('500'))
        self.assertEqual(list(self.remitted.lines.values('account_id', 'debit', 'credit')), original)
        self.batch.refresh_from_db(); receipt.refresh_from_db()
        self.assertEqual(self.batch.status, self.batch.COMPLETED)
        self.assertEqual(receipt.status, receipt.POSTED)
        self.validator.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers',
            codename='view_remittance_workbench'))
        self.client.force_login(self.validator)
        claims = self.client.get(reverse('accounting:payable_claim_export'), {'as_of': '2026-09-30'})
        self.assertContains(claims, '1500.00,1000.00,500.00')
        outward = self.client.get(reverse('vouchers:remittance_export', args=[self.batch.public_id]))
        self.assertContains(outward, self.remitted.reference)
        self.assertNotContains(outward, incoming.reference)
        returned = self.client.get(reverse('vouchers:remittance_return_export', args=[self.batch.public_id]))
        self.assertContains(returned, incoming.reference)
        self.assertContains(returned, '100.00,100.00')
        corrected = create_batch(actor=self.treasury_user, configuration_release=self.release,
            transaction_variant=self.transaction_variant, recipient_party=self.batch.recipient_party,
            fund_code=self.batch.fund_code, bank_account_code=self.batch.bank_account_code,
            remittance_date=date(2026, 9, 4), payment_method='Electronic transfer',
            authority_reference='Synthetic corrected remittance review', evidence_reference='Corrected withholding schedule')
        add_line(batch=corrected, actor=self.treasury_user, choice_key=rows[0]['choice_key'],
            amount=Decimal('50'), reason='Remit only the corrected deduction')
        submit_batch(batch=corrected, actor=self.treasury_user)
        review_batch(batch=corrected, actor=self.validator, approve=True, reason='Independent corrected schedule review')
        request = release_batch(batch=corrected, actor=self.treasury_user,
            release_reference='Corrected bank debit', acknowledgement_reference='Corrected agency receipt')
        entry, _ = materialize_remittance_journal(request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        reconcile_posted_remittance_entry(entry, self.validator)
        final = withholding_availability(finance_department_id=self.accounting.pk,
            transaction_type=self.transaction_variant.code, as_of_date=date(2026, 9, 30), include_nonpositive=True)
        self.assertEqual(final[0]['ledger_balance'], Decimal('0'))
        self.assertEqual(final[0]['available'], Decimal('0'))
        corrected_csv = self.client.get(reverse('vouchers:remittance_export', args=[corrected.public_id]))
        self.assertContains(corrected_csv, entry.reference)
        self.assertNotContains(corrected_csv, incoming.reference)
        self.assertEqual(self.client.get(reverse('vouchers:remittance_return_export',
            args=[self.batch.public_id])).content, returned.content)
