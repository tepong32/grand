from copy import deepcopy
from datetime import date
from types import SimpleNamespace

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from accounting import summary_actuals,test_summary_actuals as adopted
from accounting.summary_actuals import RECEIPTS,EXPENDITURES
from accounting.models import JournalEntry
from accounting.cash_classifications import checksum
from .test_receipt_forecast_reviews import ReceiptForecastReviewFixture
from . import test_form1_stocks as stock_fixtures
from . import form1_philhealth as service,receipt_forecasts,summary_reconciliations


class Form1PhilHealthTests(ReceiptForecastReviewFixture):
    cash=stock_fixtures.Form1StockCalendarTests.cash
    bridge=stock_fixtures.Form1StockCalendarTests.bridge
    capture_stock=stock_fixtures.Form1StockCalendarTests.capture_stock

    def inputs(self,**changes):
        args=ReceiptForecastReviewFixture.inputs(self,**changes)
        for name in ('half_components','proposed_components'):
            for row in args[name]:
                if row['disposition'] in ('include','overlap'):row['category']='philhealth'
        args['coverage']=dict(half_estimate=self.coverage(args['half_components']),proposed=self.coverage(args['proposed_components']))
        return args

    def setUp(self):
        super().setUp()
        self.reconciliation_inputs=self.args()
        self.approved=self.review_forecast(self.prepare_forecast())
        from . import form1_flows
        self.scope=form1_flows.capture(forecast=self.approved,actor=self.preparer)['payload']['members'][0]['scope']
        for actor,codes in ((self.maker,('prepare_budget_cash_evidence','view_budget_cash_evidence')),
            (self.checker,('review_budget_cash_evidence','view_budget_cash_evidence')),
            (self.preparer,('view_budget_cash_evidence',))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',codename__in=codes))
        self.prior=self.cash(date(2025,1,1));self.half=self.cash(date(2026,1,1))
        self.estimate,self.estimate_bytes=self.bridge('2026-07-01','100.00')
        self.proposed,self.proposed_bytes=self.bridge('2027-01-01','200.00')
        self.selections=[dict(entity_key=self.scope['entity_key'],opening=dict(prior_amount=dict(kind='actual',source=self.prior),
            half_amount=dict(kind='actual',source=self.half),estimate=dict(kind='forecast',source=self.estimate),
            proposed=dict(kind='forecast',source=self.proposed)))]
        self.evidence={self.estimate['checksum']:self.estimate_bytes,self.proposed['checksum']:self.proposed_bytes}
        self.source=service.capture(stock=self.capture_stock(),actor=self.preparer,evidence=self.evidence)

    def treatment(self):
        parts=[dict(key='part-'+str(index),source=row['key'],amount=row['amount'],counterpart='',
            treatment='deduct' if row['kind']=='receipt' else 'other',basis='Explicit synthetic source/funding treatment')
            for index,row in enumerate(self.source['payload']['catalog'])]
        coverage=[dict(entity=self.scope['entity_key'],column=column,kind=kind,coverage='complete',
            basis='Complete synthetic source/overlap worksheet, not an LGU acceptance')
            for column in service.components.SOURCE_COLUMNS for kind in service.KINDS]
        return parts,coverage

    def draft(self,parts=None,coverage=None,attach=True):
        original_parts,original_coverage=self.treatment()
        args=dict(source=self.source,actor=self.preparer,evidence=self.evidence,parts=parts if parts is not None else original_parts,
            coverage=coverage if coverage is not None else original_coverage,coverage_reference='Synthetic whole-source policy/treatment')
        if attach:
            args.update(authority=SimpleUploadedFile('policy.pdf',b'%PDF-1.4\nSynthetic policy authority'),
                reconciliation=SimpleUploadedFile('overlap.pdf',b'%PDF-1.4\nSynthetic exact overlap worksheet'))
        return service.prepare(**args)

    def test_positive_receipts_exact_five_columns_pure_reproduction_and_no_posting(self):
        before=JournalEntry.objects.count();original=deepcopy(self.source)
        envelope,docs=self.draft()
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            body=service.verify(envelope)
        member=body['members'][0]
        self.assertEqual(member['deduction'],dict(prior_amount='0.00',half_amount='0.00',estimate='30.00',current_total='30.00',proposed='100.00'))
        self.assertEqual(member['net_ending'],dict(prior_amount='900.00',half_amount='800.00',estimate='960.00',current_total='760.00',proposed='100.00'))
        self.assertTrue(body['deduction_partition_complete'])
        for flag in ('independently_reviewed','philhealth_deduction_complete','form_issued','cash_available'):self.assertFalse(body[flag])
        self.assertEqual(service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=docs),body)
        self.assertEqual(self.source,original);self.assertEqual(JournalEntry.objects.count(),before)

    def test_missing_policy_coverage_or_overlap_never_supplies_known_deduction(self):
        envelope,_=self.draft(attach=False)
        self.assertTrue(all(value is None for value in envelope['payload']['members'][0]['deduction'].values()))
        parts,coverage=self.treatment();coverage[0]['coverage']='missing'
        self.assertIsNone(self.draft(parts,coverage)[0]['payload']['members'][0]['deduction']['prior_amount'])
        catalog={row['key']:row for row in self.source['payload']['catalog']}
        receipt=next(row for row in parts if catalog[row['source']]['kind']=='receipt' and catalog[row['source']]['column']=='estimate')
        expense=next(row for row in parts if catalog[row['source']]['kind']=='expense' and catalog[row['source']]['column']=='estimate' and row['amount']=='40.00')
        expense['treatment']='shf';receipt.update(treatment='claimed_overlap',counterpart=expense['source'])
        body=self.draft(parts)[0]['payload']['members'][0]
        self.assertIsNone(body['deduction']['estimate']);self.assertIsNone(body['net_ending']['current_total'])
        self.assertIn(receipt['key'],body['pending_overlap_or_treatment']['estimate'])
        # Ordinary health counterpart funding does not establish an SHF overlap.
        expense['treatment']='counterpart'
        with self.assertRaises(ValidationError):self.draft(parts)
        parts,_=self.treatment()
        for row in parts:
            if catalog[row['source']]['kind']=='restriction':row['treatment']='philhealth_carryover'
        for row in parts:
            item=catalog[row['source']]
            if item['kind']=='receipt':
                counterpart=next(value for value in catalog.values() if value['kind']=='restriction' and value['column']==item['column'])
                row.update(treatment='claimed_overlap',counterpart=counterpart['key'])
        with self.assertRaisesMessage(ValidationError,'twice'):self.draft(parts)

    def test_real_signed_historical_receipts_keep_both_sources_and_exact_corrections(self):
        before=JournalEntry.objects.count()
        fixture=SimpleNamespace(maker=self.maker,fund=self.fund,budget_office=self.budget_office,
            operating_office=self.treasury,receipt_account=self.revenue,account=self.account,document=self.document)
        receipt_rows=[dict(kind='receipt',category=category,account_id=None,amount='0',source_row='zero '+category)
            for category in RECEIPTS if category!='philhealth']
        receipt_rows.extend([dict(kind='receipt',category='philhealth',account_id=self.revenue.pk,amount=value,source_row=reference)
            for value,reference in (('17','original PH receipt'),('-7','original PH correction'))])
        expense_rows=[dict(kind='expenditure',category=category,account_id=None,amount='0',source_row='expense zero '+category) for category in EXPENDITURES]
        args=adopted.SummaryActualTests.arguments(fixture,period_start=date(2025,1,1),period_end=date(2025,12,31),
            receipt_total='10',expenditure_total='0',rows=receipt_rows+expense_rows)
        actual=summary_actuals.review(summary_actuals.propose(**args),self.checker,approve=True,verified_documents=True,
            note='Verified explicit original signed PH rows and full zero coverage',authority='Independent historical adoption')
        parent=summary_reconciliations.prepare(**dict(self.reconciliation_inputs,
            prior_id=actual.public_id,prior_route='historical',expected_latest=1))
        self.accept(parent);parent.refresh_from_db()
        self.captured=receipt_forecasts.capture(reconciliation=parent,actor=self.preparer)
        self.forecast=receipt_forecasts.propose(self.captured,**self.inputs())
        self.approved=self.review_forecast(self.prepare_forecast(expected_latest=1))
        self.source=service.capture(stock=self.capture_stock(),actor=self.preparer,evidence=self.evidence)
        envelope,_=self.draft();body=service.verify(envelope)
        parts=[row for row in body['parts'] if row['original_source']['kind']=='receipt' and row['original_source']['column']=='prior_amount']
        self.assertEqual(sorted(row['amount'] for row in parts),['-7.00','17.00'])
        self.assertEqual(body['members'][0]['deduction']['prior_amount'],'10.00')
        self.assertEqual(body['members'][0]['net_ending']['prior_amount'],'900.00')
        actual.refresh_from_db();self.assertEqual(actual.payload['totals']['receipt'],'10.00')
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_original_bytes_rehash_permissions_and_successors_fail_closed(self):
        envelope,docs=self.draft();bad=dict(docs);bad['authority']+=b'changed'
        with self.assertRaises(ValidationError):service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=bad)
        changed=deepcopy(envelope);changed['payload']['members'][0]['net_ending']['proposed']='999.00';changed['checksum']=checksum(changed['payload'])
        with self.assertRaises(ValidationError):service.verify(changed)
        with self.assertRaises(PermissionDenied):service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=docs,export=True)
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label='accounting',codename='export_budget_cash_evidence'))
        self.assertEqual(service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=docs,export=True),envelope['payload'])
        self.cash(date(2026,1,1),expected_latest=1)
        with self.assertRaises(ValidationError):self.draft()
        self.assertEqual(service.reproduce(envelope,self.preparer,evidence=self.evidence,documents=docs),envelope['payload'])
