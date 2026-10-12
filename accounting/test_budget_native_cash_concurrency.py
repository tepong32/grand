"""Actual two-store capture overlap; never infer a lock from a source checksum."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from threading import Event
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections, transaction
from django.test import TransactionTestCase

from . import budget_native_cash as service
from . import budget_native_sources
from .test_budget_native_cash import NativeCashTests
from .test_budget_opening_components import OpeningComponentTests
from .models import JournalEntry
from .services import submit_entry, post_entry
from reporting.models import FinanceStatementMapping, FinanceStatementLine
from reporting.statement_services import submit_statement_mapping, review_statement_mapping


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native committed/uncommitted capture visibility')
class NativeCashConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    entry = OpeningComponentTests.entry
    post = OpeningComponentTests.post
    cash_capture = NativeCashTests.cash_capture
    configure_cash = NativeCashTests.configure_cash

    def setUp(self):
        OpeningComponentTests.setUp(self)
        self.configure_cash()

    def workers(self, first, second):
        def run(action):
            close_old_connections()
            try:
                return action()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, action) for action in (first, second)]
            return [future.result(timeout=45) for future in futures]

    def wait_for(self, signal):
        self.assertTrue(signal.wait(30), 'Native overlap did not reach its required source boundary')

    def payment(self):
        entry = self.entry('CONCURRENT-CASH-PAYMENT', Decimal('400'), source=self.source, day=4)
        return submit_entry(entry, self.maker)

    def assert_old_capture(self, artifact, expected_count):
        self.assertEqual(service.verify(artifact)['gross'], '1000.00')
        self.assertEqual(len(artifact['payload']['selected_journal_ids']), 1)
        frozen = deepcopy(artifact)
        self.assertFalse(service.is_current(artifact, self.maker))
        self.assertEqual(self.cash_capture()['payload']['gross'], '600.00')
        self.assertEqual(artifact, frozen)
        self.assertEqual(JournalEntry.objects.count(), expected_count)

    def test_uncommitted_payment_cannot_leak_into_capture(self):
        payment = self.payment()
        posted, captured = Event(), Event()
        def writer():
            try:
                with transaction.atomic(using='finance'):
                    post_entry(payment, self.poster)
                    posted.set()
                    self.wait_for(captured)
                return 'committed'
            finally:
                posted.set()
        def reader():
            try:
                self.wait_for(posted)
                return self.cash_capture()
            finally:
                captured.set()
        status, artifact = self.workers(writer, reader)
        self.assertEqual(status, 'committed')
        payment.refresh_from_db()
        self.assertEqual(payment.status, JournalEntry.POSTED)
        self.assert_old_capture(artifact, 2)

    def test_payment_committed_after_ledger_read_makes_capture_stale(self):
        payment = self.payment()
        read, committed = Event(), Event()
        original = budget_native_sources._capture
        def retained_read(*args, **kwargs):
            result = original(*args, **kwargs)
            read.set()
            self.wait_for(committed)
            return result
        def writer():
            try:
                self.wait_for(read)
                post_entry(payment, self.poster)
                return 'committed'
            finally:
                committed.set()
        with patch.object(budget_native_sources, '_capture', side_effect=retained_read):
            artifact, status = self.workers(lambda: self.cash_capture(), writer)
        self.assertEqual(status, 'committed')
        self.assert_old_capture(artifact, 2)

    def test_mapping_activation_during_capture_rejects_mixed_source_decisions(self):
        retained = self.cash_capture()
        frozen = deepcopy(retained)
        successor = FinanceStatementMapping.objects.create(department=self.department,
            statement_type=FinanceStatementMapping.CASH_FLOW, version=2,
            title='Synthetic successor cash inventory', authority_reference='Synthetic revised authority',
            local_acceptance_note='Synthetic explicit inventory review', created_by=self.maker)
        FinanceStatementLine.objects.create(mapping=successor, position=1, section_code='cash',
            section_title='Cash', line_code='cash', line_title='Cash inventory',
            selector_type=FinanceStatementLine.ACCOUNT_CODES, account_codes=['cash', 'BANK'])
        submit_statement_mapping(successor, self.maker)
        read, committed = Event(), Event()
        original = budget_native_sources._capture
        def retained_read(*args, **kwargs):
            result = original(*args, **kwargs)
            read.set()
            self.wait_for(committed)
            return result
        def reader():
            try:
                self.cash_capture()
            except ValidationError as error:
                self.assertIn('changed during capture', ' '.join(error.messages))
                return 'rejected'
            self.fail('A mapping changed between retained source reads was accepted')
        def writer():
            try:
                self.wait_for(read)
                review_statement_mapping(successor, self.poster, approve=True,
                    note='Independent synthetic successor activation')
                return 'activated'
            finally:
                committed.set()
        with patch.object(budget_native_sources, '_capture', side_effect=retained_read):
            self.assertEqual(self.workers(reader, writer), ['rejected', 'activated'])
        self.assertEqual(service.verify(retained)['gross'], '1000.00')
        self.assertFalse(service.is_current(retained, self.maker))
        self.assertEqual(retained, frozen)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(FinanceStatementMapping.objects.filter(status=FinanceStatementMapping.ACTIVE).count(), 1)
