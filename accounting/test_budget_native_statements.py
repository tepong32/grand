from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import budget_native_statements as statements
from . import budget_attributions as attribution
from . import test_budget_attributions as fixtures
from .models import ResponsibilityCenter
from .services import create_reversal, submit_entry, post_entry


class NativeStatementPreparationTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.BudgetAttributionTests.setUpTestData.__func__)
    employee = classmethod(fixtures.BudgetAttributionTests.employee.__func__)
    setUp = fixtures.BudgetAttributionTests.setUp
    make_call = fixtures.BudgetAttributionTests.make_call
    make_version = fixtures.BudgetAttributionTests.make_version
    add_line = fixtures.BudgetAttributionTests.add_line
    add_ceiling = fixtures.BudgetAttributionTests.add_ceiling
    grant = fixtures.BudgetAttributionTests.grant
    attribute_grant = fixtures.BudgetAttributionTests.attribute_grant
    journal = fixtures.BudgetAttributionTests.journal
    capture = fixtures.BudgetAttributionTests.capture
    rows = fixtures.BudgetAttributionTests.rows
    propose = fixtures.BudgetAttributionTests.propose
    review = fixtures.BudgetAttributionTests.review

    def test_split_office_totals_reconcile_all_lines_without_live_reads(self):
        other = ResponsibilityCenter.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, code='SECOND', name='Second office',
            office_id=self.budget_office.pk)
        rows = self.rows()
        rows[0]['amount'] = '60'
        rows.append(dict(rows[0], amount='40', center_id=other.pk))
        self.review(self.propose(rows))
        captured = self.capture()
        frozen = deepcopy(captured)
        with CaptureQueriesContext(connections['finance']) as queries:
            result = statements.project(captured)
        self.assertEqual(len(queries), 0)
        self.assertEqual(captured, frozen)
        data = result['payload']
        self.assertTrue(data['classification_complete'])
        self.assertFalse(data['certificate'])
        self.assertEqual(data['total'], '100.00')
        self.assertEqual(sorted(row['amount'] for row in data['rows']), ['40.00', '60.00'])
        self.assertEqual(len(data['bridge']), 2)
        self.assertEqual(data['coverage']['include']['debit'], '100.00')
        self.assertEqual(data['coverage']['exclude']['credit'], '100.00')
        # A later setup edit cannot rewrite the prepared output.
        other.name = 'Renamed'; other.save()
        self.assertEqual(statements.project(captured), result)

    def test_missing_and_unresolved_coverage_cannot_look_complete(self):
        missing = statements.project(self.capture())['payload']
        self.assertFalse(missing['classification_complete'])
        self.assertEqual(missing['coverage']['unreviewed']['debit'], '100.00')
        self.assertEqual(len(missing['bridge']), 2)
        rows = self.rows()
        rows[0] = dict(line_id=rows[0]['line_id'], amount='100', disposition='unresolved',
            purpose='unresolved', basis='Need actual office evidence')
        self.review(self.propose(rows))
        result = statements.project(self.capture())['payload']
        self.assertFalse(result['classification_complete'])
        self.assertEqual(result['issues'][0]['kind'], 'unresolved')
        self.assertEqual(result['coverage']['unresolved']['debit'], '100.00')
        self.assertEqual(result['rows'], [])

    def test_empty_scope_is_not_certified_zero(self):
        result = statements.project(self.capture(period_end=date(2026, 5, 31)))['payload']
        self.assertFalse(result['classification_complete'])
        self.assertEqual(result['issues'], [{'kind': 'empty_cohort_requires_evidence'}])
        self.assertFalse(result['certificate'])

    def test_reversal_keeps_gross_columns_and_changed_sources_do_not_rewrite_output(self):
        self.review(self.propose())
        original = statements.project(self.capture())
        reverse = create_reversal(self.entry, self.maker, reference='STATEMENT-REVERSAL',
            period=self.entry.period, entry_date=date(2026, 6, 30), reason='Synthetic exact correction')
        submit_entry(reverse, self.maker); post_entry(reverse, self.checker)
        captured = self.capture()
        records = attribution.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 1, 1), period_end=date(2026, 6, 30),
            expected_source_checksum=captured['checksum'],
            proposals=[dict(entry_id=reverse.pk, expected_latest=0,
                allocations=attribution.reversal_allocations(captured, reverse.pk))],
            reason='Exact mirrored reversal', evidence_reference='SYN-STATEMENT')
        self.review(records)
        result = statements.project(self.capture())
        self.assertEqual(original['payload']['total'], '100.00')
        self.assertEqual(result['payload']['total'], '0.00')
        self.assertEqual(result['payload']['rows'][0]['debit'], '100.00')
        self.assertEqual(result['payload']['rows'][0]['credit'], '100.00')
        self.assertTrue(result['payload']['classification_complete'])
        self.assertNotEqual(result['checksum'], original['checksum'])
        self.journal('NEW-BACKDATED', date(2026, 6, 30), Decimal('5'))
        self.assertFalse(statements.project(self.capture())['payload']['classification_complete'])

    def test_tampered_evidence_fails(self):
        captured = self.capture()
        captured['payload']['controls']['debit'] = '0.00'
        with self.assertRaises(ValidationError):
            statements.project(captured)

    def test_prior_period_origin_is_evidence_only_and_authorized_prepare_reads_once(self):
        self.review(self.propose())
        old = self.journal('PRIOR-STATEMENT', date(2025, 12, 31), Decimal('100'))
        old_capture = self.capture(period_start=date(2025, 1, 1), period_end=date(2025, 12, 31))
        records = attribution.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2025, 1, 1), period_end=date(2025, 12, 31),
            expected_source_checksum=old_capture['checksum'],
            proposals=[dict(entry_id=old.pk, expected_latest=0, allocations=self.rows(old))],
            reason='Prior actual expenditure', evidence_reference='SYN-PRIOR')
        self.review(records)
        reverse = create_reversal(old, self.maker, reference='PRIOR-CORRECTION',
            period=self.entry.period, entry_date=date(2026, 6, 30), reason='Exact prior correction')
        submit_entry(reverse, self.maker); post_entry(reverse, self.checker)
        captured = self.capture()
        records = attribution.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 1, 1), period_end=date(2026, 6, 30),
            expected_source_checksum=captured['checksum'],
            proposals=[dict(entry_id=reverse.pk, expected_latest=0,
                allocations=attribution.reversal_allocations(captured, reverse.pk))],
            reason='Current correction of prior expenditure', evidence_reference='SYN-CURRENT')
        self.review(records)
        with CaptureQueriesContext(connections['finance']) as queries:
            result = statements.prepare(actor=self.maker, fund_id=self.fund.pk,
                period_start=date(2026, 1, 1), period_end=date(2026, 6, 30))
        self.assertEqual(len(queries), 1)
        self.assertEqual(result['statement']['payload']['total'], '0.00')
        self.assertNotIn(old.pk, [row['entry_id'] for row in result['statement']['payload']['bridge']])
        self.assertIn(old.pk, [row['id'] for row in result['source']['payload']['lineage_sources']])
