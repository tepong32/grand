from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from . import budget_attributions as service
from . import test_budget_attributions as fixtures
from .models import BudgetExpenditureAttribution as Attribution, BudgetExpenditureAttributionHead as Head
from .services import create_reversal, submit_entry, post_entry


@skipUnless(connections["finance"].vendor == "mysql", "Requires native Fund row locks and consistent reads")
class BudgetAttributionConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
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

    def setUp(self):
        fixtures.BudgetAttributionTests.setUpTestData.__func__(type(self))
        fixtures.BudgetAttributionTests.setUp(self)

    def race(self, action):
        barrier = Barrier(2, timeout=30)
        def run(number):
            close_old_connections()
            try:
                barrier.wait()
                return action(number)
            except ValidationError as exc:
                return "; ".join(exc.messages)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, (1, 2)))

    def test_competing_submissions_reviews_and_coherent_multi_journal_capture(self):
        results = self.race(lambda _: "created" if self.propose() else "missing")
        self.assertEqual(results.count("created"), 1, results)
        self.assertEqual(Attribution.objects.count(), 1)
        first = list(Attribution.objects.all())
        results = self.race(lambda _: "approved" if self.review(first) else "missing")
        self.assertEqual(results.count("approved"), 1, results)
        self.assertEqual(Head.objects.count(), 1)

        second = self.journal("BATCH-SECOND", date(2026, 6, 30), Decimal("100"))
        third = self.journal("BATCH-THIRD", date(2026, 6, 30), Decimal("100"))
        batch = self.propose(proposals=[dict(entry_id=entry.pk, expected_latest=0, allocations=self.rows(entry))
                                      for entry in (second, third)])
        def action(number):
            if number == 1:
                self.review(batch)
                return "approved"
            captured = self.capture()
            result = service.reviewed_allocations(captured)
            pair = [item["status"] for item in result if item["entry_id"] in (second.pk, third.pk)]
            self.assertIn(pair, [["unreviewed", "unreviewed"], ["reviewed", "reviewed"]])
            return "coherent"
        self.assertCountEqual(self.race(action), ["approved", "coherent"])
        self.assertEqual(Head.objects.count(), 3)

        reversal = create_reversal(self.entry, self.maker, reference="CONCURRENT-REVERSAL",
            period=self.entry.period, entry_date=date(2026, 6, 30), reason="Synthetic reviewed correction")
        submit_entry(reversal, self.maker)
        post_entry(reversal, self.checker)
        inherited = service.reversal_allocations(self.capture(), reversal.pk)
        child = self.propose(proposals=[dict(entry_id=reversal.pk, expected_latest=0, allocations=inherited)])
        revised = self.rows()
        revised[0]["basis"] = "Revised independent attribution evidence"
        parent = self.propose(proposals=[dict(entry_id=self.entry.pk, expected_latest=1, allocations=revised)])
        results = self.race(lambda number: (self.review(parent if number == 1 else child),
                                            "parent" if number == 1 else "child")[1])
        self.assertIn("parent", results)
        if Head.objects.filter(entry=reversal).exists():
            with self.assertRaises(ValidationError):
                service.reviewed_allocations(self.capture())
        else:
            result = service.reviewed_allocations(self.capture())
            self.assertEqual(next(row["status"] for row in result if row["entry_id"] == reversal.pk), "unreviewed")
