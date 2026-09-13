from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
import uuid
import csv
import io
from pathlib import Path
from django.conf import settings

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounting.models import JournalEntry, JournalLine
from accounting.services import submit_entry, post_entry, subsidiary_schedule_rows, discard_draft
from . import test_advances as fixtures
from .advance_applications import prepare as prepare_expenses, withdraw
from .liquidation_corrections import prepare, restored_movements, financial_rows
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .models import VoucherPostingRequest as Request


class LiquidationCorrectionTests(fixtures.AdvanceRecognitionTests):
    def test_corrected_expense_can_be_settled_by_actual_cash_refund(self):
        from . import test_advance_refunds as refunds
        from .collections import record_receipt
        from .collection_posting import review_source, materialize, reconcile
        detail, cash = refunds.AdvanceRefundTests.refund_setup(self)
        rule = self.liquidation_rule()
        application = self.expenses(detail, rule, '1000', 'ORIGINAL', timezone.localdate())
        self.post_request(application)
        correction = prepare(application=application, actor=self.preparer, day=timezone.localdate(),
            reason='Expense was incorrect; officer returned the money', key='REFUND-INSTEAD')
        entry, _ = materialize_voucher_journal(correction, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator); entry.refresh_from_db()
        def receipt():
            return record_receipt(actor=self.treasury_user, advance_detail=detail, variant=self.transaction_variant,
                received_on=timezone.localdate(), fund_code='general-fund', receipt_book='CORRECTED-ADVANCE',
                receipt_number='001', payer_reference='', received_amount='1000', evidence_reference='Actual money returned')
        with self.assertRaisesMessage(ValidationError, 'exceeds the released'):
            receipt()
        reconcile_posted_voucher_entry(entry, self.validator)
        refund = receipt()
        review_source(source=refund, actor=self.validator, approve=True, reason='Independent receipt review')
        journal, _ = materialize(refund.posting_requests.get(), self.preparer)
        submit_entry(journal, self.preparer); post_entry(journal, self.validator); reconcile(journal, self.validator)
        self.assertEqual(journal.subsidiary_lines.get().credit, Decimal('1000'))
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())[0]['balance'], 0)

    def liquidated_advance(self):
        detail, case, instrument = self.paid_advance()
        rule = self.liquidation_rule()
        request = self.expenses(detail, rule, '1000', 'ORIGINAL', timezone.localdate())
        entry = self.post_request(request)
        return detail, case, rule, request, entry

    def expenses(self, detail, rule, amount, key, day):
        return prepare_expenses(detail=detail, actor=self.preparer, rule=rule, day=day,
            expenses=[{'account_code':'5-02-03', 'amount':amount, 'document_reference':'SYNTHETIC-EXPENSE'}],
            evidence_reference='SYNTHETIC-LIQUIDATION', key=key)

    def post_request(self, request):
        entry, _ = materialize_voucher_journal(request, self.preparer)
        submit_entry(entry, self.preparer); entry.refresh_from_db()
        post_entry(entry, self.validator); entry.refresh_from_db()
        reconcile_posted_voucher_entry(entry, self.validator)
        return entry

    def test_web_exact_correction_and_replacement_preserve_history_and_outputs(self):
        detail, case, rule, application, original = self.liquidated_advance()
        original_rows = financial_rows(original)
        self.preparer.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=('view_officer_advances','export_officer_advances','post_journal_entries')))
        self.client.force_login(self.preparer)
        earlier_response = self.client.get(reverse('accounting:advance_export'))
        earlier_export = earlier_response.content
        archived = Path(settings.GRAND_EXPORT_ROOT) / earlier_response['X-GRAND-Export-Relative-Path']
        url = reverse('accounting:advance_liquidation_correct', args=[application.public_id])
        self.assertContains(self.client.get(url), 'Correct posted expense liquidation')
        failed = self.client.post(url, {'day':'2026-08-01', 'reason':'Retained invalid-date reason','key':str(uuid.uuid4())})
        self.assertEqual(failed.status_code, 200)
        self.assertContains(failed, 'Retained invalid-date reason')
        response = self.client.post(url, {'day':timezone.localdate().isoformat(),
            'reason':'Wrong expense account on accepted liquidation', 'key':str(uuid.uuid4())})
        self.assertEqual(response.status_code, 302)
        correction = case.posting_requests.get(trigger_key__startswith='advance-liquidation-fix:')
        entry = JournalEntry.objects.get(public_id=correction.accounting_entry_public_id)
        self.assertEqual(entry.reversal_of_id, original.pk)
        submit_entry(entry, self.preparer); entry.refresh_from_db()
        # A preparer with posting permission still cannot approve their own correction.
        from django.contrib.auth import get_user_model
        with self.assertRaisesMessage(ValidationError, 'independent Accounting'):
            post_entry(entry, get_user_model().objects.get(pk=self.preparer.pk))
        post_entry(entry, self.validator); entry.refresh_from_db()
        self.assertEqual(restored_movements(application), [])
        reconcile_posted_voucher_entry(entry, self.validator)
        self.assertEqual(restored_movements(application)[0][1], Decimal('-1000'))
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())[0]['balance'], Decimal('1000'))
        self.assertEqual(archived.read_bytes(), earlier_export)
        page = self.client.get(reverse('accounting:advance_detail', args=[detail.pk]))
        self.assertContains(page, 'Liquidation corrections')
        self.assertNotContains(page, 'Correct this posted liquidation')
        replacement = self.expenses(detail, rule, '1000', 'REPLACEMENT', timezone.localdate())
        self.assertEqual(replacement.payload['advance_application']['replaces_application'], str(application.public_id))
        self.assertEqual(self.expenses(detail, rule, '1000', 'REPLACEMENT', timezone.localdate()).pk, replacement.pk)
        self.post_request(replacement)
        self.assertEqual(financial_rows(original), original_rows)
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())[0]['balance'], 0)
        current_export = self.client.get(reverse('accounting:advance_export'))
        self.assertEqual(current_export.status_code, 200)
        archived_row = next(csv.DictReader(io.StringIO(earlier_export.decode())))
        self.assertEqual(Decimal(archived_row['debits']), Decimal('1000'))
        self.assertEqual(Decimal(archived_row['credits']), Decimal('1000'))
        self.assertEqual(Decimal(archived_row['recognized_balance']), 0)
        self.assertEqual(archived.read_bytes(), earlier_export)
        case.refresh_from_db()
        self.assertEqual(case.current_stage, case.COMPLETED)

    def test_later_correction_cannot_fund_earlier_liquidation(self):
        with patch('django.utils.timezone.now', return_value=datetime(2026,9,11,3,tzinfo=dt_timezone.utc)):
            detail, case, rule, application, original = self.liquidated_advance()
        correction = prepare(application=application, actor=self.preparer, day=date(2026,9,13),
            reason='Incorrect posted expense', key='DATED')
        self.post_request(correction)
        with self.assertRaises(ValidationError):
            self.expenses(detail, rule, '1000', 'EARLIER', date(2026,9,12))
        self.assertEqual(self.expenses(detail, rule, '1000', 'LATER', date(2026,9,13)).payload['advance_application']['amount'], '1000.00')

    def test_mirror_tampering_and_discarded_correction_withdrawal(self):
        detail, case, rule, application, original = self.liquidated_advance()
        correction = prepare(application=application, actor=self.preparer, day=timezone.localdate(),
            reason='Incorrect posted expense', key='DISCARD')
        entry, _ = materialize_voucher_journal(correction, self.preparer)
        credit = entry.lines.get(credit=1000)
        original_account = credit.account_id
        JournalLine.objects.filter(pk=credit.pk).update(account=detail.journal_line.account)
        with self.assertRaisesMessage(ValidationError, 'exactly mirror'):
            submit_entry(entry, self.preparer)
        JournalLine.objects.filter(pk=credit.pk).update(account_id=original_account)
        with self.assertRaises(ValidationError):
            withdraw(correction, self.validator, 'Wrong unposted correction')
        discard_draft(entry, self.preparer, reason='Wrong proposed correction')
        withdraw(correction, self.validator, 'Wrong unposted correction')
        with self.assertRaises(ValidationError):
            materialize_voucher_journal(correction, self.preparer)
        replacement = prepare(application=application, actor=self.preparer, day=timezone.localdate(),
            reason='Corrected proposal', key='NEW-CORRECTION')
        self.post_request(replacement)
        self.assertEqual(restored_movements(application)[0][1], Decimal('-1000'))
