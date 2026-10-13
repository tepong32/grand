from datetime import date
from decimal import Decimal
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase
from vouchers import test_deduction_correction_concurrency as concurrency
from . import test_quarterly as fixtures
from .models import QuarterlyFinancialPlan
from .quarterly import edit_line, transition_plan


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class QuarterlyPlanningConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    employee = classmethod(fixtures.QuarterlyPlanningTests.employee.__func__)
    make_call = fixtures.QuarterlyPlanningTests.make_call
    add_ceiling = fixtures.QuarterlyPlanningTests.add_ceiling
    add_line = fixtures.QuarterlyPlanningTests.add_line
    make_authorized_appropriation = fixtures.QuarterlyPlanningTests.make_authorized_appropriation
    plan = fixtures.QuarterlyPlanningTests.plan
    fill = fixtures.QuarterlyPlanningTests.fill
    race = concurrency.DeductionCorrectionConcurrencyTests.race

    def setUp(self):
        fixtures.QuarterlyPlanningTests.setUpTestData.__func__(type(self))
        fixtures.QuarterlyPlanningTests.setUp(self)

    def test_competing_approvals_share_the_authority_parent(self):
        plans = [self.plan("FIRST"), self.plan("SECOND")]
        for plan in plans:
            self.fill(plan)
            transition_plan(plan=plan, action="submit", actor=self.preparer)
        def action(number):
            actor = get_user_model().objects.get(pk=self.authorizer.pk)
            transition_plan(plan=plans[number-1], action="approve", actor=actor, reason="Concurrent independent review")
            return "accepted"
        results = self.race(action)
        self.assertEqual(results.count("accepted"), 1, results)
        self.authority.refresh_from_db()
        self.assertEqual(QuarterlyFinancialPlan.objects.filter(status="approved").count(), 1)
        self.assertEqual(self.authority.current_quarterly_plan.status, "approved")

    def test_edit_and_submit_retain_exactly_one_allocation_state(self):
        plan = self.plan(); line = self.fill(plan)
        def action(number):
            actor = get_user_model().objects.get(pk=self.preparer.pk)
            if number == 1:
                edit_line(plan=plan, line_id=line.pk, actor=actor, values={"q1": Decimal("400")})
            else:
                transition_plan(plan=plan, action="submit", actor=actor)
            return "accepted"
        results = self.race(action)
        self.assertIn("accepted", results)
        plan.refresh_from_db(); line.refresh_from_db()
        self.assertEqual(plan.status, plan.FOR_REVIEW)
        self.assertEqual(plan.submitted_snapshot["rows"][0]["quarters"][0], str(line.q1))
