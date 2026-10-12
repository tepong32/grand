from dataclasses import replace
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import budget_attributions as attributions
from . import budget_native_sources
from . import test_budget_claim_sources as fixtures
from .budget_claim_components import Movement, validate_usage
from .budget_reviewed_components import source_components
from .services import create_reversal


class ReviewedComponentTests(TestCase):
    databases = {"default", "finance"}
    entry = fixtures.BudgetClaimSourceTests.entry
    post = fixtures.BudgetClaimSourceTests.post

    def setUp(self):
        fixtures.BudgetClaimSourceTests.setUp(self)
        for actor, actions in ((self.maker, ("prepare",)), (self.poster, ("review", "view"))):
            actor.user_permissions.add(*Permission.objects.filter(content_type__app_label="accounting",
                codename__in=[f"{action}_budget_attributions" for action in actions]))
        self.original = self.post(self.entry("COMPONENT-SOURCE", Decimal("1000")))
        self.source = self.original.lines.get(sequence=2)

    def capture(self):
        return budget_native_sources.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 5))

    def rows(self):
        debit = self.original.lines.get(sequence=1)
        return [dict(line_id=debit.pk, amount="1000", disposition="exclude", purpose="other_exclusion",
                     basis="Synthetic source-component test; no office expenditure certification"),
                dict(line_id=self.source.pk, amount="400", disposition="exclude", purpose="counterpart",
                     basis="Explicit synthetic principal component evidence", claim_component_basis="loan_principal"),
                dict(line_id=self.source.pk, amount="600", disposition="exclude", purpose="counterpart",
                     basis="Explicit synthetic previously recognized component evidence", claim_component_basis="recognized_expenditure")]

    def propose(self, rows=None, version=0, entry=None):
        return attributions.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 5),
            expected_source_checksum=self.capture()["checksum"],
            proposals=[dict(entry_id=(entry or self.original).pk, expected_latest=version,
                            allocations=self.rows() if rows is None else rows)],
            reason="Review explicit original-credit components", evidence_reference="SYN-COMPONENTS")

    def approve(self, records):
        return attributions.review_batch(batch_id=records[0].batch_id, actor=self.poster,
            approve=True, note="Independently checked source component evidence")

    def test_approved_complete_source_binds_exact_capacity_without_additional_reads(self):
        pending = self.propose()
        with self.assertRaises(ValidationError):
            source_components(self.capture(), self.source.pk)
        self.approve(pending)
        with CaptureQueriesContext(connections["finance"]) as queries:
            captured = self.capture()
            bound = source_components(captured, self.source.pk)
        self.assertEqual(len(queries), 1)
        self.assertEqual({item.basis: item.amount for item in bound.components},
                         {"loan_principal": Decimal("400"), "recognized_expenditure": Decimal("600")})
        principal = next(item for item in bound.components if item.basis == "loan_principal")
        use = Movement("payment", principal.key, date(2026, 9, 4), Decimal("400"),
            disposition="include", purpose="debt_principal", office_id=10, object_class="DEBT")
        self.assertEqual(validate_usage(bound.components, [use])[principal.key]["available"], "0.00")
        with self.assertRaises(ValidationError):
            validate_usage(bound.components, [replace(use, amount=Decimal("401"))])
        self.post(self.entry("LATER-PAYMENT", Decimal("400"), source=self.source, day=4))
        self.assertEqual(source_components(self.capture(), self.source.pk), bound)

    def test_missing_basis_is_not_inferred_and_invalid_declaration_is_rejected(self):
        invalid = self.rows()
        invalid[0]["claim_component_basis"] = "loan_principal"
        with self.assertRaises(ValidationError):
            self.propose(invalid)
        incomplete = self.rows()
        del incomplete[-1]["claim_component_basis"]
        self.approve(self.propose(incomplete))
        with self.assertRaisesMessage(ValidationError, "Every source-credit component"):
            source_components(self.capture(), self.source.pk)

    def test_successor_has_new_component_identities_and_old_capture_still_reproduces(self):
        self.approve(self.propose())
        retained = self.capture()
        old = source_components(retained, self.source.pk)
        self.approve(self.propose(version=1))
        current = self.capture()
        with self.assertRaisesMessage(ValidationError, "version changed"):
            source_components(current, self.source.pk, expected_attribution_id=old.attribution_id)
        new = source_components(current, self.source.pk)
        self.assertFalse({item.key for item in old.components} & {item.key for item in new.components})
        self.assertEqual(source_components(retained, self.source.pk, expected_attribution_id=old.attribution_id), old)

    def test_exact_reversal_retains_basis_but_does_not_create_new_original_capacity(self):
        self.approve(self.propose())
        reverse = create_reversal(self.original, self.maker, reference="COMPONENT-CORRECTION",
            entry_date=date(2026, 9, 4), period=self.period, reason="Synthetic exact source correction")
        self.post(reverse)
        rows = attributions.reversal_allocations(self.capture(), reverse.pk)
        self.approve(self.propose(rows, entry=reverse))
        self.assertEqual({row["claim_component_basis"] for row in rows if "claim_component_basis" in row},
                         {"loan_principal", "recognized_expenditure"})
        with self.assertRaises(ValidationError):
            source_components(self.capture(), reverse.lines.get(sequence=2).pk)
