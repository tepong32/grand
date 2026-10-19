from datetime import date
from decimal import Decimal
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase
from vouchers import test_deduction_correction_concurrency as concurrency
from . import test_quarterly as fixtures
from . import tests as budget_fixtures
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

    # Reuse the existing Budget-native fixture/class so all prior CI shard owners
    # stay stable. These writers share its same immutable appropriation line.
    make_allotment_order = budget_fixtures.AnnualBudgetPreparationTests.make_allotment_order
    add_allotment_line = budget_fixtures.AnnualBudgetPreparationTests.add_allotment_line
    make_obligation_request = budget_fixtures.AnnualBudgetPreparationTests.make_obligation_request
    add_obligation_line = budget_fixtures.AnnualBudgetPreparationTests.add_obligation_line
    dated_allotment = budget_fixtures.AnnualBudgetPreparationTests.dated_allotment
    dated_obligation = budget_fixtures.AnnualBudgetPreparationTests.dated_obligation

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

    def test_competing_backdated_releases_cannot_overrun_an_intermediate_balance(self):
        from .models import AllotmentOrderLine, AllotmentReleaseOrder
        from .services import allotment_line_balance, transition_allotment_order
        first = self.dated_allotment(self.authority, 'RACE-DATED-BASE', 5, '800')
        self.dated_allotment(self.authority, 'RACE-DATED-RETURN', 20, '800', AllotmentOrderLine.RETURN,
            AllotmentReleaseOrder.RETURN, corrects=first)
        orders = [self.dated_allotment(self.authority, 'RACE-DATED-' + str(i), 10, '200', post=False) for i in (1, 2)]
        for order in orders:
            transition_allotment_order(order, 'submit', self.preparer)
        def action(number):
            actor = get_user_model().objects.get(pk=self.authorizer.pk)
            transition_allotment_order(orders[number-1], 'post', actor, 'Independent concurrent dated release')
            return 'accepted'
        result = self.race(action)
        self.assertEqual(result.count('accepted'), 1, result)
        self.assertEqual(allotment_line_balance(self.authority.schedule_lines.get(), as_of=date(2027, 1, 10))['released'], Decimal('1000'))

    def test_backdated_hold_and_obligation_share_one_dated_capacity_lock(self):
        from .models import AllotmentOrderLine, AllotmentReleaseOrder
        from .services import obligation_line_balance, transition_allotment_order, transition_obligation_request
        self.dated_allotment(self.authority, 'RACE-DATED-EARLY', 5, '500')
        self.dated_allotment(self.authority, 'RACE-DATED-LATE', 25, '500')
        hold = self.dated_allotment(self.authority, 'RACE-DATED-HOLD', 10, '300', AllotmentOrderLine.RESERVE,
            AllotmentReleaseOrder.RESERVE, post=False)
        hold = transition_allotment_order(hold, 'submit', self.preparer)
        request = self.dated_obligation(self.authority, 'RACE-DATED-OBLIGATION', 15, '400', certify=False)
        request = transition_obligation_request(request, 'submit', self.requester)
        def action(number):
            if number == 1:
                transition_allotment_order(hold, 'post', get_user_model().objects.get(pk=self.authorizer.pk), 'Concurrent dated hold')
            else:
                transition_obligation_request(request, 'certify', get_user_model().objects.get(pk=self.certifier.pk),
                    'Concurrent dated certification', 'OBR-RACE-DATED')
            return 'accepted'
        result = self.race(action)
        self.assertEqual(result.count('accepted'), 1, result)
        balance = obligation_line_balance(self.authority.schedule_lines.get(), as_of=date(2027, 1, 15))
        self.assertGreaterEqual(balance['unobligated'], Decimal('0'))
