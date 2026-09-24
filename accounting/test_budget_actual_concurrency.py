from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase

from budget.planning_context import build_context
from . import budget_actuals as services
from . import test_budget_actuals as fixtures
from .models import BudgetActualScope, BudgetActualVersion


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class BudgetActualConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    employee = classmethod(fixtures.BudgetActualAdoptionTests.employee.__func__)
    make_call = fixtures.BudgetActualAdoptionTests.make_call
    make_version = fixtures.BudgetActualAdoptionTests.make_version
    add_line = fixtures.BudgetActualAdoptionTests.add_line
    add_ceiling = fixtures.BudgetActualAdoptionTests.add_ceiling
    grant = fixtures.BudgetActualAdoptionTests.grant
    document = fixtures.BudgetActualAdoptionTests.document
    arguments = fixtures.BudgetActualAdoptionTests.arguments

    def setUp(self):
        fixtures.BudgetActualAdoptionTests.setUpTestData.__func__(type(self))
        fixtures.BudgetActualAdoptionTests.setUp(self)

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

    def test_competing_submission_review_and_budget_capture(self):
        def propose(number):
            services.propose(**self.arguments(str(140 + number),
                actor=get_user_model().objects.get(pk=self.maker.pk)))
            return "accepted"
        results = self.race(propose)
        self.assertEqual(results.count("accepted"), 1, results)
        self.assertTrue(any("newer version" in result for result in results), results)
        self.assertEqual(BudgetActualScope.objects.count(), 1)
        first = BudgetActualVersion.objects.get()
        def decide(_):
            services.review(BudgetActualVersion.objects.get(pk=first.pk),
                get_user_model().objects.get(pk=self.checker.pk), approve=True,
                note="Independent concurrent review", authority="Reviewer")
            return "accepted"
        results = self.race(decide)
        self.assertEqual(results.count("accepted"), 1, results)
        self.assertEqual(BudgetActualScope.objects.get().current_version_id, first.pk)
        second = services.propose(**self.arguments("180", expected_latest=1))
        def capture_or_adopt(number):
            if number == 1:
                return build_context(self.version, get_user_model().objects.get(pk=self.preparer.pk))["rows"][0]["half_certified"]
            services.review(BudgetActualVersion.objects.get(pk=second.pk),
                get_user_model().objects.get(pk=self.checker.pk), approve=True,
                note="Adopt replacement during proposal capture", authority="Reviewer")
            return "accepted"
        results = self.race(capture_or_adopt)
        captured = results[0]
        self.assertIsInstance(captured, dict, results)
        selected = first if captured["certificate"] == str(first.public_id) else second
        self.assertEqual(captured["certificate"], str(selected.public_id))
        self.assertEqual(captured["amount"], selected.payload["rows"][0]["amount"])
        self.assertEqual(captured["source_checksum"], selected.payload_checksum)
        selected.refresh_from_db()
        self.assertEqual(captured["decision_checksum"], selected.decision_checksum)
        self.assertEqual(BudgetActualScope.objects.get().current_version_id, second.pk)
