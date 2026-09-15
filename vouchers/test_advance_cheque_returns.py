from datetime import date, datetime, timezone as utc
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.utils import timezone
from accounting.models import JournalEntry
from accounting.services import subsidiary_schedule_rows, submit_entry, post_entry
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line, FinanceTransactionVariant
from . import test_advance_cheques as fixtures
from .advance_applications import capacity, prepare
from .advance_refunds import movements, visible_originals
from .advance_cheques import settlement
from .cheque_returns import capture
from .cheque_redemptions import capture as redeem
from .collection_corrections import propose as correct
from .collection_posting import review_source, materialize, reconcile, withdraw_unposted
from .models import TreasuryCollectionSource as Source


class OfficerReturnTests(fixtures.OfficerChequeTests):
    def ready_return(self):
        with patch('django.utils.timezone.now',return_value=datetime(2026,9,11,3,tzinfo=utc.utc)):
            detail,cash = self.refund_setup()
        self.return_rules(cash)
        receipt = self.cheque(detail,received_on=date(2026,9,12))
        deposit = self.deposited(receipt)
        return detail,receipt,deposit

    def return_rules(self, cash):
        type(self.release).objects.filter(pk=self.release.pk).update(status='draft')
        self.release.refresh_from_db()
        self.transaction_variant.refresh_from_db()
        rule = Rule.objects.create(variant=self.transaction_variant,code='officer-return',title='Officer cheque bank return',
            event_kind=Rule.CHEQUE_RETURN,recognition_point=Rule.COLLECTION_RETURN,
            authority_reference='Synthetic reviewed original-advance treatment',created_by=self.preparer)
        for seq,side,account,purpose in [(1,Line.DEBIT,Line.PRIOR_ADVANCE,''),(2,Line.CREDIT,Line.BANK_MAPPING,'op_other_in')]:
            row=Line(rule=rule,sequence=seq,label='Synthetic officer return',side=side,account_source=account,
                amount_source=Line.EVENT_AMOUNT,cash_flow_category=purpose)
            row.full_clean(); row.save()
        self.redemption_type=FinanceTransactionVariant.objects.create(department=self.accounting,release=self.release,
            code='officer-redemption',label='Officer cheque principal replacement',kind='other',
            authority_reference='Synthetic reviewed original advance',effective_from=date(2026,1,1),status='active',created_by=self.preparer)
        rule=Rule.objects.create(variant=self.redemption_type,code='replacement',title='Officer principal replacement',
            event_kind=Rule.COLLECTION,recognition_point=Rule.COLLECTION_RECEIPT,
            authority_reference='Synthetic reviewed original receivable',created_by=self.preparer)
        for seq,side,account,code,purpose in [(1,Line.DEBIT,Line.FIXED_ACCOUNT,cash.code,'op_other_in'),
                (2,Line.CREDIT,Line.RETURN_RECEIVABLE,'','')]:
            row=Line(rule=rule,sequence=seq,label='Synthetic replacement',side=side,account_source=account,
                ledger_account_code=code,amount_source=Line.EVENT_AMOUNT,cash_flow_category=purpose)
            row.full_clean(); row.save()
        type(self.release).objects.filter(pk=self.release.pk).update(status='active')
        self.release.refresh_from_db(); self.transaction_variant.refresh_from_db(); self.redemption_type.refresh_from_db()

    def bank_return(self, receipt, deposit, **changes):
        values=dict(receipt=receipt,deposit=deposit,actor=self.treasury_user,variant=self.transaction_variant,
            debited_on=date(2026,9,13),debit_amount=receipt.amount,bank_reference='OFFICER-RETURN',
            reason='Actual bank dishonour',evidence_reference='Actual synthetic bank debit',
            applicability_reference='Independently reviewed original-officer advance treatment')
        values.update(changes)
        return capture(**values)

    def replacement(self, source, **changes):
        values=dict(original_return=source,actor=self.treasury_user,variant=self.redemption_type,
            received_on=date(2026,9,14),received_amount=source.amount,receipt_book='OFFICER-REPLACEMENT',receipt_number='001',
            evidence_reference='Actual replacement principal',old_receipt_disposition='surrendered',old_receipt_evidence='Original OR retained')
        values.update(changes)
        return redeem(**values)

    def test_return_restores_only_dated_posted_capacity_and_original_subsidiary(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit)
        self.assertIn('under review',settlement(receipt)['status'])
        with self.assertRaises(ValidationError): capacity(detail,date(2026,9,13),Decimal('601'))
        entry=self.post_refund_source(source)
        row=entry.subsidiary_lines.get()
        self.assertEqual((row.reference_key,row.journal_line.account_id,row.debit),
            (detail.reference_key,detail.journal_line.account_id,Decimal('400')))
        self.assertNotIn(row.pk,visible_originals(self.treasury_user).values_list('pk',flat=True))
        self.assertIn('original advance adjusted',settlement(receipt)['status'])
        capacity(detail,date(2026,9,13),Decimal('1000'))
        with self.assertRaises(ValidationError): capacity(detail,date(2026,9,12),Decimal('601'))
        self.assertEqual(movements(detail),[(date(2026,9,12),Decimal('400')),(date(2026,9,13),Decimal('-400'))])
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk,'advance',timezone.localdate())[0]['balance'],Decimal('1000'))

    def test_return_reconciliation_does_not_free_capacity_early(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit)
        review_source(source=source,actor=self.validator,approve=True,reason='Independent bank return')
        entry,_=materialize(source.posting_requests.get(),self.preparer)
        submit_entry(entry,self.preparer); post_entry(entry,self.validator)
        with self.assertRaises(ValidationError): capacity(detail,date(2026,9,13),Decimal('1000'))
        reconcile(entry,self.validator)
        capacity(detail,date(2026,9,13),Decimal('1000'))

    def test_cash_replacement_reuses_original_officer_and_reserves_once(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit); self.post_refund_source(source)
        replacement=self.replacement(source)
        with self.assertRaises(ValidationError): self.replacement(source,receipt_number='002')
        with self.assertRaises(ValidationError): capacity(detail,date(2026,9,14),Decimal('601'))
        entry=self.post_refund_source(replacement)
        self.assertEqual(entry.subsidiary_lines.get().reference_key,detail.reference_key)
        self.assertEqual(sum(value for day,value in movements(detail)),Decimal('400'))
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk,'advance',timezone.localdate())[0]['balance'],Decimal('600'))

    def test_source_error_correction_reserves_before_post_and_mirrors_officer(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit); self.post_refund_source(source)
        correction=correct(original=source,actor=self.treasury_user,corrected_on=date(2026,9,14),reason='Wrong bank debit attribution')
        with self.assertRaises(ValidationError): capacity(detail,date(2026,9,14),Decimal('601'))
        with self.assertRaises(ValidationError): capacity(detail,date(2026,9,13),Decimal('601'))
        entry=self.post_refund_source(correction)
        self.assertEqual(entry.subsidiary_lines.get().credit,Decimal('400'))
        self.assertEqual(sum(value for day,value in movements(detail)),Decimal('400'))
        source.refresh_from_db(); self.assertEqual(source.status,Source.CORRECTED)

    def test_return_correction_cannot_consume_a_later_expense_commitment(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit); self.post_refund_source(source)
        rule=self.liquidation_rule()
        prepare(detail=detail,actor=self.preparer,rule=rule,day=date(2026,9,15),
            expenses=[{'account_code':'5-02-03','amount':'700','document_reference':'Actual expenses'}],
            evidence_reference='Actual accepted expenses',key='later-expenses')
        with self.assertRaises(ValidationError):
            correct(original=source,actor=self.treasury_user,corrected_on=date(2026,9,14),reason='Wrong return')
        self.assertFalse(source.corrections.exists())

    def test_rejected_return_correction_releases_only_its_unposted_hold(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit); self.post_refund_source(source)
        correction=correct(original=source,actor=self.treasury_user,corrected_on=date(2026,9,14),reason='Wrong return')
        review_source(source=correction,actor=self.validator,approve=False,reason='The actual bank debit was correct')
        capacity(detail,date(2026,9,14),Decimal('1000'))
        self.assertEqual(sum(value for day,value in movements(detail)),Decimal('0'))

    def test_replacement_cheque_return_keeps_old_redemption_identity_occupied(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit); self.post_refund_source(source)
        replacement=self.replacement(source,cheque={'kind':'manager','bank':'Synthetic manager bank','drawer_account':'Manager account',
            'number':'MAN-001','drawer':'Synthetic bank','date':'2026-09-14'})
        # Give the second actual deposit its own reference.
        self.post_refund_source(replacement)
        from .collections import record_deposit
        from finance.models import FinanceConfigurationItem
        bank=FinanceConfigurationItem.objects.get(release=self.release,category='bank_account',code='gf-lbp')
        second_deposit=record_deposit(actor=self.treasury_user,variant=self.transaction_variant,deposited_on=date(2026,9,14),
            fund_code='general-fund',deposit_reference='REPLACEMENT-DEP',receiving_bank_id=bank.public_id,
            allocations=[{'receipt':str(replacement.public_id),'amount':'400'}],evidence_reference='Actual replacement deposit')
        self.post_refund_source(second_deposit)
        second_return=self.bank_return(replacement,second_deposit,debited_on=date(2026,9,15),bank_reference='SECOND-RETURN')
        self.post_refund_source(second_return)
        capacity(detail,date(2026,9,15),Decimal('1000'))
        with self.assertRaises(ValidationError): self.replacement(source,received_on=date(2026,9,15),receipt_number='reuse-old')
        fresh=self.replacement(second_return,received_on=date(2026,9,15),receipt_number='second-principal')
        self.assertEqual(fresh.proposal['advance_refund']['original_detail'],detail.pk)

    def test_changed_officer_subsidiary_cannot_be_submitted(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit)
        review_source(source=source,actor=self.validator,approve=True,reason='Actual bank debit')
        entry,_=materialize(source.posting_requests.get(),self.preparer)
        entry.subsidiary_lines.update(reference_key='finance-party:another-officer')
        with self.assertRaises(ValidationError): submit_entry(entry,self.preparer)
        self.assertEqual(JournalEntry.objects.get(pk=entry.pk).status,JournalEntry.DRAFT)

    def test_fixed_counterpart_cannot_replace_selected_original_advance_instruction(self):
        detail,receipt,deposit=self.ready_return()
        rule=Rule.objects.get(variant=self.transaction_variant,event_kind=Rule.CHEQUE_RETURN)
        rule.lines.filter(side=Line.DEBIT).update(account_source=Line.FIXED_ACCOUNT,ledger_account_code=detail.journal_line.account.code)
        with self.assertRaisesMessage(ValidationError,'selected-original-advance debit'):
            self.bank_return(receipt,deposit)
        self.assertFalse(Source.objects.filter(kind=Source.CHEQUE_RETURN).exists())


    def test_return_and_correction_outputs_retain_original_officer(self):
        import csv
        import io
        from django.contrib.auth.models import Permission
        from django.urls import reverse
        from .collection_outputs import generate,content
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit); self.post_refund_source(source)
        self.treasury_user.user_permissions.add(Permission.objects.get(content_type__app_label='finance',codename='export_finance_work'))
        output=generate(source=source,actor=self.treasury_user)
        frozen=content(output,self.treasury_user)
        self.assertIn(b'Officer cheque bank-return adjustment',frozen)
        self.assertIn(detail.entry.reference.encode(),frozen)
        correction=correct(original=source,actor=self.treasury_user,corrected_on=date(2026,9,14),reason='Mistaken bank debit reference')
        self.post_refund_source(correction)
        corrected=content(generate(source=correction,actor=self.treasury_user),self.treasury_user)
        self.assertIn(b'Officer cheque bank-return correction',corrected)
        self.assertIn(detail.entry.reference.encode(),corrected)
        self.assertEqual(content(output,self.treasury_user),frozen)
        self.client.force_login(self.treasury_user)
        response=self.client.get(reverse('vouchers:collection_export'))
        self.assertEqual(response.status_code,200)
        rows=list(csv.DictReader(io.StringIO(response.content.decode('utf-8'))))
        selected=[row for row in rows if row['Reference'] in {source.document_reference,correction.document_reference}]
        self.assertEqual(len(selected),2)
        self.assertTrue(all(row['Original advance JEV'] == detail.entry.reference for row in selected))
        self.assertTrue(all(row['Officer advance identity'] == detail.reference_key for row in selected))


class OfficerReturnConcurrencyTests(fixtures.OfficerChequeConcurrencyTests):
    ready_return=OfficerReturnTests.ready_return
    return_rules=OfficerReturnTests.return_rules
    bank_return=OfficerReturnTests.bank_return
    replacement=OfficerReturnTests.replacement

    def test_return_correction_and_expense_cannot_reserve_the_same_restored_amount(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit); self.post_refund_source(source)
        rule=self.liquidation_rule()
        def compete(number):
            if number == 1:
                correct(original=source,actor=self.treasury_user,corrected_on=date(2026,9,14),reason='Wrong return attribution')
            else:
                prepare(detail=detail,actor=self.preparer,rule=rule,day=date(2026,9,14),
                    expenses=[{'account_code':'5-02-03','amount':'700','document_reference':'RACE'}],
                    evidence_reference='Actual expense',key='return-correction-expense')
            return 'accepted'
        results=self.race(compete)
        self.assertEqual(results.count('accepted'),1,results)

    def test_replacement_and_expense_share_original_case_capacity(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit); self.post_refund_source(source)
        rule=self.liquidation_rule()
        def compete(number):
            if number == 1:
                self.replacement(source)
            else:
                prepare(detail=detail,actor=self.preparer,rule=rule,day=date(2026,9,14),
                    expenses=[{'account_code':'5-02-03','amount':'700','document_reference':'RACE'}],
                    evidence_reference='Actual expense',key='replacement-expense')
            return 'accepted'
        results=self.race(compete)
        self.assertEqual(results.count('accepted'),1,results)

    def test_return_post_recovery_and_expense_follow_case_before_finance_locks(self):
        detail,receipt,deposit=self.ready_return()
        source=self.bank_return(receipt,deposit)
        review_source(source=source,actor=self.validator,approve=True,reason='Actual bank debit')
        entry,_=materialize(source.posting_requests.get(),self.preparer)
        submit_entry(entry,self.preparer); post_entry(entry,self.validator)
        rule=self.liquidation_rule()
        def compete(number):
            if number == 1:
                reconcile(JournalEntry.objects.get(pk=entry.pk),self.validator)
                return 'reconciled'
            prepare(detail=detail,actor=self.preparer,rule=rule,day=date(2026,9,14),
                expenses=[{'account_code':'5-02-03','amount':'700','document_reference':'RACE'}],
                evidence_reference='Actual expense',key='return-recovery-expense')
            return 'accepted'
        results=self.race(compete)
        self.assertIn('reconciled',results)
        self.assertTrue(any(item == 'accepted' or 'exceeds the released' in item for item in results),results)
