from datetime import date
from decimal import Decimal
from copy import deepcopy

from django.core.exceptions import ValidationError
from django.test import TestCase
from departments.models import Department

from . import budget_attributions as attributions
from . import budget_native_sources
from . import test_budget_application_components as fixtures
from .budget_component_usage import component_usage
from .budget_reviewed_components import source_components
from .cash_classifications import checksum
from .models import BudgetExpenditureAttributionHead, ResponsibilityCenter
from .services import create_reversal


class ComponentUsageTests(TestCase):
    databases = {"default", "finance"}
    setUp = fixtures.ApplicationComponentTests.setUp
    entry = fixtures.ApplicationComponentTests.entry
    post = fixtures.ApplicationComponentTests.post
    rows = fixtures.ApplicationComponentTests.rows
    approve = fixtures.ApplicationComponentTests.approve
    reference = fixtures.ApplicationComponentTests.reference
    payment_rows = fixtures.ApplicationComponentTests.payment_rows

    def capture(self, period_end=None):
        return budget_native_sources.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 1), period_end=period_end or date(2026, 9, 10))

    def propose(self, rows=None, version=0, entry=None, period_end=None):
        return attributions.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 1), period_end=period_end or date(2026, 9, 10),
            expected_source_checksum=self.capture(period_end)["checksum"],
            proposals=[dict(entry_id=(entry or self.original).pk, expected_latest=version,
                            allocations=self.rows() if rows is None else rows)],
            reason="Complete component usage review", evidence_reference="SYN-DATED-USAGE")

    def principal_rows(self, entry, amount, center=None):
        return [dict(line_id=entry.lines.get(sequence=1).pk, amount=str(amount), disposition="include",
                     purpose="debt_principal", center_id=(center or self.center).pk, expense_class="DEBT",
                     basis="Explicit synthetic principal payment", claim_component=self.reference("loan_principal")),
                dict(line_id=entry.lines.get(sequence=2).pk, amount=str(amount), disposition="exclude",
                     purpose="counterpart", basis="Actual bank counterpart")]

    def reverse_and_review(self, entry, reference, day):
        reverse = create_reversal(entry, self.maker, reference=reference,
            entry_date=date(2026, 9, day), period=self.period, reason="Synthetic exact financial correction")
        self.post(reverse)
        self.approve(self.propose(attributions.reversal_allocations(self.capture(), reverse.pk), entry=reverse))
        return reverse

    def test_distinct_offices_cannot_reuse_component_capacity_and_failed_review_rolls_back(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        other = self.post(self.entry("OTHER-PAYMENT", Decimal("300"), source=self.source, day=5))
        requesting_office = Department.objects.create(name="Other requesting office", slug="usage-other-office")
        office = ResponsibilityCenter.objects.create(**self.owner, code="SECOND", name="Other office", office_id=requesting_office.pk)
        pending = self.propose(self.principal_rows(other, "300", office), entry=other)
        with self.assertRaisesMessage(ValidationError, "dated classification capacity"):
            self.approve(pending)
        pending[0].refresh_from_db()
        self.assertEqual(pending[0].status, "submitted")
        self.assertIsNone(pending[0].reviewed_at)
        self.assertFalse(BudgetExpenditureAttributionHead.objects.filter(entry=other).exists())
        result = component_usage(self.capture(), entry_ids=[self.payment.pk])
        self.assertIn(other.pk, result["unreviewed_entry_ids"])
        key = self.reference("loan_principal")["component_key"]
        self.assertEqual(result["components"][key]["applied"], "200.00")

    def test_future_out_of_period_use_blocks_an_earlier_overallocation(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        later = self.post(self.entry("LATER", Decimal("200"), source=self.source, day=5))
        self.approve(self.propose(self.principal_rows(later, "200"), entry=later))
        earlier = self.post(self.entry("BACKDATED", Decimal("100"), source=self.source, day=3))
        boundary = date(2026, 9, 3)
        pending = self.propose(self.principal_rows(earlier, "100"), entry=earlier, period_end=boundary)
        with self.assertRaisesMessage(ValidationError, "dated classification capacity"):
            self.approve(pending)
        result = component_usage(self.capture(boundary), entry_ids=[earlier.pk])
        self.assertIn(later.pk, result["entry_ids"])
        self.assertIn(self.payment.pk, result["entry_ids"])

    def test_later_return_does_not_fund_earlier_use_but_restores_actual_later_capacity(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        self.reverse_and_review(self.payment, "RETURN", 5)
        earlier = self.post(self.entry("EARLY-USE", Decimal("400"), source=self.source, day=4))
        with self.assertRaisesMessage(ValidationError, "dated classification capacity"):
            self.approve(self.propose(self.principal_rows(earlier, "400"), entry=earlier))
        # The earlier posted payment exists. Classify its actual mixed portions
        # explicitly rather than deleting it or treating failed review as reversal.
        rows = self.principal_rows(earlier, "200")
        rows[-1]["amount"] = "400"
        rows.insert(1, dict(line_id=earlier.lines.get(sequence=1).pk, amount="200", disposition="exclude",
            purpose="settlement", basis="Explicit recognized portion", claim_component=self.reference("recognized_expenditure")))
        self.approve(self.propose(rows, version=1, entry=earlier))
        later = self.post(self.entry("AFTER-RETURN", Decimal("200"), source=self.source, day=6))
        self.approve(self.propose(self.principal_rows(later, "200"), entry=later))
        key = self.reference("loan_principal")["component_key"]
        result = component_usage(self.capture(), require_complete=True)
        self.assertEqual(result["components"][key]["applied"], "400.00")
        self.assertEqual(result["components"][key]["boundaries"][1]["available"], "0.00")

    def test_source_cancellation_and_its_reversal_preserve_capacity_lineage(self):
        self.approve(self.propose(self.payment_rows(), entry=self.payment))
        self.reverse_and_review(self.payment, "PAYMENT-RETURN", 5)
        cancelled = self.reverse_and_review(self.original, "SOURCE-CANCEL", 6)
        key = self.reference("loan_principal")["component_key"]
        self.assertEqual(component_usage(self.capture(), require_complete=True)["components"][key]["capacity"], "0.00")
        self.reverse_and_review(cancelled, "SOURCE-RESTORE", 7)
        result = component_usage(self.capture(), require_complete=True)
        self.assertEqual(result["components"][key]["capacity"], "400.00")
        self.assertEqual(result["components"][key]["available"], "400.00")

    def test_missing_decisions_do_not_establish_complete_component_coverage(self):
        result = component_usage(self.capture())
        self.assertFalse(result["complete"])
        self.assertIn(self.payment.pk, result["unreviewed_entry_ids"])
        with self.assertRaisesMessage(ValidationError, "all unreviewed"):
            component_usage(self.capture(), require_complete=True)

    def test_pre_claim_captures_remain_readable_without_claiming_component_coverage(self):
        for schema in (1, 2):
            captured = deepcopy(self.capture())
            captured["payload"]["schema"] = schema
            captured["payload"].pop("claim_sources", None)
            for entry in captured["payload"]["journals"]:
                entry.pop("claim_evidence", None)
                entry.pop("attribution", None)
            captured["checksum"] = checksum(captured["payload"])
            captured["evidence_checksum"] = checksum(dict(source_checksum=captured["checksum"], captured_at=captured["captured_at"]))
            retained = deepcopy(captured)
            result = attributions.reviewed_allocations(captured)
            self.assertTrue(all(row["status"] == "unreviewed" for row in result))
            self.assertEqual(captured, retained)
            with self.assertRaises(ValidationError):
                component_usage(captured, require_complete=True)

    def test_transitive_stale_source_cannot_hide_behind_an_unchanged_direct_head(self):
        source, reference = self.source, self.reference("loan_principal")
        for number in (1, 2):
            swap = self.entry(f"COMPOUND-{number}", Decimal("100"), source=source, day=3 + number)
            credit = swap.lines.get(sequence=2)
            credit.account = self.accounts["payable"]
            credit.cash_flow_category = ""
            credit.payable_party_key, credit.payable_claim_reference = "supplier-001", f"COMPOUND-{number}"
            credit.save()
            self.post(swap)
            rows = [dict(line_id=swap.lines.get(sequence=1).pk, amount="100", disposition="exclude", purpose="settlement",
                         basis="Explicit synthetic liability replacement", claim_component=reference),
                    dict(line_id=credit.pk, amount="100", disposition="exclude", purpose="counterpart",
                         basis="Explicit replacement credit", claim_component_basis="non_expenditure")]
            self.approve(self.propose(rows, entry=swap))
            bound = source_components(self.capture(), credit.pk)
            source = credit
            reference = dict(source_line_id=credit.pk, attribution_id=bound.attribution_id, component_key=bound.components[0].key)
        retained = self.capture()
        self.approve(self.propose(version=1))
        with self.assertRaisesMessage(ValidationError, "no longer reproduces"):
            component_usage(self.capture(), entry_ids=[source.entry_id])
        self.assertEqual(component_usage(retained, entry_ids=[source.entry_id])["components"][reference["component_key"]]["capacity"], "100.00")
