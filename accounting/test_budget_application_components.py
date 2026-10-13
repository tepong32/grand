from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import budget_attributions as attributions
from . import test_budget_reviewed_components as fixtures
from . import test_budget_claim_sources as claim_fixtures
from . import shared_claim_proposals
from .budget_application_components import bind_application_rows
from .budget_reviewed_components import source_components
from .models import ResponsibilityCenter
from .services import create_reversal


class ApplicationComponentTests(TestCase):
    databases = {"default", "finance"}
    entry = fixtures.ReviewedComponentTests.entry
    post = fixtures.ReviewedComponentTests.post
    capture = fixtures.ReviewedComponentTests.capture
    rows = fixtures.ReviewedComponentTests.rows
    propose = fixtures.ReviewedComponentTests.propose
    approve = fixtures.ReviewedComponentTests.approve
    legacy = claim_fixtures.BudgetClaimSourceTests.legacy
    detail = claim_fixtures.BudgetClaimSourceTests.detail
    schedule = claim_fixtures.BudgetClaimSourceTests.schedule
    sources_and_payment = claim_fixtures.BudgetClaimSourceTests.sources_and_payment

    def setUp(self):
        fixtures.ReviewedComponentTests.setUp(self)
        self.approve(self.propose())
        self.bound = source_components(self.capture(), self.source.pk)
        self.center = ResponsibilityCenter.objects.create(**self.owner, code="OFFICE", name="Synthetic office",
                                                         office_id=self.department.pk)
        self.payment = self.post(self.entry("BOUND-PAYMENT", Decimal("600"), source=self.source, day=4))

    def reference(self, basis):
        component = next(item for item in self.bound.components if item.basis == basis)
        return dict(source_line_id=self.source.pk, attribution_id=self.bound.attribution_id, component_key=component.key)

    def payment_rows(self):
        debit = self.payment.lines.get(sequence=1)
        credit = self.payment.lines.get(sequence=2)
        return [dict(line_id=debit.pk, amount="200", disposition="include", purpose="debt_principal",
                     center_id=self.center.pk, expense_class="DEBT", basis="Explicit synthetic principal payment share",
                     claim_component=self.reference("loan_principal")),
                dict(line_id=debit.pk, amount="400", disposition="exclude", purpose="settlement",
                     basis="Explicit synthetic previously recognized settlement share",
                     claim_component=self.reference("recognized_expenditure")),
                dict(line_id=credit.pk, amount="600", disposition="exclude", purpose="counterpart",
                     basis="Bank counterpart is not a second expenditure")]

    def test_complete_payment_binding_is_reviewed_and_retained_in_one_capture(self):
        records = self.propose(self.payment_rows(), entry=self.payment)
        self.assertEqual(records[0].source_snapshot["component_sources"][0]["attribution"]["public_id"], self.bound.attribution_id)
        self.approve(records)
        with CaptureQueriesContext(connections["finance"]) as queries:
            captured = self.capture()
            projected = attributions.reviewed_allocations(captured)
            bound = bind_application_rows(captured, self.payment.pk, records[0].allocations)
        self.assertEqual(len(queries), 1)
        self.assertEqual(len(bound["bindings"]), 2)
        self.assertEqual({row["basis"]: row["amount"] for row in bound["bindings"]},
                         {"loan_principal": "200.00", "recognized_expenditure": "400.00"})
        self.assertTrue(all(row["status"] == "reviewed" for row in projected))

    def test_wrong_component_capacity_and_second_recognition_are_rejected(self):
        rows = self.payment_rows()
        rows[0]["claim_component"] = self.reference("recognized_expenditure")
        with self.assertRaisesMessage(ValidationError, "second expenditure"):
            self.propose(rows, entry=self.payment)
        rows = self.payment_rows()
        rows[0]["amount"], rows[1]["amount"] = "500", "100"
        with self.assertRaisesMessage(ValidationError, "another component"):
            self.propose(rows, entry=self.payment)
        rows = self.payment_rows()
        rows[0]["claim_component"]["component_key"] = "invented-component"
        with self.assertRaises(ValidationError):
            self.propose(rows, entry=self.payment)
        rows = self.payment_rows()
        rows[-1]["claim_component"] = self.reference("loan_principal")
        with self.assertRaisesMessage(ValidationError, "exact retained financial application"):
            self.propose(rows, entry=self.payment)

    def test_missing_component_stays_unresolved_instead_of_implicit_settlement(self):
        rows = self.payment_rows()
        del rows[1]["claim_component"]
        with self.assertRaisesMessage(ValidationError, "entire application"):
            self.propose(rows, entry=self.payment)
        debit = self.payment.lines.get(sequence=1)
        unresolved = [dict(line_id=debit.pk, amount="600", disposition="unresolved", purpose="unresolved",
                           basis="Component attribution awaits evidence"), rows[-1]]
        records = self.propose(unresolved, entry=self.payment)
        self.approve(records)
        result = bind_application_rows(self.capture(), self.payment.pk, records[0].allocations)
        self.assertEqual(result, {"bindings": [], "unresolved_line_ids": [debit.pk]})

    def test_source_successor_blocks_pending_review_and_preserves_old_approved_capture(self):
        records = self.propose(self.payment_rows(), entry=self.payment)
        self.approve(records)
        retained = self.capture()
        expected = deepcopy(attributions.reviewed_allocations(retained))
        pending = self.propose(self.payment_rows(), version=1, entry=self.payment)
        self.approve(self.propose(version=1))
        with self.assertRaises(ValidationError):
            self.approve(pending)
        with self.assertRaises(ValidationError):
            attributions.reviewed_allocations(self.capture())
        self.assertEqual(attributions.reviewed_allocations(retained), expected)

    def test_payment_return_inherits_component_identity_amount_office_and_sign(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        returned = create_reversal(self.payment, self.maker, reference="BOUND-RETURN",
            entry_date=date(2026, 9, 5), period=self.period, reason="Synthetic actual returned payment")
        self.post(returned)
        rows = attributions.reversal_allocations(self.capture(), returned.pk)
        records = self.propose(rows, entry=returned)
        self.approve(records)
        bound = bind_application_rows(self.capture(), returned.pk, records[0].allocations)
        self.assertEqual({row["signed_amount"] for row in bound["bindings"]}, {"-200.00", "-400.00"})
        self.assertEqual({row["component_key"] for row in bound["bindings"]},
                         {item.key for item in self.bound.components})

    def test_shared_payment_cannot_move_amount_between_original_credits(self):
        first, second, payment, args = self.schedule()
        shared_claim_proposals.review(shared_claim_proposals.propose(**args), self.poster,
            approve=True, note="Checked exact shared original credit amounts")
        refs = []
        for source in (first, second):
            rows = [dict(line_id=line.pk, amount=str(line.debit or line.credit), disposition="exclude",
                         purpose="counterpart", basis="Synthetic reviewed shared-source evidence")
                    for line in source.entry.lines.order_by("sequence")]
            next(row for row in rows if row["line_id"] == source.pk)["claim_component_basis"] = "recognized_expenditure"
            self.approve(self.propose(rows, entry=source.entry))
            bound = source_components(self.capture(), source.pk)
            refs.append(dict(source_line_id=source.pk, attribution_id=bound.attribution_id,
                             component_key=bound.components[0].key))
        bank = payment.entry.lines.get(sequence=2)
        rows = [dict(line_id=payment.pk, amount=amount, disposition="exclude", purpose="settlement",
                     basis="Exact reviewed historical payment share", claim_component=reference)
                for amount, reference in zip(("400", "100"), refs)]
        rows.append(dict(line_id=bank.pk, amount="500", disposition="exclude", purpose="counterpart",
                         basis="One actual bank amount"))
        with self.assertRaisesMessage(ValidationError, "each original credit"):
            self.propose(rows, entry=payment.entry)
        rows[0]["amount"], rows[1]["amount"] = "300", "200"
        records = self.propose(rows, entry=payment.entry)
        self.approve(records)
        result = bind_application_rows(self.capture(), payment.entry_id, records[0].allocations)
        self.assertEqual({row["source_line_id"]: row["amount"] for row in result["bindings"]},
                         {first.pk: "300.00", second.pk: "200.00"})
