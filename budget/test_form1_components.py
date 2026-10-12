from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from accounting.cash_classifications import checksum
from accounting.models import JournalEntry, JournalLine, LedgerAccount, AccountingPeriod
from accounting.services import submit_entry, post_entry
from accounting import budget_receipt_sources, budget_receipt_attributions, budget_native_sources, budget_attributions
from accounting import summary_actuals, test_summary_actuals as historical_fixtures
from . import test_receipt_forecast_reviews as fixtures
from . import form1_flows, form1_components as service
from . import summary_reconciliations, receipt_forecasts


class Form1ComponentTests(fixtures.ReceiptForecastReviewFixture):
    def setUp(self):
        super().setUp()
        approved = self.review_forecast(self.prepare_forecast())
        self.flows = form1_flows.capture(forecast=approved, actor=self.preparer)

    def test_complete_original_component_inventory_is_pure_and_not_account_authority(self):
        before = JournalEntry.objects.count()
        original = deepcopy(self.flows)
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            inventory = service.inventory(self.flows)
            body = service.verify(inventory)
        self.assertEqual(self.flows, original)
        self.assertEqual(len(body['controls']), (21+5)*4)
        self.assertTrue(all(row['coverage'] == 'covered' for row in body['controls']))
        self.assertFalse(body['account_itemization_complete'])
        self.assertFalse(body['independently_reviewed'])
        self.assertFalse(body['form_issued'])
        self.assertTrue(all(row['identity']['column'] != 'current_total' for row in body['components']))
        receipts = [row for row in body['components'] if row['identity']['kind'] == 'receipt']
        self.assertEqual(sorted(row['amount'] for row in receipts), ['100.00', '30.00'])
        self.assertTrue(all(row['reporting_account_status'] == 'not_mapped' for row in body['components']))
        self.assertEqual(JournalEntry.objects.count(), before)

    def test_rehashed_component_amount_and_omission_do_not_reproduce(self):
        captured = service.inventory(self.flows)
        for omitted in (False, True):
            changed = deepcopy(captured)
            if omitted:
                changed['payload']['components'].pop()
            else:
                changed['payload']['components'][0]['amount'] = '999.00'
            changed['checksum'] = checksum(changed['payload'])
            with self.assertRaises(ValidationError): service.verify(changed)

    def test_real_historical_zero_rows_preserve_missing_categories_and_null_source_accounts(self):
        def document():
            from reportlab.pdfgen import canvas
            stream=BytesIO(); page=canvas.Canvas(stream)
            for number, line in enumerate(('SYNTHETIC TEST ONLY: General Fund 2025 joint zero source/TB',
                'R1 service receipts 0; E1 MOOE expenditure 0; other categories unspecified',
                'Synthetic Treasurer: authority T, July 1 2026', 'Synthetic Accountant: authority A, July 2 2026')):
                page.drawString(30,790-number*25,line)
            page.save()
            return SimpleUploadedFile('synthetic-2025-zero.pdf',stream.getvalue(),content_type='application/pdf')
        fixture=SimpleNamespace(maker=self.maker,fund=self.fund,budget_office=self.budget_office,
            operating_office=self.treasury,receipt_account=self.revenue,account=self.account,document=document)
        args=historical_fixtures.SummaryActualTests.arguments(fixture,period_start=date(2025,1,1),period_end=date(2025,12,31),
            receipt_total='0',expenditure_total='0',rows=[
                dict(kind='receipt',category='service',account_id=None,amount='0',source_row='R1'),
                dict(kind='expenditure',category='mooe',account_id=None,amount='0',source_row='E1')])
        source=summary_actuals.review(summary_actuals.propose(**args),self.checker,approve=True,
            note='Verified synthetic original zero rows only',authority='Independent adoption authority',verified_documents=True)
        parent=summary_reconciliations.prepare(**self.args(prior_id=source.public_id,prior_route='historical',expected_latest=1))
        self.accept(parent); parent.refresh_from_db()
        self.captured=receipt_forecasts.capture(reconciliation=parent,actor=self.preparer)
        self.forecast=receipt_forecasts.propose(self.captured,**self.inputs())
        approved=self.review_forecast(self.prepare_forecast(expected_latest=1))
        before=JournalEntry.objects.count()
        flows=form1_flows.capture(forecast=approved,actor=self.preparer)
        with self.assertNumQueries(0,using='default'),self.assertNumQueries(0,using='finance'):
            body=service.verify(service.inventory(flows))
        prior=[row for row in body['components'] if row['identity']['column']=='prior_amount']
        self.assertEqual(len(prior),2)
        self.assertTrue(all(row['amount']=='0.00' and row['source_account'] is None for row in prior))
        missing=[row for row in body['controls'] if row['coverage']=='missing']
        self.assertEqual(len(missing),24)
        self.assertTrue(all(row['declared_amount'] is None and row['component_keys']==[] for row in missing))
        self.assertEqual(JournalEntry.objects.count(),before)

    def test_real_reviewed_native_receipt_retains_cash_source_without_inferred_reporting_account(self):
        owner = dict(department_id=self.accounting_office.pk, department_label=self.accounting_office.name)
        period, _ = AccountingPeriod.objects.get_or_create(department_id=self.accounting_office.pk,
            fiscal_year=2026, period_number=6, defaults=dict(department_label=self.accounting_office.name,
                label='Synthetic component receipt period', starts_on=date(2026,6,1), ends_on=date(2026,6,30)))
        entry = JournalEntry.objects.create(**owner, period=period, fund=self.fund, reference='SYN-COMPONENT-RECEIPT',
            entry_date=date(2026,6,20), description='Synthetic manual cash receipt with explicit reviewed classification',
            source_type='manual', created_by_id=self.maker.pk, created_by_label=self.maker.username)
        cash = LedgerAccount.objects.get(department_id=self.accounting_office.pk, code='NATIVE-SYN-CASH')
        debit = JournalLine.objects.create(entry=entry, sequence=1, account=cash, debit='20.00')
        credit = JournalLine.objects.create(entry=entry, sequence=2, account=self.revenue, credit='20.00')
        submit_entry(entry, self.maker); post_entry(entry, self.checker)
        scope = dict(actor=self.maker, fund_id=self.fund.pk, period_start=date(2026,1,1), period_end=date(2026,6,30))
        observed = budget_receipt_sources.capture(**scope)
        batch = budget_receipt_attributions.propose_batch(**scope, expected_source_checksum=observed['source_checksum'],
            proposals=[dict(entry_id=entry.pk, expected_latest=0, rows=[
                dict(line_id=debit.pk, amount='20', disposition='include', purpose='receipt', category='service',
                    basis='Synthetic explicit cash service receipt classification'),
                dict(line_id=credit.pk, amount='20', disposition='exclude', purpose='counterpart', category='',
                    basis='Original revenue credit is not a second cash receipt')])],
            reason='Synthetic receipt component proof', evidence_reference='Synthetic original receipt worksheet')
        budget_receipt_attributions.review_batch(batch_id=batch.public_id, actor=self.checker, approve=True,
            note='Independently checked original cash and revenue counterpart')
        observed = budget_native_sources.capture(**scope)
        expense = budget_attributions.propose_batch(**scope, expected_source_checksum=observed['checksum'],
            proposals=[dict(entry_id=entry.pk, expected_latest=0, allocations=[dict(line_id=line.pk, amount='20',
                disposition='exclude', purpose='counterpart', basis='Receipt is not original expenditure activity') for line in (debit,credit)])],
            reason='Explicit expense exclusions', evidence_reference='Synthetic receipt source worksheet')
        budget_attributions.review_batch(batch_id=expense[0].batch_id, actor=self.checker, approve=True,
            note='Verified no expenditure from this receipt')
        half = self.make_actuals(2026,6,expected_latest=1)
        parent = summary_reconciliations.prepare(**self.args(half_id=half.public_id, expected_latest=1))
        self.accept(parent); parent.refresh_from_db()
        self.captured = receipt_forecasts.capture(reconciliation=parent, actor=self.preparer)
        self.forecast = receipt_forecasts.propose(self.captured, **self.inputs())
        approved = self.review_forecast(self.prepare_forecast(expected_latest=1))
        before = JournalEntry.objects.count()
        flows = form1_flows.capture(forecast=approved, actor=self.preparer)
        with self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            body = service.verify(service.inventory(flows))
        actual = [row for row in body['components'] if row['identity']['kind']=='receipt'
            and row['identity']['column']=='half_amount']
        self.assertEqual(len(actual),1)
        self.assertEqual(actual[0]['amount'],'20.00')
        self.assertEqual(actual[0]['source_account']['id'],cash.pk)
        self.assertEqual(actual[0]['evidence']['allocation']['line_id'],debit.pk)
        self.assertEqual(actual[0]['reporting_account_status'],'not_mapped')
        self.assertEqual(JournalEntry.objects.count(),before)
