from copy import deepcopy
from hashlib import sha256
import json
from django.contrib.auth.models import Permission, Group
from django.test import Client
from django.urls import reverse
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_account_reviews as fixtures
from . import form1_account_reviews as service, form1_account_views as views
from . import receipt_forecasts, form1_components, form1_flows
from .models import Form1AccountReview as Record


class Form1AccountViewTests(fixtures.Form1AccountReviewFixture):
    def url(self,name,*args): return reverse('budget:'+name,args=args)

    def clerk_rows(self):
        return [dict(row,account_id=str(row['account_id']) if row['account_id'] else '')
            for row in self.account_allocations(self.targets['valid'])]

    def create_http(self,**changes):
        self.client.force_login(self.preparer)
        url=self.url('form1_account_prepare',self.approved_forecast.public_id)
        page=self.client.get(url); self.assertEqual(page.status_code,200)
        data=dict(preview=page.context['form']['preview'].value(),allocation=json.dumps(self.clerk_rows()),
            coverage_reference='Synthetic complete clerk selections',code_reference='Synthetic code authority only',
            evidence=self.code_document())
        data.update(changes)
        return self.client.post(url,data),data

    def test_guided_intake_independent_decision_original_downloads_and_no_posting(self):
        before=JournalEntry.objects.count()
        response,data=self.create_http(); self.assertEqual(response.status_code,302)
        record=Record.objects.get()
        self.assertContains(self.client.get(response.url),'SYNTHETIC-valid')
        self.client.force_login(self.checker)
        review=self.url('form1_account_review',record.public_id)
        invalid=self.client.post(review,dict(action='approve',authority='Synthetic Accountant',note='Independent review'))
        self.assertEqual(invalid.status_code,409); self.assertContains(invalid,'explicitly verify',status_code=409)
        self.assertEqual(self.client.post(review,dict(action='approve',authority='Synthetic Accountant',note='Independent review',codes_verified='on')).status_code,302)
        record.refresh_from_db(); self.assertEqual(record.status,'approved')
        response=self.client.get(self.url('form1_account_export',record.public_id,'json'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(json.loads(response.content),service.snapshot(record,self.checker,export=True))
        self.assertEqual(response['X-GRAND-Export-SHA256'],sha256(response.content).hexdigest())
        response=self.client.get(self.url('form1_account_export',record.public_id,'authority'))
        self.assertEqual(response.content,bytes(record.evidence)); self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_preview_actor_latest_binding_preserved_choices_and_eligible_account_dates(self):
        response,data=self.create_http(code_reference='')
        self.assertEqual(response.status_code,200); self.assertEqual(response.context['editor']['allocation'],self.clerk_rows())
        self.assertFalse(Record.objects.exists())
        for row in response.context['editor']['components']:
            self.assertNotIn(str(self.revenue.pk),row['eligible_accounts'])
            if row['identity']['column']=='proposed':
                self.assertNotIn(str(self.targets['late'].pk),row['eligible_accounts'])
                self.assertNotIn(str(self.targets['retired'].pk),row['eligible_accounts'])
        response,data=self.create_http(); self.assertEqual(response.status_code,302)
        data['evidence']=self.code_document()
        self.assertContains(self.client.post(self.url('form1_account_prepare',self.approved_forecast.public_id),data),'preview changed')
        self.reviewer.user_permissions.add(*Permission.objects.filter(content_type__app_label='budget',
            codename__in=['prepare_form1_account_reviews','view_budget_receipt_forecasts']))
        self.client.force_login(self.reviewer); data['evidence']=self.code_document()
        self.assertContains(self.client.post(self.url('form1_account_prepare',self.approved_forecast.public_id),data),'another actor')
        self.assertEqual(Record.objects.count(),1)

    def test_ownership_csrf_uat_and_export_only_source_access(self):
        response,data=self.create_http(); record=Record.objects.get()
        self.client.force_login(self.maker)
        self.assertEqual(self.client.get(response.url).status_code,403)
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(response.url).status_code,200)
        self.assertEqual(self.client.get(self.url('form1_account_prepare',self.approved_forecast.public_id)).status_code,403)
        self.client.force_login(self.checker)
        csrf=Client(enforce_csrf_checks=True); csrf.force_login(self.checker)
        self.assertEqual(csrf.post(self.url('form1_account_review',record.public_id),dict(action='return',authority='Designation',note='Return')).status_code,403)
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='budget',codename='view_form1_account_reviews'))
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals'))
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(response.url).status_code,403)
        export=self.url('form1_account_export',record.public_id,'json')
        self.assertEqual(self.client.get(export).status_code,200)
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='export_native_budget_actuals'))
        self.assertEqual(self.client.get(export).status_code,403)

    def test_complete_register_filters_and_second_page_without_hidden_cap(self):
        for index in range(55): self.prepare_accounts(expected_latest=index)
        self.client.force_login(self.checker)
        url=self.url('form1_accounts')
        page=self.client.get(url,dict(q=self.fund.code,status='prepared',page=2))
        self.assertEqual(page.status_code,200); self.assertEqual(page.context['page'].paginator.count,55)
        self.assertEqual(len(page.context['page'].object_list),5)
        self.assertEqual(self.client.get(url,dict(status='invented')).status_code,400)
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals'))
        self.assertEqual(self.client.get(url).context['page'].paginator.count,0)

    def test_real_forecast_splits_complete_editor_detail_pages_and_navigation(self):
        half=[self.component('half-'+str(index),'worksheet','1',coverage_key='half-'+str(index)) for index in range(30)]
        args=self.inputs(half_components=half); args['coverage']['half_estimate']=self.coverage(half)
        self.forecast=receipt_forecasts.propose(self.captured,**args)
        self.approved_forecast=self.review_forecast(self.prepare_forecast(expected_latest=1))
        self.inventory=form1_components.inventory(form1_flows.capture(forecast=self.approved_forecast,actor=self.preparer))
        self.client.force_login(self.preparer)
        response=self.client.get(self.url('form1_account_prepare',self.approved_forecast.public_id))
        self.assertEqual(len(response.context['editor']['components']),34)
        self.assertContains(response,'form1-accounts.js')
        forecast_detail=self.client.get(self.url('receipt_forecast_detail',self.approved_forecast.public_id))
        self.assertContains(forecast_detail,'Select reporting accounts for Accounting review')
        response,_=self.create_http(); self.assertEqual(response.status_code,302)
        second=self.client.get(response.url,dict(page=2))
        self.assertEqual(second.context['page'].paginator.count,34)
        self.assertEqual(len(second.context['page'].object_list),9)
