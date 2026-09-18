from datetime import date
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase

from vouchers import test_deduction_correction_concurrency as concurrent
from . import test_planning_context as fixtures
from .models import BudgetVersion
from .planning_context import set_estimate
from .services import transition_version


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class PlanningContextConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    employee = classmethod(fixtures.PlanningContextTests.employee.__func__)
    make_call = fixtures.PlanningContextTests.make_call
    make_version = fixtures.PlanningContextTests.make_version
    add_line = fixtures.PlanningContextTests.add_line
    add_ceiling = fixtures.PlanningContextTests.add_ceiling
    race = concurrent.DeductionCorrectionConcurrencyTests.race

    def setUp(self):
        fixtures.PlanningContextTests.setUpTestData.__func__(type(self))
        fixtures.PlanningContextTests.setUp(self)

    def test_estimate_change_and_submission_share_the_version_lock(self):
        def action(number):
            actor = get_user_model().objects.get(pk=self.preparer.pk)
            if number == 1:
                set_estimate(version=self.version, line_id=self.line.pk, actor=actor, amount=Decimal("40"),
                    as_of=date(2026, 8, 1), basis="Concurrent forecast")
            else:
                transition_version(self.version, "submit", actor)
            return "accepted"
        results = self.race(action)
        self.assertIn("accepted", results)
        self.version.refresh_from_db()
        self.line.refresh_from_db()
        self.assertEqual(self.version.status, BudgetVersion.FOR_REVIEW)
        retained = self.version.planning_context_snapshot["rows"][0]["estimate"]
        expected = str(self.line.second_half_estimate) if self.line.second_half_estimate is not None else None
        self.assertEqual(retained, expected)
