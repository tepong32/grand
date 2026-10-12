from threading import Event
from unittest.mock import patch
from django.db import connections
from . import test_budget_receipt_attribution_concurrency as fixtures
from . import budget_receipt_cohorts as service, budget_receipt_sources as sources
from vouchers import test_collection_workflow as collection_fixtures
from . import budget_receipt_attributions as reviews


class ReceiptCohortConcurrencyTests(fixtures.ReceiptAttributionConcurrencyTests):
    def cohort(self):
        return service.capture(actor=self.preparer,fund_id=self.receipt_fund.pk,
            period_start=self.arguments['period_start'],period_end=self.arguments['period_end'])

    def test_head_approval_waits_for_complete_capture_and_old_cohort_stays_reproducible(self):
        pending=reviews.propose_batch(**self.arguments)
        observed,attempted=Event(),Event()
        original=sources._capture_for_owner
        def observe(*args,**kwargs):
            retained=original(*args,**kwargs)
            if not observed.is_set():
                observed.set(); self.wait_for(attempted)
            return retained
        def mark_attempt(execute,sql,params,many,context):
            if 'accounting_fund' in sql and 'FOR UPDATE' in sql.upper(): attempted.set()
            return execute(sql,params,many,context)
        def reader(): return self.cohort()
        def writer():
            self.wait_for(observed)
            with connections['finance'].execute_wrapper(mark_attempt): self.decide(pending)
            return 'approved'
        with patch.object(sources,'_capture_for_owner',side_effect=observe):
            captured,result=self.workers(reader,writer)
        self.assertEqual(result,'approved')
        payload=service.verify(captured)
        self.assertFalse(payload['classification_complete'])
        self.assertEqual(payload['classified_receipts'],'0.00')
        self.assertEqual(payload['heads'][0]['member'],None)
        self.assertFalse(service.is_current(captured,self.preparer))
        self.assertTrue(service.verify(self.cohort())['classification_complete'])

    def test_post_after_ledger_read_returns_coherent_old_review_cohort_already_stale(self):
        self.decide(reviews.propose_batch(**self.arguments))
        deposit=self.deposit(self.receipt,'100','COHORT-NATIVE-POST-OVERLAP')
        collection_fixtures.review_source(source=deposit,actor=self.validator,approve=True,reason='Independent synthetic bank deposit')
        request=deposit.posting_requests.get()
        staged,_=collection_fixtures.materialize(request,self.preparer)
        collection_fixtures.submit_entry(staged,self.preparer)
        observed,committed=Event(),Event()
        original=sources._capture_for_owner
        def observe(*args,**kwargs):
            retained=original(*args,**kwargs); observed.set(); self.wait_for(committed); return retained
        def reader(): return self.cohort()
        def writer():
            try:
                self.wait_for(observed)
                collection_fixtures.post_entry(staged,self.validator)
                collection_fixtures.reconcile(staged,self.validator)
                return 'posted'
            finally: committed.set()
        with patch.object(sources,'_capture_for_owner',side_effect=observe):
            captured,result=self.workers(reader,writer)
        self.assertEqual(result,'posted')
        payload=service.verify(captured)
        self.assertTrue(payload['classification_complete'])
        self.assertEqual(payload['classified_receipts'],'100.00')
        self.assertEqual(len(payload['inventory']['payload']['journals']),1)
        self.assertEqual(len(payload['bridge']),3)
        self.assertFalse(service.is_current(captured,self.preparer))
        self.assertFalse(service.verify(self.cohort())['classification_complete'])
