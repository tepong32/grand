import csv
import io
import json
import zipfile
from hashlib import sha256
from django.contrib.auth.models import Permission, Group
from django.test import Client
from django.core.management import call_command
from django.urls import reverse
from .test_budget_actuals_certifications import NativeActualsCertificationTests
from . import budget_actuals_certifications as certifications
from .models import NativeBudgetActualsPreparation, NativeBudgetActualsDecision
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP


class NativeActualsViewTests(NativeActualsCertificationTests):
    def url(self,name,record=None,**kwargs):
        if record: kwargs['public_id']=record.public_id
        return reverse('accounting:native_actuals_'+name,kwargs=kwargs)

    def scope_data(self):
        return dict(fund=self.receipt_fund.pk,budget_department=self.budget_office.pk,
            treasury_department=self.treasury.pk,year=2026,period='h1',entity_type='general',
            enterprise_reference='',entity_label='Synthetic complete General Fund')

    def test_guided_preparation_review_joint_decisions_and_complete_exports(self):
        self.client.force_login(self.preparer)
        response=self.client.get(self.url('create'),self.scope_data())
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['captured']['payload']['classification_complete'])
        form=response.context['form']
        data=self.scope_data() | dict(expected_source_checksum=form.initial['expected_source_checksum'],
            expected_latest=0,entity_basis='Entire named Fund',coverage_basis='All source lines reviewed',
            reference='Synthetic reconciliation',authority='Synthetic preparation authority',reason='Complete categories')
        self.assertEqual(self.client.post(self.url('create'),data).status_code,400)
        self.assertFalse(NativeBudgetActualsPreparation.objects.exists())
        data['confirmed']='on'
        response=self.client.post(self.url('create'),data)
        self.assertEqual(response.status_code,302)
        record=NativeBudgetActualsPreparation.objects.get()
        self.assertEqual(self.client.get(self.url('detail',record)).status_code,200)
        self.client.force_login(self.validator)
        decision=dict(outcome='approve',authority='Independent review authority',note='Reviewed all sources')
        self.assertEqual(self.client.get(self.url('review',record)).status_code,405)
        self.assertEqual(self.client.post(self.url('review',record),decision).status_code,400)
        decision['verified']='on'
        self.assertEqual(self.client.post(self.url('review',record),decision).status_code,302)
        self.assertEqual(self.client.post(self.url('review',record),decision).status_code,409)
        decision['outcome']='certify'
        self.assertEqual(self.client.post(self.url('decide',record,role='accountant'),decision).status_code,302)
        self.client.force_login(self.treasury_user)
        response=self.client.get(self.url('detail',record))
        self.assertEqual(response.status_code,200)
        self.assertEqual([row['role'] for row in response.context['decision_forms']],['treasurer'])
        self.assertEqual(self.client.post(self.url('decide',record,role='treasurer'),decision).status_code,302)
        response=self.client.get(self.url('detail',record),dict(source_q='No matches',tb_q='No matches'))
        self.assertEqual(response.status_code,200); self.assertTrue(response.context['current'])
        self.assertEqual(len(response.context['sources']),0)
        self.assertEqual(len(response.context['rows']),26)
        snapshot=self.client.get(self.url('export',record,kind='snapshot'),dict(source_q='No matches'))
        self.assertEqual(snapshot.status_code,200)
        self.assertEqual(certifications.verify_snapshot(json.loads(snapshot.content))['totals']['receipt'],'100.00')
        first=self.client.get(self.url('export',record,kind='package'))
        second=self.client.get(self.url('export',record,kind='package'),dict(source_q='No matches',tb_page=99))
        self.assertEqual(first.status_code,200); self.assertEqual(first.content,second.content)
        self.assertEqual(first['X-GRAND-Export-SHA256'],sha256(first.content).hexdigest())
        with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
            self.assertEqual(archive.read('joint-evidence.json'),snapshot.content)
            rows=list(csv.reader(io.StringIO(archive.read('category-coverage.csv').decode('utf-8-sig'))))
            self.assertEqual(len(rows),27)
            tb=list(csv.reader(io.StringIO(archive.read('fund-trial-balance.csv').decode('utf-8-sig'))))
            self.assertEqual(len(tb),3)
            self.assertTrue(any(row[5]=='-100.00' for row in tb[1:]))
            bridge=list(csv.reader(io.StringIO(archive.read('source-movements.csv').decode('utf-8-sig'))))
            self.assertEqual(len(bridge),6)
            self.assertEqual([row[5] for row in bridge[1:] if row[0]=='Receipt'],['60.00','40.00','-100.00'])

    def test_http_scope_roles_uat_csrf_and_export_only(self):
        record=self.reviewed_preparation()
        self.client.force_login(self.treasury_user)
        self.assertEqual(self.client.post(self.url('review',record),{}).status_code,403)
        self.assertEqual(self.client.post(self.url('decide',record,role='accountant'),{}).status_code,403)
        csrf=Client(enforce_csrf_checks=True); csrf.force_login(self.treasury_user)
        self.assertEqual(csrf.post(self.url('decide',record,role='treasurer'),{}).status_code,403)
        group,_=Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)
        self.treasury_user.groups.add(group)
        self.assertEqual(self.client.post(self.url('decide',record,role='treasurer'),{}).status_code,403)
        self.assertEqual(self.client.get(self.url('detail',record)).status_code,200)
        self.treasury_user.groups.remove(group)
        self.treasury_user.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals'))
        self.assertEqual(self.client.get(self.url('detail',record)).status_code,403)
        self.assertEqual(self.client.get(self.url('export',record,kind='snapshot')).status_code,200)
        self.assertEqual(self.client.get(self.url('export',record,kind='unknown')).status_code,404)

    def test_stale_guard_and_successor_scope(self):
        self.client.force_login(self.preparer)
        response=self.client.get(self.url('create'),self.scope_data()); form=response.context['form']
        data=self.scope_data() | dict(expected_source_checksum=form.initial['expected_source_checksum'],
            expected_latest=0,entity_basis='Complete entity',coverage_basis='Full period evidence',
            reference='Reconciliation',authority='Authority',reason='Reason',confirmed='on')
        self.post_source(self.new_receipt('HTTP-LATER'))
        self.assertEqual(self.client.post(self.url('create'),data).status_code,400)
        self.assertFalse(NativeBudgetActualsPreparation.objects.exists())
        # The new source lacks reviewed partitions; it must not acquire implicit zeros.
        response=self.client.get(self.url('create'),self.scope_data())
        self.assertIsNone(response.context['form'])
        self.assertContains(response,'Source classification is incomplete')

    def test_dedicated_role_configuration_and_scope_locked_successor(self):
        record=self.reviewed_preparation()
        call_command('configure_finance_roles',stdout=io.StringIO())
        self.treasury_user.user_permissions.clear()
        self.treasury_user.groups.add(Group.objects.get(name='Budget Actuals Treasurer Certifier'))
        self.client.force_login(self.treasury_user)
        self.assertContains(self.client.get(reverse('accounting:workspace')),'Receipt and expenditure actuals')
        self.assertEqual(self.client.get(self.url('register')).status_code,200)
        self.assertEqual(self.client.get(self.url('detail',record)).status_code,200)
        self.assertEqual(self.client.get(self.url('create')).status_code,403)
        for name in ('Accounting Reviewer','Treasury Collection Officer','Treasury Disbursement Officer'):
            self.assertFalse(Group.objects.get(name=name).permissions.filter(codename__in=(
                'certify_accountant_native_budget_actuals','certify_treasurer_native_budget_actuals')).exists())
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(self.url('successor',record)).status_code,200)
        data=self.scope_data(); data['entity_label']='Changed scope'
        response=self.client.post(self.url('successor',record),data)
        self.assertEqual(response.status_code,400)
        self.assertContains(response,'A successor must retain',status_code=400)
