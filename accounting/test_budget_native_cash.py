from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError

from .test_budget_opening_components import OpeningComponentTests
from . import budget_native_cash as service
from .models import Fund, LedgerAccount, PostingMapping, JournalEntry, JournalLine, OpeningBalanceBatch
from .services import create_reversal, validate_opening_batch, submit_opening_batch, decide_opening_batch, post_opening_batch, reconcile_opening_batch


class NativeCashTests(OpeningComponentTests):
    def setUp(self):
        super().setUp()
        self.configure_cash()

    def configure_cash(self):
        from reporting.models import FinanceStatementMapping, FinanceStatementLine
        from reporting.statement_services import submit_statement_mapping, review_statement_mapping
        self.bank = LedgerAccount.objects.create(**self.owner, code='BANK', title='Synthetic bank', account_type='asset', normal_balance='debit')
        PostingMapping.objects.create(**self.owner, category=PostingMapping.BANK, source_code='bank', label='Synthetic bank', account=self.bank)
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label='accounting', codename='view_budget_cash_evidence'))
        for actor, code in ((self.maker, 'manage_report_definitions'), (self.poster, 'approve_reports')):
            actor.user_permissions.add(Permission.objects.get(content_type__app_label='reporting', codename=code))
        self.mapping = FinanceStatementMapping.objects.create(department=self.department,
            statement_type=FinanceStatementMapping.CASH_FLOW, version=1, title='Synthetic cash inventory',
            authority_reference='Synthetic cash and bank inventory', local_acceptance_note='Synthetic scope only', created_by=self.maker)
        FinanceStatementLine.objects.create(mapping=self.mapping, position=1, section_code='cash', section_title='Cash',
            line_code='cash', line_title='Cash inventory', selector_type=FinanceStatementLine.ACCOUNT_CODES, account_codes=['cash', 'BANK'])
        submit_statement_mapping(self.mapping, self.maker)
        review_statement_mapping(self.mapping, self.poster, approve=True, note='Independent inventory review')
        self.batch = self.original.opening_balance_posting.batch

    def cash_capture(self, day=4, boundary='end_of_day', **changes):
        values = dict(actor=self.maker, fund_id=self.fund.pk, opening_batch_id=self.batch.pk,
            entity_key='general', coverage_authority='Explicit synthetic General Fund opening/entity coverage',
            balance_date=date(2026, 9, day), boundary=boundary)
        values.update(changes); return service.capture(**values)

    def test_cumulative_cash_boundaries_transfer_reversal_and_capture_guards(self):
        payment = self.post(self.entry('CASH-PAYMENT', Decimal('400'), source=self.source, day=4))
        deposit = JournalEntry.objects.create(**self.owner, reference='CASH-DEPOSIT', fund=self.fund, period=self.period,
            entry_date=date(2026, 9, 4), description='Synthetic internal deposit', created_by_id=self.maker.pk,
            created_by_label=self.maker.username)
        JournalLine.objects.create(entry=deposit, sequence=1, account=self.bank, debit=50, cash_flow_category='internal')
        JournalLine.objects.create(entry=deposit, sequence=2, account=self.accounts['cash'], credit=50, cash_flow_category='internal')
        self.post(deposit)
        count = JournalEntry.objects.count()
        start = self.cash_capture(boundary='start_of_day')['payload']
        artifact = self.cash_capture(); end = service.verify(artifact)
        self.assertEqual(start['gross'], '1000.00')
        self.assertEqual(end['gross'], '600.00')
        self.assertEqual(end['account_balances'], {'BANK': '50.00', 'cash': '550.00'})
        self.assertEqual(end['restriction_status'], 'not_supplied')
        self.assertEqual(end['certification_status'], 'not_certified')
        self.assertEqual(JournalEntry.objects.count(), count)
        self.assertTrue(service.is_current(artifact, self.maker))
        self.assertEqual(self.cash_capture()['source_checksum'], artifact['source_checksum'])
        future = self.cash_capture(5)
        retained = deepcopy(end)
        reversal = create_reversal(payment, self.maker, reference='CASH-RETURN', entry_date=date(2026, 9, 5), period=self.period, reason='Synthetic exact bank return')
        self.post(reversal)
        self.assertEqual(self.cash_capture(5, 'start_of_day')['payload']['gross'], '600.00')
        self.assertEqual(self.cash_capture(5)['payload']['gross'], '1000.00')
        self.assertFalse(service.is_current(future, self.maker))
        self.assertEqual(service.verify(future)['gross'], '600.00')
        self.assertEqual(end, retained)
        corrupt = deepcopy(artifact); corrupt['payload']['gross'] = '999.00'
        with self.assertRaises(ValidationError): service.verify(corrupt)
        omitted = deepcopy(end['mapping']); omitted['accounts'] = [row for row in omitted['accounts'] if row['code'] != 'BANK']
        with self.assertRaisesMessage(ValidationError, 'reviewed scope'):
            service.project(end['ledger'], omitted, end['opening'], balance_date=date(2026, 9, 4), boundary='end_of_day', entity_key='general', coverage_authority='Explicit coverage')
        changed = deepcopy(end['mapping']); changed['reviewed_by'] += 1
        with patch.object(service, 'mapping_evidence', side_effect=[end['mapping'], changed]), self.assertRaisesMessage(ValidationError, 'changed during capture'):
            self.cash_capture()
        with self.assertRaisesMessage(ValidationError, 'earlier'):
            self.cash_capture(day=1, balance_date=date(2026, 8, 31))

    def test_explicit_zero_opening_scope_and_missing_or_conflicting_baseline(self):
        empty = Fund.objects.create(**self.owner, code='EMPTY', name='Synthetic explicit zero fund')
        with self.assertRaisesMessage(ValidationError, 'no exact posting'):
            self.cash_capture(fund_id=empty.pk)
        zero = OpeningBalanceBatch.objects.create(**self.owner, fiscal_year=self.batch.fiscal_year, period=self.period,
            title='Synthetic zero ledger', source_reference='ZERO-CASH', is_zero_balance_declaration=True,
            created_by_id=self.maker.pk, created_by_label=self.maker.username)
        zero = validate_opening_batch(zero, self.maker)
        zero = submit_opening_batch(zero, self.maker)
        zero = decide_opening_batch(zero, self.poster, decision=OpeningBalanceBatch.APPROVED, evidence_note='Independent explicit zero evidence')
        zero = post_opening_batch(zero, self.poster)
        zero, result = reconcile_opening_batch(zero, self.poster)
        self.assertTrue(result['reconciled'])
        count = JournalEntry.objects.count()
        captured = self.cash_capture(fund_id=empty.pk, opening_batch_id=zero.pk)['payload']
        self.assertEqual(captured['gross'], '0.00')
        self.assertTrue(captured['opening']['zero'])
        self.assertEqual(captured['scope']['fund']['id'], empty.pk)
        self.assertEqual(JournalEntry.objects.count(), count)
        with self.assertRaisesMessage(ValidationError, 'Unexpected'):
            self.cash_capture(opening_batch_id=zero.pk)
        with self.assertRaises(ValidationError):
            self.cash_capture(fund_id=empty.pk, opening_batch_id=zero.pk, coverage_authority='')

    def test_retained_decisions_and_projection_reproduce_without_live_source_reads(self):
        artifact = self.cash_capture()
        payload = artifact['payload']
        self.assertEqual(payload['schema'], 2)
        self.assertEqual(payload['mapping']['activation']['reason'], 'Independent inventory review')
        self.assertIn('created_at', payload['mapping']['activation'])
        self.assertEqual(payload['mapping']['activation'], payload['mapping']['events'][-1])
        opening_actions = {event['action'] for event in payload['opening']['events']}
        self.assertTrue({'approved', 'posted', 'reconciled'} <= opening_actions)
        approval = next(event for event in payload['opening']['events'] if event['action'] == 'approved')
        self.assertEqual(approval['actor'], self.poster.pk)
        self.assertTrue(approval['reason'])
        self.assertIn('actor_label', approval)
        with patch.object(service, 'mapping_evidence', side_effect=AssertionError('No live mapping read')), \
             patch.object(service, 'opening_source', side_effect=AssertionError('No live opening read')), \
             self.assertNumQueries(0, using='default'), self.assertNumQueries(0, using='finance'):
            self.assertEqual(service.verify(artifact), payload)

        # Even a recomputed outer fingerprint cannot substitute inconsistent
        # controls or decision evidence in a trusted retained artifact.
        def rehash(value):
            value['checksum'] = service.checksum(value['payload'])
            value['source_checksum'] = service.source_checksum(value['payload'])
            return value
        corrupt = deepcopy(artifact); corrupt['payload']['gross'] = '999.00'
        with self.assertRaisesMessage(ValidationError, 'source projection'):
            service.verify(rehash(corrupt))
        corrupt = deepcopy(artifact)
        corrupt['payload']['opening']['events'] = [event for event in corrupt['payload']['opening']['events'] if event['action'] != 'approved']
        with self.assertRaisesMessage(ValidationError, 'original source decision'):
            service.verify(rehash(corrupt))
        corrupt = deepcopy(artifact); corrupt['payload']['mapping']['activation']['actor'] = self.maker.pk
        with self.assertRaisesMessage(ValidationError, 'independent activation'):
            service.verify(rehash(corrupt))
        corrupt = deepcopy(artifact); corrupt['payload']['opening']['postings'][0]['row_count'] += 1
        with self.assertRaisesMessage(ValidationError, 'financial lines'):
            service.verify(rehash(corrupt))
        corrupt = deepcopy(artifact)
        posted = next(event for event in corrupt['payload']['opening']['events'] if event['action'] == 'posted')
        posted['snapshot']['journal_entries'] = []
        with self.assertRaisesMessage(ValidationError, 'posting decisions'):
            service.verify(rehash(corrupt))
        malformed = {'payload': {'kind': 'native_budget_gross_cash', 'schema': 2}}
        malformed['checksum'] = service.checksum(malformed['payload'])
        with self.assertRaisesMessage(ValidationError, 'invalid source structure'):
            service.verify(malformed)
