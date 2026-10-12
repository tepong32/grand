from copy import deepcopy
from decimal import Decimal
from datetime import date
from types import SimpleNamespace
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from accounting.models import JournalEntry
from accounting.summary_actuals import RECEIPTS,EXPENDITURES
from accounting.cash_classifications import checksum
from . import test_form1_account_proposals as fixtures, test_form1_components as historical
from . import form1_account_proposals as drafts, form1_itemization as service, form1_components, form1_flows
from . import summary_reconciliations,receipt_forecasts
from accounting import summary_actuals,test_summary_actuals as adopted


class Form1ItemizationTests(fixtures.Form1AccountProposalFixture):
    def itemize(self,rows=None):
        draft=self.propose_accounts(rows if rows is not None else self.account_allocations(self.targets['valid']))
        return service.compose(draft)

    def test_complete_original_shares_query_free_hierarchy_and_no_posting(self):
        before=JournalEntry.objects.count(); original=deepcopy(self.inventory)
        rows=self.account_allocations(self.targets['valid']); first=rows.pop(0)
        value=Decimal(first['amount'])
        rows.extend([dict(first,key='split-a',amount=str(value/2)),dict(first,key='split-b',amount=str(value/2))])
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            result=self.itemize(rows); body=service.verify(result)
        member=body['members'][0]
        self.assertEqual([row['category'] for row in member['receipt']['rows']],list(RECEIPTS))
        self.assertEqual([row['category'] for row in member['expenditure']['rows']],list(EXPENDITURES))
        self.assertEqual(member['receipt']['hierarchy'][-1]['amounts'],member['receipt']['totals'])
        shares=[share for kind in ('receipt','expenditure') for leaf in member[kind]['rows'] for account in leaf['accounts'] for share in account['source_shares']]
        self.assertEqual(len(shares),len(rows)); self.assertEqual(len({row['allocation']['key'] for row in shares}),len(rows))
        self.assertEqual(self.inventory,original); self.assertEqual(JournalEntry.objects.count(),before)
        for flag in ('independently_reviewed','code_authority_approved','stock_complete','spa_subdivisions_complete','philhealth_deduction_complete','form_issued','cash_available'):
            self.assertFalse(body[flag])

    def test_unresolved_amounts_and_distinct_account_identities_remain_visible(self):
        unresolved=service.verify(self.itemize(self.account_allocations()))
        self.assertFalse(unresolved['selection_complete'])
        accounts=[account for member in unresolved['members'] for kind in ('receipt','expenditure') for leaf in member[kind]['rows'] for account in leaf['accounts']]
        self.assertTrue(all(row['disposition']=='unresolved' and row['account'] is None for row in accounts))
        rows=self.account_allocations(self.targets['valid'])
        component={row['key']:row for row in self.inventory['payload']['components']}
        for row in rows:
            if component[row['component']]['identity']['column']=='half_amount':row['account_id']=self.targets['retired'].pk
        body=service.verify(self.itemize(rows))
        expense=next(row for row in body['members'][0]['expenditure']['rows'] if row['category']=='mooe')
        self.assertEqual({row['account']['id'] for row in expense['accounts']},{self.targets['valid'].pk,self.targets['retired'].pk})
        self.assertEqual(service.sum_rows(expense['accounts']),expense['amounts'])

    def test_real_historical_explicit_zero_and_missing_coverage_remain_distinct(self):
        historical.Form1ComponentTests.test_real_historical_zero_rows_preserve_missing_categories_and_null_source_accounts(self)
        approved=self.version.receipt_forecasts.filter(status='approved').order_by('-version').first()
        self.inventory=form1_components.inventory(form1_flows.capture(forecast=approved,actor=self.preparer))
        rows=self.account_allocations(self.targets['valid']); sources={row['key']:row for row in self.inventory['payload']['components']}
        for row in rows:
            if sources[row['component']]['source_account'] is None:row['account_id']=None
        body=service.verify(self.itemize(rows)); member=body['members'][0]
        self.assertFalse(body['source_coverage_complete'])
        self.assertIsNone(member['receipt']['totals']['prior_amount'])
        self.assertIsNone(member['receipt']['hierarchy'][-1]['amounts']['prior_amount'])
        missing=next(row for row in member['receipt']['rows'] if row['category']=='basic_rpt')
        self.assertIsNone(missing['amounts']['prior_amount']); self.assertEqual(missing['accounts'],[])
        known=next(row for row in member['receipt']['rows'] if row['category']=='service')
        self.assertEqual(known['amounts']['prior_amount'],'0.00')
        self.assertTrue(any(row['account'] is None and row['disposition']=='mapped' and row['source_shares'] for row in known['accounts']))

    def test_rehashed_derived_hierarchy_share_and_approval_tampering_rejected(self):
        original=self.itemize()
        for name in ('amount','hierarchy','share','approval'):
            changed=deepcopy(original); body=changed['payload']; member=body['members'][0]
            if name=='amount':member['receipt']['rows'][0]['amounts']['estimate']='999.00'
            elif name=='hierarchy':member['receipt']['hierarchy'][-1]['leaves'].append('service')
            elif name=='share':
                account=next(account for leaf in member['receipt']['rows'] for account in leaf['accounts'])
                account['source_shares'].pop()
            else:body['independently_reviewed']=True
            changed['checksum']=checksum(body)
            with self.subTest(name=name),self.assertRaises(ValidationError):service.verify(changed)

    def test_genuine_adopted_signed_activity_retains_net_zero_account_row(self):
        def document():
            from reportlab.pdfgen import canvas
            stream=BytesIO(); page=canvas.Canvas(stream)
            page.drawString(30,790,'SYNTHETIC 2025 joint source/TB: service receipts zero; MOOE +10 and -10, net zero')
            page.drawString(30,760,'Synthetic Treasurer T July 1 2026; Accountant A July 2 2026; other leaves unspecified')
            page.save()
            return SimpleUploadedFile('synthetic-signed-history.pdf',stream.getvalue(),content_type='application/pdf')
        fixture=SimpleNamespace(maker=self.maker,fund=self.fund,budget_office=self.budget_office,
            operating_office=self.treasury,receipt_account=self.revenue,account=self.account,document=document)
        args=adopted.SummaryActualTests.arguments(fixture,period_start=date(2025,1,1),period_end=date(2025,12,31),
            receipt_total='0',expenditure_total='0',rows=[
                dict(kind='receipt',category='service',account_id=None,amount='0',source_row='R1'),
                dict(kind='expenditure',category='mooe',account_id=self.account.pk,amount='10',source_row='E1 original recognition'),
                dict(kind='expenditure',category='mooe',account_id=self.account.pk,amount='-10',source_row='E2 original correction')])
        source=summary_actuals.review(summary_actuals.propose(**args),self.checker,approve=True,
            note='Verified original signed source rows',authority='Independent adoption',verified_documents=True)
        parent=summary_reconciliations.prepare(**self.args(prior_id=source.public_id,prior_route='historical',expected_latest=1))
        self.accept(parent);parent.refresh_from_db()
        self.captured=receipt_forecasts.capture(reconciliation=parent,actor=self.preparer)
        self.forecast=receipt_forecasts.propose(self.captured,**self.inputs())
        approved=self.review_forecast(self.prepare_forecast(expected_latest=1))
        self.inventory=form1_components.inventory(form1_flows.capture(forecast=approved,actor=self.preparer))
        rows=self.account_allocations(self.targets['valid']); components={row['key']:row for row in self.inventory['payload']['components']}
        for row in rows:
            if components[row['component']]['source_account'] is None:row['account_id']=None
        before=JournalEntry.objects.count(); body=service.verify(self.itemize(rows))
        leaf=next(row for row in body['members'][0]['expenditure']['rows'] if row['category']=='mooe')
        account=next(row for row in leaf['accounts'] if row['account']['id']==self.targets['valid'].pk)
        signed=[share['allocation']['amount'] for share in account['source_shares']
            if components[share['source_component']]['identity']['column']=='prior_amount']
        self.assertEqual(sorted(signed),['-10.00','10.00']);self.assertEqual(account['amounts']['prior_amount'],'0.00')
        self.assertEqual(JournalEntry.objects.count(),before)
