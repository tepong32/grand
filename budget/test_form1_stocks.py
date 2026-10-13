from copy import deepcopy
from datetime import date

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from accounting import budget_cash
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from .test_receipt_forecast_reviews import ReceiptForecastReviewFixture
from . import form1_flows as flows, form1_stocks as service
from . import form1_stock_sources as stocks, form1_cash_forecasts as bridges


class Form1StockCalendarTests(ReceiptForecastReviewFixture):
    def setUp(self):
        super().setUp()
        self.approved=self.review_forecast(self.prepare_forecast())
        self.flow=flows.capture(forecast=self.approved,actor=self.preparer)
        self.scope=self.flow['payload']['members'][0]['scope']
        for actor,codes in ((self.maker,('prepare_budget_cash_evidence','view_budget_cash_evidence')),
            (self.checker,('review_budget_cash_evidence','view_budget_cash_evidence')),
            (self.preparer,('view_budget_cash_evidence',))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',codename__in=codes))
        self.prior=self.cash(date(2025,1,1)); self.half=self.cash(date(2026,1,1))
        self.estimate,self.estimate_bytes=self.bridge('2026-07-01','100.00')
        self.proposed,self.proposed_bytes=self.bridge('2027-01-01','200.00')
        self.selections=[dict(entity_key=self.scope['entity_key'],opening=dict(
            prior_amount=dict(kind='actual',source=self.prior),half_amount=dict(kind='actual',source=self.half),
            estimate=dict(kind='forecast',source=self.estimate),proposed=dict(kind='forecast',source=self.proposed)))]
        self.evidence={self.estimate['checksum']:self.estimate_bytes,self.proposed['checksum']:self.proposed_bytes}

    def cash(self,day,**changes):
        args=dict(actor=self.maker,fund_id=self.fund.pk,budget_department_id=self.scope['budget_department_id'],
            treasury_department_id=self.scope['treasury_department_id'],entity_key=self.scope['entity_key'],
            entity_label=self.scope['entity_label'],balance_date=day,boundary='start_of_day',gross='1000',
            restricted='100',net='900',rows=[dict(key='R1',reference='restriction row 1',purpose='Explicit restriction',
                coverage='Whole scope',amount='100')],no_restrictions=False,declaration='',
            overlap_basis='Whole original disjoint restriction inventory',certificate=self.document(),
            reconciliation=self.document(),expected_latest=0,accountant_name='Synthetic Accountant',
            treasurer_name='Synthetic Treasurer',accountant_certified_on=date(2026,7,2),treasurer_certified_on=date(2026,7,2))
        for name in ('reference','scope_authority','gross_basis','coverage','reconciliation_basis',
            'accountant_authority','treasurer_authority','reason'):args[name]='Synthetic stock '+name
        args.update(changes)
        record=budget_cash.propose(**args)
        budget_cash.review(record,self.checker,adopt=True,verified_documents=True,note='Verified originals',authority='Independent adoption')
        expected={key:record.payload['scope'][key] for key in stocks.SCOPE_FIELDS}
        return stocks.capture(route='historical',identity=str(record.public_id),expected_scope=expected,actor=self.preparer)

    def bridge(self,target,amount):
        return bridges.propose(source=self.half,actor=self.preparer,
            evidence=SimpleUploadedFile('timing.pdf',b'%PDF-1.4\nSynthetic cash timing forecast'),
            target_date=target,target_boundary='start_of_day',cash_changes=[dict(key='in',source_row='cash timing row 1',
                effective_date='2026-06-15',direction='in',amount=amount,basis='Explicit dated projected cash receipt')],
            proposed_restrictions=[],restriction_changes=[],cash_coverage='complete',cash_basis='Whole cash timing inventory',
            no_cash_changes=False,cash_declaration='',restriction_coverage='complete',
            restriction_basis='Original restrictions remain with explicit whole target coverage',no_restrictions=False,restriction_declaration='')

    def capture_stock(self,**changes):
        args=dict(forecast=self.approved,actor=self.preparer,selections=self.selections,evidence=self.evidence,
            stock_convention=service.CONVENTION,boundary_basis='Annual opening reuses January H1 boundary; July remains a separate stock')
        args.update(changes); return service.capture(**args)

    def test_real_flow_stock_calendar_and_resource_controls_without_posting(self):
        before=JournalEntry.objects.count(); draft=self.capture_stock()
        with self.assertNumQueries(0,using='finance'),self.assertNumQueries(0,using='default'):
            body=service.verify(draft)
        member=body['members'][0]; cells=member['opening']
        self.assertEqual(cells['half_amount']['net'],'900.00'); self.assertEqual(cells['estimate']['net'],'1000.00')
        self.assertEqual(cells['current_total']['net'],'900.00')
        self.assertEqual(cells['current_total']['reference_column'],'half_amount')
        self.assertEqual(cells['proposed']['net'],'1100.00')
        self.assertEqual(member['draft_resource_ending'],dict(prior_amount='900.00',half_amount='800.00',
            estimate='990.00',current_total='790.00',proposed='200.00'))
        self.assertFalse(member['certified_actual_closing_cash'])
        for flag in ('stock_complete','independently_reviewed','philhealth_deduction_complete','form_issued','cash_available'):
            self.assertFalse(body[flag])
        self.assertEqual(service.reproduce(draft,self.preparer,evidence=self.evidence),body)
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_missing_boundaries_remain_unknown_and_stock_totals_are_not_added(self):
        selected=deepcopy(self.selections)
        selected[0]['opening']['half_amount']=dict(kind='missing',basis='January actual certificate unavailable')
        draft=self.capture_stock(selections=selected)
        member=draft['payload']['members'][0]
        self.assertIsNone(member['opening']['half_amount']['net'])
        self.assertIsNone(member['opening']['current_total']['net'])
        self.assertIsNone(member['draft_resource_ending']['current_total'])
        self.assertEqual(member['opening']['estimate']['net'],'1000.00')
        self.assertFalse(member['opening_coverage_complete'])
        changed=deepcopy(draft); changed['payload']['members'][0]['opening']['current_total']['net']='1900.00'
        changed['checksum']=checksum(changed['payload'])
        with self.assertRaises(ValidationError):service.verify(changed)

    def test_wrong_calendar_actual_forecast_and_worksheet_selections_fail(self):
        for column,source,kind in (('prior_amount',self.half,'actual'),('half_amount',self.estimate,'forecast'),
            ('proposed',self.half,'actual'),('estimate',self.proposed,'forecast')):
            selected=deepcopy(self.selections);selected[0]['opening'][column]=dict(kind=kind,source=source)
            with self.subTest(column=column),self.assertRaises(ValidationError):self.capture_stock(selections=selected)
        selected=deepcopy(self.selections); selected[0]['opening']['current_total']=dict(kind='actual',source=self.half)
        with self.assertRaises(ValidationError):self.capture_stock(selections=selected)
        with self.assertRaises(ValidationError):self.capture_stock(stock_convention='add_semester_stocks')
        wrong=dict(self.evidence);wrong[self.estimate['checksum']]+=b'changed'
        with self.assertRaises(ValidationError):self.capture_stock(evidence=wrong)
        with self.assertRaises(ValidationError):self.capture_stock(evidence=None)

    def test_source_export_revocation_and_successors_preserve_original_draft(self):
        draft=self.capture_stock()
        with self.assertRaises(PermissionDenied):service.reproduce(draft,self.preparer,evidence=self.evidence,export=True)
        permission=Permission.objects.get(content_type__app_label='accounting',codename='export_budget_cash_evidence')
        self.preparer.user_permissions.add(permission)
        self.assertEqual(service.reproduce(draft,self.preparer,evidence=self.evidence,export=True),draft['payload'])
        self.preparer.user_permissions.remove(permission)
        with self.assertRaises(PermissionDenied):service.reproduce(draft,self.preparer,evidence=self.evidence,export=True)
        self.cash(date(2026,1,1),expected_latest=1)
        with self.assertRaises(ValidationError):self.capture_stock()
        self.assertEqual(service.reproduce(draft,self.preparer,evidence=self.evidence),draft['payload'])
