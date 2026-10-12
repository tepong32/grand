from datetime import date
from types import SimpleNamespace
from django.contrib.auth.models import Permission
from accounting import summary_actuals
from accounting.models import LedgerAccount
from accounting.test_summary_actuals import SummaryActualTests
from departments.models import Department
from .test_office_form_concurrency import OfficeFormConcurrencyFixture
from .models import BudgetSummaryReconciliation
from . import office_forms, summary_reconciliations as service


class SummaryReconciliationConcurrencyTests(OfficeFormConcurrencyFixture):
    def setUp(self):
        super().setUp()
        self.form = office_forms.decide(item=office_forms.prepare(**self.form_args()),actor=self.reviewer,
            issue=True,note='Independent synthetic issue')
        treasury = Department.objects.create(name='Synthetic race Treasury',slug='race-treasury')
        receipt = LedgerAccount.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name,code='RACE-SERVICE',title='Synthetic receipt',
            account_type='revenue',normal_balance='credit')
        for actor, actions in ((self.maker,('prepare','view')),(self.checker,('review','view'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
                codename__in=[f'{action}_budget_summary_actuals' for action in actions]))
        fixture = SimpleNamespace(maker=self.maker,fund=self.fund,budget_office=self.budget_office,
            operating_office=treasury,receipt_account=receipt,account=self.account,document=SummaryActualTests().document)
        prior_args = SummaryActualTests.arguments(fixture,period_start=date(2025,1,1),period_end=date(2025,12,31),
            receipt_total='0',expenditure_total='0',rows=[
                {'kind':'receipt','category':'service','account_id':None,'amount':'0','source_row':'prior R0'},
                {'kind':'expenditure','category':'mooe','account_id':None,'amount':'0','source_row':'prior E0'}])
        half_args = SummaryActualTests.arguments(fixture,expenditure_total='100')
        half_args['rows'][1]['amount']='100'
        sources = [summary_actuals.review(summary_actuals.propose(**args),self.checker,approve=True,
            note='Verified synthetic source',authority='Independent designation',verified_documents=True)
            for args in (prior_args,half_args)]
        self.preparation = dict(proposal=self.version,actor=self.preparer,prior_id=sources[0].public_id,
            half_id=sources[1].public_id,form_ids=[self.form.public_id],expected_offices=[self.form.office_id],
            entity_key='general',coverage_reference='Synthetic complete entity/office designation',expected_latest=0)

    def test_competing_creation_and_reviews_retain_one_version_and_decision(self):
        results = self.race(lambda _: 'prepared' if service.prepare(**self.preparation) else 'missing')
        self.assertEqual(results.count('prepared'),1,results)
        self.assertEqual(BudgetSummaryReconciliation.objects.count(),1)
        record = BudgetSummaryReconciliation.objects.get()
        results = self.race(lambda _: 'accepted' if service.review(record,self.reviewer,accept=True,
            note='Independent concurrent coverage review',authority='Designation') else 'missing')
        self.assertEqual(results.count('accepted'),1,results)
        record.refresh_from_db()
        self.assertEqual(record.status,'accepted')
        service.verify(record)

    def test_successor_and_acceptance_share_proposal_lock(self):
        record = service.prepare(**self.preparation)
        def action(number):
            if number==1:
                service.prepare(**(self.preparation|{'expected_latest':1}))
                return 'successor'
            service.review(record,self.reviewer,accept=True,note='Independent coverage review',authority='Designation')
            return 'accepted'
        results = self.race(action)
        self.assertIn('successor',results)
        record.refresh_from_db()
        if 'accepted' in results:
            self.assertEqual(record.status,'accepted')
            service.verify(record)
        else:
            self.assertEqual(record.status,'prepared')
            self.assertTrue(any('latest preparation' in result for result in results),results)
        successor = BudgetSummaryReconciliation.objects.get(version=2)
        service.review(successor,self.reviewer,accept=True,note='Independent successor review',authority='Designation')
        service.verify(BudgetSummaryReconciliation.objects.get(version=1))

    def test_conflicting_accept_and_return_decide_once(self):
        record = service.prepare(**self.preparation)
        def action(number):
            accept = number==1
            service.review(record,self.reviewer,accept=accept,note='Independent decision',authority='Designation')
            return 'accepted' if accept else 'returned'
        results = self.race(action)
        self.assertEqual(sum(value in ('accepted','returned') for value in results),1,results)
        record.refresh_from_db()
        self.assertIn(record.status,('accepted','returned'))
        service.verify(record)
