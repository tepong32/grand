import io,json
from datetime import date
from hashlib import sha256
from django.contrib.auth.models import Group,Permission
from django.core.management import call_command
from django.test import Client
from django.contrib.staticfiles import finders
from django.urls import reverse
from .test_budget_receipt_attributions import ReceiptAttributionTests
from . import budget_receipt_attributions as service
from .models import BudgetReceiptAttributionBatch as Batch,JournalEntry,Fund
from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from vouchers.collection_corrections import propose as correction
from vouchers.collections import record_receipt


class ReceiptClassificationViewTests(ReceiptAttributionTests):
    def url(self,name,**kwargs): return reverse('accounting:receipt_classification_'+name,kwargs=kwargs)
    def scope(self): return dict(fund=self.receipt_fund.pk,start='2026-09-01',end='2026-09-30')

    def post_data(self,entry,rows=None):
        response=self.client.get(self.url('prepare',entry_id=entry.pk),self.scope())
        self.assertEqual(response.status_code,200)
        form=response.context['form']
        return self.scope() | dict(expected_source_checksum=form.initial['expected_source_checksum'],
            expected_latest=form.initial['expected_latest'],reason='Synthetic complete source treatment',
            evidence_reference='Synthetic journal reconciliation',confirmed='on',
            rows=json.dumps(rows if rows is not None else self.rows(self.inventory(),entry.pk,receipt=True)))

    def test_guided_split_review_full_export_and_deposit_exclusion(self):
        self.assertIsNotNone(finders.find('accounting/budget-receipt-components.js'))
        receipt=self.capture(); entry=self.post_source(receipt)
        deposit=self.post_source(self.deposit(receipt,'100','HTTP-TRANSFER'))
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(self.url('sources'),self.scope()).context['page'].paginator.count,2)
        data=self.post_data(entry)
        self.assertEqual(self.client.post(self.url('prepare',entry_id=entry.pk),dict(data,confirmed='')).status_code,400)
        self.assertEqual(Batch.objects.count(),0)
        response=self.client.post(self.url('prepare',entry_id=entry.pk),data)
        self.assertEqual(response.status_code,302); batch=Batch.objects.get()
        detail=self.client.get(self.url('detail',batch_id=batch.public_id))
        self.assertEqual(detail.status_code,200); self.assertEqual(detail.context['count'],3)
        self.assertIsNone(detail.context['review_form'])
        self.assertEqual(self.client.post(self.url('review',batch_id=batch.public_id),dict(outcome='approve',note='Maker attempt',confirmed='on')).status_code,409)
        self.client.force_login(self.validator)
        decision=dict(outcome='approve',note='Checked all original source components')
        self.assertEqual(self.client.get(self.url('review',batch_id=batch.public_id)).status_code,405)
        self.assertEqual(self.client.post(self.url('review',batch_id=batch.public_id),decision).status_code,400)
        decision['confirmed']='on'
        self.assertEqual(self.client.post(self.url('review',batch_id=batch.public_id),decision).status_code,302)
        self.assertEqual(self.client.post(self.url('review',batch_id=batch.public_id),decision).status_code,409)
        response=self.client.get(self.url('export',batch_id=batch.public_id),dict(q='No match',page=99))
        self.assertEqual(response.status_code,200); body=service.verify_snapshot(json.loads(response.content))
        self.assertEqual(len(body['members'][0]['partition']['payload']['allocations']),3)
        self.assertEqual(response['X-GRAND-Export-SHA256'],sha256(response.content).hexdigest())
        filtered=self.client.get(self.url('detail',batch_id=batch.public_id),dict(q='No match'))
        self.assertEqual(len(filtered.context['page']),0); self.assertEqual(filtered.context['count'],3)
        self.client.force_login(self.preparer)
        rows=self.rows(self.inventory(),deposit.pk,receipt=False); data=self.post_data(deposit,rows)
        self.assertEqual(self.client.post(self.url('prepare',entry_id=deposit.pk),data).status_code,302)
        self.assertEqual(JournalEntry.objects.count(),2)

    def test_bad_components_stale_source_scope_uat_csrf_and_export_only(self):
        receipt=self.capture(); entry=self.post_source(receipt); self.client.force_login(self.preparer)
        data=self.post_data(entry)
        for rows in ([],[dict(line_id=entry.lines.first().pk,amount='NaN',disposition='include',purpose='receipt',category='service',basis='Invalid amount')],
            [dict(line_id=999999,amount='100',disposition='exclude',purpose='counterpart',category='',basis='Wrong original line')]):
            self.assertEqual(self.client.post(self.url('prepare',entry_id=entry.pk),dict(data,rows=json.dumps(rows))).status_code,400)
        self.assertEqual(Batch.objects.count(),0)
        later=record_receipt(actor=self.treasury_user,variant=self.transaction_variant,received_on=date(2026,9,12),
            fund_code='general-fund',receipt_book='SYNTHETIC',receipt_number='HTTP-LATER',received_amount='100',
            payer_reference='Synthetic later payor',evidence_reference='Synthetic authority')
        self.post_source(later)
        self.assertEqual(self.client.post(self.url('prepare',entry_id=entry.pk),data).status_code,400)
        self.assertEqual(Batch.objects.count(),0)
        fresh=self.post_data(entry)
        self.assertEqual(self.client.post(self.url('prepare',entry_id=entry.pk),fresh).status_code,302)
        batch=Batch.objects.get()
        csrf=Client(enforce_csrf_checks=True); csrf.force_login(self.validator)
        self.assertEqual(csrf.post(self.url('review',batch_id=batch.public_id),dict(outcome='approve',note='Review',confirmed='on')).status_code,403)
        group,_=Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP); self.preparer.groups.add(group)
        self.assertEqual(self.client.post(self.url('prepare',entry_id=entry.pk),fresh).status_code,403)
        self.assertEqual(self.client.get(self.url('detail',batch_id=batch.public_id)).status_code,200)
        self.preparer.groups.remove(group)
        for code in ('view','prepare','review'):
            self.preparer.user_permissions.remove(Permission.objects.get(content_type__app_label='accounting',codename=code+'_budget_receipt_attributions'))
        self.assertEqual(self.client.get(self.url('detail',batch_id=batch.public_id)).status_code,403)
        self.assertEqual(self.client.get(self.url('export',batch_id=batch.public_id)).status_code,200)
        self.client.force_login(self.treasury_user)
        self.assertEqual(self.client.get(self.url('sources'),self.scope()).status_code,403)
        self.treasury_user.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=('view_budget_receipt_attributions','export_budget_receipt_attributions')))
        self.assertEqual(self.client.get(self.url('detail',batch_id=batch.public_id)).status_code,404)
        self.assertEqual(self.client.get(self.url('export',batch_id=batch.public_id)).status_code,404)

    def test_explicit_reversal_pairs_inherit_complete_approved_original(self):
        receipt=self.capture(); entry=self.post_source(receipt); inventory=self.inventory()
        original=self.decide(service.propose_batch(**self.args([self.member_args(inventory,entry)])))
        reversal=self.post_source(correction(original=receipt,actor=self.treasury_user,corrected_on=date(2026,9,13),
            reason='Synthetic correction'))
        self.client.force_login(self.preparer)
        response=self.client.get(self.url('prepare',entry_id=reversal.pk),self.scope())
        self.assertEqual(response.status_code,200); self.assertIsNotNone(response.context['pairing'])
        form=response.context['form']; pairing=response.context['pairing']
        data=self.scope()|dict(expected_source_checksum=form.initial['expected_source_checksum'],expected_latest=0,
            confirmed='on',reason='Inherited exact original',evidence_reference='Reviewed original reversal')
        self.assertEqual(self.client.post(self.url('prepare',entry_id=reversal.pk),data).status_code,400)
        for name,field in pairing.fields.items():
            self.assertEqual(len(field.choices),2); data[name]=field.choices[1][0]
        self.assertEqual(self.client.post(self.url('prepare',entry_id=reversal.pk),data).status_code,302)
        child=Batch.objects.exclude(pk=original.pk).get(); member=child.members.get()
        self.assertEqual(member.partition['payload']['controls']['classified_receipts'],'-100.00')
        self.assertEqual(len(member.partition['payload']['allocations']),3)
        self.client.force_login(self.validator)
        self.assertEqual(self.client.post(self.url('review',batch_id=child.public_id),dict(outcome='approve',note='Exact mirrored lines and original review verified',confirmed='on')).status_code,302)
        self.assertEqual(JournalEntry.objects.count(),2)

    def test_dedicated_roles_and_whole_batch_search(self):
        receipt=self.capture(); entry=self.post_source(receipt); deposit=self.post_source(self.deposit(receipt,'100','WHOLE-DEPOSIT'))
        inventory=self.inventory(); batch=service.propose_batch(**self.args([self.member_args(inventory,entry),self.member_args(inventory,deposit,receipt=False)]))
        call_command('configure_finance_roles',stdout=io.StringIO())
        self.validator.user_permissions.clear(); self.validator.groups.add(Group.objects.get(name='Budget Receipt Reviewer'))
        self.client.force_login(self.validator)
        self.assertContains(self.client.get(reverse('accounting:workspace')),'Receipt source classification')
        response=self.client.get(self.url('register'),dict(q='WHOLE-DEPOSIT'))
        self.assertEqual(response.context['page'].paginator.count,1)
        detail=self.client.get(self.url('detail',batch_id=batch.public_id)); self.assertEqual(len(detail.context['body']['members']),2)
        self.assertEqual(detail.context['count'],5)
        self.assertEqual(self.client.get(self.url('prepare',entry_id=entry.pk),self.scope()).status_code,403)

    def test_original_document_reference_search_preserves_full_source_and_batch_counts(self):
        receipt=self.capture(); entry=self.post_source(receipt); deposit=self.post_source(self.deposit(receipt,'100','FIND-ACTUAL-SLIP'))
        self.client.force_login(self.preparer)
        response=self.client.get(self.url('sources'),self.scope()|dict(q='FIND-ACTUAL-SLIP'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['page'].paginator.count,1)
        self.assertEqual(response.context['page'][0]['entry_id'],deposit.pk)
        self.assertEqual(response.context['captured']['payload']['controls']['journals'],2)
        inventory=self.inventory()
        batch=service.propose_batch(**self.args([self.member_args(inventory,entry),self.member_args(inventory,deposit,receipt=False)]))
        self.assertEqual(self.client.get(self.url('register'),dict(q='FIND-ACTUAL-SLIP')).context['page'].paginator.count,1)
        self.assertEqual(len(self.client.get(self.url('detail',batch_id=batch.public_id)).context['body']['members']),2)
