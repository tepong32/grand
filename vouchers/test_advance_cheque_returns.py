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
    def assessed_charge_setup(self, cash, *, suffix='', purpose='op_services', account_type='revenue'):
        from accounting.models import LedgerAccount
        owner = {'department_id':self.accounting.pk,'department_label':self.accounting.name}
        revenue = LedgerAccount.objects.create(**owner,code='OFFICER-FEE'+suffix,title='Synthetic assessed charge',
            account_type=account_type,normal_balance='credit')
        debtor = LedgerAccount.objects.create(**owner,code='OFFICER-FEE-DUE'+suffix,title='Synthetic returned charge receivable',
            account_type='asset',normal_balance='debit')
        type(self.release).objects.filter(pk=self.release.pk).update(status='draft')
        self.release.refresh_from_db()
        variant = FinanceTransactionVariant.objects.create(department=self.accounting,release=self.release,
            code='officer-assessed-charge'+suffix,label='Explicit assessed charge',kind='other',
            authority_reference='Synthetic applicable assessment authority',effective_from=date(2026,1,1),status='active',created_by=self.preparer)
        for event,point,target in ((Rule.COLLECTION,Rule.COLLECTION_RECEIPT,revenue),
                (Rule.CHEQUE_RETURN,Rule.COLLECTION_RETURN,debtor)):
            rule = Rule.objects.create(variant=variant,code=event,title='Synthetic assessed component',
                event_kind=event,recognition_point=point,authority_reference='Synthetic reviewed component treatment',created_by=self.preparer)
            specs = [(Line.DEBIT,Line.FIXED_ACCOUNT,cash.code,purpose),
                (Line.CREDIT,Line.FIXED_ACCOUNT,target.code,'')] if event == Rule.COLLECTION else [
                (Line.DEBIT,Line.FIXED_ACCOUNT,target.code,''),(Line.CREDIT,Line.BANK_MAPPING,'',purpose)]
            for sequence,(side,account,code,row_purpose) in enumerate(specs,1):
                row = Line(rule=rule,sequence=sequence,label='Synthetic explicit component',side=side,
                    account_source=account,ledger_account_code=code,cash_flow_category=row_purpose,amount_source=Line.EVENT_AMOUNT)
                row.full_clean();row.save()
        type(self.release).objects.filter(pk=self.release.pk).update(status='active');self.release.refresh_from_db()
        charge = {'variant':str(variant.public_id),'amount':'25',
            'authority_reference':'Synthetic approved applicable ordinance reference',
            'assessment_reference':'Synthetic actual fixed assessment25; not an inferred rate'}
        return variant, charge, revenue, debtor

    def test_assessed_officer_redemption_reserves_and_posts_only_original_principal(self):
        from accounting.models import JournalSubsidiaryLine,LedgerAccount
        detail, receipt, deposit = self.ready_return()
        cash = LedgerAccount.objects.get(pk=receipt.proposal['cash_account_id'])
        _, charge, revenue, _ = self.assessed_charge_setup(cash)
        source = self.bank_return(receipt,deposit); self.post_refund_source(source)
        try:
            replacement = self.replacement(source,received_amount='425',charges=[charge])
        except ValidationError as exc:
            self.fail(f'Explicit reviewed assessed-charge redemption was rejected: {exc}')
        self.assertEqual(replacement.amount,Decimal('425'))
        self.assertEqual(Decimal(replacement.proposal['advance_refund']['amount']),Decimal('400'))
        self.assertEqual(sum(value for _,value in movements(detail)),Decimal('400'))
        capacity(detail,date(2026,9,14),Decimal('600'))
        with self.assertRaises(ValidationError):capacity(detail,date(2026,9,14),Decimal('600.01'))
        entry = self.post_refund_source(replacement)
        self.assertEqual(set(entry.lines.filter(account=cash).values_list('cash_flow_category','debit')),
            {('op_other_in',Decimal('400')),('op_services',Decimal('25'))})
        self.assertEqual(entry.lines.get(account=revenue).credit,Decimal('25'))
        subsidiary = entry.subsidiary_lines.get(category=JournalSubsidiaryLine.ADVANCE)
        self.assertEqual((subsidiary.journal_line.account_id,subsidiary.credit),
            (detail.journal_line.account_id,Decimal('400')))
        self.assertEqual(subsidiary_schedule_rows(self.accounting.pk,'advance',timezone.localdate())[0]['balance'],Decimal('600'))

    def ready_return(self):
        with patch('django.utils.timezone.now',return_value=datetime(2026,9,11,3,tzinfo=utc.utc)):
            detail,cash = self.refund_setup()
        self.return_rules(cash)
        receipt = self.cheque(detail,received_on=date(2026,9,12))
        deposit = self.deposited(receipt)
        return detail,receipt,deposit

    def assessed_replacement(self, *, cheque=False, purpose='op_services'):
        from accounting.models import LedgerAccount
        detail, receipt, deposit = self.ready_return()
        cash = LedgerAccount.objects.get(pk=receipt.proposal['cash_account_id'])
        variant, charge, revenue, debtor = self.assessed_charge_setup(cash)
        variant.posting_rules.get(event_kind=Rule.COLLECTION).lines.filter(side=Line.DEBIT).update(cash_flow_category=purpose)
        variant.posting_rules.get(event_kind=Rule.CHEQUE_RETURN).lines.filter(side=Line.CREDIT).update(cash_flow_category=purpose)
        returned = self.bank_return(receipt,deposit);self.post_refund_source(returned)
        changes = {'cheque':{'kind':'manager','bank':'Synthetic bank','drawer_account':'Manager account',
            'number':'ASSESSED-001','drawer':'Synthetic bank','date':'2026-09-14'}} if cheque else {}
        replacement = self.replacement(returned,received_amount='425',charges=[charge],**changes)
        return detail,returned,replacement,variant,charge,revenue,debtor

    def replacement_deposit(self, receipt, *, reference='ASSESSED-DEP', value=None):
        from .collections import record_deposit
        from finance.models import FinanceConfigurationItem
        bank = FinanceConfigurationItem.objects.get(release=self.release,category='bank_account',code='gf-lbp')
        return record_deposit(actor=self.treasury_user,variant=self.transaction_variant,deposited_on=receipt.source_date,
            fund_code='general-fund',deposit_reference=reference,receiving_bank_id=bank.public_id,
            allocations=[{'receipt':str(receipt.public_id),'amount':str(receipt.amount if value is None else value)}],
            evidence_reference='Actual whole combined cheque deposit')

    def mixed_redemption_type(self, cash):
        from .cheque_components import COMPONENT_AMOUNT
        type(self.release).objects.filter(pk=self.release.pk).update(status='draft');self.release.refresh_from_db()
        variant = FinanceTransactionVariant.objects.create(department=self.accounting,release=self.release,
            code='officer-mixed-replacement',label='Whole officer and charge replacement',kind='other',
            authority_reference='Synthetic reviewed original cash components',effective_from=date(2026,1,1),status='active',created_by=self.preparer)
        rule = Rule.objects.create(variant=variant,code='mixed-replacement',title='Whole exact original components',
            event_kind=Rule.COLLECTION,recognition_point=Rule.COLLECTION_RECEIPT,
            authority_reference='Synthetic reviewed original counterpart settlement',created_by=self.preparer)
        for sequence,purpose in enumerate(('op_other_in','op_services'),1):
            row = Line(rule=rule,sequence=sequence,label='Original purpose',side=Line.DEBIT,
                account_source=Line.FIXED_ACCOUNT,ledger_account_code=cash.code,
                cash_flow_category=purpose,amount_source=COMPONENT_AMOUNT)
            row.full_clean();row.save()
        row = Line(rule=rule,sequence=3,label='Original receivables',side=Line.CREDIT,
            account_source=Line.RETURN_RECEIVABLE,amount_source=Line.EVENT_AMOUNT)
        row.full_clean();row.save()
        type(self.release).objects.filter(pk=self.release.pk).update(status='active');self.release.refresh_from_db()
        return variant

    def assessed_return(self, receipt, deposit, variant, **changes):
        values = {'debited_on':date(2026,9,15),'bank_reference':'ASSESSED-RETURN',
            'charge_treatments':[{'purpose':'op_services','variant':str(variant.public_id)}]}
        values.update(changes)
        return self.bank_return(receipt,deposit,**values)

    def test_combined_officer_cheque_deposits_whole_total_and_clears_independently(self):
        from . import cheque_clearing as clearing
        detail,_,receipt,_,_,_,_ = self.assessed_replacement(cheque=True)
        self.post_refund_source(receipt)
        with self.assertRaises(ValidationError):self.replacement_deposit(receipt,value='400')
        self.assertFalse(Source.objects.filter(kind=Source.DEPOSIT,document_reference='ASSESSED-DEP').exists())
        deposit = self.replacement_deposit(receipt);self.post_refund_source(deposit)
        self.assertEqual(deposit.amount,Decimal('425'))
        self.assertIn('clearing pending',settlement(receipt)['status'])
        before = JournalEntry.objects.count()
        clearance = clearing.propose(receipt=receipt,deposit=deposit,actor=self.treasury_user,
            cleared_on=date(2026,9,14),bank_reference='ACTUAL-CLEAR',evidence_reference='Actual bank confirmation')
        self.assertIn('clearing pending',settlement(receipt)['status'])
        clearing.review(clearance=clearance,actor=self.validator,approve=True,reason='Independent confirmation')
        self.assertIn('clearing confirmed',settlement(receipt)['status'])
        self.assertEqual(JournalEntry.objects.count(),before)
        self.assertEqual(sum(value for _,value in movements(detail)),Decimal('400'))

    def test_combined_officer_return_and_successor_settle_exact_counterparts_without_duplicate_revenue(self):
        from accounting.models import LedgerAccount
        detail,first,receipt,variant,charge,revenue,debtor = self.assessed_replacement(cheque=True)
        self.post_refund_source(receipt)
        deposit = self.replacement_deposit(receipt);self.post_refund_source(deposit)
        returned = self.assessed_return(receipt,deposit,variant)
        with self.assertRaises(ValidationError):capacity(detail,date(2026,9,15),Decimal('601'))
        entry = self.post_refund_source(returned)
        self.assertEqual(entry.lines.get(account=detail.journal_line.account).debit,Decimal('400'))
        self.assertEqual(entry.lines.get(account=debtor).debit,Decimal('25'))
        self.assertEqual(sum(row.credit for row in entry.lines.all()),Decimal('425'))
        self.assertEqual(entry.subsidiary_lines.get().debit,Decimal('400'))
        capacity(detail,date(2026,9,15),Decimal('1000'))
        with self.assertRaises(ValidationError):self.replacement(first,receipt_number='OLD-REUSE')
        mixed = self.mixed_redemption_type(LedgerAccount.objects.get(pk=receipt.proposal['cash_account_id']))
        successor = self.replacement(returned,variant=mixed,received_on=date(2026,9,16),receipt_number='SUCCESSOR',
            received_amount='450',charges=[charge],cheque={'kind':'cashier','bank':'Synthetic bank','drawer_account':'Cashier',
            'number':'ASSESSED-002','drawer':'Synthetic bank','date':'2026-09-16'})
        second_entry = self.post_refund_source(successor)
        self.assertEqual(second_entry.lines.get(account=detail.journal_line.account).credit,Decimal('400'))
        self.assertEqual(second_entry.lines.get(account=debtor).credit,Decimal('25'))
        self.assertEqual(second_entry.lines.get(account=revenue).credit,Decimal('25'))
        second_deposit = self.replacement_deposit(successor,reference='ASSESSED-DEP2');self.post_refund_source(second_deposit)
        second_return = self.assessed_return(successor,second_deposit,variant,debited_on=date(2026,9,17),bank_reference='ASSESSED-RETURN2')
        last = self.post_refund_source(second_return)
        self.assertEqual(last.lines.get(account=detail.journal_line.account).debit,Decimal('400'))
        self.assertEqual(last.lines.get(account=debtor).debit,Decimal('50'))
        self.assertEqual(last.subsidiary_lines.get().debit,Decimal('400'))
        self.assertEqual(sum(value for _,value in movements(detail)),Decimal('0'))
        self.assertEqual(sum(row.credit for row in last.lines.all()),Decimal('450'))

    def test_fee_sharing_officer_cash_purpose_still_has_separate_advance_amount(self):
        detail,_,receipt,variant,_,_,debtor = self.assessed_replacement(cheque=True,purpose='op_other_in')
        self.post_refund_source(receipt)
        deposit = self.replacement_deposit(receipt);self.post_refund_source(deposit)
        returned = self.assessed_return(receipt,deposit,variant,
            charge_treatments=[{'purpose':'op_other_in','variant':str(variant.public_id)}])
        entry = self.post_refund_source(returned)
        self.assertEqual(entry.lines.get(account=debtor).debit,Decimal('25'))
        self.assertEqual(entry.lines.get(account=detail.journal_line.account).debit,Decimal('400'))
        self.assertEqual(entry.lines.get(credit__gt=0).credit,Decimal('425'))
        next_receipt = self.replacement(returned,received_on=date(2026,9,16),receipt_number='SAME-PURPOSE')
        next_entry = self.post_refund_source(next_receipt)
        self.assertEqual(next_entry.lines.get(account=debtor).credit,Decimal('25'))
        self.assertEqual(next_entry.subsidiary_lines.get().credit,Decimal('400'))

    def test_component_return_rejects_missing_duplicate_wrong_amount_and_advance_account(self):
        detail,_,receipt,variant,_,_,_ = self.assessed_replacement(cheque=True)
        self.post_refund_source(receipt)
        deposit = self.replacement_deposit(receipt);self.post_refund_source(deposit)
        choice = {'purpose':'op_services','variant':str(variant.public_id)}
        for choices in ([],[choice,choice],[dict(choice,purpose='op_other_in')],
                [dict(choice,amount='24.99')],[dict(choice,variant='not-an-identity')]):
            with self.subTest(choices=choices),self.assertRaises(ValidationError):
                self.assessed_return(receipt,deposit,variant,charge_treatments=choices)
        self.assertFalse(receipt.cheque_returns.exists())
        debit = variant.posting_rules.get(event_kind=Rule.CHEQUE_RETURN).lines.get(side=Line.DEBIT)
        debit.ledger_account_code = detail.journal_line.account.code;debit.save(update_fields=['ledger_account_code'])
        with self.assertRaisesMessage(ValidationError,'cannot increase the original officer advance'):
            self.assessed_return(receipt,deposit,variant)
        self.assertFalse(receipt.cheque_returns.exists())

    def test_charge_return_recipe_is_current_at_review_and_pinned_for_posting(self):
        _,_,receipt,variant,_,_,debtor = self.assessed_replacement(cheque=True)
        self.post_refund_source(receipt)
        deposit = self.replacement_deposit(receipt);self.post_refund_source(deposit)
        returned = self.assessed_return(receipt,deposit,variant)
        rule = variant.posting_rules.get(event_kind=Rule.CHEQUE_RETURN)
        original = rule.authority_reference
        Rule.objects.filter(pk=rule.pk).update(authority_reference='Changed after capture')
        with self.assertRaisesMessage(ValidationError,'component return recipe changed'):
            review_source(source=returned,actor=self.validator,approve=True,reason='Stale recipe')
        Rule.objects.filter(pk=rule.pk).update(authority_reference=original)
        review_source(source=returned,actor=self.validator,approve=True,reason='Current exact charge treatment')
        Rule.objects.filter(pk=rule.pk).update(authority_reference='Changed after independent approval')
        entry,_ = materialize(returned.posting_requests.get(),self.preparer)
        submit_entry(entry,self.preparer);post_entry(entry,self.validator);reconcile(entry,self.validator)
        self.assertEqual(entry.lines.get(account=debtor).debit,Decimal('25'))

    def test_whole_receipt_correction_releases_only_principal_after_reconciliation(self):
        detail,returned,receipt,_,_,revenue,_ = self.assessed_replacement()
        original = self.post_refund_source(receipt)
        correction = correct(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,16),reason='Wrong actual replacement receipt')
        self.assertEqual(correction.amount,Decimal('425'))
        review_source(source=correction,actor=self.validator,approve=True,reason='Independent source correction')
        entry,_ = materialize(correction.posting_requests.get(),self.preparer)
        submit_entry(entry,self.preparer);post_entry(entry,self.validator)
        with self.assertRaises(ValidationError):self.replacement(returned,receipt_number='PREMATURE')
        with self.assertRaises(ValidationError):capacity(detail,date(2026,9,16),Decimal('601'))
        reconcile(entry,self.validator)
        self.assertEqual(entry.subsidiary_lines.get().debit,Decimal('400'))
        self.assertEqual(entry.lines.get(account=revenue).debit,Decimal('25'))
        self.assertEqual(sorted((r.account_id,r.debit,r.credit,r.cash_flow_category) for r in entry.lines.all()),
            sorted((r.account_id,r.credit,r.debit,r.cash_flow_category) for r in original.lines.all()))
        capacity(detail,date(2026,9,16),Decimal('1000'))
        with self.assertRaises(ValidationError):capacity(detail,date(2026,9,15),Decimal('601'))
        successor = self.replacement(returned,received_on=date(2026,9,16),receipt_number='AFTER-CORRECTION')
        self.assertEqual(successor.amount,Decimal('400'))

    def test_combined_bank_return_correction_restores_principal_hold_not_whole_total(self):
        detail,_,receipt,variant,_,_,debtor = self.assessed_replacement(cheque=True)
        self.post_refund_source(receipt)
        deposit = self.replacement_deposit(receipt);self.post_refund_source(deposit)
        returned = self.assessed_return(receipt,deposit,variant);original = self.post_refund_source(returned)
        correction = correct(original=returned,actor=self.treasury_user,corrected_on=date(2026,9,16),reason='Misattributed whole bank debit')
        capacity(detail,date(2026,9,16),Decimal('600'))
        with self.assertRaises(ValidationError):capacity(detail,date(2026,9,16),Decimal('600.01'))
        entry = self.post_refund_source(correction)
        self.assertEqual(entry.lines.get(account=debtor).credit,Decimal('25'))
        self.assertEqual(entry.subsidiary_lines.get().credit,Decimal('400'))
        self.assertEqual(sum(r.debit for r in entry.lines.all()),Decimal('425'))
        self.assertEqual(entry.reversal_of_id,original.pk)
        self.assertEqual(sum(value for _,value in movements(detail)),Decimal('400'))

    def test_combined_materialization_recovery_keeps_one_principal_hold_and_exact_charge(self):
        from .models import CollectionPostingRequest
        detail,_,receipt,_,_,revenue,_ = self.assessed_replacement()
        review_source(source=receipt,actor=self.validator,approve=True,reason='Independent explicit assessment')
        request = receipt.posting_requests.get();save = CollectionPostingRequest.save
        def interrupted(row,*args,**kwargs):
            if row.status == row.MATERIALIZED:raise RuntimeError('Interrupted source link')
            return save(row,*args,**kwargs)
        with patch.object(CollectionPostingRequest,'save',interrupted),self.assertRaises(RuntimeError):materialize(request,self.preparer)
        entry,created = materialize(request,self.preparer)
        self.assertFalse(created)
        self.assertEqual(entry.lines.get(account=revenue).credit,Decimal('25'))
        self.assertEqual(entry.subsidiary_lines.get().credit,Decimal('400'))
        self.assertEqual(sum(value for _,value in movements(detail)),Decimal('400'))
        submit_entry(entry,self.preparer);post_entry(entry,self.validator);reconcile(entry,self.validator)

    def test_combined_principal_tampering_blocks_review(self):
        from copy import deepcopy
        from .remittances import _digest
        _,_,receipt,_,_,_,_ = self.assessed_replacement()
        original = deepcopy(receipt.proposal)
        for value in ('399.00','425.00'):
            changed = deepcopy(original);changed['officer_components']['amount'] = value
            Source.objects.filter(pk=receipt.pk).update(proposal=changed,proposal_checksum=_digest(changed))
            with self.subTest(value=value),self.assertRaises(ValidationError):
                review_source(source=receipt,actor=self.validator,approve=True,reason='Tampered component')
        Source.objects.filter(pk=receipt.pk).update(proposal=original,proposal_checksum=_digest(original))
        self.post_refund_source(receipt)

    def test_multiple_charge_purposes_retain_separate_receivables_and_one_officer_subsidiary(self):
        from accounting.models import LedgerAccount
        detail,receipt,deposit = self.ready_return()
        cash = LedgerAccount.objects.get(pk=receipt.proposal['cash_account_id'])
        first,charge,_,first_debtor = self.assessed_charge_setup(cash)
        second,other,liability,second_debtor = self.assessed_charge_setup(cash,suffix='-2',purpose='op_taxes',account_type='liability')
        other['amount'] = '20'
        original = self.bank_return(receipt,deposit);self.post_refund_source(original)
        replacement = self.replacement(original,received_amount='445',charges=[charge,other],
            cheque={'kind':'cashier','bank':'Bank','drawer_account':'Account','number':'MULTI-FEE','drawer':'Bank','date':'2026-09-14'})
        entry = self.post_refund_source(replacement)
        self.assertEqual(entry.lines.get(account=liability).credit,Decimal('20'))
        second_deposit = self.replacement_deposit(replacement);self.post_refund_source(second_deposit)
        returned = self.assessed_return(replacement,second_deposit,first,charge_treatments=[
            {'purpose':'op_services','variant':str(first.public_id)}, {'purpose':'op_taxes','variant':str(second.public_id)}])
        entry = self.post_refund_source(returned)
        self.assertEqual(entry.lines.get(account=first_debtor).debit,Decimal('25'))
        self.assertEqual(entry.lines.get(account=second_debtor).debit,Decimal('20'))
        self.assertEqual(entry.subsidiary_lines.get().debit,Decimal('400'))
        self.assertEqual(set(entry.lines.filter(credit__gt=0).values_list('cash_flow_category','credit')),
            {('op_other_in',Decimal('400')),('op_services',Decimal('25')),('op_taxes',Decimal('20'))})
        self.assertEqual(sum(value for _,value in movements(detail)),Decimal('0'))

    def test_successor_cannot_reassign_exact_original_return_debit_evidence(self):
        from accounting.models import LedgerAccount
        from copy import deepcopy
        from .remittances import _digest
        _,_,receipt,variant,_,_,debtor = self.assessed_replacement(cheque=True)
        self.post_refund_source(receipt)
        deposit = self.replacement_deposit(receipt);self.post_refund_source(deposit)
        returned = self.assessed_return(receipt,deposit,variant);self.post_refund_source(returned)
        mixed = self.mixed_redemption_type(LedgerAccount.objects.get(pk=receipt.proposal['cash_account_id']))
        successor = self.replacement(returned,variant=mixed,received_on=date(2026,9,16),receipt_number='EXACT-LINKS')
        original = deepcopy(successor.proposal)
        changed = deepcopy(original)
        changed['redemption']['return_debits'][1]['line'] = changed['redemption']['return_debits'][0]['line']
        Source.objects.filter(pk=successor.pk).update(proposal=changed,proposal_checksum=_digest(changed))
        with self.assertRaises(ValidationError):review_source(source=successor,actor=self.validator,approve=True,reason='Duplicate counterpart')
        Source.objects.filter(pk=successor.pk).update(proposal=original,proposal_checksum=_digest(original))
        review_source(source=successor,actor=self.validator,approve=True,reason='Exact original counterparts')
        entry,_ = materialize(successor.posting_requests.get(),self.preparer)
        entry.lines.filter(account=debtor).update(credit=Decimal('24'))
        with self.assertRaises(ValidationError):submit_entry(entry,self.preparer)
        self.assertEqual(JournalEntry.objects.get(pk=entry.pk).status,JournalEntry.DRAFT)

    def test_corrected_history_retains_whole_combined_receipt_for_original_correction(self):
        from .advance_corrected_refunds import evidence
        detail,returned,receipt,_,_,_,_ = self.assessed_replacement()
        self.post_refund_source(receipt)
        self.post_refund_source(correct(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,16),reason='Wrong replacement'))
        self.post_refund_source(correct(original=returned,actor=self.treasury_user,corrected_on=date(2026,9,16),reason='Wrong bank attribution'))
        for source in (returned.return_deposit,returned.return_receipt):
            self.post_refund_source(correct(original=source,actor=self.treasury_user,corrected_on=date(2026,9,16),reason='Correct actual original refund history'))
        retained = evidence(detail,date(2026,9,16))
        self.assertEqual(len(retained),2)
        pair = next(row['receipt'] for row in retained if row['receipt']['original']['source'] == str(receipt.public_id))
        self.assertEqual(Decimal(pair['original']['amount']),Decimal('425'))
        self.assertEqual(Decimal(pair['correction']['amount']),Decimal('425'))
        evidence(detail,date(2026,9,16),retained=retained)
        Source.objects.filter(pk=receipt.pk).update(review_reason='Altered independently reviewed receipt')
        with self.assertRaises(ValidationError):evidence(detail,date(2026,9,16),retained=retained)
        Source.objects.filter(pk=receipt.pk).update(review_reason=receipt.review_reason)
        entry = JournalEntry.objects.get(public_id=returned.posting_requests.get().accounting_entry_public_id)
        entry.lines.filter(debit__gt=0).update(account_id=receipt.proposal['cash_account_id'])
        with self.assertRaises(ValidationError):evidence(detail,date(2026,9,16))

    def test_retirement_flag_without_exact_reconciled_correction_cannot_validate_history(self):
        from .collection_posting import validate_collection_journal
        _,_,receipt,_,_,_,_ = self.assessed_replacement()
        entry = self.post_refund_source(receipt)
        Source.objects.filter(pk=receipt.pk).update(redemption_active=False)
        with self.assertRaisesMessage(ValidationError,'exactly corrected, reconciled receipt'):
            validate_collection_journal(entry)

    def test_authenticated_combined_entry_return_components_and_immutable_copies(self):
        from accounting.models import LedgerAccount
        from django.contrib.auth.models import Group,Permission
        from django.urls import reverse
        from .collection_outputs import generate,content
        detail,receipt,deposit = self.ready_return()
        variant,charge,_,debtor = self.assessed_charge_setup(LedgerAccount.objects.get(pk=receipt.proposal['cash_account_id']))
        returned = self.bank_return(receipt,deposit);self.post_refund_source(returned)
        self.client.force_login(self.treasury_user)
        url = reverse('vouchers:cheque_redemption_create',args=[returned.public_id])
        self.assertContains(self.client.get(url),'Only this original amount applies to the officer advance')
        values = {'variant':self.redemption_type.pk,'received_on':'2026-09-14','received_amount':'400',
            'receipt_book':'HTTP-ASSESSED','receipt_number':'001','evidence_reference':'Actual cheque425',
            'old_receipt_disposition':'surrendered','old_receipt_evidence':'Original OR surrendered',
            'method':'manager','cheque_bank':'Bank','cheque_drawer_account':'Account','cheque_number':'HTTP-ASSESSED',
            'cheque_drawer':'Bank','cheque_date':'2026-09-14',
            'charges-TOTAL_FORMS':'1','charges-INITIAL_FORMS':'0','charges-0-variant':str(variant.public_id),
            **{'charges-0-'+key:charge[key] for key in ('amount','authority_reference','assessment_reference')}}
        self.assertContains(self.client.post(url,values),'total actually received must equal')
        self.assertFalse(returned.redemption_receipts.exists())
        values['received_amount'] = '425'
        response = self.client.post(url,values)
        self.assertEqual(response.status_code,302,response.context['form'].errors if response.status_code == 200 else '')
        replacement = returned.redemption_receipts.get();self.post_refund_source(replacement)
        self.treasury_user.user_permissions.add(Permission.objects.get(content_type__app_label='finance',codename='export_finance_work'))
        output = generate(source=replacement,actor=self.treasury_user);frozen = content(output,self.treasury_user)
        self.assertIn(b'Officer principal component',frozen)
        self.assertIn(b'425.00',frozen);self.assertIn(b'400.00',frozen)
        deposited = self.replacement_deposit(replacement);self.post_refund_source(deposited)
        url = reverse('vouchers:cheque_return_create',args=[replacement.public_id])
        self.assertContains(self.client.get(url),'Returned charge components')
        values = {'deposit':deposited.pk,'variant':self.transaction_variant.pk,'debited_on':'2026-09-15',
            'debit_amount':'425','bank_reference':'HTTP-FEE-RETURN','reason':'Actual dishonour',
            'evidence_reference':'Actual whole bank debit425','applicability_reference':'Reviewed officer and fee return treatments'}
        self.assertEqual(self.client.post(url,values).status_code,200)
        self.assertFalse(replacement.cheque_returns.exists())
        values.update({'components-TOTAL_FORMS':'1','components-INITIAL_FORMS':'1',
            'components-0-purpose':'op_other_in','components-0-variant':str(variant.public_id)})
        self.assertEqual(self.client.post(url,values).status_code,302)
        bank_return = replacement.cheque_returns.get()
        self.assertEqual(bank_return.proposal['officer_charge_returns'][0]['purpose'],'op_services')
        entry = self.post_refund_source(bank_return)
        self.assertEqual(entry.lines.get(account=debtor).debit,Decimal('25'))
        self.assertEqual(content(output,self.treasury_user),frozen)
        self.assertIn(b'Returned charge receivables',content(generate(source=bank_return,actor=self.treasury_user),self.treasury_user))
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.post(url,values).status_code,403)
        self.treasury_user.groups.add(Group.objects.get_or_create(name='Finance UAT Viewer')[0])
        self.client.force_login(self.treasury_user)
        self.assertEqual(self.client.post(url,values).status_code,403)

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

    def test_assessed_charge_cannot_reduce_officer_advance_by_receipt_total(self):
        detail, receipt, deposit = self.ready_return()
        source = self.bank_return(receipt, deposit); self.post_refund_source(source)
        before = movements(detail)
        with self.assertRaises(ValidationError):
            self.replacement(source, received_amount='425', charges=[{'variant':str(self.transaction_variant.public_id),
                'amount':'25','authority_reference':'Synthetic fee basis','assessment_reference':'Synthetic 25 assessment'}])
        self.assertEqual(movements(detail), before)
        self.assertFalse(source.redemption_receipts.exists())
        self.post_refund_source(self.replacement(source))
        self.assertEqual(sum(value for day, value in movements(detail)), Decimal('400'))

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
    assessed_charge_setup=OfficerReturnTests.assessed_charge_setup
    assessed_replacement=OfficerReturnTests.assessed_replacement
    replacement_deposit=OfficerReturnTests.replacement_deposit
    assessed_return=OfficerReturnTests.assessed_return

    def assessed_expense_race(self, value):
        from accounting.models import LedgerAccount
        detail,receipt,deposit = self.ready_return()
        _,charge,_,_ = self.assessed_charge_setup(LedgerAccount.objects.get(pk=receipt.proposal['cash_account_id']))
        source = self.bank_return(receipt,deposit);self.post_refund_source(source)
        rule = self.liquidation_rule()
        def compete(number):
            if number == 1:self.replacement(source,received_amount='425',charges=[charge])
            else:prepare(detail=detail,actor=self.preparer,rule=rule,day=date(2026,9,14),
                expenses=[{'account_code':'5-02-03','amount':value,'document_reference':'RACE'}],
                evidence_reference='Actual expense',key='assessed-replacement-expense')
            return 'accepted'
        return detail,self.race(compete)

    def test_combined_replacement_and_excess_expense_cannot_overreserve_principal(self):
        _,results = self.assessed_expense_race('601')
        self.assertEqual(results.count('accepted'),1,results)

    def test_combined_replacement_and_exact_remaining_expense_both_fit(self):
        detail,results = self.assessed_expense_race('600')
        self.assertEqual(results.count('accepted'),2,results)
        self.assertEqual(sum(value for _,value in movements(detail)),Decimal('400'))
        with self.assertRaises(ValidationError):capacity(detail,date(2026,9,14),Decimal('0.01'))

    def test_combined_return_correction_and_expense_share_principal_capacity(self):
        detail,_,receipt,variant,_,_,_ = self.assessed_replacement(cheque=True)
        self.post_refund_source(receipt)
        deposit = self.replacement_deposit(receipt);self.post_refund_source(deposit)
        returned = self.assessed_return(receipt,deposit,variant);self.post_refund_source(returned)
        rule = self.liquidation_rule()
        def compete(number):
            if number == 1:correct(original=returned,actor=self.treasury_user,corrected_on=date(2026,9,16),reason='Wrong attribution')
            else:prepare(detail=detail,actor=self.preparer,rule=rule,day=date(2026,9,16),
                expenses=[{'account_code':'5-02-03','amount':'601','document_reference':'RACE'}],
                evidence_reference='Actual expense',key='assessed-return-correction-expense')
            return 'accepted'
        results = self.race(compete)
        self.assertEqual(results.count('accepted'),1,results)

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
