from unittest import skipUnless
from django.db import connections
from django.test import TransactionTestCase

from .test_summary_actuals import SummaryActualTests
from .test_budget_cash import BudgetCashTests
from .test_budget_attribution_concurrency import BudgetAttributionConcurrencyTests
from . import budget_cash as service
from .models import BudgetCashEvidence as Record, AccountingAuditEvent, JournalEntry


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native cash Fund/record locks')
class BudgetCashConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = SummaryActualTests.__dict__['employee']
    make_call = SummaryActualTests.make_call
    make_version = SummaryActualTests.make_version
    add_line = SummaryActualTests.add_line
    add_ceiling = SummaryActualTests.add_ceiling
    grant = SummaryActualTests.grant
    grant_summary = SummaryActualTests.grant_summary
    arguments = SummaryActualTests.arguments
    document = SummaryActualTests.document
    cash_args = BudgetCashTests.cash_args
    race = BudgetAttributionConcurrencyTests.race

    def setUp(self):
        SummaryActualTests.setUpTestData.__func__(type(self))
        SummaryActualTests.setUp(self)
        self.journal_count = JournalEntry.objects.count()

    def decide(self, record, adopt=True):
        return service.review(record, self.checker, adopt=adopt,
            note='Synthetic independent original-source review', authority='Synthetic designation', verified_documents=True)

    def assert_retained(self, record, payload_checksum, certificate, reconciliation):
        record.refresh_from_db()
        self.assertEqual(record.payload_checksum, payload_checksum)
        self.assertEqual(bytes(record.certificate), certificate)
        self.assertEqual(bytes(record.reconciliation), reconciliation)
        self.assertEqual(service.verify(record)['net'], '75.00')
        self.assertEqual(JournalEntry.objects.count(), self.journal_count)

    def test_competing_initial_creation_and_adoption(self):
        # Prepare distinct uploads/permissions before racing; financial locks alone
        # are under test, rather than incidental default-store permission writes.
        arguments = [self.cash_args(), self.cash_args()]
        results = self.race(lambda n: 'created' if service.propose(**arguments[n-1]) else 'missing')
        self.assertEqual(results.count('created'), 1, results)
        self.assertEqual(Record.objects.count(), 1)
        record = Record.objects.get()
        retained = (record.payload_checksum, bytes(record.certificate), bytes(record.reconciliation))
        results = self.race(lambda _: 'adopted' if self.decide(record) else 'missing')
        self.assertEqual(results.count('adopted'), 1, results)
        self.assert_retained(record, *retained)
        self.assertEqual(record.status, 'adopted')
        self.assertEqual(AccountingAuditEvent.objects.filter(action='budget_cash_submitted').count(), 1)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='budget_cash_adopted').count(), 1)

    def test_successor_racing_adoption_preserves_both_versions(self):
        first = service.propose(**self.cash_args())
        retained = (first.payload_checksum, bytes(first.certificate), bytes(first.reconciliation))
        arguments = self.cash_args(expected_latest=1)
        def action(number):
            if number == 1:
                service.propose(**arguments)
                return 'successor'
            self.decide(first)
            return 'adopted'
        results = self.race(action)
        self.assertIn('successor', results)
        self.assertEqual(Record.objects.count(), 2)
        self.assert_retained(first, *retained)
        # Either adoption committed before successor creation, or a now-stale
        # adoption was rejected. Both retain the original evidence unchanged.
        self.assertEqual(first.status, 'adopted' if 'adopted' in results else 'submitted')
        latest = Record.objects.get(version=2)
        self.decide(latest)
        latest.refresh_from_db(); self.assertEqual(latest.status, 'adopted')
        self.assertEqual(service.verify(latest)['version'], 2)

    def test_conflicting_adopt_and_return_record_one_independent_decision(self):
        record = service.propose(**self.cash_args())
        retained = (record.payload_checksum, bytes(record.certificate), bytes(record.reconciliation))
        results = self.race(lambda n: self.decide(record, adopt=n == 1).status)
        winners = [result for result in results if result in ('adopted', 'returned')]
        self.assertEqual(len(winners), 1, results)
        self.assert_retained(record, *retained)
        self.assertEqual(record.status, winners[0])
        self.assertEqual(AccountingAuditEvent.objects.filter(action__in=('budget_cash_adopted', 'budget_cash_returned')).count(), 1)
