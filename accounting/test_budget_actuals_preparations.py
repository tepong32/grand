from copy import deepcopy
from datetime import date
from unittest import skipUnless
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TransactionTestCase
from departments.models import Department
from budget.models import BudgetCall
from vouchers.collections import record_receipt
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import budget_actuals_preparations as service, budget_native_actuals as actuals
from . import budget_receipt_sources as receipts, budget_receipt_attributions as receipt_reviews
from . import budget_native_sources as ledger, budget_attributions as expenses
from . import test_budget_native_actuals as fixtures
from . import test_budget_receipt_attributions as receipt_fixtures
from . import test_budget_attribution_concurrency as races
from .models import FiscalYear, Fund, AccountingPeriod, NativeBudgetActualsPreparation as Record, JournalEntry, AccountingAuditEvent
from vouchers import test_collection_workflow as collection_fixtures


class NativeActualsReviewTests(fixtures.NativeActualsPreparationTests):
    def setUp(self):
        super().setUp()
        # Inherited source/storage scenarios retain their original empty-ledger
        # fixture. Only actuals-review scenarios (including certification/view
        # scenarios defined by subclasses) require this extra reviewed receipt.
        scenario = next((cls for cls in type(self).__mro__
                         if self._testMethodName in vars(cls)), type(self))
        if issubclass(scenario, NativeActualsReviewTests):
            self.configure_preparation()

    def configure_preparation(self):
        for actor, codes in ((self.preparer,('view','prepare','review','export')),
                              (self.validator,('view','review','export'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
                codename__in=[action+'_native_budget_actuals' for action in codes]))
        self.validator.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
            codename='view_native_budget_statements'))
        self.budget_office=Department.objects.create(name='Synthetic actuals Budget office')
        fiscal,_=FiscalYear.objects.get_or_create(department_id=self.accounting.pk,year=2026,defaults=dict(
            department_label=self.accounting.name,label='Synthetic FY 2026',starts_on=date(2026,1,1),
            ends_on=date(2026,12,31),business_date=date(2026,6,12)))
        BudgetCall.objects.create(department_id=self.budget_office.pk,department_label=self.budget_office.name,
            fiscal_year=fiscal,title='Synthetic annual call',authority_reference='Synthetic office link',
            instructions='Synthetic complete actuals preparation',proposal_opens_on=date(2026,1,1),
            proposal_due_on=date(2026,6,30),created_by_id=self.preparer.pk,created_by_label=self.preparer.username)
        AccountingPeriod.objects.get_or_create(department_id=self.accounting.pk,fiscal_year=2026,period_number=6,
            defaults=dict(department_label=self.accounting.name,label='Synthetic June',starts_on=date(2026,6,1),ends_on=date(2026,6,30)))
        self.receipt=self.new_receipt('HALF-001')
        entry=self.post_source(self.receipt)
        inventory=receipts.capture(actor=self.preparer,fund_id=self.receipt_fund.pk,
            period_start=date(2026,1,1),period_end=date(2026,6,30))
        batch=receipt_reviews.propose_batch(actor=self.preparer,fund_id=self.receipt_fund.pk,
            period_start=date(2026,1,1),period_end=date(2026,6,30),expected_source_checksum=inventory['source_checksum'],
            proposals=[self.member_args(inventory,entry)],reason='Synthetic H1 source classification',evidence_reference='Synthetic H1 receipt review')
        receipt_reviews.review_batch(batch_id=batch.public_id,actor=self.validator,approve=True,note='Independent H1 receipt classification')
        captured=ledger.capture(actor=self.preparer,fund_id=self.receipt_fund.pk,
            period_start=date(2026,1,1),period_end=date(2026,6,30))
        rows=[dict(line_id=line['id'],amount=str(max(line['debit'],line['credit'])),
            disposition='exclude',purpose='revenue',basis='Actual collection receipt is not expenditure')
            for line in captured['payload']['journals'][0]['lines']]
        records=expenses.propose_batch(actor=self.preparer,fund_id=self.receipt_fund.pk,
            period_start=date(2026,1,1),period_end=date(2026,6,30),expected_source_checksum=captured['checksum'],
            proposals=[dict(entry_id=entry.pk,expected_latest=0,allocations=rows)],
            reason='Explicit H1 collection exclusions',evidence_reference='Synthetic independent expense review')
        expenses.review_batch(batch_id=records[0].batch_id,actor=self.validator,approve=True,note='Independent exclusions')

    def new_receipt(self, number):
        return record_receipt(actor=self.treasury_user,variant=self.transaction_variant,received_on=date(2026,6,12),
            fund_code='general-fund',receipt_book='SYNTHETIC-HALF',receipt_number=number,
            payer_reference='Synthetic H1 payer',received_amount='100',evidence_reference='Synthetic actual H1 collection')

    def preparation_args(self, **changes):
        captured=actuals.capture(actor=self.preparer,fund_id=self.receipt_fund.pk,
            period_start=date(2026,1,1),period_end=date(2026,6,30))
        args=self.coverage_args(captured)
        args.update(actor=self.preparer,fund_id=self.receipt_fund.pk,budget_department_id=self.budget_office.pk,
            treasury_department_id=self.treasury.pk,period_start=date(2026,1,1),period_end=date(2026,6,30),
            expected_latest=0,expected_source_checksum=captured['source_checksum'],reference='Synthetic H1 native sources',
            authority='Synthetic complete source/entity authority',reason='Explicit independent category coverage')
        args.update(changes); return args

    def review_preparation(self, record, **changes):
        args=dict(preparation_id=record.pk,actor=self.validator,approve=True,
            authority='Synthetic independent category/entity review',note='Reconciled all retained leaves and source controls')
        args.update(changes); return service.review(**args)

    def test_retention_independent_observation_versions_and_immutability(self):
        count=JournalEntry.objects.count(); first=service.prepare(**self.preparation_args())
        original=deepcopy(service.verify(first))
        with self.assertRaises(ValidationError): self.review_preparation(first,actor=self.preparer)
        first=self.review_preparation(first)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            self.assertEqual(service.verify(first),original)
        self.assertTrue(service.is_current(first,self.preparer))
        self.assertIsNotNone(first.review_observation)
        self.assertIsNone(original['coverage']['payload']['receipt_total'])
        self.assertEqual(original['coverage']['payload']['certification_status'],'not_certified')
        with self.assertRaises(ValidationError): first.delete()
        first.review_note='Rewrite'; first._decision_write=True
        with self.assertRaises(ValidationError): first.save()
        first.refresh_from_db()
        second=service.prepare(**self.preparation_args(expected_latest=1))
        self.assertFalse(service.is_current(first,self.preparer))
        self.assertEqual(service.verify(first),original)
        self.assertEqual(second.version,2); self.assertEqual(JournalEntry.objects.count(),count)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='native_budget_actuals_prepared').count(),2)

    def test_new_source_blocks_review_and_stale_return_preserves_original(self):
        args=self.preparation_args(); record=service.prepare(**args); original=deepcopy(record.payload)
        self.post_source(self.new_receipt('HALF-002'))
        with self.assertRaisesMessage(ValidationError,'sources changed'): self.review_preparation(record)
        with self.assertRaisesMessage(ValidationError,'sources changed'): service.prepare(**dict(args,expected_latest=1))
        returned=self.review_preparation(record,approve=False,note='Actual later receipt requires fresh full classification')
        self.assertIsNone(returned.review_observation); self.assertEqual(service.verify(returned),original)
        self.assertFalse(service.is_current(returned,self.preparer))
        with self.assertRaises(ValidationError): self.review_preparation(returned)

    def test_period_scope_permissions_uat_and_noncurrent_version_approval(self):
        args=self.preparation_args()
        with self.assertRaises(ValidationError): service.prepare(**dict(args,period_start=date(2026,6,1)))
        with self.assertRaises(ValidationError): service.prepare(**dict(args,treasury_department_id=True))
        first=service.prepare(**args); second=service.prepare(**dict(args,expected_latest=1))
        with self.assertRaisesMessage(ValidationError,'latest'): self.review_preparation(first)
        with self.assertRaises(PermissionDenied): self.review_preparation(second,actor=self.treasury_user)
        group,_=Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP); self.validator.groups.add(group)
        with self.assertRaises(PermissionDenied): self.review_preparation(second)
        self.assertTrue(service.visible(self.validator).filter(pk=second.pk).exists())
        self.validator.groups.remove(group)
        approved=self.review_preparation(second)
        self.assertTrue(service.is_current(approved,self.preparer))
        self.assertEqual(Record.objects.count(),2)
        original=deepcopy(service.verify(approved))
        Fund.objects.filter(pk=self.receipt_fund.pk).update(department_id=self.treasury.pk)
        self.assertFalse(service.is_current(approved,self.preparer))
        self.assertEqual(service.verify(approved),original)
        returned=self.review_preparation(first,approve=False,note='Old Accounting owner retains a stale return')
        self.assertEqual(returned.status,'returned')


@skipUnless(connections['finance'].vendor=='mysql','Requires native actuals Fund/version locks')
class NativeActualsReviewConcurrencyTests(TransactionTestCase):
    databases={'default','finance'}
    employee=classmethod(fixtures.NativeActualsPreparationTests.employee.__func__)
    configure_mapping=fixtures.NativeActualsPreparationTests.configure_mapping
    configure_receipt_permissions=fixtures.NativeActualsPreparationTests.configure_receipt_permissions
    post_source=fixtures.NativeActualsPreparationTests.post_source
    rows=fixtures.NativeActualsPreparationTests.rows
    member_args=fixtures.NativeActualsPreparationTests.member_args
    coverage_args=fixtures.NativeActualsPreparationTests.coverage_args
    configure_preparation=NativeActualsReviewTests.configure_preparation
    new_receipt=NativeActualsReviewTests.new_receipt
    preparation_args=NativeActualsReviewTests.preparation_args
    review_preparation=NativeActualsReviewTests.review_preparation
    race=races.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        receipt_fixtures.ReceiptAttributionTests.setUpTestData.__func__(type(self))
        collection_fixtures.CollectionWorkflowTests.setUp(self)
        self.configure_mapping(); self.configure_receipt_permissions()
        self.preparer.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=['view_native_budget_statements','prepare_budget_attributions','view_budget_attributions']))
        self.validator.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=['review_budget_attributions','view_budget_attributions']))
        self.configure_preparation()

    def test_competing_preparation_and_review_retain_single_version_decision(self):
        args=self.preparation_args()
        results=self.race(lambda _: 'created' if service.prepare(**args) else 'missing')
        self.assertEqual(results.count('created'),1,results)
        record=Record.objects.get()
        results=self.race(lambda _: 'approved' if self.review_preparation(record) else 'missing')
        self.assertEqual(results.count('approved'),1,results)
        record.refresh_from_db(); self.assertTrue(service.is_current(record,self.preparer))
        self.assertEqual(AccountingAuditEvent.objects.filter(action='native_budget_actuals_reviewed').count(),1)

    def test_successor_and_old_approval_serialize_without_old_current_use(self):
        first=service.prepare(**self.preparation_args()); args=self.preparation_args(expected_latest=1)
        def action(number):
            if number==1:
                service.prepare(**args); return 'successor'
            self.review_preparation(first); return 'approved'
        results=self.race(action); self.assertIn('successor',results)
        first.refresh_from_db(); self.assertFalse(service.is_current(first,self.preparer))
        self.assertEqual(Record.objects.count(),2)
        newest=self.review_preparation(Record.objects.get(version=2))
        self.assertTrue(service.is_current(newest,self.preparer))
