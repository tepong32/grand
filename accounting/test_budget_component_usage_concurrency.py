from decimal import Decimal
from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase

from . import test_budget_component_usage as fixtures
from . import test_budget_attribution_concurrency as race_fixtures
from .budget_component_usage import component_usage
from .models import BudgetExpenditureAttributionHead


@skipUnless(connections["finance"].vendor == "mysql", "Requires native Fund row locks")
class ComponentUsageConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = fixtures.ComponentUsageTests.setUp
    entry = fixtures.ComponentUsageTests.entry
    post = fixtures.ComponentUsageTests.post
    rows = fixtures.ComponentUsageTests.rows
    approve = fixtures.ComponentUsageTests.approve
    reference = fixtures.ComponentUsageTests.reference
    payment_rows = fixtures.ComponentUsageTests.payment_rows
    capture = fixtures.ComponentUsageTests.capture
    propose = fixtures.ComponentUsageTests.propose
    principal_rows = fixtures.ComponentUsageTests.principal_rows
    race = race_fixtures.BudgetAttributionConcurrencyTests.race

    def test_competing_approvals_cannot_each_consume_the_same_remaining_component(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        entries = [self.post(self.entry(f"COMPETING-{number}", Decimal("200"), source=self.source, day=5))
                   for number in (1, 2)]
        candidates = [self.propose(self.principal_rows(entry, "200"), entry=entry) for entry in entries]
        results = self.race(lambda number: "approved" if self.approve(candidates[number - 1]) else "missing")
        self.assertEqual(results.count("approved"), 1, results)
        self.assertTrue(any("dated classification capacity" in result for result in results), results)
        self.assertEqual(BudgetExpenditureAttributionHead.objects.filter(entry__in=entries).count(), 1)
        statuses = []
        for records in candidates:
            records[0].refresh_from_db()
            statuses.append(records[0].status)
        self.assertCountEqual(statuses, ["approved", "submitted"])
        key = self.reference("loan_principal")["component_key"]
        self.assertEqual(component_usage(self.capture())["components"][key]["applied"], "400.00")
