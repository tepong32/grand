from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from accounting import summary_actuals, test_summary_actuals as adopted
from . import test_form1_account_proposals as fixtures
from . import form1_spa_proposals as service, form1_components, form1_flows
from . import summary_reconciliations, receipt_forecasts


class Form1SPAProposalTests(fixtures.Form1AccountProposalFixture):
    def signed_history(self, category='spa'):
        def document():
            from reportlab.pdfgen import canvas
            stream=BytesIO(); page=canvas.Canvas(stream)
            page.drawString(30,790,f'SYNTHETIC 2025 joint source/TB: service zero; {category} +10 and -10, net zero')
            page.drawString(30,765,'Synthetic Treasurer T July 1 2026; Accountant A July 2 2026; other leaves unspecified')
            page.save()
            return SimpleUploadedFile('synthetic-spa-source.pdf',stream.getvalue(),content_type='application/pdf')
        fixture=SimpleNamespace(maker=self.maker,fund=self.fund,budget_office=self.budget_office,
            operating_office=self.treasury,receipt_account=self.revenue,account=self.account,document=document)
        args=adopted.SummaryActualTests.arguments(fixture,period_start=date(2025,1,1),period_end=date(2025,12,31),
            receipt_total='0',expenditure_total='0',rows=[
                dict(kind='receipt',category='service',account_id=None,amount='0',source_row='R1'),
                dict(kind='expenditure',category=category,account_id=self.account.pk,amount='10',source_row='E1 original recognition'),
                dict(kind='expenditure',category=category,account_id=self.account.pk,amount='-10',source_row='E2 original correction')])
        source=summary_actuals.review(summary_actuals.propose(**args),self.checker,approve=True,
            note='Verified original signed category/source rows',authority='Independent source adoption',verified_documents=True)
        parent=summary_reconciliations.prepare(**self.args(prior_id=source.public_id,prior_route='historical',expected_latest=1))
        self.accept(parent); parent.refresh_from_db()
        self.captured=receipt_forecasts.capture(reconciliation=parent,actor=self.preparer)
        self.forecast=receipt_forecasts.propose(self.captured,**self.inputs())
        approved=self.review_forecast(self.prepare_forecast(expected_latest=1))
        self.inventory=form1_components.inventory(form1_flows.capture(forecast=approved,actor=self.preparer))
        return source

    def spa_inputs(self):
        components={row['key']:row for row in self.inventory['payload']['components']}
        allocations=self.account_allocations(self.targets['valid'])
        for row in allocations:
            if components[row['component']]['source_account'] is None: row['account_id']=None
        draft=self.propose_accounts(allocations)
        parts=[dict(key='spa-'+str(index),allocation=row['key'],amount=row['amount'],subdivision='development',
            basis='Synthetic explicit source treatment; not a statutory percentage or spending authorization')
            for index,row in enumerate(draft['payload']['allocations'])
            if components[row['component']]['identity']['kind']=='expenditure' and components[row['component']]['category']=='spa']
        coverage=[]
        for member in self.inventory['payload']['flows']['payload']['members']:
            control=next(row for row in member['expenditure']['rows'] if row['category']=='spa')
            for column in form1_components.SOURCE_COLUMNS:
                for subdivision in service.SUBDIVISIONS:
                    coverage.append(dict(entity=member['entity_key'],column=column,subdivision=subdivision,
                        coverage='complete' if control['amounts'][column] is not None else 'missing',
                        basis='Synthetic explicit whole subdivision/no-activity coverage; missing sources stay missing'))
        return draft,parts,coverage

    def propose_spa(self,draft,parts,coverage):
        return service.propose(draft,parts,coverage,coverage_reference='Synthetic whole source subdivision evidence; pending independent review')

    def test_genuine_no_activity_requires_explicit_complete_matrix_without_posting(self):
        draft,parts,coverage=self.spa_inputs(); self.assertEqual(parts,[])
        before=JournalEntry.objects.count(); original=deepcopy(draft)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            body=service.verify(self.propose_spa(draft,parts,coverage))
        self.assertTrue(body['spa_partition_complete']); self.assertEqual(len(body['coverage']),24)
        self.assertTrue(all(value=='0.00' for row in body['members'][0]['rows'] for value in row['amounts'].values()))
        self.assertFalse(body['independently_reviewed']); self.assertFalse(body['form_issued'])
        self.assertEqual(draft,original); self.assertEqual(JournalEntry.objects.count(),before)
        with self.assertRaises(ValidationError): self.propose_spa(draft,parts,coverage[:-1])

    def test_genuine_signed_history_splits_preserve_opposing_subdivisions_and_original_shares(self):
        source=self.signed_history(); draft,parts,coverage=self.spa_inputs()
        positive=next(row for row in parts if row['amount']=='10.00')
        positive['amount']='6.00'
        parts.append(dict(positive,key='spa-positive-split',amount='4.00',subdivision='ldrrm'))
        before=JournalEntry.objects.count()
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            body=service.verify(self.propose_spa(draft,parts,coverage))
        member=body['members'][0]; rows={row['subdivision']:row for row in member['rows']}
        self.assertEqual(rows['development']['amounts']['prior_amount'],'-4.00')
        self.assertEqual(rows['ldrrm']['amounts']['prior_amount'],'4.00')
        self.assertEqual(member['totals']['prior_amount'],'0.00')
        self.assertEqual(len(body['parts']),3)
        self.assertEqual({row['source_identity']['source']['record'] for row in body['parts']},{str(source.public_id)})
        self.assertEqual(sorted(row['original_allocation']['amount'] for row in body['parts']),['-10.00','10.00','10.00'])
        self.assertEqual(JournalEntry.objects.count(),before); self.assertFalse(body['cash_available'])

    def test_genuine_missing_historical_spa_coverage_cannot_become_zero_or_complete(self):
        self.signed_history(category='mooe'); draft,parts,coverage=self.spa_inputs()
        body=service.verify(self.propose_spa(draft,parts,coverage)); member=body['members'][0]
        self.assertFalse(body['spa_partition_complete']); self.assertIsNone(member['totals']['prior_amount'])
        self.assertTrue(all(row['amounts']['prior_amount'] is None for row in member['rows']))
        guessed=deepcopy(coverage)
        next(row for row in guessed if row['column']=='prior_amount')['coverage']='complete'
        with self.assertRaises(ValidationError): self.propose_spa(draft,parts,guessed)

    def test_unresolved_missing_parts_signs_and_rehashed_derivatives_are_rejected_or_retained(self):
        self.signed_history(); draft,parts,coverage=self.spa_inputs()
        unresolved=deepcopy(parts); unresolved[0]['subdivision']='unresolved'
        body=service.verify(self.propose_spa(draft,unresolved,coverage))
        self.assertFalse(body['spa_partition_complete'])
        self.assertEqual(len(body['members'][0]['unresolved_parts']),1)
        self.assertTrue(all(row['amounts']['prior_amount'] is None for row in body['members'][0]['rows']))
        for label in ('omitted','duplicate','opposite','non_spa','coverage'):
            changed=deepcopy(parts); changed_coverage=deepcopy(coverage)
            if label=='omitted': changed.pop()
            elif label=='duplicate': changed.append(deepcopy(changed[0]))
            elif label=='opposite': changed[0]['amount']=str(-Decimal(changed[0]['amount']))
            elif label=='non_spa': changed[0]['allocation']=next(row['key'] for row in draft['payload']['allocations'] if row['key'] not in {part['allocation'] for part in parts})
            else: changed_coverage.append(deepcopy(changed_coverage[0]))
            with self.subTest(label=label),self.assertRaises(ValidationError): self.propose_spa(draft,changed,changed_coverage)
        original=self.propose_spa(draft,parts,coverage)
        for label in ('amount','part','approval'):
            changed=deepcopy(original)
            if label=='amount': changed['payload']['members'][0]['rows'][0]['amounts']['prior_amount']='999.00'
            elif label=='part': changed['payload']['parts'][0]['source_identity']['source']['record']='invented'
            else: changed['payload']['independently_reviewed']=True
            changed['checksum']=checksum(changed['payload'])
            with self.subTest(label=label),self.assertRaises(ValidationError): service.verify(changed)
