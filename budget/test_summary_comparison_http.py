"""Real two-store source creation and authorized comparison submission."""
from types import SimpleNamespace
from datetime import date
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.test import Client
from accounting import summary_actuals
from accounting.models import LedgerAccount, JournalEntry
from accounting.test_summary_actuals import SummaryActualTests
from departments.models import Department
from .test_office_forms import OfficeFormTests
from . import office_forms
from . import summary_reconciliations as reconciliation


class SummaryComparisonHTTPTests(OfficeFormTests):
    def test_real_sources_visibility_cohort_and_immutable_history(self):
        self.complete_proposal()
        first = office_forms.decide(item=office_forms.prepare(**self.form_args()), actor=self.reviewer,
            issue=True, note='Independent synthetic issue')
        second = office_forms.decide(item=office_forms.prepare(**self.form_args(expected_latest=1)), actor=self.reviewer,
            issue=True, note='Independent successor issue')
        treasury = Department.objects.create(name='Synthetic cohort Treasury', slug='cohort-treasury')
        receipt = LedgerAccount.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='COHORT-SERVICE', title='Synthetic receipt',
            account_type='revenue', normal_balance='credit')
        for actor, actions in ((self.maker, ('prepare', 'view')), (self.checker, ('review', 'view'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
                codename__in=[f'{action}_budget_summary_actuals' for action in actions]))
        fixture = SimpleNamespace(maker=self.maker, fund=self.fund, budget_office=self.budget_office,
            operating_office=treasury, receipt_account=receipt, account=self.account,
            document=SummaryActualTests().document)
        submitted = summary_actuals.propose(**SummaryActualTests.arguments(fixture))
        url = reverse('budget:summary_comparison', args=[second.public_id])
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(url, {'summary': submitted.public_id}).status_code, 404)
        adopted = summary_actuals.review(submitted, self.checker, approve=True, note='Independent source verification',
            authority='Synthetic adoption designation', verified_documents=True)
        url += '?summary=' + str(adopted.public_id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['result']['difference'], '40.00')
        data = {'office_forms': [second.pk], 'expected_offices': [second.office_id], 'entity_key': 'general',
            'coverage_reference': 'Synthetic complete office/entity designation', 'complete': 'on'}
        before = JournalEntry.objects.count()
        retained = (bytes(second.document), second.payload_checksum, adopted.payload_checksum)
        response = self.client.post(url, data)
        self.assertEqual(response.context['cohort']['difference'], '40.00')
        self.assertContains(response, 'Retained reconciliation and independent coverage review remain required')
        response = self.client.post(url, data | {'office_forms': [first.pk, second.pk]})
        self.assertContains(response, 'one issued version per office')
        response = self.client.post(url, data | {'expected_offices': [second.office_id, treasury.pk]})
        self.assertContains(response, 'exactly the declared expected offices')
        response = self.client.post(url, data | {'complete': ''})
        self.assertIsNone(response.context['cohort'])
        response = self.client.post(url, data | {'entity_key': 'enterprise:wrong'})
        self.assertContains(response, 'differs from the joint reporting entity')
        self.assertEqual(self.client.get(url.split('?')[0], {'summary': 'invalid'}).status_code, 404)
        self.client.force_login(self.checker)
        self.assertEqual(self.client.get(url).status_code, 403)
        second.refresh_from_db(); adopted.refresh_from_db()
        self.assertEqual((bytes(second.document), second.payload_checksum, adopted.payload_checksum), retained)
        self.assertEqual(JournalEntry.objects.count(), before)
        prior_args = SummaryActualTests.arguments(fixture, period_start=date(2025,1,1),period_end=date(2025,12,31),
            receipt_total='0',expenditure_total='0', rows=[
                {'kind':'receipt','category':'service','account_id':None,'amount':'0','source_row':'prior R0'},
                {'kind':'expenditure','category':'mooe','account_id':None,'amount':'0','source_row':'prior E0'}])
        prior = summary_actuals.review(summary_actuals.propose(**prior_args),self.checker,approve=True,
            note='Reviewed synthetic prior-year zero controls',authority='Synthetic independent designation',verified_documents=True)
        args = dict(proposal=self.version,actor=self.preparer,prior_id=prior.public_id,half_id=adopted.public_id,
            form_ids=[second.public_id],expected_offices=[second.office_id],entity_key='general',
            coverage_reference='Synthetic complete entity/office designation',expected_latest=0)
        record = reconciliation.prepare(**args)
        self.assertEqual(record.payload['schema'],2)
        self.assertEqual(record.payload['actuals']['half']['decision'],summary_actuals.decision_snapshot(adopted))
        self.assertEqual(record.payload['forms'][0]['decision'],office_forms.decision_payload(second))
        from copy import copy,deepcopy
        from accounting.cash_classifications import checksum
        for family in ('actuals','forms'):
            shadow = copy(record); shadow.payload = deepcopy(record.payload)
            source = shadow.payload['actuals']['half'] if family=='actuals' else shadow.payload['forms'][0]
            source['decision']['note']='Altered original review'
            shadow.payload_checksum=checksum(shadow.payload)
            with self.assertRaisesMessage(ValidationError,'original'):
                reconciliation.verify(shadow)
        legacy = copy(record); legacy.payload = deepcopy(record.payload); legacy.payload['schema']=1
        for source in list(legacy.payload['actuals'].values())+legacy.payload['forms']: source.pop('decision')
        legacy.payload_checksum=checksum(legacy.payload)
        self.assertEqual(reconciliation.verify(legacy)['schema'],1)
        self.assertEqual(record.payload['comparisons']['half']['difference'],'40.00')
        with self.assertRaisesMessage(ValidationError,'Resolve every class'):
            reconciliation.review(record,self.reviewer,accept=True,note='Review',authority='Designation')
        returned = reconciliation.review(record,self.reviewer,accept=False,note='Resolve source difference',authority='Designation')
        self.assertEqual(returned.status,'returned')
        with self.assertRaises(ValidationError): returned.delete()
        with self.assertRaises(ValidationError): reconciliation.prepare(**args)
        successor_args = SummaryActualTests.arguments(fixture,expected_latest=1,expenditure_total='100')
        successor_args['rows'][1]['amount']='100'
        corrected = summary_actuals.review(summary_actuals.propose(**successor_args),self.checker,approve=True,
            note='Reviewed matching synthetic source',authority='Designation',verified_documents=True)
        next_record = reconciliation.prepare(**(args|{'half_id':corrected.public_id,'expected_latest':1}))
        accepted = reconciliation.review(next_record,self.reviewer,accept=True,note='Verified both periods and complete office set',authority='Designation')
        self.assertEqual(accepted.status,'accepted')
        self.assertEqual(reconciliation.verify(returned)['actuals']['half']['id'],str(adopted.public_id))
        self.assertEqual(JournalEntry.objects.count(),before)
        self.client.force_login(self.preparer)
        preparation_url = reverse('budget:summary_reconciliation_prepare',args=[self.version.public_id])
        page = self.client.get(preparation_url)
        self.assertEqual(page.status_code,200)
        values = {'preview':page.context['form']['preview'].value(),'prior':prior.pk,'half':corrected.pk,
            'office_forms':[second.pk],'expected_offices':[second.office_id],
            'coverage_reference':'Synthetic independent office cohort designation','complete':'on'}
        response = self.client.post(preparation_url,values)
        self.assertEqual(response.status_code,302)
        from .models import BudgetSummaryReconciliation
        browser_record = BudgetSummaryReconciliation.objects.get(version=3)
        self.assertContains(self.client.post(preparation_url,values),'newer reconciliation preparation')
        detail_url = reverse('budget:summary_reconciliation_detail',args=[browser_record.public_id])
        detail = self.client.get(detail_url)
        self.assertContains(detail,'Pinned source versions')
        self.assertFalse(detail.context['can_review'])
        self.client.force_login(self.reviewer)
        review_url = reverse('budget:summary_reconciliation_review',args=[browser_record.public_id])
        self.assertEqual(self.client.post(review_url,{'action':'bogus'}).status_code,400)
        self.assertEqual(self.client.post(review_url,{'action':'accept','authority':'Synthetic review designation','note':'Verified complete cohort and both periods'}).status_code,302)
        self.assertEqual(self.client.post(review_url,{'action':'accept','authority':'x','note':'x'}).status_code,409)
        exported = self.client.get(reverse('budget:summary_reconciliation_export',args=[browser_record.public_id]))
        self.assertEqual(exported.status_code,200)
        import hashlib,json
        self.assertEqual(hashlib.sha256(exported.content).hexdigest(),exported['X-GRAND-Export-SHA256'])
        self.assertEqual(json.loads(exported.content)['decision']['status'],'accepted')
        self.assertContains(self.client.get(reverse('budget:summary_reconciliations',args=[self.version.public_id])),'All 3 versions')
        self.client.force_login(self.checker)
        self.assertEqual(self.client.get(detail_url).status_code,403)
        self.assertEqual(self.client.get(reverse('budget:summary_reconciliation_export',args=[browser_record.public_id])).status_code,403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.preparer)
        self.assertEqual(csrf_client.post(url, data).status_code, 403)
        self.client.force_login(self.preparer)
        type(adopted).objects.filter(pk=adopted.pk).update(payload_checksum='0' * 64)
        response = self.client.get(url)
        self.assertContains(response, 'Retained joint summary identity or evidence changed')
        self.assertIsNone(response.context['cohort'])
        self.assertIsNone(response.context['result'])
