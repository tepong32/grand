from copy import deepcopy
from hashlib import sha256
import json
import uuid
from unittest.mock import patch

from django.contrib.auth.models import Permission, Group
from django.test import Client
from django.urls import reverse
from accounting.models import JournalEntry
from accounting.cash_classifications import checksum
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import test_form1_spa_reviews as fixtures, form1_spa_reviews as service
from . import test_form1_spa_proposals as signed_fixtures
from .models import Form1SPAReview as Record


class Form1SPAViewTests(fixtures.Form1SPAReviewFixture):
    signed_history=signed_fixtures.Form1SPAProposalTests.signed_history
    def url(self,name,*args): return reverse('budget:'+name,args=args)

    def create_http(self,**changes):
        self.client.force_login(self.preparer)
        url=self.url('form1_spa_prepare',self.account_record.public_id)
        page=self.client.get(url); self.assertEqual(page.status_code,200)
        _,parts,coverage=self.spa_inputs()
        data=dict(preview=page.context['form']['preview'].value(),parts=json.dumps(parts),
            coverage=json.dumps(coverage),coverage_reference='Synthetic whole-source coverage',
            reference='Synthetic original SPA authority',evidence=self.spa_document())
        data.update(changes)
        return self.client.post(url,data),data

    def test_guided_intake_two_roles_exact_downloads_and_no_posting(self):
        before=JournalEntry.objects.count()
        self.client.force_login(self.preparer)
        account_page=self.client.get(self.url('form1_account_detail',self.account_record.public_id))
        self.assertContains(account_page,'Prepare SPA subdivision review')
        response,_=self.create_http(); self.assertEqual(response.status_code,302)
        record=Record.objects.get()
        for actor,role in ((self.reviewer,'budget'),(self.checker,'accounting')):
            self.client.force_login(actor)
            page=self.client.get(response.url); self.assertEqual(page.context['roles'],[role])
            url=self.url('form1_spa_review',record.public_id,role)
            data=dict(action='approve',authority='Synthetic '+role,note='Independent treatment verification')
            self.assertEqual(self.client.post(url,data).status_code,409)
            self.assertEqual(self.client.post(url,dict(data,treatment_verified='on')).status_code,302)
        record.refresh_from_db(); self.assertEqual(record.status,'approved')
        page=self.client.get(response.url); self.assertContains(page,'Current sources checked')
        self.assertEqual(page.context['roles'],[])
        output=self.client.get(self.url('form1_spa_export',record.public_id,'json'))
        self.assertEqual(json.loads(output.content),service.snapshot(record,self.checker,export=True))
        self.assertEqual(output['X-GRAND-Export-SHA256'],sha256(output.content).hexdigest())
        self.assertEqual(self.client.get(self.url('form1_spa_export',record.public_id,'authority')).content,bytes(record.evidence))
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_actor_latest_preview_and_invalid_input_preserve_original_choices(self):
        response,data=self.create_http(reference='')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['editor']['coverage'],json.loads(data['coverage']))
        self.assertFalse(Record.objects.exists())
        response,data=self.create_http(); self.assertEqual(response.status_code,302)
        data['evidence']=self.spa_document()
        url=self.url('form1_spa_prepare',self.account_record.public_id)
        self.assertContains(self.client.post(url,data),'preview changed')
        self.reviewer.user_permissions.add(Permission.objects.get(content_type__app_label='budget',codename='prepare_form1_spa_reviews'))
        self.client.force_login(self.reviewer); data['evidence']=self.spa_document()
        self.assertContains(self.client.post(url,data),'another actor')
        self.assertEqual(Record.objects.count(),1)

    def test_role_csrf_uat_export_only_and_revoked_original_source(self):
        response,_=self.create_http(); record=Record.objects.get()
        self.client.force_login(self.checker)
        self.assertEqual(self.client.post(self.url('form1_spa_review',record.public_id,'budget'),{}).status_code,403)
        csrf=Client(enforce_csrf_checks=True); csrf.force_login(self.checker)
        self.assertEqual(csrf.post(self.url('form1_spa_review',record.public_id,'accounting'),{}).status_code,403)
        self.checker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        self.assertEqual(self.client.get(response.url).status_code,200)
        self.assertEqual(self.client.post(self.url('form1_spa_review',record.public_id,'accounting'),{}).status_code,403)
        self.checker.user_permissions.remove(*Permission.objects.filter(content_type__app_label='budget',codename__in=['view_form1_spa_reviews','view_form1_account_reviews']))
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='view_native_budget_actuals'))
        self.assertEqual(self.client.get(response.url).status_code,403)
        url=self.url('form1_spa_export',record.public_id,'json')
        self.assertEqual(self.client.get(url).status_code,200)
        for kind in ('flow-json','flow-pdf'):
            self.assertEqual(self.client.get(self.url('form1_spa_export',record.public_id,kind)).status_code,200)
        self.checker.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename='export_native_budget_actuals'))
        self.assertEqual(self.client.get(url).status_code,403)
        for kind in ('flow-json','flow-pdf'):
            self.assertEqual(self.client.get(self.url('form1_spa_export',record.public_id,kind)).status_code,403)

    def test_all_history_versions_paginate_and_missing_coverage_remains_unknown(self):
        _,parts,coverage=self.spa_inputs(); coverage[0]['coverage']='missing'
        record=self.prepare_spa(parts=parts,coverage=coverage)
        self.client.force_login(self.reviewer)
        page=self.client.get(self.url('form1_spa_detail',record.public_id))
        self.assertContains(page,'Unknown'); self.assertContains(page,'unresolved')
        copies=[]
        for version in range(2,53):
            item=deepcopy(record); item.pk=None; item.public_id=uuid.uuid4(); item.version=version
            item.payload=deepcopy(record.payload)
            item.payload['identity'].update(public_id=str(item.public_id),version=version)
            item.payload_checksum=checksum(item.payload); copies.append(item)
        Record.objects.bulk_create(copies)
        url=self.url('form1_spas')
        with patch.object(service,'_sources',wraps=service._sources) as source_checks:
            first=self.client.get(url); second=self.client.get(url,{'page':2})
        self.assertEqual(source_checks.call_count,2)
        self.assertEqual(first.context['page'].paginator.count,52)
        self.assertEqual(len(first.context['page']),50); self.assertEqual(len(second.context['page']),2)
        ids={row.pk for response in (first,second) for row in response.context['page']}
        self.assertEqual(ids,set(Record.objects.values_list('pk',flat=True)))
        self.assertEqual(self.client.get(url,{'status':'bad'}).status_code,400)
        self.assertEqual(self.client.get(url,{'q':str(record.public_id)}).context['page'].paginator.count,1)

    def test_genuine_signed_history_http_split_keeps_opposing_sources_and_class_control(self):
        self.signed_history()
        self.approved_forecast=self.version.receipt_forecasts.filter(status='approved').order_by('-version').first()
        allocations=self.account_allocations(self.targets['valid'])
        components={row['key']:row for row in self.inventory['payload']['components']}
        for row in allocations:
            if components[row['component']]['source_account'] is None: row['account_id']=None
        self.account_record=self.review_accounts(self.prepare_accounts(allocations=allocations,expected_latest=1))
        _,parts,coverage=self.spa_inputs()
        positive=next(row for row in parts if row['amount']=='10.00'); positive['amount']='6.00'
        parts.append(dict(positive,key='positive-four',amount='4.00',subdivision='ldrrm'))
        before=JournalEntry.objects.count()
        response,_=self.create_http(parts=json.dumps(parts),coverage=json.dumps(coverage))
        self.assertEqual(response.status_code,302)
        record=Record.objects.get(); record=self.approve_spa(record)
        self.client.force_login(self.checker)
        detail=self.client.get(response.url)
        self.assertContains(detail,'Original SPA class control'); self.assertContains(detail,'-4.00')
        self.assertEqual(len(detail.context['part_page']),3)
        self.assertEqual(sorted(row['original_amount'] for row in detail.context['part_page']),['-10.00','10.00','10.00'])
        retained=json.loads(self.client.get(self.url('form1_spa_export',record.public_id,'json')).content)
        self.assertEqual(retained,service.snapshot(record,self.checker,export=True))
        self.assertTrue(retained['independently_reviewed']); self.assertFalse(retained['form_issued'])
        self.assertEqual(JournalEntry.objects.count(),before)
