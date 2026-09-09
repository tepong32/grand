"""Native concurrent HTTP matching preserves identity and controlled conflict feedback."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError, connections
from django.db.models.query import QuerySet
from django.test import Client, TransactionTestCase
from django.urls import reverse

from accounting.models import BankReconciliationEvent, BankStatementBatch, BankStatementMatch, BankStatementRow, PostingMapping
from accounting.services import auto_match_bank_statement, post_entry, stage_bank_statement_csv, submit_entry
from accounting import services as accounting_services, tests as accounting_tests

class BankMatchTransactionTests(TransactionTestCase):
    databases = {'default', 'finance'}
    _employee = classmethod(accounting_tests.StandaloneAccountingTests._employee.__func__)
    _grant = classmethod(accounting_tests.StandaloneAccountingTests._grant.__func__)
    _entry = accounting_tests.StandaloneAccountingTests._entry

    def _fixture(self):
        accounting_tests.StandaloneAccountingTests.setUpTestData.__func__(type(self))
        PostingMapping.objects.create(
            department_id=self.accounting_department.pk, department_label=self.accounting_department.name,
            category=PostingMapping.BANK, source_code='SYN-RACE-BANK', label='Synthetic race bank', account=self.cash,
        )
        entry = self._entry(reference='SYN-RACE-001')
        submit_entry(entry, self.preparer)
        post_entry(entry, self.poster)
        line = entry.lines.get(account=self.cash)
        rows = []
        for index in (1, 2):
            batch = BankStatementBatch.objects.create(
                department_id=self.accounting_department.pk, department_label=self.accounting_department.name,
                statement_reference=f'SYN-RACE-{index}', bank_account_code='SYN-RACE-BANK',
                bank_name='Synthetic race bank', fund=self.fund, period_start=date(2027, 1, 1),
                period_end=date(2027, 1, 31), received_on=date(2027, 2, 1), opening_balance=Decimal('0'),
                closing_balance=Decimal('100'), expected_row_count=1, expected_deposits=Decimal('100'),
                expected_withdrawals=Decimal('0'), created_by_id=self.preparer.pk, created_by_label=self.preparer.username,
            )
            batch = stage_bank_statement_csv(batch, self.preparer, SimpleUploadedFile(
                f'race-{index}.csv', b'transaction_date,bank_reference,description,withdrawal,deposit,running_balance\n2027-01-15,SYN-RACE-001,Synthetic deposit,,100.00,100.00\n',
                content_type='text/csv'))
            rows.append(batch.rows.get(source_version=batch.source_version).pk)
        return line, rows

    @skipUnless(connections["finance"].vendor == "mysql", "Native MySQL concurrency regression.")
    def test_two_statements_cannot_claim_the_same_posted_bank_line(self):
        line, rows = self._fixture()
        barrier = Barrier(2, timeout=15)
        original_create = QuerySet.create
        def synchronized_create(queryset, **kwargs):
            if queryset.model is BankStatementMatch:
                barrier.wait()
            return original_create(queryset, **kwargs)
        line_id = line.pk
        clients = {}
        for row_id in rows:
            client = Client(raise_request_exception=False)
            client.force_login(self.preparer)
            clients[row_id] = client
        def worker(row_id):
            connections.close_all()
            try:
                row = BankStatementRow.objects.select_related('batch').get(pk=row_id)
                response = clients[row_id].post(reverse('accounting:bank_reconciliation_match', kwargs={
                    'public_id': row.batch.public_id, 'row_id': row_id,
                }), {'journal_line_id': line_id, 'reason': 'Synthetic concurrent browser matching'})
                return {'status': response.status_code, 'messages': [str(item) for item in get_messages(response.wsgi_request)]}
            except Exception as exc:
                return {'error': type(exc).__name__, 'detail': str(exc)}
            finally:
                connections.close_all()
        with patch.object(QuerySet, 'create', synchronized_create), ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(worker, rows))
        count = BankStatementMatch.objects.filter(journal_line_id=line_id, status=BankStatementMatch.ACTIVE).count()
        self.assertEqual(BankStatementMatch.objects.count(), 1, outcomes)
        self.assertEqual(count, 1, outcomes)
        self.assertEqual([item.get('status') for item in outcomes], [302, 302], outcomes)
        self.assertEqual(sum('Reload the statement' in message for item in outcomes for message in item['messages']), 1)

    def test_automatic_match_conflict_rolls_back_the_complete_action_without_replay(self):
        _line, rows = self._fixture()
        batch = BankStatementRow.objects.get(pk=rows[0]).batch
        before_version = batch.state_version
        original_event = accounting_services._bank_event
        def fail_after_match_event(*args, **kwargs):
            original_event(*args, **kwargs)
            raise OperationalError(1213, 'Synthetic deadlock after match and event writes')
        with patch.object(accounting_services, '_bank_event', side_effect=fail_after_match_event) as event:
            with self.assertRaisesMessage(ValidationError, 'This request was rolled back'):
                auto_match_bank_statement(batch, self.preparer)
            self.assertEqual(event.call_count, 1, 'Never implicitly replay the failed financial action.')
        self.assertFalse(BankStatementMatch.objects.exists())
        self.assertFalse(BankReconciliationEvent.objects.filter(action='row_matched').exists())
        batch.refresh_from_db()
        self.assertEqual(batch.state_version, before_version)
        self.assertEqual(auto_match_bank_statement(batch, self.preparer), 1)
        self.assertEqual(BankStatementMatch.objects.count(), 1)
        self.assertEqual(BankReconciliationEvent.objects.filter(action='row_matched').count(), 1)

    def test_unrelated_database_failure_is_not_misreported_as_a_match_conflict(self):
        _line, rows = self._fixture()
        batch = BankStatementRow.objects.get(pk=rows[0]).batch
        with patch.object(accounting_services, '_bank_event', side_effect=OperationalError(2006, 'Synthetic connection failure')):
            with self.assertRaises(OperationalError):
                auto_match_bank_statement(batch, self.preparer)
        self.assertFalse(BankStatementMatch.objects.exists())
