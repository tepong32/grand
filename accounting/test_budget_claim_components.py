from dataclasses import replace
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .budget_claim_components import Component, Movement, validate_usage


class BudgetClaimComponentTests(SimpleTestCase):
    def source(self, key="principal", amount="500", basis="loan_principal"):
        return Component(key, date(2026, 1, 1), Decimal(amount), basis)

    def use(self, key="payment", amount="400", day=2, component="principal", **extra):
        return Movement(key, component, date(2026, 1, day), Decimal(amount),
            disposition="include", purpose="debt_principal", office_id=10, object_class="DEBT", **extra)

    def test_mixed_components_do_not_borrow_capacity_or_count_recognition_again(self):
        sources = [self.source(), self.source("recognized", "500", "recognized_expenditure")]
        settlement = Movement("settlement", "recognized", date(2026, 1, 2), Decimal("500"))
        result = validate_usage(sources, [self.use(amount="500"), settlement])
        self.assertEqual(result["principal"]["available"], "0.00")
        with self.assertRaises(ValidationError):
            validate_usage(sources, [self.use(amount="600")])
        with self.assertRaises(ValidationError):
            validate_usage(sources, [self.use(component="recognized")])

    def test_two_offices_share_one_component_capacity(self):
        with self.assertRaises(ValidationError):
            validate_usage([self.source()], [self.use(), replace(self.use("other", "200"), office_id=20)])

    def test_later_return_cannot_fund_earlier_overuse(self):
        payment = self.use()
        returned = replace(payment, key="return", amount=Decimal("-400"), effective_date=date(2026, 1, 4), reverses="payment")
        with self.assertRaises(ValidationError):
            validate_usage([self.source()], [payment, returned, self.use("too-early", "200", day=3)])
        result = validate_usage([self.source()], [returned, self.use("later", "500", day=5), payment])
        self.assertEqual(result["principal"]["applied"], "500.00")
        self.assertEqual(result["principal"]["boundaries"][1]["available"], "100.00")

    def test_exact_reversal_cannot_change_office_duplicate_return_or_invent_capacity(self):
        payment = self.use()
        returned = replace(payment, key="return", amount=Decimal("-400"), reverses="payment")
        for invalid in (replace(returned, office_id=20), replace(returned, amount=Decimal("-399")),
                        replace(returned, reverses=None)):
            with self.assertRaises(ValidationError):
                validate_usage([self.source()], [payment, invalid])
        with self.assertRaises(ValidationError):
            validate_usage([self.source()], [payment, returned, replace(returned, key="second-return")])

    def test_source_cancellation_and_reversal_of_reversal_preserve_dated_limits(self):
        cancel = Movement("cancel", "principal", date(2026, 1, 3), Decimal("-500"), kind="capacity",
                          reverses="origin:principal", purpose="source_capacity")
        with self.assertRaises(ValidationError):
            validate_usage([self.source()], [self.use(), cancel])
        restore = replace(cancel, key="restore", amount=Decimal("500"), effective_date=date(2026, 1, 4), reverses="cancel")
        result = validate_usage([self.source()], [restore, cancel, self.use(day=5)])
        self.assertEqual(result["principal"]["available"], "100.00")

    def test_missing_or_cyclic_reversal_is_rejected(self):
        first = self.use(reverses="second")
        second = replace(first, key="second", amount=Decimal("-400"), reverses="payment")
        with self.assertRaises(ValidationError):
            validate_usage([self.source()], [first, second])
        with self.assertRaises(ValidationError):
            validate_usage([self.source()], [first])

    def test_long_retained_reversal_chain_has_no_recursion_limit(self):
        events = [self.use()]
        for number in range(1200):
            prior = events[-1]
            events.append(replace(prior, key=f"reversal-{number}", amount=-prior.amount, reverses=prior.key))
        result = validate_usage([self.source()], reversed(events))
        self.assertEqual(result["principal"]["applied"], "400.00")
