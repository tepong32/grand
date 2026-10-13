import json
from copy import deepcopy
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from accounting.models import JournalEntry
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP, FINANCE_ROLE_PERMISSIONS
from .test_form1_packages import Form1PackageFixture
from .models import Form1Package
from . import form1_packages as packages


class Form1PackageIntakeTests(Form1PackageFixture):
    def url(self): return reverse('budget:form1_package_prepare', args=[self.spa_record.public_id])

    def upload(self, name, data): return SimpleUploadedFile(name, data)

    def input(self, *, unknown=False, changed_bytes=False):
        data = dict(action='preview', boundary_basis='Annual January reference, explicit separate semester cash boundaries')
        for column, choice in self.selections[0]['opening'].items():
            prefix='opening-0-'+column+'-'
            if unknown:
                data[prefix+'kind']='missing'; data[prefix+'missing_basis']='Original cash evidence not yet available'
                continue
            data[prefix+'kind']=choice['kind']
            actual=choice['source'] if choice['kind']=='actual' else choice['source']['payload']['source']
            data[prefix+'source']=actual['payload']['route']+':'+actual['payload']['public_id']
            if choice['kind']=='forecast':
                source=choice['source']['payload']
                for key,value in source['inputs'].items():
                    if key in ('target_date','target_boundary'): continue
                    data[prefix+key]=json.dumps(value) if isinstance(value,(list,bool)) else value
                original=self.evidence[choice['source']['checksum']]+(b'changed' if changed_bytes else b'')
                data[prefix+'worksheet']=self.upload(source['evidence']['name'], original)
        return data

    def treatments(self, response, *, unknown=False):
        editor=response.context['editor']; self.assertIsNotNone(editor)
        return dict(parts=json.dumps([dict(key='http-'+str(index),source=row['key'],amount=row['amount'],
            treatment='unresolved' if unknown else 'deduct' if row['kind']=='receipt' else 'other',
            counterpart='',basis='Explicit original funding treatment') for index,row in enumerate(editor['catalog'])]),
            coverage=json.dumps([dict(entity=row['entity'],column=row['column'],kind=row['kind'],
                coverage='missing' if unknown else 'complete',basis='Whole original source coverage') for row in editor['matrix']]),
            coverage_reference='Original policy and overlap reconciliation',reference='Synthetic first whole draft',
            authority=self.upload('policy.pdf',b'%PDF-1.4\nSynthetic policy'),
            reconciliation=self.upload('overlap.pdf',b'%PDF-1.4\nSynthetic worksheet'))

    def preview(self, **kwargs):
        self.client.force_login(self.preparer)
        response=self.client.post(self.url(),self.input(**kwargs))
        self.assertEqual(response.status_code,200, response.content.decode()[:2000])
        self.assertEqual(Form1Package.objects.count(),0)
        return response

    def retain_data(self, response, **kwargs):
        data=self.input(**kwargs); data.update(self.treatments(response, unknown=kwargs.get('unknown',False)))
        data.update(action='retain',preview=response.context['treatment']['preview'].value())
        return data

    def test_first_complete_package_http_sources_bytes_and_no_authority(self):
        self.preparer.user_permissions.clear(); self.preparer.groups.clear()
        for permission in FINANCE_ROLE_PERMISSIONS['Budget Form 1 Package Preparer']:
            app,code=permission.split('.')
            self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label=app,codename=code))
        self.client.force_login(self.preparer); before=JournalEntry.objects.count()
        source_original=deepcopy(self.spa_record.payload)
        response=self.client.get(self.url()); self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.context['openings']),4)
        self.assertContains(response,'Choose a source treatment')
        self.assertNotContains(response,'Retain draft for independent office reviews')
        self.assertContains(self.client.get(reverse('budget:form1_spa_detail',args=[self.spa_record.public_id])),self.url())
        response=self.preview(); data=self.retain_data(response)
        response=self.client.post(self.url(),data)
        self.assertEqual(response.status_code,302,response.content.decode()[:2000])
        record=Form1Package.objects.get()
        self.assertEqual(record.version,1); self.assertEqual(record.spa_review_id,self.spa_record.pk)
        body=packages.snapshot(record,self.preparer)['payload']['assembly']['payload']
        self.assertTrue(body['calculation_coverage_complete'])
        self.assertEqual(body['members'][0]['net_ending'],self.envelope['payload']['members'][0]['net_ending'])
        self.assertEqual(len(record.attachments.all()),4)
        for key,data in self.evidence.items():
            self.assertEqual(packages.attachment_bytes(record,self.preparer,'cash:'+key),data)
        self.assertFalse(record.decisions.exists())
        for flag in ('independently_reviewed','stock_complete','philhealth_deduction_complete','form_issued','cash_available'):
            self.assertIs(body[flag],False)
        self.spa_record.refresh_from_db(); self.assertEqual(self.spa_record.payload,source_original)
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_unknown_first_package_cannot_certify_missing_coverage(self):
        response=self.preview(unknown=True); data=self.retain_data(response,unknown=True)
        data.pop('authority'); data.pop('reconciliation')
        bad=dict(data); coverage=json.loads(data['coverage']); coverage[0]['coverage']='complete'
        bad['coverage']=json.dumps(coverage)
        # The first coverage row is a receipt, so choose missing restriction explicitly.
        for row in coverage:
            if row['kind']=='restriction': row['coverage']='complete'; break
        bad['coverage']=json.dumps(coverage)
        self.assertEqual(self.client.post(self.url(),bad).status_code,409)
        self.assertEqual(Form1Package.objects.count(),0)
        response=self.client.post(self.url(),data); self.assertEqual(response.status_code,302)
        body=Form1Package.objects.get().payload['assembly']['payload']
        self.assertFalse(body['calculation_coverage_complete'])
        self.assertTrue(all(value is None for value in body['members'][0]['net_ending'].values()))

    def test_actor_expiry_tamper_changed_bytes_and_version_block_retention(self):
        response=self.preview(); token=response.context['treatment']['preview'].value()
        data=self.retain_data(response); data['preview']=token+'tampered'
        self.assertEqual(self.client.post(self.url(),data).status_code,409)
        from django.core import signing
        signed=signing.loads(token,salt='form1-whole-preparation-preview-v1'); signed['actor']=self.checker.pk
        data=self.retain_data(response); data['preview']=signing.dumps(signed,salt='form1-whole-preparation-preview-v1')
        self.assertEqual(self.client.post(self.url(),data).status_code,409)
        data=self.retain_data(response)
        with patch('django.core.signing.time.time',return_value=4102444800):
            self.assertEqual(self.client.post(self.url(),data).status_code,409)
        self.assertEqual(self.client.post(self.url(),self.retain_data(response,changed_bytes=True)).status_code,409)
        original=self.retain()
        self.assertEqual(self.client.post(self.url(),self.retain_data(response)).status_code,409)
        self.assertEqual(Form1Package.objects.count(),1); self.assertEqual(original.version,1)

    def test_invalid_boundaries_worksheet_partition_and_actions_have_no_writes(self):
        self.client.force_login(self.preparer)
        data=self.input(); data['opening-0-prior_amount-source']=data['opening-0-half_amount-source']
        self.assertEqual(self.client.post(self.url(),data).status_code,409)
        data=self.input(); data.pop('opening-0-estimate-no_cash_changes')
        self.assertEqual(self.client.post(self.url(),data).status_code,409)
        data=self.input(); data['opening-0-proposed-kind']='actual'
        self.assertEqual(self.client.post(self.url(),data).status_code,409)
        data=self.input(); data['opening-0-estimate-cash_changes']='{"unexpected":1}'
        self.assertEqual(self.client.post(self.url(),data).status_code,409)
        data=self.input(); data['action']='issue'; self.assertEqual(self.client.post(self.url(),data).status_code,400)
        response=self.preview(); data=self.retain_data(response)
        parts=json.loads(data['parts']); parts[0]['amount']='999.00'; data['parts']=json.dumps(parts)
        self.assertEqual(self.client.post(self.url(),data).status_code,409)
        self.assertEqual(Form1Package.objects.count(),0)

    def test_unauthorized_office_uat_source_revocation_and_csrf(self):
        self.assertEqual(self.client.get(self.url()).status_code,302)
        self.client.force_login(self.checker); self.assertEqual(self.client.get(self.url()).status_code,403)
        self.preparer.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.client.force_login(self.preparer); self.assertEqual(self.client.get(self.url()).status_code,403)
        self.preparer.groups.clear()
        response=self.preview()
        self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='budget',codename='view_budget_receipt_forecasts'))
        self.assertEqual(self.client.post(self.url(),self.retain_data(response)).status_code,403)
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',codename='view_budget_receipt_forecasts'))
        protected=Client(enforce_csrf_checks=True); protected.force_login(self.preparer)
        self.assertEqual(protected.post(self.url(),self.input()).status_code,403)
        self.assertEqual(Form1Package.objects.count(),0)

    def test_source_successor_blocks_old_preview_but_preserves_history(self):
        response=self.preview()
        self.cash(date(2025,1,1),expected_latest=1)
        self.assertEqual(self.client.post(self.url(),self.retain_data(response)).status_code,409)
        self.prepare_forecast(expected_latest=1)
        self.assertEqual(self.client.post(self.url(),self.retain_data(response)).status_code,409)
        self.assertEqual(Form1Package.objects.count(),0)
