from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json

from django.core.exceptions import ValidationError
from django.urls import reverse
from pypdf import PdfReader
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from . import test_form1_spa_reviews as fixtures, test_form1_spa_proposals as signed
from . import form1_spa_reviews as reviews, form1_spa_output as output, form1_flow_output as flows


class Form1SPAOutputTests(fixtures.Form1SPAReviewFixture):
    signed_history=signed.Form1SPAProposalTests.signed_history

    def retained(self,record): return reviews.snapshot(record,self.checker,export=True)

    def export(self,record,kind):
        return self.client.get(reverse('budget:form1_spa_export',args=(record.public_id,kind)))

    def pdf_text(self,content):
        pages=PdfReader(BytesIO(content)).pages
        for page in pages:self.assertIn('INCOMPLETE DRAFT',page.extract_text())
        return '\n'.join(page.extract_text() for page in pages)

    def test_exact_original_pair_all_controls_pure_composition_and_no_posting(self):
        record=self.approve_spa(self.prepare_spa()); snapshot=self.retained(record)
        before=JournalEntry.objects.count(); original=deepcopy(snapshot)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            envelope=output.package(snapshot); body=output.verify(envelope); content=output.render_pdf(envelope)
        self.assertEqual(body['spa_review'],snapshot)
        self.assertEqual(body['flow'],flows.package(snapshot['payload']['source_account_review']))
        self.assertEqual(len(body['members'][0]['rows']),6)
        self.assertTrue(all(value=='0.00' for row in body['members'][0]['rows'] for value in row['amounts'].values()))
        self.assertFalse(body['form_issued']); self.assertFalse(body['cash_available'])
        self.assertFalse(body['source_freshness_certified'])
        self.assertEqual(snapshot,original); self.assertEqual(JournalEntry.objects.count(),before)
        self.assertEqual(output.render_pdf(envelope),content)
        text=self.pdf_text(content)
        for row in snapshot['decisions']:self.assertIn(row['checksum'],text)
        for row in body['members'][0]['rows']:self.assertIn(row['label'],text)
        self.assertIn('Original SPA class control',text)
        self.assertIn('Current total',text); self.assertIn('Proposed',text)
        self.client.force_login(self.checker)
        self.assertEqual(json.loads(self.export(record,'flow-json').content),envelope)
        response=self.export(record,'flow-pdf')
        self.assertEqual(response.status_code,200); self.assertEqual(response.content,content)
        self.assertEqual(response['X-GRAND-Export-SHA256'],sha256(content).hexdigest())
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertIn('form1-flow-spa-draft-',response['Content-Disposition'])
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_genuine_signed_history_retains_account_split_and_original_opposing_parts(self):
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
        record=self.approve_spa(self.prepare_spa(parts=parts,coverage=coverage))
        before=JournalEntry.objects.count(); snapshot=self.retained(record)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            member=output.verify(output.package(snapshot))['members'][0]
        self.assertEqual(member['original_spa_control']['prior_amount'],'0.00')
        rows={row['subdivision']:row for row in member['rows']}
        self.assertEqual(rows['development']['amounts']['prior_amount'],'-4.00')
        self.assertEqual(rows['ldrrm']['amounts']['prior_amount'],'4.00')
        account=rows['development']['accounts'][0]
        self.assertEqual(account['amounts']['prior_amount'],'-4.00')
        self.assertEqual(sorted(part['amount'] for part in account['source_parts']),['-10.00','6.00'])
        self.assertEqual(sorted(part['original_allocation']['amount'] for part in account['source_parts']),['-10.00','10.00'])
        self.assertEqual(JournalEntry.objects.count(),before)
        text=self.pdf_text(output.render_pdf(output.package(snapshot)))
        self.assertIn('-4.00',text)
        for part in snapshot['payload']['draft']['payload']['parts']:
            self.assertIn(part['key'],text); self.assertIn(part['allocation'],text)
            self.assertIn('signed part '+part['amount'],text)

    def test_missing_partial_returned_and_superseded_states_keep_original_evidence(self):
        _,parts,coverage=self.spa_inputs(); coverage[0]['coverage']='missing'
        missing=self.prepare_spa(parts=parts,coverage=coverage)
        member=output.package(self.retained(missing))['payload']['members'][0]
        self.assertEqual(member['original_spa_control']['prior_amount'],'0.00')
        self.assertTrue(all(row['amounts']['prior_amount'] is None for row in member['rows']))
        self.assertIn('Unknown',self.pdf_text(output.render_pdf(output.package(self.retained(missing)))))
        self.decide_spa(missing,approve=False,treatment_verified=False)
        self.assertEqual(output.package(self.retained(missing))['payload']['spa_review']['status'],'returned')
        self.assertIn('state returned',self.pdf_text(output.render_pdf(output.package(self.retained(missing)))))
        complete=self.decide_spa(self.prepare_spa(expected_latest=1))
        partial=output.package(self.retained(complete))
        self.assertFalse(partial['payload']['spa_review']['independently_reviewed'])
        self.assertIn('state partially_approved',self.pdf_text(output.render_pdf(partial)))
        complete=self.decide_spa(complete,role='accounting')
        retained=output.package(self.retained(complete))
        original_pdf=output.render_pdf(retained)
        self.prepare_spa(expected_latest=2)
        self.assertFalse(reviews.is_current(complete,self.checker))
        self.assertEqual(output.package(self.retained(complete)),retained)
        self.assertEqual(output.render_pdf(output.package(self.retained(complete))),original_pdf)

    def test_rehashed_pair_role_owner_state_and_derived_rows_fail_closed(self):
        record=self.approve_spa(self.prepare_spa()); original=self.retained(record)
        for label in ('pair','role','owner','state','date'):
            changed=deepcopy(original)
            if label=='pair':
                changed['payload']['identity']['fund_id']+=1
                changed['payload_checksum']=checksum(changed['payload'])
                for row in changed['decisions']:
                    row['payload_checksum']=changed['payload_checksum']
                    row['checksum']=checksum({key:value for key,value in row.items() if key!='checksum'})
            elif label=='role':
                changed['decisions'][1]['actor_id']=changed['decisions'][0]['actor_id']
            elif label=='owner': changed['decisions'][0]['actor_department_id']+=1
            elif label=='state': changed['status']='prepared'
            else: changed['decisions'][0]['decided_at']='2020-01-01T00:00:00+00:00'
            if label in ('role','owner','date'):
                for row in changed['decisions']:
                    row['checksum']=checksum({key:value for key,value in row.items() if key!='checksum'})
            with self.subTest(label=label),self.assertRaises(ValidationError): output.package(changed)
        envelope=output.package(original)
        envelope['payload']['members'][0]['rows'][0]['amounts']['prior_amount']='999.00'
        envelope['checksum']=checksum(envelope['payload'])
        with self.assertRaises(ValidationError): output.verify(envelope)
        with self.assertRaises(ValidationError): output.render_pdf(envelope)
