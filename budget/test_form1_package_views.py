from copy import deepcopy

from django.contrib.auth.models import Group, Permission
from django.test import Client
from django.urls import reverse
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from .test_form1_package_reviews import Form1PackageReviewFixture
from .models import Form1PackageDecision
from . import form1_package_reviews as reviews, form1_packages as packages


class Form1PackageReviewViewTests(Form1PackageReviewFixture):
    def url(self, record, role='budget'):
        return reverse('budget:form1_package_review',args=[record.public_id,role])

    def data(self, role='budget', action='approve', verified='true'):
        data=dict(action=action,authority='Synthetic separate office designation',
            note='Independent inspection of the original sources and explicit findings')
        for key in reviews.CHECKS[role]:
            data[key+'_verified']=verified
            data[key+'_basis']='Synthetic original evidence inspection: '+key
        return data

    def test_three_office_http_decisions_retain_originals_and_no_financial_authority(self):
        record=self.retain();original=deepcopy(record.payload);before=JournalEntry.objects.count()
        for role,actor in self.reviewers.items():
            self.client.force_login(actor)
            detail=reverse('budget:form1_package_detail',args=[record.public_id])
            response=self.client.get(detail)
            self.assertEqual(response.status_code,200)
            self.assertEqual([item['role'] for item in response.context['decision_forms']],[role])
            self.assertContains(response,'Choose a finding')
            self.assertContains(response,self.url(record,role))
            response=self.client.post(self.url(record,role),self.data(role))
            self.assertRedirects(response,detail,fetch_redirect_response=False)
            self.assertEqual(self.client.get(detail).context['decision_forms'],[])
            self.assertEqual(record.decisions.get(role=role).actor_id,actor.pk)
        state=reviews.snapshot(record,self.reviewer)
        self.assertEqual(state['status'],'reviewed')
        for flag in ('statutorily_certified','chief_executive_approved','form_issued','cash_available'):
            self.assertIs(state[flag],False)
        self.assertEqual(packages.snapshot(record,self.reviewer)['payload'],original)
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_explicit_checks_missing_invalid_false_and_return_with_csrf(self):
        record=self.retain();self.client.force_login(self.reviewer)
        data=self.data();data.pop('stock_calendar_verified')
        response=self.client.post(self.url(record),data)
        self.assertEqual(response.status_code,409);self.assertContains(response,'This field is required',status_code=409)
        data=self.data();data['stock_calendar_verified']='yes'
        self.assertEqual(self.client.post(self.url(record),data).status_code,409)
        data=self.data(verified='false')
        response=self.client.post(self.url(record),data)
        self.assertEqual(response.status_code,409);self.assertContains(response,'every check verified',status_code=409)
        self.assertEqual(Form1PackageDecision.objects.count(),0)
        protected=Client(enforce_csrf_checks=True);protected.force_login(self.reviewer)
        self.assertEqual(protected.post(self.url(record),self.data(action='return',verified='false')).status_code,403)
        protected.get(reverse('budget:form1_package_detail',args=[record.public_id]))
        token=protected.cookies['csrftoken'].value
        response=protected.post(self.url(record),self.data(action='return',verified='false'),HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,302)
        row=record.decisions.get();original=deepcopy(row.payload)
        self.assertFalse(row.approve)
        self.assertTrue(all(check['verified'] is False for check in row.payload['checks'].values()))
        response=self.client.post(self.url(record),self.data())
        self.assertEqual(response.status_code,409)
        self.assertContains(response,'distinct designated officer',status_code=409)
        row.refresh_from_db();self.assertEqual(row.payload,original)
        self.assertEqual(Form1PackageDecision.objects.count(),1)

    def test_roles_maker_viewer_uat_source_revocation_and_http_methods(self):
        record=self.retain();detail=reverse('budget:form1_package_detail',args=[record.public_id])
        self.assertEqual(self.client.post(self.url(record),self.data()).status_code,302)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(self.url(record)).status_code,405)
        self.assertEqual(self.client.post(self.url(record,'chief_executive'),self.data()).status_code,400)
        data=self.data();data['action']='issue'
        self.assertEqual(self.client.post(self.url(record),data).status_code,400)
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(detail).context['decision_forms'],[])
        self.assertEqual(self.client.post(self.url(record),self.data()).status_code,403)
        grant=Permission.objects.get(content_type__app_label='budget',codename='review_form1_package_budget')
        self.preparer.user_permissions.add(grant)
        self.assertEqual(self.client.post(self.url(record),self.data()).status_code,409)
        self.client.force_login(self.treasurer)
        self.assertEqual(self.client.post(self.url(record),self.data()).status_code,403)
        self.treasurer.user_permissions.add(grant)
        self.assertEqual(self.client.post(self.url(record),self.data()).status_code,409)
        self.reviewer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(detail).context['decision_forms'],[])
        self.assertEqual(self.client.post(self.url(record),self.data()).status_code,403)
        self.reviewer.groups.clear()
        source=Permission.objects.get(content_type__app_label='budget',codename='view_budget_receipt_forecasts')
        self.reviewer.user_permissions.remove(source)
        self.assertEqual(self.client.post(self.url(record),self.data()).status_code,403)
        self.assertEqual(Form1PackageDecision.objects.count(),0)

    def test_stale_sources_block_approval_but_retain_independent_return(self):
        record=self.retain();original=deepcopy(record.payload)
        self.prepare_forecast(expected_latest=1)
        self.client.force_login(self.reviewer)
        response=self.client.post(self.url(record),self.data())
        self.assertEqual(response.status_code,409);self.assertContains(response,'current original sources',status_code=409)
        self.assertEqual(Form1PackageDecision.objects.count(),0)
        self.assertEqual(self.client.post(self.url(record),self.data(action='return')).status_code,302)
        self.assertEqual(reviews.snapshot(record,self.reviewer)['status'],'returned')
        self.assertEqual(packages.snapshot(record,self.reviewer)['payload'],original)

    def test_unknown_coverage_cannot_be_approved_with_all_checks_verified(self):
        ph,documents=self.ph_draft(attach=False)
        record=self.retain(envelope=self.assembled(philhealth_source=ph,documents=documents),documents=documents)
        self.client.force_login(self.checker)
        response=self.client.post(self.url(record,'accounting'),self.data('accounting'))
        self.assertEqual(response.status_code,409);self.assertContains(response,'complete package',status_code=409)
        self.assertEqual(Form1PackageDecision.objects.count(),0)
        self.assertEqual(self.client.post(self.url(record,'accounting'),self.data('accounting',action='return')).status_code,302)
        self.assertFalse(record.decisions.get().approve)
