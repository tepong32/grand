from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from . import budget_attributions as service
from . import budget_native_sources
from . import claim_attributions as history
from . import test_budget_claim_sources as claims
from . import test_budget_component_usage as fixtures
from .budget_component_usage import component_usage
from .budget_reviewed_components import source_components
from .models import FiscalYear, JournalEntry, OpeningBalanceBatch, ResponsibilityCenter
from .services import stage_opening_csv, submit_opening_batch, decide_opening_batch, post_opening_batch, reconcile_opening_batch


class StructuralComponentNormalizationTests(SimpleTestCase):
    def test_component_evidence_does_not_include_the_structural_movement(self):
        source = {'journal': {'reversal_of_id': None, 'lines': [
            {'id': 1, 'account_id': 1, 'account': {'account_type': 'liability'},
             'debit': '0.00', 'credit': '400.00', 'payable_origin_id': None}]},
            'lineage': {'origin_source_type': 'opening', 'issue': ''}}
        rows = [dict(line_id=1, amount='400.00', disposition='exclude', purpose='opening',
                     basis='Explicit retained principal evidence', claim_component_basis='loan_principal')]
        for origin in ('opening', 'closing', *JournalEntry.DIRECT_EQUITY_SOURCES):
            with self.subTest(origin=origin):
                source['lineage']['origin_source_type'] = origin
                self.assertEqual(service.normalize(source, rows, {})[0]['disposition'], 'exclude')
                included = deepcopy(rows)
                included[0].update(disposition='include', purpose='debt_principal')
                with self.assertRaisesMessage(ValidationError, 'cannot become period expenditure'):
                    service.normalize(source, included, {})


class OpeningComponentTests(TestCase):
    databases = {'default', 'finance'}
    entry = fixtures.ComponentUsageTests.entry
    post = fixtures.ComponentUsageTests.post
    approve = fixtures.ComponentUsageTests.approve
    reference = fixtures.ComponentUsageTests.reference
    payment_rows = fixtures.ComponentUsageTests.payment_rows
    capture = fixtures.ComponentUsageTests.capture
    propose = fixtures.ComponentUsageTests.propose
    reverse_and_review = fixtures.ComponentUsageTests.reverse_and_review

    def rows(self):
        rows = fixtures.ComponentUsageTests.rows(self)
        for row in rows:
            row['purpose'] = 'opening'
        return rows

    def setUp(self):
        claims.BudgetClaimSourceTests.setUp(self)
        for actor, names in ((self.maker, ('prepare_opening_balances', 'prepare_budget_attributions')),
                             (self.poster, ('approve_opening_balances', 'post_opening_balances',
                                            'review_budget_attributions', 'view_budget_attributions'))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting', codename__in=names))
        year = FiscalYear.objects.create(**self.owner, year=2026, label='Synthetic opening year',
            starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31), business_date=date(2026, 9, 1),
            status=FiscalYear.APPROVED, created_by_id=self.maker.pk)
        self.period.fiscal_year_record = year
        self.period.save(update_fields=('fiscal_year_record',))
        batch = OpeningBalanceBatch.objects.create(**self.owner, fiscal_year=year, period=self.period,
            title='Synthetic retained opening liabilities', source_reference='SYN-OPENING-COMPONENTS',
            expected_row_count=2, expected_debit=1000, expected_credit=1000,
            created_by_id=self.maker.pk, created_by_label=self.maker.username)
        csv = b'fund_code,account_code,debit,credit\nGF,cash,1000,0\nGF,payable,0,1000\n'
        batch = stage_opening_csv(batch, self.maker, SimpleUploadedFile('opening.csv', csv))
        batch = submit_opening_batch(batch, self.maker)
        batch = decide_opening_batch(batch, self.poster, decision=OpeningBalanceBatch.APPROVED,
                                     evidence_note='Independently checked retained opening schedule')
        batch = post_opening_batch(batch, self.poster)
        batch, result = reconcile_opening_batch(batch, self.poster)
        self.assertTrue(result['reconciled'])
        self.original = batch.postings.get().entry
        self.source = self.original.lines.get(sequence=2)
        proposal = history.propose(self.source, self.maker, applications=[], party_key='supplier-001',
            claim_reference='OPENING-CLAIM', evidence_reference='SYN-OPENING-DEBT-SCHEDULE',
            reason='Explicit identity from retained opening liability evidence', expected_version=0)
        history.review(proposal, self.poster, approve=True, note='Checked exact original liability identity')
        self.center = ResponsibilityCenter.objects.create(**self.owner, code='OFFICE', name='Synthetic office',
                                                         office_id=self.department.pk)

    def prepare_payment(self):
        self.approve(self.propose())
        self.bound = source_components(self.capture(), self.source.pk)
        self.payment = self.post(self.entry('OPENING-PAYMENT', Decimal('600'), source=self.source, day=4))

    def test_governed_opening_supports_later_principal_without_counting_opening_or_prior_expense(self):
        before = list(self.original.lines.values('id', 'account_id', 'debit', 'credit', 'payable_origin_id'))
        self.prepare_payment()
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        with CaptureQueriesContext(connections['finance']) as queries:
            captured = budget_native_sources.capture(actor=self.maker, fund_id=self.fund.pk,
                period_start=date(2026, 9, 4), period_end=date(2026, 9, 10))
            projected = service.reviewed_allocations(captured)
            usage = component_usage(captured, require_complete=True)
        self.assertEqual(len(queries), 1)
        self.assertEqual([row['entry_id'] for row in projected], [self.payment.pk])
        included = [row for item in projected for row in item['allocations'] if row['disposition'] == 'include']
        self.assertEqual(sum(Decimal(row['signed_amount']) for row in included), Decimal('200'))
        self.assertTrue(usage['complete'])
        self.assertEqual(before, list(self.original.lines.values('id', 'account_id', 'debit', 'credit', 'payable_origin_id')))
        full = service.reviewed_allocations(self.capture())
        opening = next(item for item in full if item['entry_id'] == self.original.pk)
        self.assertTrue(all(row['disposition'] == 'exclude' for row in opening['allocations']))
        retained = deepcopy(captured)
        self.reverse_and_review(self.payment, 'OPENING-PAYMENT-RETURN', 5)
        self.assertEqual(service.reviewed_allocations(retained), projected)
        current = service.reviewed_allocations(self.capture())
        self.assertEqual(sum(Decimal(row['signed_amount']) for item in current for row in item['allocations']
                             if row['disposition'] == 'include'), Decimal('0'))

    def test_opening_basis_is_not_inferred_and_prior_expense_cannot_be_counted_again(self):
        incomplete = self.rows()
        del incomplete[-1]['claim_component_basis']
        self.approve(self.propose(incomplete))
        with self.assertRaisesMessage(ValidationError, 'Every source-credit component'):
            source_components(self.capture(), self.source.pk)
        self.approve(self.propose(version=1))
        self.bound = source_components(self.capture(), self.source.pk)
        self.payment = self.post(self.entry('OPENING-PAYMENT', Decimal('600'), source=self.source, day=4))
        rows = self.payment_rows()
        rows[0]['claim_component'] = self.reference('recognized_expenditure')
        with self.assertRaisesMessage(ValidationError, 'second expenditure'):
            self.propose(rows, entry=self.payment)
