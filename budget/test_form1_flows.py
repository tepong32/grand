from copy import deepcopy
from django.core.exceptions import PermissionDenied, ValidationError
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry
from accounting.summary_actuals import RECEIPTS
from . import test_receipt_forecast_reviews as fixtures
from . import form1_flows as service
from . import receipt_forecast_reviews, receipt_forecasts
from . import summary_reconciliations


class Form1FlowTests(fixtures.ReceiptForecastReviewFixture):
    def setUp(self):
        super().setUp()
        self.approved = self.review_forecast(self.prepare_forecast())

    def test_whole_source_flow_capture_and_query_free_reproduction(self):
        before = JournalEntry.objects.count()
        captured = service.capture(forecast=self.approved, actor=self.preparer)
        original = deepcopy(captured)
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            body = service.verify(captured)
        self.assertEqual(captured, original)
        member = body['members'][0]
        self.assertEqual(member['receipt']['totals'], dict(prior_amount='0.00', half_amount='0.00',
            estimate='30.00', current_total='30.00', proposed='100.00'))
        self.assertEqual(member['expenditure']['totals']['half_amount'], '100.00')
        self.assertEqual(len(member['receipt']['rows']), 21)
        self.assertEqual(len(member['expenditure']['rows']), 5)
        self.assertTrue(body['flow_coverage_complete'])
        for key in ('stock_complete', 'account_itemization_complete', 'philhealth_deduction_complete', 'form_issued', 'cash_available'):
            self.assertFalse(body[key])
        self.assertEqual(JournalEntry.objects.count(), before)

    def test_missing_actual_categories_never_create_zero_or_current_total(self):
        source = dict(rows=[dict(kind='receipt', category='service', amount='0.00')], totals=dict(receipt='0.00'))
        amounts = service.actual_leaves(source, 'receipt', RECEIPTS)
        self.assertEqual(amounts['service'], '0.00')
        self.assertIsNone(amounts['philhealth'])
        complete = {key:'0.00' for key in RECEIPTS}
        with self.assertNumQueries(0, using='finance'):
            rows = service.flow_rows(RECEIPTS, amounts, amounts, complete, complete)
        self.assertIsNone(rows['totals']['prior_amount'])
        self.assertIsNone(rows['totals']['current_total'])
        self.assertEqual(rows['totals']['estimate'], '0.00')
        source['totals']['receipt'] = '1.00'
        with self.assertRaises(ValidationError): service.actual_leaves(source, 'receipt', RECEIPTS)

    def test_mixed_routes_do_not_bypass_whole_fund_entity_capacity(self):
        for routes in (('native', 'historical'), ('historical', 'native')):
            with self.subTest(routes=routes):
                periods = {}
                args = dict(fund_id=1, start='2026-01-01', end='2026-06-30')
                service.claim_period(periods, **args, entity='general', route=routes[0])
                with self.assertRaises(ValidationError):
                    service.claim_period(periods, **args, entity='enterprise', route=routes[1])
                service.claim_period(periods, **dict(args, fund_id=2), entity='enterprise', route=routes[1])

    def test_original_office_context_reproduces_future_columns_without_queries(self):
        captured = service.capture(forecast=self.approved, actor=self.preparer)
        form = captured['payload']['sources']['reconciliations'][0]['payload']['forms'][0]
        args = dict(proposal=str(self.version.public_id), department_id=self.version.department_id, fund_id=self.fund.pk)
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            service.verify(captured)
            service.office_schedule(form, **args)
        changed = deepcopy(form)
        changed['payload']['schedule']['rows'][0]['estimate'] = '999.00'
        changed['payload_checksum'] = checksum(changed['payload'])
        with self.assertRaises(ValidationError): service.office_schedule(changed, **args)
        with self.assertRaises(ValidationError): service.office_schedule(form, **dict(args, proposal='another-proposal'))

    def test_permissions_stale_capture_and_unchanged_retained_evidence(self):
        captured = service.capture(forecast=self.approved, actor=self.preparer)
        with self.assertRaises(PermissionDenied): service.capture(forecast=self.approved, actor=self.maker)
        self.revenue.title = 'Later original chart change'
        self.revenue.save(update_fields=['title'])
        with self.assertRaises(ValidationError): service.capture(forecast=self.approved, actor=self.preparer)
        with self.assertNumQueries(0, using='finance'): service.verify(captured)

    def test_derived_tamper_and_parent_omission_are_rejected(self):
        captured = service.capture(forecast=self.approved, actor=self.preparer)
        changed = deepcopy(captured)
        changed['payload']['members'][0]['receipt']['totals']['proposed'] = '200.00'
        changed['checksum'] = checksum(changed['payload'])
        with self.assertRaises(ValidationError): service.verify(changed)
        sources = deepcopy(captured['payload']['sources'])
        sources['reconciliations'] = []
        with self.assertRaises(ValidationError): service.compose(sources)
        sources = deepcopy(captured['payload']['sources'])
        sources['forecast']['reviewed_totals']['general']['proposed'] = '200.00'
        with self.assertRaises(ValidationError): service.compose(sources)

    def test_two_real_declared_entities_cannot_reuse_one_native_fund_cohort(self):
        prior = self.make_actuals(2025, 12, entity_key='enterprise:synthetic', entity_label='Synthetic enterprise')
        half = self.make_actuals(2026, 6, entity_key='enterprise:synthetic', entity_label='Synthetic enterprise')
        parent = summary_reconciliations.prepare(**self.args(prior_id=prior.public_id,
            half_id=half.public_id, entity_key='enterprise:synthetic'))
        self.accept(parent); parent.refresh_from_db()
        second = receipt_forecasts.capture(reconciliation=parent, actor=self.preparer)
        proposals = []
        for captured in (self.captured, second):
            entity = captured['payload']['scope']['entity_key']
            args = self.inputs()
            for column, key, amount in (('half_components', 'half_estimate', '15'),
                                       ('proposed_components', 'proposed', '50')):
                parts = args[column]
                for row in parts:
                    row['amount'] = amount
                    row['coverage_key'] = entity+'-funding'
                for row in list(parts):
                    excluded = dict(row, key=row['key']+'-unused', disposition='exclude', category='',
                        account_id=None, coverage_key='', overlap_of='', basis='Explicit unused entity share')
                    parts.append(excluded)
                args['coverage'][key] = self.coverage(parts)
            proposals.append(receipt_forecasts.propose(captured, **args))
        entities = sorted([dict(key=proposal['payload']['capture']['payload']['scope']['entity_key'],
            label=proposal['payload']['capture']['payload']['scope']['entity_label']) for proposal in proposals], key=lambda row:row['key'])
        record = self.review_forecast(self.prepare_forecast(proposals=proposals, entity_inventory=entities, expected_latest=1))
        before = JournalEntry.objects.count()
        with self.assertRaisesMessage(ValidationError, 'reuse whole actuals'):
            service.capture(forecast=record, actor=self.preparer)
        self.assertEqual(JournalEntry.objects.count(), before)
