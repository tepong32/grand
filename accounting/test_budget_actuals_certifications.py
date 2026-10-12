from copy import deepcopy
from datetime import date
from unittest import skipUnless
from unittest.mock import patch
from threading import Event
from django.contrib.auth.models import Permission, Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test.utils import CaptureQueriesContext
from . import budget_actuals_certifications as service, budget_actuals_preparations as preparations
from . import budget_native_actuals as actuals
from . import test_budget_actuals_preparations as fixtures
from .models import NativeBudgetActualsDecision as Decision, JournalEntry, JournalLine, AccountingPeriod, AccountingAuditEvent
from .services import submit_entry, post_entry
from .cash_classifications import checksum
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from vouchers import test_collection_workflow as collection_fixtures
from . import test_budget_native_cash_concurrency as worker_fixtures


class NativeActualsCertificationTests(fixtures.NativeActualsReviewTests):
    def setUp(self):
        super().setUp(); self.configure_certifiers()

    def configure_certifiers(self):
        for actor,role in ((self.validator,'accountant'),(self.treasury_user,'treasurer')):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
                codename__in=['view_native_budget_actuals','export_native_budget_actuals',
                    'certify_'+role+'_native_budget_actuals']))

    def reviewed_preparation(self):
        return self.review_preparation(preparations.prepare(**self.preparation_args()))

    def decision(self,record,role='accountant',**changes):
        args=dict(preparation_id=record.pk,actor=self.validator if role=='accountant' else self.treasury_user,
            role=role,certify=True,authority='Synthetic designated '+role,
            note='Verified full Fund category coverage, original postings and trial balance')
        args.update(changes); return service.decide(**args)

    def test_named_joint_decisions_exact_trial_balance_and_zero_query_detached_snapshot(self):
        record=self.reviewed_preparation(); original=deepcopy(record.payload); count=JournalEntry.objects.count()
        with self.assertRaises(PermissionDenied): actuals.capture(actor=self.treasury_user,fund_id=record.fund_id,
            period_start=record.period_start,period_end=record.period_end)
        with CaptureQueriesContext(connections['finance']) as queries:
            first=self.decision(record,'treasurer')
        self.assertEqual(len([q for q in queries if 'posting_evidence' in q['sql'] and 'accounting_fund' in q['sql']]),1)
        pending=service.snapshot(record,self.treasury_user)
        self.assertEqual(pending['payload']['status'],'awaiting_joint_certification')
        self.assertEqual(pending['payload']['totals'],dict(receipt=None,expenditure=None))
        self.decision(record); captured=service.snapshot(record,self.treasury_user,action='export')
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            body=service.verify_snapshot(captured)
        self.assertEqual(body['status'],'jointly_certified')
        self.assertEqual(body['totals'],dict(receipt='100.00',expenditure='0.00'))
        self.assertEqual(body['trial_balance']['payload']['totals'],dict(opening='0.00',debit='100.00',credit='100.00',
            closing='0.00',closing_debit='100.00',closing_credit='100.00'))
        self.assertEqual(body['trial_balance']['payload']['lines'],2)
        self.assertTrue(service.is_current(record,self.treasury_user))
        self.assertEqual(record.payload,original); self.assertEqual(JournalEntry.objects.count(),count)
        with self.assertRaises(ValidationError): first.delete()
        first.actor_label='Rewrite';
        with self.assertRaises(ValidationError): first.save()

    def test_stale_source_return_closes_pending_roles_and_preserves_first_observation(self):
        record=self.reviewed_preparation(); first=self.decision(record)
        retained=deepcopy(first.payload); self.post_source(self.new_receipt('JOINT-LATER'))
        with self.assertRaisesMessage(ValidationError,'sources changed'): self.decision(record,'treasurer')
        returned=self.decision(record,'treasurer',certify=False,note='New real receipt requires successor preparation')
        self.assertIsNone(returned.payload['observation'])
        captured=service.snapshot(record,self.validator)
        self.assertEqual(service.verify_snapshot(captured)['status'],'returned')
        self.assertIsNone(captured['payload']['totals']['receipt'])
        self.assertFalse(service.is_current(record,self.validator))
        self.assertEqual(first.payload,retained)
        with self.assertRaises(ValidationError): self.decision(record,'treasurer')

    def test_maker_generic_role_office_and_uat_denial_and_rehashed_evidence_tamper(self):
        record=self.reviewed_preparation()
        with self.assertRaises(PermissionDenied): self.decision(record,actor=self.preparer)
        for role in ('accountant','treasurer'):
            self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
                codename='certify_'+role+'_native_budget_actuals'))
        with self.assertRaises(ValidationError): self.decision(record,actor=self.preparer)
        self.validator.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',
            codename='certify_treasurer_native_budget_actuals'))
        with self.assertRaises(PermissionDenied): self.decision(record,'treasurer',actor=self.validator)
        group,_=Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP); self.treasury_user.groups.add(group)
        with self.assertRaises(PermissionDenied): self.decision(record,'treasurer')
        self.treasury_user.groups.remove(group)
        self.decision(record); self.decision(record,'treasurer')
        captured=service.snapshot(record,self.validator)
        for field,value in (('status','awaiting_joint_certification'),('totals',dict(receipt='900.00',expenditure='0.00'))):
            altered=deepcopy(captured); altered['payload'][field]=value; altered['checksum']=checksum(altered['payload'])
            with self.assertRaises(ValidationError): service.verify_snapshot(altered)
        altered=deepcopy(captured)
        altered['payload']['trial_balance']['payload']['totals']['closing_debit']='999.00'
        altered['payload']['trial_balance']['checksum']=checksum(altered['payload']['trial_balance']['payload'])
        altered['checksum']=checksum(altered['payload'])
        with self.assertRaises(ValidationError): service.verify_snapshot(altered)

    def test_new_version_prevents_old_certification_but_retains_explicit_return(self):
        record=self.reviewed_preparation(); self.decision(record)
        preparations.prepare(**self.preparation_args(expected_latest=1))
        with self.assertRaisesMessage(ValidationError,'latest'): self.decision(record,'treasurer')
        self.decision(record,'treasurer',certify=False,note='A newer complete preparation supersedes this one')
        self.assertEqual(service.snapshot(record,self.treasury_user)['payload']['status'],'returned')

    def test_trial_balance_prior_year_opening_and_later_period_post_are_separate_from_actuals(self):
        def posted(reference,day,amount):
            period,_=AccountingPeriod.objects.get_or_create(department_id=self.accounting.pk,
                fiscal_year=day.year,period_number=day.month,defaults=dict(department_label=self.accounting.name,
                    label='Synthetic TB boundary',starts_on=day.replace(day=1),ends_on=day))
            entry=JournalEntry.objects.create(department_id=self.accounting.pk,department_label=self.accounting.name,
                fund=self.receipt_fund,period=period,reference=reference,entry_date=day,
                description='Synthetic independently posted TB boundary activity',created_by_id=self.preparer.pk,
                created_by_label=self.preparer.username)
            JournalLine.objects.create(entry=entry,sequence=1,account=self.collection_cash,debit=amount,cash_flow_category='op_services')
            JournalLine.objects.create(entry=entry,sequence=2,account=self.collection_revenue,credit=amount)
            submit_entry(entry,self.preparer); return post_entry(entry,self.validator)
        old=posted('JOINT-TB-OLD',date(2025,12,31),'50.00')
        record=self.reviewed_preparation(); self.decision(record); self.decision(record,'treasurer')
        retained=service.snapshot(record,self.validator)
        rows=retained['payload']['trial_balance']['payload']['rows']
        cash=next(row for row in rows if row['account']['id']==self.collection_cash.pk)
        self.assertEqual((cash['opening'],cash['debit'],cash['credit'],cash['closing']),('50.00','100.00','0.00','150.00'))
        self.assertIn(old.pk,{source['entry_id'] for source in cash['sources']})
        self.assertEqual(retained['payload']['totals']['receipt'],'100.00')
        later=posted('JOINT-TB-LATER',date(2026,9,12),'30.00')
        self.assertTrue(service.is_current(record,self.validator))
        self.assertNotIn(later.pk,{source['entry_id'] for row in rows for source in row['sources']})
        self.assertEqual(service.snapshot(record,self.validator),retained)
        service.verify_snapshot(retained)


@skipUnless(connections['finance'].vendor=='mysql','Requires native actuals joint decision locks')
class NativeActualsCertificationConcurrencyTests(fixtures.NativeActualsReviewConcurrencyTests):
    configure_certifiers=NativeActualsCertificationTests.configure_certifiers
    decision=NativeActualsCertificationTests.decision
    workers=worker_fixtures.NativeCashConcurrencyTests.workers
    wait_for=worker_fixtures.NativeCashConcurrencyTests.wait_for

    def setUp(self):
        super().setUp(); self.configure_certifiers()
        # Inherited preparation races must start with their original empty history.
        scenario=next((owner for owner in type(self).__mro__
            if self._testMethodName in vars(owner)),type(self))
        if issubclass(scenario,NativeActualsCertificationConcurrencyTests):
            self.record=self.review_preparation(preparations.prepare(**self.preparation_args()))

    def test_competing_certification_and_return_commit_one_immutable_role_decision(self):
        results=self.race(lambda number:'decided' if self.decision(self.record,certify=(number==1)) else 'missing')
        self.assertEqual(results.count('decided'),1,results)
        self.assertEqual(Decision.objects.count(),1)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='native_budget_actuals_decided').count(),1)
        service.verify_snapshot(service.snapshot(self.record,self.validator))

    def test_concurrent_distinct_officers_retain_complete_joint_snapshot(self):
        results=self.race(lambda number:'certified' if self.decision(self.record,
            'accountant' if number==1 else 'treasurer') else 'missing')
        self.assertEqual(results.count('certified'),2,results)
        captured=service.snapshot(self.record,self.treasury_user)
        self.assertEqual(service.verify_snapshot(captured)['status'],'jointly_certified')
        self.assertEqual(Decision.objects.count(),2)
        self.assertTrue(service.is_current(self.record,self.validator))

    def test_actual_post_after_role_observation_preserves_already_stale_joint_certificate(self):
        self.decision(self.record,'treasurer')
        later=self.new_receipt('JOINT-NATIVE-LATER')
        collection_fixtures.review_source(source=later,actor=self.validator,approve=True,reason='Independent later source')
        request=later.posting_requests.get()
        staged,_=collection_fixtures.materialize(request,self.preparer)
        collection_fixtures.submit_entry(staged,self.preparer)
        observed,posted=Event(),Event(); original=service._observe
        def observe(record):
            retained=original(record); observed.set(); self.wait_for(posted); return retained
        def reader(): return self.decision(self.record)
        def writer():
            try:
                self.wait_for(observed)
                collection_fixtures.post_entry(staged,self.validator)
                collection_fixtures.reconcile(staged,self.validator)
                return 'posted'
            finally: posted.set()
        with patch.object(service,'_observe',side_effect=observe):
            decision,result=self.workers(reader,writer)
        self.assertEqual(result,'posted')
        retained=service.snapshot(self.record,self.validator)
        self.assertEqual(service.verify_snapshot(retained)['status'],'jointly_certified')
        self.assertEqual(retained['payload']['totals']['receipt'],'100.00')
        self.assertEqual(decision.payload['observation']['actuals']['payload']['receipts']['payload']['classified_receipts'],'100.00')
        self.assertFalse(service.is_current(self.record,self.validator))
