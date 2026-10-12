from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from vouchers.roles import FINANCE_UAT_VIEWER_GROUP
from . import budget_native_certifications as service
from . import test_budget_attributions as fixtures
from .models import NativeBudgetStatement as Statement


class NativeCertificationTests(TestCase):
    databases = {'default', 'finance'}
    setUpTestData = classmethod(fixtures.BudgetAttributionTests.setUpTestData.__func__)
    employee = classmethod(fixtures.BudgetAttributionTests.employee.__func__)
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

    def native_grant(self, actor, *actions):
        actor.user_permissions.add(*Permission.objects.filter(content_type__app_label='accounting',
            codename__in=[f'{action}_native_budget_statements' for action in actions]))

    def setUp(self):
        fixtures.BudgetAttributionTests.setUp(self)
        self.review(self.propose())
        self.native_grant(self.maker, 'prepare', 'view')
        self.native_grant(self.checker, 'certify', 'view')

    def native_propose(self, **changes):
        args = dict(actor=self.maker, fund_id=self.fund.pk, period_start=date(2026, 1, 1),
            period_end=date(2026, 6, 30), expected_latest=0,
            expected_source_checksum=self.capture()['checksum'], reason='Prepare actual office expenditure',
            coverage='Synthetic complete fund ledger and independently reconciled office classification',
            evidence_reference='SYN-NATIVE-STATEMENT')
        args.update(changes)
        return service.propose(**args)

    def decide(self, record, **changes):
        args = dict(statement_id=record.pk, actor=self.checker, certify=True,
            authority='Synthetic Local Accountant designation', note='Independently verified complete sources and allocation')
        args.update(changes)
        return service.decide(**args)

    def test_retained_native_decision_and_successor_never_rewrite_evidence(self):
        first = self.native_propose()
        frozen = deepcopy(first.payload)
        first = self.decide(first)
        self.assertTrue(service.is_current(first, self.checker))
        self.assertFalse(first.payload['statement']['payload']['certificate'])
        self.assertEqual(first.status, Statement.CERTIFIED)
        successor = self.decide(self.native_propose(expected_latest=1))
        self.assertFalse(service.is_current(first, self.checker))
        self.assertTrue(service.is_current(successor, self.checker))
        first.refresh_from_db()
        self.assertEqual(first.payload, frozen)
        service.verify(first)
        first.payload = {}
        with self.assertRaises(ValidationError):
            first.save()
        with self.assertRaises(ValidationError):
            successor.delete()

    def test_backdated_source_blocks_certification_but_allows_return(self):
        record = self.native_propose()
        self.journal('NATIVE-BACKDATE', date(2026, 6, 30), Decimal('5'))
        with self.assertRaises(ValidationError):
            self.decide(record)
        self.assertEqual(self.decide(record, certify=False).status, Statement.RETURNED)
        with self.assertRaises(ValidationError):
            self.native_propose(expected_latest=1)  # New source is unclassified.

    def test_newer_pending_preparation_blocks_older_decision(self):
        first = self.native_propose()
        second = self.native_propose(expected_latest=1)
        with self.assertRaises(ValidationError):
            self.decide(first)
        self.decide(first, certify=False)
        self.assertEqual(self.decide(second).status, Statement.CERTIFIED)
        with self.assertRaises(ValidationError):
            self.decide(second)

    def test_distinct_authority_self_decision_uat_and_foreign_scope(self):
        record = self.native_propose()
        self.checker.user_permissions.remove(*Permission.objects.filter(codename='certify_native_budget_statements'))
        with self.assertRaises(PermissionDenied):
            self.decide(record)
        self.native_grant(self.maker, 'certify')
        with self.assertRaises(ValidationError):
            self.decide(record, actor=self.maker)
        self.native_grant(self.checker, 'certify')
        self.checker.groups.add(Group.objects.get_or_create(name=FINANCE_UAT_VIEWER_GROUP)[0])
        with self.assertRaises(PermissionDenied):
            self.decide(record)
        self.assertFalse(service.is_current(record, self.checker))
        self.native_grant(self.preparer, 'view', 'certify')
        with self.assertRaises(PermissionDenied):
            service.is_current(record, self.preparer)
        with self.assertRaises(PermissionDenied):
            self.decide(record, actor=self.preparer)

    def test_stale_preview_replay_bad_period_and_tampering_fail(self):
        with self.assertRaises(ValidationError):
            self.native_propose(expected_source_checksum='not-current')
        with self.assertRaises(ValidationError):
            self.native_propose(period_start=date(2026, 2, 1))
        record = self.native_propose()
        with self.assertRaises(ValidationError):
            self.native_propose()
        Statement.objects.filter(pk=record.pk).update(payload_checksum='tampered')
        with self.assertRaises(ValidationError):
            self.decide(record)

    def test_later_post_preserves_certified_snapshot_but_invalidates_new_use(self):
        record = self.decide(self.native_propose())
        frozen = deepcopy(record.payload)
        self.journal('LATER-POST', date(2026, 6, 30), Decimal('8'))
        self.assertFalse(service.is_current(record, self.checker))
        record.refresh_from_db()
        self.assertEqual(record.payload, frozen)
        self.assertEqual(record.status, Statement.CERTIFIED)
        service.verify(record)
