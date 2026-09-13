from decimal import Decimal
from datetime import date, datetime, timezone as datetime_timezone
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from accounting.models import LedgerAccount, JournalLine
from accounting.services import submit_entry, post_entry, subsidiary_schedule_rows
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line, FinanceConfigurationItem
from .test_advances import AdvanceRecognitionTests
from .collections import record_receipt, record_deposit
from .collection_posting import review_source, materialize, reconcile


class AdvanceRefundTests(AdvanceRecognitionTests):
    def test_correction_releases_refund_hold_only_from_its_actual_date(self):
        from .advance_applications import prepare
        from .collection_corrections import propose
        with patch('django.utils.timezone.now', return_value=datetime(2026, 9, 11, 3, tzinfo=datetime_timezone.utc)):
            detail, _ = self.refund_setup()
        with self.assertRaises(ValidationError):
            self.capture_refund(detail, day=date(2026,9,10))
        refund = self.capture_refund(detail, amount='600', day=date(2026,9,12))
        self.post_refund_source(refund)
        correction = propose(original=refund, actor=self.treasury_user, corrected_on=date(2026,9,13), reason='Incorrect receipt')
        self.post_refund_source(correction)
        rule = self.liquidation_rule()
        def expense(day, value, key):
            return prepare(detail=detail, actor=self.preparer, rule=rule, day=day,
                expenses=[{'account_code':'5-02-03','amount':value,'document_reference':key}],
                evidence_reference=key, key=key)
        with self.assertRaisesMessage(ValidationError, 'exceeds the released'):
            expense(date(2026,9,11), '600', 'earlier-expense')
        self.assertEqual(expense(date(2026,9,13), '1000', 'after-correction').payload['advance_application']['amount'], '1000.00')

    def test_interrupted_refund_materialization_recovers_one_hold_and_uat_cannot_prepare(self):
        from .models import CollectionPostingRequest
        from .advance_refunds import movements
        from django.contrib.auth.models import Group
        detail, _ = self.refund_setup()
        refund = self.capture_refund(detail)
        review_source(source=refund, actor=self.validator, approve=True, reason='Independent review')
        request = refund.posting_requests.get()
        save = CollectionPostingRequest.save
        def interrupted(row, *args, **kwargs):
            if row.status == row.MATERIALIZED:
                raise RuntimeError('Interrupted source link')
            return save(row, *args, **kwargs)
        with patch.object(CollectionPostingRequest, 'save', interrupted), self.assertRaises(RuntimeError):
            materialize(request, self.preparer)
        entry, created = materialize(request, self.preparer)
        self.assertFalse(created)
        self.assertEqual(entry.subsidiary_lines.count(), 1)
        self.assertEqual(sum(value for day, value in movements(detail)), Decimal('400'))
        submit_entry(entry, self.preparer); post_entry(entry, self.validator); reconcile(entry, self.validator)
        self.treasury_user.groups.add(Group.objects.get_or_create(name='Finance UAT Viewer')[0])
        with self.assertRaises(PermissionDenied):
            self.capture_refund(detail, number='UAT')

    def test_web_refund_retains_printed_officer_source_and_unposted_withdrawal(self):
        from django.urls import reverse
        from accounting.services import discard_draft
        from .models import TreasuryCollectionSource
        from .collection_posting import withdraw_unposted
        from .advance_refunds import movements
        detail, _ = self.refund_setup()
        self.client.force_login(self.treasury_user)
        url = reverse('vouchers:collection_create')
        self.assertContains(self.client.get(url), 'Original officer advance')
        response = self.client.post(url, {'advance_detail': detail.pk, 'variant': self.transaction_variant.pk,
            'received_on': timezone.localdate().isoformat(), 'fund_code':'general-fund',
            'receipt_book':'WEB-REFUND', 'receipt_number':'001', 'payer_reference':'',
            'received_amount':'400', 'evidence_reference':'Synthetic officer money returned'})
        self.assertEqual(response.status_code, 302)
        refund = TreasuryCollectionSource.objects.get(book_reference='WEB-REFUND')
        self.assertEqual(refund.proposal['payer_reference'], detail.reference_label)
        self.post_refund_source(refund)
        self.treasury_user.user_permissions.add(Permission.objects.get(content_type__app_label='finance', codename='export_finance_work'))
        self.client.force_login(self.treasury_user)
        generated = self.client.post(reverse('vouchers:collection_output_generate', args=[refund.public_id]))
        self.assertEqual(generated.status_code, 302)
        content = self.client.get(generated.url).content
        self.assertIn(b'Officer advance cash refund', content)
        self.assertIn(detail.entry.reference.encode(), content)
        exported = self.client.get(reverse('vouchers:collection_export'))
        self.assertContains(exported, 'Original advance JEV')
        self.assertContains(exported, detail.entry.reference)
        pending = self.capture_refund(detail, amount='600', number='PENDING')
        review_source(source=pending, actor=self.validator, approve=True, reason='Independent receipt review')
        draft, _ = materialize(pending.posting_requests.get(), self.preparer)
        with self.assertRaises(ValidationError):
            withdraw_unposted(source=pending, actor=self.validator, reason='Incorrect unposted receipt')
        discard_draft(draft, self.preparer, reason='Incorrect draft')
        withdraw_unposted(source=pending, actor=self.validator, reason='Incorrect unposted receipt')
        self.assertEqual(sum(value for day, value in movements(detail)), Decimal('400'))
        self.assertEqual(self.client.get(generated.url).content, content)

    def refund_setup(self):
        detail, case, instrument = self.paid_advance()
        # Build synthetic setup as draft, then activate it; never edit operator setup.
        type(self.release).objects.filter(pk=self.release.pk).update(status='draft')
        self.release.refresh_from_db()
        self.transaction_variant.refresh_from_db()
        cash = LedgerAccount.objects.create(department_id=self.accounting.pk, department_label=self.accounting.name,
            code='REFUND-CASH', title='Synthetic Treasury cash', account_type='asset', normal_balance='debit')
        for code, actor in [('prepare_collections', self.treasury_user), ('prepare_collection_deposits', self.treasury_user),
                            ('review_collections', self.validator), ('view_collection_register', self.treasury_user)]:
            actor.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers', codename=code))
        for event, point in [(Rule.COLLECTION, Rule.COLLECTION_RECEIPT), (Rule.DEPOSIT, Rule.COLLECTION_DEPOSIT)]:
            rule = Rule.objects.create(variant=self.transaction_variant, code='refund-'+event, title='Synthetic refund '+event,
                event_kind=event, recognition_point=point, description='Synthetic reviewed advance refund',
                authority_reference='Synthetic local basis', created_by=self.preparer)
            specifications = [(Line.DEBIT, Line.FIXED_ACCOUNT, Line.EVENT_AMOUNT, cash.code, 'op_other_in'),
                (Line.CREDIT, Line.PRIOR_ADVANCE, Line.EVENT_AMOUNT, '', '')] if event == Rule.COLLECTION else [
                (Line.DEBIT, Line.BANK_MAPPING, Line.EVENT_AMOUNT, '', 'internal'),
                (Line.CREDIT, Line.ALLOCATION_ACCOUNTS, Line.EACH_ALLOCATION, '', 'internal')]
            for sequence, (side, account, amount, code, purpose) in enumerate(specifications, 1):
                row = Line(rule=rule, sequence=sequence, label='Synthetic refund line', side=side,
                    account_source=account, amount_source=amount, ledger_account_code=code, cash_flow_category=purpose)
                row.full_clean(); row.save()
        type(self.release).objects.filter(pk=self.release.pk).update(status='active')
        self.release.refresh_from_db()
        self.transaction_variant.refresh_from_db()
        return detail, cash

    def capture_refund(self, detail, amount='400', number='001', day=None):
        return record_receipt(actor=self.treasury_user, advance_detail=detail, variant=self.transaction_variant,
            received_on=day or timezone.localdate(), fund_code='general-fund', receipt_book='REFUND-BOOK', receipt_number=number,
            payer_reference='Not used to replace officer identity', received_amount=amount,
            evidence_reference='Synthetic actual officer cash return')

    def post_refund_source(self, source):
        review_source(source=source, actor=self.validator, approve=True, reason='Independent actual receipt review')
        entry, _ = materialize(source.posting_requests.get(), self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator)
        reconcile(entry, self.validator)
        source.refresh_from_db(); entry.refresh_from_db()
        return entry

    def test_refund_expense_deposit_and_exact_corrections_retain_original_advance(self):
        from .advance_applications import prepare, materialize as make_expense, reconcile as close_expense
        from .advance_refunds import movements
        from .collection_corrections import propose
        detail, cash = self.refund_setup()
        refund = self.capture_refund(detail)
        rule = self.liquidation_rule()
        def expense(value, key):
            return prepare(detail=detail, actor=self.preparer, rule=rule, day=timezone.localdate(),
                expenses=[{'account_code':'5-02-03', 'amount':value, 'document_reference':key}],
                evidence_reference=key, key=key)
        with self.assertRaisesMessage(ValidationError, 'exceeds the released'):
            expense('600.01', 'over')
        payment = self.post_refund_source(refund)
        self.assertEqual(payment.subsidiary_lines.get().credit, Decimal('400'))
        request = expense('600', 'expenses')
        entry, _ = make_expense(request, self.preparer)
        submit_entry(entry, self.preparer); post_entry(entry, self.validator); entry.refresh_from_db()
        close_expense(entry, self.validator)
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())[0]['balance'], 0)
        bank = FinanceConfigurationItem.objects.get(release=self.release, category='bank_account', code='gf-lbp')
        deposit = record_deposit(actor=self.treasury_user, variant=self.transaction_variant, deposited_on=timezone.localdate(),
            fund_code='general-fund', deposit_reference='REFUND-DEP', receiving_bank_id=bank.public_id,
            allocations=[{'receipt':str(refund.public_id), 'amount':'400'}], evidence_reference='Synthetic actual deposit')
        self.post_refund_source(deposit)
        lines = JournalLine.objects.filter(entry__status='posted', account=cash)
        self.assertEqual(sum(row.debit-row.credit for row in lines), 0)
        with self.assertRaisesMessage(ValidationError, 'allocated deposits'):
            propose(original=refund, actor=self.treasury_user, corrected_on=timezone.localdate(), reason='Wrong original receipt')
        correction = propose(original=deposit, actor=self.treasury_user, corrected_on=timezone.localdate(), reason='Wrong deposit')
        self.post_refund_source(correction)
        correction = propose(original=refund, actor=self.treasury_user, corrected_on=timezone.localdate(), reason='Wrong refund')
        reversal = self.post_refund_source(correction)
        self.assertEqual(reversal.reversal_of_id, payment.pk)
        self.assertEqual(reversal.subsidiary_lines.get().debit, Decimal('400'))
        self.assertEqual(sum(value for day, value in movements(detail)), 0)
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk, 'advance', timezone.localdate())[0]['balance'], Decimal('400'))
        self.assertEqual(payment.subsidiary_lines.get().credit, Decimal('400'))
        self.assertEqual(expense('400', 'remaining').payload['advance_application']['amount'], '400.00')
