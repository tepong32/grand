from copy import deepcopy
from datetime import date
from unittest import skipUnless
from unittest.mock import patch
from threading import Event
from django.db import connections
from django.test import TransactionTestCase
from . import test_budget_receipt_attributions as fixtures
from . import test_budget_attribution_concurrency as race_fixture
from . import test_budget_native_cash_concurrency as worker_fixture
from . import budget_receipt_attributions as service
from . import budget_receipt_sources as sources
from .models import BudgetReceiptAttributionBatch as Batch, BudgetReceiptAttribution as Member, BudgetReceiptAttributionHead as Head, AccountingAuditEvent
from vouchers.collection_corrections import propose as propose_correction
from vouchers import test_collection_workflow as collection_fixtures


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native receipt Fund/batch locks')
class ReceiptAttributionConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = classmethod(fixtures.ReceiptAttributionTests.employee.__func__)
    configure_mapping = fixtures.ReceiptAttributionTests.configure_mapping
    configure_receipt_permissions = fixtures.ReceiptAttributionTests.configure_receipt_permissions
    capture = fixtures.ReceiptAttributionTests.capture
    deposit = fixtures.ReceiptAttributionTests.deposit
    post_source = fixtures.ReceiptAttributionTests.post_source
    inventory = fixtures.ReceiptAttributionTests.inventory
    rows = fixtures.ReceiptAttributionTests.rows
    pairs = fixtures.ReceiptAttributionTests.pairs
    args = fixtures.ReceiptAttributionTests.args
    member_args = fixtures.ReceiptAttributionTests.member_args
    decide = fixtures.ReceiptAttributionTests.decide
    race = race_fixture.BudgetAttributionConcurrencyTests.race
    workers = worker_fixture.NativeCashConcurrencyTests.workers
    wait_for = worker_fixture.NativeCashConcurrencyTests.wait_for

    def setUp(self):
        fixtures.ReceiptAttributionTests.setUpTestData.__func__(type(self))
        collection_fixtures.CollectionWorkflowTests.setUp(self)
        self.configure_mapping(); self.configure_receipt_permissions()
        self.receipt = self.capture(); self.entry = self.post_source(self.receipt)
        inventory = self.inventory()
        self.arguments = self.args([self.member_args(inventory,self.entry)])

    def test_competing_proposals_and_reviews_retain_one_version_head_and_decision(self):
        results=self.race(lambda _: 'created' if service.propose_batch(**self.arguments) else 'missing')
        self.assertEqual(results.count('created'),1,results)
        self.assertEqual(Member.objects.count(),1)
        batch=Batch.objects.get(); original=deepcopy(service.snapshot(batch,self.preparer))
        results=self.race(lambda _: 'approved' if self.decide(batch) else 'missing')
        self.assertEqual(results.count('approved'),1,results)
        batch.refresh_from_db()
        self.assertEqual(service.snapshot(batch,self.preparer)['payload'],original['payload'])
        self.assertEqual(Head.objects.count(),1)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='budget_receipt_approved').count(),1)

    def test_successor_and_approval_serialize_without_old_version_becoming_current(self):
        first=service.propose_batch(**self.arguments)
        arguments=deepcopy(self.arguments); arguments['proposals'][0]['expected_latest']=1
        def action(number):
            if number==1:
                service.propose_batch(**arguments); return 'successor'
            self.decide(first); return 'approved'
        results=self.race(action)
        self.assertIn('successor',results)
        first.refresh_from_db()
        self.assertFalse(service.is_current(first,self.preparer))
        self.assertEqual(Member.objects.count(),2)
        newest=Member.objects.get(version=2)
        self.decide(newest.batch)
        self.assertEqual(Head.objects.get().attribution_id,newest.pk)

    def test_parent_successor_and_correction_approval_preserve_pins_and_staleness(self):
        original=self.decide(service.propose_batch(**self.arguments)); parent=original.members.get()
        fix=propose_correction(original=self.receipt,actor=self.treasury_user,corrected_on=date(2026,9,13),reason='Synthetic receipt dependency race')
        child=self.post_source(fix); inventory=self.inventory()
        pending=service.propose_batch(**self.args([dict(entry_id=child.pk,expected_latest=0,
            inherit_from=str(parent.public_id),line_pairs=self.pairs(inventory,child.pk,self.entry.pk))]))
        frozen=deepcopy(service.snapshot(pending,self.preparer))
        arguments=self.args([self.member_args(inventory,self.entry,latest=1)])
        def action(number):
            if number==1:
                service.propose_batch(**arguments); return 'successor'
            self.decide(pending); return 'approved'
        results=self.race(action)
        self.assertIn('successor',results)
        pending.refresh_from_db()
        self.assertEqual(service.snapshot(pending,self.preparer)['payload'],frozen['payload'])
        self.assertFalse(service.is_current(pending,self.preparer))
        self.assertEqual(pending.status,Batch.APPROVED if 'approved' in results else Batch.SUBMITTED)
        self.assertEqual(Head.objects.filter(entry=child).count(),1 if 'approved' in results else 0)

    def test_actual_deposit_after_observation_retains_approval_but_blocks_current_use(self):
        pending=service.propose_batch(**self.arguments)
        frozen=deepcopy(service.snapshot(pending,self.preparer))
        deposit=self.deposit(self.receipt,'100','RECEIPT-APPROVAL-OVERLAP')
        collection_fixtures.review_source(source=deposit,actor=self.validator,approve=True,reason='Independent actual deposit source review')
        request=deposit.posting_requests.get()
        staged,_=collection_fixtures.materialize(request,self.preparer)
        collection_fixtures.submit_entry(staged,self.preparer)
        observed,committed=Event(),Event()
        original=sources._capture_for_owner
        def capture_then_wait(*args,**kwargs):
            retained=original(*args,**kwargs)
            observed.set(); self.wait_for(committed)
            return retained
        def reviewer():
            self.decide(pending); return 'approved'
        def poster():
            try:
                self.wait_for(observed)
                collection_fixtures.post_entry(staged,self.validator)
                collection_fixtures.reconcile(staged,self.validator)
                return 'posted'
            finally:
                committed.set()
        with patch.object(sources,'_capture_for_owner',side_effect=capture_then_wait):
            self.assertEqual(self.workers(reviewer,poster),['approved','posted'])
        pending.refresh_from_db()
        self.assertEqual(pending.status,Batch.APPROVED)
        self.assertEqual(service.snapshot(pending,self.preparer)['payload'],frozen['payload'])
        self.assertFalse(service.is_current(pending,self.preparer))
        self.assertEqual(AccountingAuditEvent.objects.filter(action='budget_receipt_approved').count(),1)
