from datetime import date
from decimal import Decimal
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from . import tests as fixtures
from .models import AllotmentMovement, ObligationMovement, QuarterlyFinancialPlan, QuarterlyPlanLine, BudgetAuditEvent
from .quarterly import create_plan, edit_header, edit_line, plan_context, transition_plan
from .services import transition_allotment_order


class QuarterlyPlanningTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.AnnualBudgetPreparationTests.setUpTestData.__func__)
    employee = classmethod(fixtures.AnnualBudgetPreparationTests.employee.__func__)
    make_call = fixtures.AnnualBudgetPreparationTests.make_call
    add_ceiling = fixtures.AnnualBudgetPreparationTests.add_ceiling
    add_line = fixtures.AnnualBudgetPreparationTests.add_line
    make_authorized_appropriation = fixtures.AnnualBudgetPreparationTests.make_authorized_appropriation
    make_allotment_order = fixtures.AnnualBudgetPreparationTests.make_allotment_order
    add_allotment_line = fixtures.AnnualBudgetPreparationTests.add_allotment_line

    def setUp(self):
        self.clock = patch("django.utils.timezone.localdate", return_value=date(2027, 1, 10))
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.authority = self.make_authorized_appropriation("1000")

    def plan(self, reference="PLAN-2027"):
        return create_plan(authorization=self.authority, actor=self.preparer, reference=reference,
            prepared_on=date(2027, 1, 2), evidence_reference="Synthetic department plan and approval route",
            change_basis="Synthetic service delivery timing")

    def fill(self, plan, q1="200"):
        return edit_line(plan=plan, line_id=plan.lines.get().pk, actor=self.preparer,
            values={"q1": Decimal(q1), "q2": Decimal("100"), "q3": Decimal("100"), "q4": Decimal("0"),
                "basis": "Synthetic quarterly procurement timing", "indicator": "Service cycles", "target_unit": "cycles",
                "target_q1": "2", "target_q2": "1", "target_q3": "1", "target_q4": "0"})

    def approve(self, plan):
        plan = transition_plan(plan=plan, action="submit", actor=self.preparer)
        return transition_plan(plan=plan, action="approve", actor=self.authorizer, reason="Independent synthetic planning review")

    def order(self, number="ARO-Q1", amount="200"):
        order = self.make_allotment_order(self.authority, number=number, total=amount)
        self.add_allotment_line(order, amount)
        return order

    def test_budget_proposal_and_quarterly_history_reach_all_retained_events(self):
        plan = self.plan()
        for target, route in ((self.authority.version, "budget:version_detail"), (plan, "budget:quarterly_detail")):
            with self.subTest(route=route):
                self.client.force_login(self.reviewer if route == "budget:version_detail" else self.preparer)
                for index in range(45):
                    BudgetAuditEvent.objects.create(
                        department_id=target.department_id, department_label=target.department_label,
                        target_type=target._meta.model_name, target_id=str(target.public_id),
                        action="synthetic_history", actor_id=self.preparer.pk, actor_label="Synthetic preparer",
                        reason=f"Retained decision {index:03}",
                    )
                expected = set(BudgetAuditEvent.objects.filter(target_id=str(target.public_id)).values_list("pk", flat=True))
                event_count = BudgetAuditEvent.objects.count()
                first = self.client.get(reverse(route, args=(target.public_id,)))
                self.assertContains(first, "Retained decision 044")
                self.assertFalse(first.context["event_page"].expanded)
                seen = set()
                for number in range(1, first.context["event_page"].paginator.num_pages + 1):
                    response = self.client.get(reverse(route, args=(target.public_id,)), {"events_page": number})
                    self.assertContains(response, '<details id="budget-history" class="card" open>')
                    ids = {event.pk for event in response.context["events"]}
                    self.assertFalse(seen & ids)
                    seen |= ids
                self.assertEqual(seen, expected)
                self.assertContains(response, "events_page=1#budget-history")
                self.assertEqual(BudgetAuditEvent.objects.count(), event_count)
                self.client.force_login(self.outsider)
                self.assertEqual(self.client.get(reverse(route, args=(target.public_id,)), {"events_page": 2}).status_code, 404)
        self.client.force_login(self.preparer)
        hidden = self.client.get(reverse("budget:version_detail", args=(self.authority.version.public_id,)), {"events_page": 2})
        self.assertEqual(list(hidden.context["events"]), [])
        self.assertNotContains(hidden, "Retained decision")

    def test_complete_explicit_allocations_and_approval_do_not_move_money(self):
        plan = self.plan()
        self.assertFalse(plan_context(plan)["rows"][0]["complete"])
        with self.assertRaisesMessage(ValidationError, "four explicit"):
            transition_plan(plan=plan, action="submit", actor=self.preparer)
        for amount in ("-1", "1001"):
            with self.assertRaises(ValidationError): self.fill(plan, amount)
        self.fill(plan)
        plan = self.approve(plan)
        self.assertEqual(plan.submitted_snapshot["rows"][0]["unplanned"], "600.00")
        self.assertEqual(plan.submitted_snapshot["rows"][0]["quarters"][3], "0.00")
        self.assertFalse(AllotmentMovement.objects.exists())
        self.assertFalse(ObligationMovement.objects.exists())
        self.authority.refresh_from_db()
        self.assertEqual(self.authority.current_quarterly_plan_id, plan.pk)
        with self.assertRaises(ValidationError): self.fill(plan)
        with self.assertRaises(ValidationError): plan.save()

    def test_independent_scope_uat_and_physical_target_validation(self):
        plan = self.plan(); self.fill(plan)
        self.preparer.user_permissions.add(Permission.objects.get(content_type__app_label="budget", codename="approve_allotment_releases"))
        plan = transition_plan(plan=plan, action="submit", actor=self.preparer)
        with self.assertRaisesMessage(ValidationError, "preparer"):
            transition_plan(plan=plan, action="approve", actor=self.preparer, reason="Self review")
        with self.assertRaises(PermissionDenied):
            create_plan(authorization=self.authority, actor=self.outsider, reference="Wrong office", prepared_on=date(2027,1,2), evidence_reference="x", change_basis="x")
        plan = transition_plan(plan=plan, action="return", actor=self.authorizer, reason="Correct targets")
        with self.assertRaises(ValidationError):
            edit_line(plan=plan, line_id=plan.lines.get().pk, actor=self.preparer, values={"indicator": ""})
        self.preparer.groups.add(Group.objects.get_or_create(name="Finance UAT Viewer")[0])
        with self.assertRaises(PermissionDenied): self.fill(plan)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("budget:quarterly_detail", args=[plan.public_id])).status_code, 404)

    def test_stale_review_and_tampering_cannot_replace_current_plan(self):
        first, stale = self.plan("FIRST"), self.plan("STALE")
        self.fill(first); self.fill(stale)
        stale = transition_plan(plan=stale, action="submit", actor=self.preparer)
        first = self.approve(first)
        with self.assertRaisesMessage(ValidationError, "stale"):
            transition_plan(plan=stale, action="approve", actor=self.authorizer, reason="Old basis")
        successor = self.plan("SUCCESSOR")
        self.assertEqual(successor.supersedes_id, first.pk)
        successor = transition_plan(plan=successor, action="submit", actor=self.preparer)
        QuarterlyPlanLine.objects.filter(plan=successor).update(q1=Decimal("201"))
        with self.assertRaisesMessage(ValidationError, "rows changed"):
            transition_plan(plan=successor, action="approve", actor=self.authorizer, reason="Tampered")
        self.authority.refresh_from_db(); self.assertEqual(self.authority.current_quarterly_plan_id, first.pk)

    def test_allotment_pins_plan_and_deviation_without_rewriting_prior_output(self):
        plan = self.plan("ORIGINAL-PLAN"); self.fill(plan); plan = self.approve(plan)
        order = self.order(amount="300")
        with self.assertRaisesMessage(ValidationError, "deviation basis"):
            transition_allotment_order(order, "submit", self.preparer)
        order.planning_deviation_basis = "Advance Q2 purchase into Q1 based on procurement evidence"
        order.save()
        order = transition_allotment_order(order, "submit", self.preparer)
        retained = order.planning_context_snapshot
        newer = self.plan("REVISED-PLAN"); self.fill(newer, "500"); self.approve(newer)
        order = transition_allotment_order(order, "post", self.authorizer, "Independent financial and planning review")
        self.assertEqual(order.planning_context_snapshot, retained)
        self.client.force_login(self.authorizer)
        with tempfile.TemporaryDirectory() as folder, override_settings(GRAND_EXPORT_ROOT=folder):
            result = self.client.get(reverse("budget:allotment_export", args=[order.public_id]))
            self.assertContains(result, "ORIGINAL-PLAN"); self.assertNotContains(result, "REVISED-PLAN")
        plan.refresh_from_db(); self.assertEqual(plan.status, plan.APPROVED)

    def test_intervening_release_requires_return_and_retained_deviation_basis(self):
        plan = self.plan(); self.fill(plan, "300"); self.approve(plan)
        first, second = self.order("FIRST", "200"), self.order("SECOND", "200")
        first = transition_allotment_order(first, "submit", self.preparer)
        second = transition_allotment_order(second, "submit", self.preparer)
        transition_allotment_order(first, "post", self.authorizer, "Reviewed")
        with self.assertRaisesMessage(ValidationError, "Other releases"):
            transition_allotment_order(second, "post", self.authorizer, "Reviewed")
        second = transition_allotment_order(second, "return", self.authorizer, "Explain timing change")
        second.planning_deviation_basis = "Updated delivery schedule"; second.save()
        second = transition_allotment_order(second, "submit", self.preparer)
        second = transition_allotment_order(second, "post", self.authorizer, "Reviewed revised evidence")
        self.assertEqual(AllotmentMovement.objects.count(), 2)

    def test_return_header_correction_and_browser_routes_preserve_review_history(self):
        plan = self.plan(); self.fill(plan)
        plan = transition_plan(plan=plan, action="submit", actor=self.preparer)
        original = plan.submitted_snapshot
        plan = transition_plan(plan=plan, action="return", actor=self.authorizer, reason="Clarify header")
        plan = edit_header(plan=plan, actor=self.preparer, values={"reference": "CORRECTED", "prepared_on": date(2027,1,3),
            "evidence_reference": "Corrected synthetic reference", "change_basis": "Explained revision"})
        plan = self.approve(plan)
        self.assertTrue(BudgetAuditEvent.objects.filter(target_id=str(plan.public_id), action="quarterly_submit", snapshot__context=original).exists())
        self.client.force_login(self.preparer)
        self.assertContains(self.client.get(reverse("budget:quarterly_detail", args=[plan.public_id])), "Current approved plan")
        with tempfile.TemporaryDirectory() as folder, override_settings(GRAND_EXPORT_ROOT=folder):
            self.assertContains(self.client.get(reverse("budget:quarterly_export", args=[plan.public_id])), "CORRECTED")
        self.assertContains(self.client.get(reverse("budget:authorization_detail", args=[self.authority.public_id])), "Prepare plan or successor")

    def test_dated_control_sources_and_contributors_remain_distinct(self):
        order = self.order()
        order = transition_allotment_order(order, "submit", self.preparer)
        transition_allotment_order(order, "post", self.authorizer, "Synthetic release without a plan")
        plan = self.plan(); self.fill(plan)
        self.assertEqual(plan_context(plan)["rows"][0]["control_sources"], [])
        plan = edit_header(plan=plan, actor=self.preparer, values={"reference": "DATED", "prepared_on": date(2027,1,6),
            "evidence_reference": "Dated release context", "change_basis": "Include posted release"})
        context = plan_context(plan)
        self.assertEqual(context["rows"][0]["control_sources"][0]["reference"], order.order_number)
        self.assertEqual(Decimal(context["rows"][0]["balances"]["released"]), Decimal("200"))
        self.authorizer.user_permissions.add(Permission.objects.get(content_type__app_label="budget", codename="prepare_allotment_releases"))
        edit_line(plan=plan, line_id=plan.lines.get().pk, actor=self.authorizer, values={"basis": "Reviewer contributed this edit"})
        plan = transition_plan(plan=plan, action="submit", actor=self.preparer)
        with self.assertRaisesMessage(ValidationError, "preparer"):
            transition_plan(plan=plan, action="approve", actor=self.authorizer, reason="Must use another reviewer")
        self.client.force_login(self.authorizer)
        response = self.client.get(reverse("budget:quarterly_detail", args=[plan.public_id]))
        self.assertContains(response, "Awaiting an authorized Budget reviewer")
        self.assertNotContains(response, "Approve planning schedule")
