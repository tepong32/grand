from copy import deepcopy
from threading import Event
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase

from . import budget_cash_certifications as service, budget_cash_preparations as preparations
from . import test_budget_cash_certifications as fixtures
from . import test_budget_native_cash_concurrency as capture_races
from . import test_budget_attribution_concurrency as attribution_races
from .models import NativeBudgetCashDecision as Decision, JournalEntry, AccountingAuditEvent
from .services import post_entry


@skipUnless(connections['finance'].vendor == 'mysql', 'Requires native joint cash row locks and source overlap')
class NativeCashCertificationConcurrencyTests(TransactionTestCase):
    databases = {'default', 'finance'}
    entry = capture_races.NativeCashConcurrencyTests.entry
    post = capture_races.NativeCashConcurrencyTests.post
    configure_cash = capture_races.NativeCashConcurrencyTests.configure_cash
    configure_native = fixtures.NativeCashCertificationTests.configure_native
    preparation_args = fixtures.NativeCashCertificationTests.preparation_args
    historical = fixtures.NativeCashCertificationTests.historical
    configure_certifiers = fixtures.NativeCashCertificationTests.configure_certifiers
    grant_certifier = fixtures.NativeCashCertificationTests.grant_certifier
    cash_preparation = fixtures.NativeCashCertificationTests.cash_preparation
    decision = fixtures.NativeCashCertificationTests.decision
    workers = capture_races.NativeCashConcurrencyTests.workers
    wait_for = capture_races.NativeCashConcurrencyTests.wait_for
    payment = capture_races.NativeCashConcurrencyTests.payment
    race = attribution_races.BudgetAttributionConcurrencyTests.race

    def setUp(self):
        capture_races.NativeCashConcurrencyTests.setUp(self)
        self.configure_native()
        self.configure_certifiers()
        self.record = self.cash_preparation()

    def test_competing_same_role_decisions_keep_one_authority_and_audit(self):
        results = self.race(lambda _: 'certified' if self.decision(self.record) else 'missing')
        self.assertEqual(results.count('certified'), 1, results)
        self.assertEqual(Decision.objects.count(), 1)
        self.assertEqual(AccountingAuditEvent.objects.filter(action='native_budget_cash_decided').count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_return_and_other_role_approval_cannot_create_joint_certification(self):
        def action(number):
            self.decision(self.record, 'treasurer' if number == 1 else 'accountant', certify=number == 2)
            return 'returned' if number == 1 else 'certified'
        results = self.race(action)
        self.assertEqual(results.count('returned'), 1, results)
        self.assertEqual(service.snapshot(self.record, self.poster)['payload']['status'], 'returned')
        self.assertFalse(service.is_current(self.record, self.poster))
        self.assertEqual(Decision.objects.filter(outcome='returned').count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_successor_and_approval_serialize_and_old_version_cannot_be_current(self):
        def action(number):
            if number == 1:
                preparations.prepare(**self.preparation_args(expected_latest=1,
                    restriction_source_id=self.record.restriction_source_id))
                return 'successor'
            self.decision(self.record)
            return 'certified'
        results = self.race(action)
        self.assertEqual(results.count('successor'), 1, results)
        self.assertFalse(service.is_current(self.record, self.poster))
        with self.assertRaises(ValidationError):
            self.decision(self.record, 'treasurer')
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_post_before_second_role_read_rejects_it_preserves_first(self):
        first = self.decision(self.record)
        frozen = deepcopy(first.payload)
        payment, committed = self.payment(), Event()
        def writer():
            try:
                post_entry(payment, self.poster)
                return 'posted'
            finally:
                committed.set()
        def reader():
            self.wait_for(committed)
            with self.assertRaisesMessage(ValidationError, 'sources changed'):
                self.decision(self.record, 'treasurer')
            return 'rejected'
        self.assertEqual(self.workers(writer, reader), ['posted', 'rejected'])
        self.assertEqual(Decision.objects.count(), 1)
        self.assertEqual(service.verify_decision(self.record, first), frozen)
        payment.refresh_from_db()
        self.assertEqual(payment.status, JournalEntry.POSTED)

    def test_post_after_second_role_read_keeps_fixed_joint_snapshot_but_is_stale(self):
        first = self.decision(self.record)
        original_preparation = deepcopy(self.record.payload)
        first_payload = deepcopy(first.payload)
        payment, read, committed = self.payment(), Event(), Event()
        original = service._observe
        def observed(*args, **kwargs):
            result = original(*args, **kwargs)
            read.set()
            self.wait_for(committed)
            return result
        def writer():
            try:
                self.wait_for(read)
                post_entry(payment, self.poster)
                return 'posted'
            finally:
                committed.set()
        with patch.object(service, '_observe', side_effect=observed):
            second, status = self.workers(lambda: self.decision(self.record, 'treasurer'), writer)
        self.assertEqual(status, 'posted')
        self.assertEqual(service.snapshot(self.record, self.treasurer)['payload']['status'], 'jointly_certified')
        self.assertFalse(service.is_current(self.record, self.treasurer))
        self.assertEqual(service.verify_decision(self.record, first), first_payload)
        service.verify_decision(self.record, second)
        self.record.refresh_from_db()
        self.assertEqual(self.record.payload, original_preparation)
        self.assertEqual(Decision.objects.count(), 2)
        payment.refresh_from_db()
        self.assertEqual(payment.status, JournalEntry.POSTED)
