from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from accounting.models import LedgerAccount, Fund, AccountingPeriod, JournalLine
from accounting.services import submit_entry, post_entry
from finance.models import FinancePostingRule as Rule, FinancePostingRuleLine as Line, FinanceConfigurationItem, FinanceNumberingSequence
from .test_collection_sources import CollectionSourceStorageTests
from .collections import record_receipt, record_deposit, remaining_receipts
from .collection_posting import review_source, materialize, reconcile
from .models import CollectionPostingRequest


class CollectionWorkflowTests(CollectionSourceStorageTests):
    def setUp(self):
        owner={'department_id':self.accounting.pk,'department_label':self.accounting.name}
        self.collection_cash=LedgerAccount.objects.create(**owner,code='COL-CASH',title='Synthetic collection cash',account_type='asset',normal_balance='debit')
        self.deposit_bank=LedgerAccount.objects.create(**owner,code='COL-BANK',title='Synthetic deposit bank',account_type='asset',normal_balance='debit')
        self.collection_revenue=LedgerAccount.objects.create(**owner,code='COL-REV',title='Synthetic collection revenue',account_type='revenue',normal_balance='credit')
        Fund.objects.get_or_create(department_id=self.accounting.pk,code='general-fund',defaults={'department_label':self.accounting.name,'name':'General fund'})
        AccountingPeriod.objects.get_or_create(department_id=self.accounting.pk,fiscal_year=2026,period_number=9,defaults={
            'department_label':self.accounting.name,'label':'Synthetic September','starts_on':date(2026,9,1),'ends_on':date(2026,9,30)})
        from accounting.models import PostingMapping
        PostingMapping.objects.update_or_create(department_id=self.accounting.pk,category=PostingMapping.BANK,source_code='gf-lbp',
            defaults={'department_label':self.accounting.name,'label':'Synthetic deposit bank','account':self.deposit_bank,'is_active':True})
        self.bank_item=FinanceConfigurationItem.objects.get(release=self.release,category='bank_account',code='gf-lbp')
        FinanceNumberingSequence.objects.get_or_create(department=self.accounting,release=self.release,fiscal_year=2026,
            document_type='journal-entry',defaults={'prefix':'COL-JEV-','padding':5,'next_number':1,'status':'active','created_by':self.preparer})
        for code,user in [('prepare_collections',self.treasury_user),('prepare_collection_deposits',self.treasury_user),('review_collections',self.validator)]:
            user.user_permissions.add(Permission.objects.get(content_type__app_label='vouchers',codename=code))
        for event,point in [(Rule.COLLECTION,Rule.COLLECTION_RECEIPT),(Rule.DEPOSIT,Rule.COLLECTION_DEPOSIT)]:
            rule=Rule.objects.create(variant=self.transaction_variant,code=event,title='Synthetic '+event,event_kind=event,
                recognition_point=point,description='Synthetic reviewed collection/deposit treatment',authority_reference='Synthetic policy',created_by=self.preparer)
            if event==Rule.COLLECTION:
                specifications=[(Line.DEBIT,Line.FIXED_ACCOUNT,Line.EVENT_AMOUNT,self.collection_cash.code,'op_services'),
                    (Line.CREDIT,Line.FIXED_ACCOUNT,Line.EVENT_AMOUNT,self.collection_revenue.code,'')]
            else:
                specifications=[(Line.DEBIT,Line.BANK_MAPPING,Line.EVENT_AMOUNT,'','internal'),
                    (Line.CREDIT,Line.ALLOCATION_ACCOUNTS,Line.EACH_ALLOCATION,'','internal')]
            for sequence,(side,account_source,amount_source,code,purpose) in enumerate(specifications,start=1):
                Line.objects.create(rule=rule,sequence=sequence,label='Synthetic reviewed line',side=side,account_source=account_source,
                    amount_source=amount_source,ledger_account_code=code,cash_flow_category=purpose)

    def capture(self):
        return record_receipt(actor=self.treasury_user,variant=self.transaction_variant,received_on=date(2026,9,12),
            fund_code='general-fund',receipt_book='SYNTHETIC-BOOK',receipt_number='001',payer_reference='Synthetic payer',
            received_amount='100',evidence_reference='Synthetic actual collection')

    def deposit(self,receipt,value,reference):
        return record_deposit(actor=self.treasury_user,variant=self.transaction_variant,deposited_on=date(2026,9,12),
            fund_code='general-fund',deposit_reference=reference,receiving_bank_id=self.bank_item.public_id,
            allocations=[{'receipt':str(receipt.public_id),'amount':value}],evidence_reference='Synthetic bank slip')

    def post_source(self,source):
        review_source(source=source,actor=self.validator,approve=True,reason='Independent actual source review')
        request=source.posting_requests.get()
        entry,_=materialize(request,self.preparer)
        submit_entry(entry,self.preparer);post_entry(entry,self.validator)
        reconcile(entry,self.validator);reconcile(entry,self.validator)
        return entry

    def test_receipt_and_partial_deposits_preserve_cash_and_recognize_revenue_once(self):
        receipt=self.capture()
        with self.assertRaises(ValidationError):self.capture()
        with self.assertRaises(ValidationError):self.deposit(receipt,'60','DEP-1')
        self.post_source(receipt)
        first=self.deposit(receipt,'60','DEP-1')
        with self.assertRaises(ValidationError):self.deposit(receipt,'41','DEP-2')
        self.post_source(first)
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('40'))
        self.post_source(self.deposit(receipt,'40','DEP-2'))
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('0'))
        posted=JournalLine.objects.filter(entry__status='posted')
        self.assertEqual(sum(r.debit-r.credit for r in posted.filter(account=self.collection_cash)),Decimal('0'))
        self.assertEqual(sum(r.debit-r.credit for r in posted.filter(account=self.deposit_bank)),Decimal('100'))
        self.assertEqual(sum(r.credit-r.debit for r in posted.filter(account=self.collection_revenue)),Decimal('100'))

    def test_interrupted_receipt_handoff_recovers_one_finance_journal(self):
        receipt=self.capture();review_source(source=receipt,actor=self.validator,approve=True,reason='Independent receipt review')
        request=receipt.posting_requests.get();save=CollectionPostingRequest.save
        def fail(row,*args,**kwargs):
            if row.status==row.MATERIALIZED:raise RuntimeError('Interrupted default link')
            return save(row,*args,**kwargs)
        with patch.object(CollectionPostingRequest,'save',fail),self.assertRaises(RuntimeError):materialize(request,self.preparer)
        entry,created=materialize(request,self.preparer)
        self.assertFalse(created)
        submit_entry(entry,self.preparer);post_entry(entry,self.validator);reconcile(entry,self.validator)

    def test_preparer_cannot_review_own_receipt_even_with_review_permission(self):
        receipt=self.capture()
        self.treasury_user.user_permissions.add(Permission.objects.get(
            content_type__app_label='vouchers',codename='review_collections'))
        with self.assertRaises((PermissionDenied,ValidationError)):
            review_source(source=receipt,actor=self.treasury_user,approve=True,reason='Self review')
        self.assertFalse(receipt.posting_requests.exists())

    def test_balanced_manual_edit_cannot_replace_approved_receipt_rows(self):
        receipt=self.capture()
        review_source(source=receipt,actor=self.validator,approve=True,reason='Independent review')
        entry,_=materialize(receipt.posting_requests.get(),self.preparer)
        line=entry.lines.get(sequence=2)
        line.account=self.payable_account
        with self.assertRaises(ValidationError):line.save()
        # Simulate corruption below the normal model guard to exercise submission evidence.
        JournalLine.objects.filter(pk=line.pk).update(account=self.payable_account)
        with self.assertRaises(ValidationError):submit_entry(entry,self.preparer)

    def test_deposit_cannot_predate_collection(self):
        receipt=self.capture();self.post_source(receipt)
        with self.assertRaises(ValidationError):
            record_deposit(actor=self.treasury_user,variant=self.transaction_variant,deposited_on=date(2026,9,11),
                fund_code='general-fund',deposit_reference='EARLY',receiving_bank_id=self.bank_item.public_id,
                allocations=[{'receipt':str(receipt.public_id),'amount':'100'}],evidence_reference='Synthetic slip')

    def test_collection_only_policy_does_not_bypass_payment_cycle(self):
        from finance.services import collection_event_policy_error
        rules=list(self.transaction_variant.posting_rules.filter(event_kind__in=(Rule.COLLECTION,Rule.DEPOSIT)))
        self.assertEqual(collection_event_policy_error(rules),'')
        rules[0].accounting_effect=Rule.NO_ENTRY
        self.assertTrue(collection_event_policy_error(rules))
        self.assertIsNone(collection_event_policy_error(list(self.transaction_variant.posting_rules.all())))

    def test_receipt_http_capture_register_export_and_office_boundary(self):
        from django.urls import reverse
        self.treasury_user.user_permissions.add(Permission.objects.get(
            content_type__app_label='vouchers',codename='view_collection_register'))
        self.treasury_user.user_permissions.add(Permission.objects.get(
            content_type__app_label='finance',codename='export_finance_work'))
        self.client.force_login(self.treasury_user)
        page=self.client.get(reverse('vouchers:collection_create'))
        self.assertEqual(page.status_code,200)
        response=self.client.post(reverse('vouchers:collection_create'),{
            'variant':self.transaction_variant.pk,'received_on':'2026-09-12','fund_code':'general-fund',
            'receipt_book':'WEB-BOOK','receipt_number':'WEB-001','payer_reference':'Synthetic payer',
            'received_amount':'100','evidence_reference':'Actual synthetic receipt'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'WEB-001')
        from .models import TreasuryCollectionSource
        source=TreasuryCollectionSource.objects.get(document_reference='WEB-001')
        self.validator.user_permissions.add(Permission.objects.get(
            content_type__app_label='vouchers',codename='view_collection_register'))
        self.client.force_login(self.validator)
        self.assertContains(self.client.get(response.url),'Review basis')
        decision=self.client.post(reverse('vouchers:collection_review',args=[source.public_id]),{
            'decision':'approve','reason':'Independent web review'})
        self.assertEqual(decision.status_code,302)
        entry,_=materialize(source.posting_requests.get(),self.preparer)
        submit_entry(entry,self.preparer);post_entry(entry,self.validator);reconcile(entry,self.validator)
        self.client.force_login(self.treasury_user)
        self.assertContains(self.client.get(reverse('vouchers:collection_register')),'100.00')
        output=self.client.get(reverse('vouchers:collection_export'))
        self.assertEqual(output.status_code,200)
        self.assertIn(b'WEB-001',output.content)
        self.assertIn(b'100.00',output.content)
        self.budget_user.user_permissions.add(Permission.objects.get(
            content_type__app_label='vouchers',codename='view_collection_register'))
        self.client.force_login(self.budget_user)
        self.assertEqual(self.client.get(response.url).status_code,404)
        from django.contrib.auth.models import Group
        self.treasury_user.groups.add(Group.objects.get_or_create(name='Finance UAT Viewer')[0])
        self.client.force_login(self.treasury_user)
        self.assertEqual(self.client.get(reverse('vouchers:collection_register')).status_code,200)
        self.assertEqual(self.client.get(reverse('vouchers:collection_create')).status_code,403)

    def test_partial_deposit_web_review_posting_and_register(self):
        from django.urls import reverse
        from .models import TreasuryCollectionSource
        for user in (self.treasury_user,self.preparer,self.validator):
            user.user_permissions.add(Permission.objects.get(
                content_type__app_label='vouchers',codename='view_collection_register'))
        receipt=self.capture()

        def web_post(source):
            self.client.force_login(self.validator)
            response=self.client.post(reverse('vouchers:collection_review',args=[source.public_id]),{
                'decision':'approve','reason':'Independent actual source review'})
            self.assertEqual(response.status_code,302)
            self.client.force_login(self.preparer)
            response=self.client.post(reverse('vouchers:collection_accounting_action',args=[source.public_id,'materialize']))
            self.assertEqual(response.status_code,302)
            posting=source.posting_requests.get();posting.refresh_from_db()
            from accounting.models import JournalEntry
            entry=JournalEntry.objects.get(public_id=posting.accounting_entry_public_id)
            self.assertEqual(self.client.post(reverse('accounting:entry_submit',args=[entry.public_id])).status_code,302)
            self.client.force_login(self.validator)
            self.assertEqual(self.client.post(reverse('accounting:entry_post',args=[entry.public_id])).status_code,302)
            source.refresh_from_db();self.assertEqual(source.status,source.POSTED)
            # Explicit retry remains safe after automatic post reconciliation.
            self.assertEqual(self.client.post(reverse('vouchers:collection_accounting_action',args=[source.public_id,'reconcile'])).status_code,302)

        web_post(receipt)
        self.client.force_login(self.treasury_user)
        page=self.client.get(reverse('vouchers:collection_deposit_create'))
        self.assertContains(page,'Amount in this deposit')
        for amount,reference in [('60','WEB-DEP-1'),('40','WEB-DEP-2')]:
            self.client.force_login(self.treasury_user)
            response=self.client.post(reverse('vouchers:collection_deposit_create'),{
                'variant':self.transaction_variant.pk,'deposited_on':'2026-09-12','fund_code':'general-fund',
                'deposit_reference':reference,'receiving_bank_id':str(self.bank_item.public_id),
                'evidence_reference':'Synthetic deposit slip','shares-TOTAL_FORMS':'1','shares-INITIAL_FORMS':'0',
                'shares-MIN_NUM_FORMS':'1','shares-MAX_NUM_FORMS':'1000',
                'shares-0-receipt':receipt.pk,'shares-0-amount':amount})
            self.assertEqual(response.status_code,302)
            self.assertContains(self.client.get(response.url),'Deposit allocations')
            web_post(TreasuryCollectionSource.objects.get(document_reference=reference))
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('0'))
        posted=JournalLine.objects.filter(entry__status='posted')
        self.assertEqual(sum(r.debit-r.credit for r in posted.filter(account=self.deposit_bank)),Decimal('100'))
        self.assertEqual(sum(r.credit-r.debit for r in posted.filter(account=self.collection_revenue)),Decimal('100'))

    def test_unposted_withdrawal_preserves_approval_and_requires_discard(self):
        from .collection_posting import withdraw_unposted
        from accounting.services import discard_draft
        receipt=self.capture()
        review_source(source=receipt,actor=self.validator,approve=True,reason='Original review')
        receipt.refresh_from_db();decision=(receipt.reviewed_by_id,receipt.reviewed_at,receipt.review_reason)
        posting=receipt.posting_requests.get();entry,_=materialize(posting,self.preparer)
        with self.assertRaises(ValidationError):
            withdraw_unposted(source=receipt,actor=self.validator,reason='Wrong payer reference')
        discard_draft(entry,self.preparer,reason='Source needs correction')
        from django.urls import reverse
        self.validator.user_permissions.add(Permission.objects.get(
            content_type__app_label='vouchers',codename='view_collection_register'))
        self.validator.user_permissions.add(Permission.objects.get(
            content_type__app_label='finance',codename='export_finance_work'))
        self.client.force_login(self.validator)
        response=self.client.post(reverse('vouchers:collection_review',args=[receipt.public_id]),{
            'decision':'withdraw','reason':'Wrong payer reference'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Approval withdrawn:')
        receipt.refresh_from_db();withdrawn=receipt
        output=self.client.get(reverse('vouchers:collection_export'))
        self.assertContains(output,'Wrong payer reference')
        self.assertContains(output,posting.jev_number)
        self.assertEqual((withdrawn.reviewed_by_id,withdrawn.reviewed_at,withdrawn.review_reason),decision)
        posting.refresh_from_db();self.assertEqual(posting.status,posting.CANCELLED)
        replacement=self.capture()
        self.assertEqual(replacement.version,2);self.assertEqual(replacement.supersedes_id,receipt.pk)
        self.post_source(replacement)
        with self.assertRaises(ValidationError):
            withdraw_unposted(source=replacement,actor=self.validator,reason='Cannot erase a posted receipt')
        withdrawn.withdrawal_reason='Changed'
        with self.assertRaises(ValidationError):withdrawn.save()

    def test_unposted_deposit_withdrawal_releases_hold_and_keeps_lineage(self):
        from .collection_posting import withdraw_unposted
        receipt=self.capture();self.post_source(receipt)
        deposit=self.deposit(receipt,'60','CORRECT-DEPOSIT')
        review_source(source=deposit,actor=self.validator,approve=True,reason='Initial deposit review')
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('40'))
        withdraw_unposted(source=deposit,actor=self.validator,reason='Actual slip was 40')
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('100'))
        replacement=self.deposit(receipt,'40','CORRECT-DEPOSIT')
        self.assertEqual(replacement.supersedes_id,deposit.pk)
        self.post_source(replacement)
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('60'))

    def test_posted_deposit_then_receipt_correction_retains_exact_reversals(self):
        from .collection_corrections import propose
        receipt=self.capture();receipt_entry=self.post_source(receipt)
        deposit=self.deposit(receipt,'60','POSTED-ERROR');deposit_entry=self.post_source(deposit)
        with self.assertRaises(ValidationError):
            propose(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Receipt error')
        from django.urls import reverse
        self.treasury_user.user_permissions.add(Permission.objects.get(
            content_type__app_label='vouchers',codename='view_collection_register'))
        self.client.force_login(self.treasury_user)
        response=self.client.post(reverse('vouchers:collection_correction_create',args=[deposit.public_id]),{
            'corrected_on':'2026-09-12','reason':'Wrong deposit'})
        self.assertEqual(response.status_code,302)
        self.assertContains(self.client.get(response.url),'Original posted source')
        correction=deposit.corrections.get()
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('40'))
        fixed=self.post_source(correction)
        self.assertEqual(fixed.reversal_of_id,deposit_entry.pk)
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('100'))
        receipt_fix=propose(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Wrong receipt')
        with self.assertRaises(ValidationError):self.deposit(receipt,'10','BLOCKED')
        fixed_receipt=self.post_source(receipt_fix)
        self.assertEqual(fixed_receipt.reversal_of_id,receipt_entry.pk)
        for account in (self.collection_cash,self.deposit_bank,self.collection_revenue):
            self.assertEqual(sum(r.debit-r.credit for r in JournalLine.objects.filter(account=account,entry__status='posted')),Decimal('0'))
        replacement=self.capture()
        self.assertEqual(replacement.supersedes_id,receipt.pk)
        self.assertEqual(replacement.version,2)

    def test_future_correction_cannot_fund_earlier_deposit(self):
        from .collection_corrections import propose
        receipt=record_receipt(actor=self.treasury_user,variant=self.transaction_variant,received_on=date(2026,9,11),
            fund_code='general-fund',receipt_book='DATED',receipt_number='001',payer_reference='Synthetic payer',
            received_amount='100',evidence_reference='Actual prior receipt')
        self.post_source(receipt)
        arguments=dict(actor=self.treasury_user,variant=self.transaction_variant,deposited_on=date(2026,9,11),
            fund_code='general-fund',receiving_bank_id=self.bank_item.public_id,
            allocations=[{'receipt':str(receipt.public_id),'amount':'100'}],evidence_reference='Actual prior slip')
        deposit=record_deposit(**arguments,deposit_reference='DATED-DEP');self.post_source(deposit)
        correction_entry=self.post_source(propose(original=deposit,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Correct wrong slip'))
        with self.assertRaises(ValidationError):record_deposit(**arguments,deposit_reference='TOO-EARLY')
        self.post_source(self.deposit(receipt,'100','ACTUAL-CORRECTED'))
        from accounting.models import JournalEntry
        # A mismatched restored store must not turn a default status into free cash.
        JournalEntry.objects.filter(pk=correction_entry.pk).update(status=JournalEntry.DRAFT)
        with self.assertRaises(ValidationError):remaining_receipts(self.treasury.pk)

    def test_retained_printable_copy_survives_correction_and_checks_integrity(self):
        from django.urls import reverse
        from .collection_outputs import content
        from .collection_corrections import propose
        from .models import CollectionOutput
        self.treasury_user.user_permissions.add(Permission.objects.get(
            content_type__app_label='vouchers',codename='view_collection_register'))
        self.treasury_user.user_permissions.add(Permission.objects.get(
            content_type__app_label='finance',codename='export_finance_work'))
        receipt=self.capture();self.post_source(receipt)
        deposit=self.deposit(receipt,'60','PRINT-DEP');self.post_source(deposit)
        self.client.force_login(self.treasury_user)
        generated=self.client.post(reverse('vouchers:collection_output_generate',args=[deposit.public_id]))
        self.assertEqual(generated.status_code,302)
        download=self.client.get(generated.url)
        self.assertEqual(download.status_code,200)
        original=download.content
        self.assertIn(b'PRINT-DEP',original);self.assertIn(b'SYNTHETIC-BOOK',original)
        self.assertIn(b'60.00',original)
        output=deposit.issued_outputs.get()
        self.post_source(propose(original=deposit,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Correct posted deposit'))
        self.assertEqual(self.client.get(generated.url).content,original)
        newer=self.client.post(reverse('vouchers:collection_output_generate',args=[deposit.public_id]))
        self.assertContains(self.client.get(newer.url),'Corrections recorded when this copy was generated')
        self.assertEqual(deposit.issued_outputs.count(),2)
        output.html='Changed'
        with self.assertRaises(ValidationError):output.save()
        with self.assertRaises(ValidationError):output.delete()
        CollectionOutput.objects.filter(pk=output.pk).update(html='Corrupted stored bytes')
        output.refresh_from_db()
        with self.assertRaises(ValidationError):content(output,self.treasury_user)
        self.assertEqual(self.client.get(generated.url).status_code,409)

    def test_posted_correction_reconciliation_failure_keeps_allocation_until_retry(self):
        from .collection_corrections import propose
        receipt=self.capture();self.post_source(receipt)
        deposit=self.deposit(receipt,'60','RECOVERY');self.post_source(deposit)
        correction=propose(original=deposit,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Incorrect slip')
        review_source(source=correction,actor=self.validator,approve=True,reason='Independent review')
        request=correction.posting_requests.get();entry,_=materialize(request,self.preparer)
        submit_entry(entry,self.preparer);post_entry(entry,self.validator)
        save=CollectionPostingRequest.save
        def fail(row,*args,**kwargs):
            if row.status == row.POSTED:raise RuntimeError('Interrupted reconciliation')
            return save(row,*args,**kwargs)
        with patch.object(CollectionPostingRequest,'save',fail),self.assertRaises(RuntimeError):
            reconcile(entry,self.validator)
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('40'))
        reconcile(entry,self.validator);reconcile(entry,self.validator)
        self.assertEqual(remaining_receipts(self.treasury.pk)[str(receipt.public_id)],Decimal('100'))

    def test_historical_correction_keeps_recipe_and_uses_current_numbering(self):
        from .collection_corrections import propose
        from finance.models import FinanceConfigurationRelease
        receipt=self.capture();self.post_source(receipt)
        original=receipt.posting_requests.get().posting_rule_snapshot
        # Fixture represents an independently activated successor setup, without rewriting old rules.
        FinanceConfigurationRelease.objects.filter(pk=self.release.pk).update(status='superseded')
        successor=FinanceConfigurationRelease.objects.create(department=self.accounting,code='collection-successor',
            title='Synthetic reviewed successor',fiscal_year=2026,status='active',effective_from=date(2026,9,12),created_by=self.preparer)
        FinanceNumberingSequence.objects.filter(department=self.accounting,fiscal_year=2026,document_type='journal-entry').update(
            release=successor,prefix='CURRENT-')
        correction=propose(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,12),reason='Historical source error')
        entry=self.post_source(correction)
        request=correction.posting_requests.get()
        self.assertEqual(request.posting_rule_snapshot,original)
        self.assertEqual(correction.configuration_release_id,self.release.pk)
        self.assertTrue(entry.reference.startswith('CURRENT-'))

    def test_collection_role_has_navigation_without_disbursement_or_posting_authority(self):
        from django.contrib.auth.models import Group
        from django.urls import reverse
        from .roles import FINANCE_ROLE_PERMISSIONS
        from .access import can_view_workbench
        from accounting.access import can_post_journals
        role=Group.objects.create(name='Synthetic collection role')
        for name in FINANCE_ROLE_PERMISSIONS['Treasury Collection Officer']:
            app,code=name.split('.',1)
            role.permissions.add(Permission.objects.get(content_type__app_label=app,codename=code))
        self.treasury_user.user_permissions.clear();self.treasury_user.groups.clear()
        self.treasury_user.groups.add(role)
        self.assertFalse(can_view_workbench(self.treasury_user))
        self.assertFalse(can_post_journals(self.treasury_user))
        self.client.force_login(self.treasury_user)
        response=self.client.get(reverse('vouchers:collection_register'))
        self.assertContains(response,'Collections and deposits')
        self.assertContains(response,reverse('vouchers:collection_create'))
        self.assertEqual(self.client.get(reverse('vouchers:collection_create')).status_code,200)
        source=self.capture()
        with self.assertRaises(PermissionDenied):
            review_source(source=source,actor=self.treasury_user,approve=True,reason='Not authorized')
