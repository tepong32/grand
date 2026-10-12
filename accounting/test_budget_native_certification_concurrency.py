from copy import deepcopy
from datetime import date
from threading import Event
from unittest import skipUnless
from unittest.mock import patch

from django.db import connections
from django.test import TransactionTestCase

from . import test_budget_native_certifications as fixtures
from .test_budget_attribution_concurrency import BudgetAttributionConcurrencyTests
from . import test_budget_native_cash_concurrency as capture_races
from . import budget_native_certifications as service
from . import budget_native_sources as sources
from .models import NativeBudgetStatement as Statement, JournalEntry, JournalLine
from .services import submit_entry, post_entry


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native Fund row locks')
class NativeCertificationConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    employee = classmethod(fixtures.NativeCertificationTests.employee.__func__)
    make_call = fixtures.NativeCertificationTests.make_call
    make_version = fixtures.NativeCertificationTests.make_version
    add_line = fixtures.NativeCertificationTests.add_line
    add_ceiling = fixtures.NativeCertificationTests.add_ceiling
    grant = fixtures.NativeCertificationTests.grant
    attribute_grant = fixtures.NativeCertificationTests.attribute_grant
    journal = fixtures.NativeCertificationTests.journal
    capture = fixtures.NativeCertificationTests.capture
    rows = fixtures.NativeCertificationTests.rows
    propose = fixtures.NativeCertificationTests.propose
    review = fixtures.NativeCertificationTests.review
    native_grant = fixtures.NativeCertificationTests.native_grant
    native_propose = fixtures.NativeCertificationTests.native_propose
    decide = fixtures.NativeCertificationTests.decide
    race = BudgetAttributionConcurrencyTests.race
    workers = capture_races.NativeCashConcurrencyTests.workers
    wait_for = capture_races.NativeCashConcurrencyTests.wait_for

    def setUp(self):
        fixtures.NativeCertificationTests.setUpTestData.__func__(type(self))
        fixtures.NativeCertificationTests.setUp(self)

    def test_competing_preparations_and_decisions_keep_one_version_and_decision(self):
        result = self.race(lambda _: 'prepared' if self.native_propose() else 'missing')
        self.assertEqual(result.count('prepared'), 1, result)
        self.assertEqual(Statement.objects.count(), 1)
        record = Statement.objects.get()
        result = self.race(lambda _: 'certified' if self.decide(record) else 'missing')
        self.assertEqual(result.count('certified'), 1, result)
        record.refresh_from_db()
        self.assertEqual(record.status, Statement.CERTIFIED)

    def test_post_after_freshness_read_preserves_fixed_certificate_but_blocks_current_use(self):
        record = self.native_propose()
        frozen = deepcopy(record.payload)
        entry = JournalEntry.objects.create(
            department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name,
            period=self.entry.period, fund=self.fund, reference='CERTIFICATION-OVERLAP',
            entry_date=date(2026, 6, 30), description='Synthetic ordinary source posted during certification',
            created_by_id=self.maker.pk, created_by_label=self.maker.username)
        JournalLine.objects.create(entry=entry, sequence=1, account=self.account,
            responsibility_center=self.center, debit=5)
        JournalLine.objects.create(entry=entry, sequence=2, account=self.offset, credit=5)
        submit_entry(entry, self.maker)
        read, committed = Event(), Event()
        original = sources.is_current

        def retained_read(*args, **kwargs):
            current = original(*args, **kwargs)
            self.assertTrue(current)
            read.set()
            self.wait_for(committed)
            return current

        def writer():
            try:
                self.wait_for(read)
                post_entry(entry, self.checker)
                return 'posted'
            finally:
                committed.set()

        with patch.object(sources, 'is_current', side_effect=retained_read):
            decided, status = self.workers(lambda: self.decide(record), writer)
        self.assertEqual(status, 'posted')
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.POSTED)
        decided.refresh_from_db()
        self.assertEqual(decided.status, Statement.CERTIFIED)
        self.assertEqual(service.verify(decided), frozen)
        self.assertFalse(service.is_current(decided, self.checker))
        self.assertEqual(JournalEntry.objects.count(), 2)
        self.assertEqual(Statement.objects.count(), 1)
