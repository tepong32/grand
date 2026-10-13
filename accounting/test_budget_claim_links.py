from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import test_budget_claim_sources as fixtures
from . import budget_claim_links as service
from . import shared_claim_proposals, claim_attributions as history
from .services import create_reversal


class BudgetClaimLinkTests(TestCase):
    databases = {"default", "finance"}
    setUp = fixtures.BudgetClaimSourceTests.setUp
    entry = fixtures.BudgetClaimSourceTests.entry
    post = fixtures.BudgetClaimSourceTests.post
    legacy = fixtures.BudgetClaimSourceTests.legacy
    detail = fixtures.BudgetClaimSourceTests.detail
    proposal = fixtures.BudgetClaimSourceTests.proposal
    sources_and_payment = fixtures.BudgetClaimSourceTests.sources_and_payment
    schedule = fixtures.BudgetClaimSourceTests.schedule
    capture = fixtures.BudgetClaimSourceTests.capture

    def test_native_whole_payment_and_exact_return_keep_original_and_sign(self):
        original = self.post(self.entry("ORIGINAL", Decimal("1000")))
        source = original.lines.get(sequence=2)
        payment = self.post(self.entry("PAYMENT", Decimal("400"), source=source, day=4))
        returned = create_reversal(payment, self.maker, reference="RETURNED",
            entry_date=date(2026, 9, 5), period=self.period, reason="Actual returned payment")
        self.post(returned)
        with CaptureQueriesContext(connections["finance"]) as queries:
            result = service.application_links(self.capture())
        self.assertEqual(len(queries), 1)
        self.assertEqual(len(result["links"]), 2)
        self.assertEqual({row["source_line_id"] for row in result["links"]}, {source.pk})
        self.assertEqual({row["signed_amount"] for row in result["links"]}, {"400.00", "-400.00"})
        self.assertEqual(result["unlinked_liability_lines"], [])

    def test_shared_historical_amounts_are_complete_without_duplicate_whole_payment(self):
        first, second, payment, args = self.schedule()
        shared_claim_proposals.review(shared_claim_proposals.propose(**args), self.poster,
            approve=True, note="Checked both source shares")
        with CaptureQueriesContext(connections["finance"]) as queries:
            result = service.application_links(self.capture())
        self.assertEqual(len(queries), 1)
        self.assertEqual({row["source_line_id"]: row["amount"] for row in result["links"]},
                         {first.pk: "300.00", second.pk: "200.00"})
        self.assertEqual({row["line_id"] for row in result["links"]}, {payment.pk})
        self.assertEqual(sum(Decimal(row["amount"]) for row in result["links"]), Decimal("500"))

    def test_unlinked_liability_is_explicit_and_unrelated_bad_history_is_not_used(self):
        source, payment = self.legacy()
        record = history.review(self.proposal(source, [payment]), self.poster, approve=True, note="Historical source")
        other = self.post(self.entry("OTHER-ORIGINAL", Decimal("25"), day=5, claim="OTHER"))
        history.Attribution.objects.filter(pk=record.pk).update(reason="Invalid unrelated approval")
        captured = self.capture()
        with self.assertRaises(ValidationError):
            service.application_links(captured)
        result = service.application_links(captured, entry_ids=[other.pk])
        self.assertEqual(result["links"], [])
        self.assertEqual(result["unlinked_liability_lines"], [{"entry_id": other.pk,
            "line_id": other.lines.get(sequence=2).pk, "debit": "0.00", "credit": "25.00", "reversal_of_id": None}])
