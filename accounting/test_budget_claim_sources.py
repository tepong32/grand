"""Capture actual reviewed claim links without multiplying ledger activity."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from . import budget_native_sources as capture_service
from . import budget_attributions
from . import budget_claim_sources
from . import claim_attributions as history
from . import test_claim_attributions as fixtures
from . import test_claim_splits as split_fixtures
from . import test_shared_claim_proposals as shared_fixtures
from . import shared_claim_proposals


class BudgetClaimSourceTests(TestCase):
    databases = {"default", "finance"}
    entry = fixtures.ClaimAttributionTests.entry
    post = fixtures.ClaimAttributionTests.post
    legacy = fixtures.ClaimAttributionTests.legacy
    detail = fixtures.ClaimAttributionTests.detail
    proposal = fixtures.ClaimAttributionTests.proposal
    sources_and_payment = shared_fixtures.SharedClaimProposalTests.sources_and_payment
    schedule = shared_fixtures.SharedClaimProposalTests.schedule

    def setUp(self):
        fixtures.ClaimAttributionTests.setUp(self)
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label="accounting",
            codename="view_budget_attributions"))

    def capture(self):
        return capture_service.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 4), period_end=date(2026, 9, 5))

    def test_historical_link_brings_outside_period_original_without_counting_it(self):
        source, payment = self.legacy()
        before = self.capture()
        self.assertEqual(before["payload"]["claim_sources"], [])
        approved = history.review(self.proposal(source, [payment]), self.poster,
            approve=True, note="Reconciled original and historical payment")
        with CaptureQueriesContext(connections["finance"]) as queries:
            captured = self.capture()
            verified = budget_claim_sources.verified_claims(captured)
        self.assertEqual(len(queries), 1)
        self.assertEqual(verified[source.pk]["public_id"], str(approved.public_id))
        self.assertNotEqual(captured["checksum"], before["checksum"])
        self.assertEqual(captured["payload"]["controls"]["debit"], "400.00")
        self.assertEqual(captured["payload"]["controls"]["lines"], 2)
        self.assertEqual([item["id"] for item in captured["payload"]["claim_sources"]], [source.entry_id])
        original = captured["payload"]["claim_sources"][0]
        claim = next(line["claim_attribution"] for line in original["lines"] if line["id"] == source.pk)
        self.assertEqual(claim["public_id"], str(approved.public_id))
        self.assertEqual(claim["source_snapshot"], approved.source_snapshot)
        self.assertEqual(claim["reviewed_at"], approved.reviewed_at.isoformat())
        evidence = budget_attributions.financial_source(captured["payload"], payment.entry_id)
        self.assertEqual(evidence["claim_sources"][0]["id"], source.entry_id)
        frozen = deepcopy(captured)
        history.review(self.proposal(source, [payment], expected_version=1, claim_reference="CORRECTED"),
            self.poster, approve=True, note="Corrected documentary reference")
        self.assertFalse(capture_service.is_current(captured, self.maker))
        self.assertEqual(captured, frozen)
        self.assertEqual(budget_claim_sources.verified_claims(captured)[source.pk]["public_id"], str(approved.public_id))
        self.assertNotEqual(evidence, budget_attributions.financial_source(self.capture()["payload"], payment.entry_id))
        # Simulate altered retained decision data; a new coherent capture alone
        # must not make it a valid independently reviewed historical link.
        history.Attribution.objects.filter(source=source, version=2).update(reason="Changed without review")
        with self.assertRaises(ValidationError):
            budget_claim_sources.verified_claims(self.capture())

    def test_split_invoice_join_keeps_one_financial_line_and_exact_invoice_amounts(self):
        source, payment = self.legacy()
        rows = split_fixtures.HistoricalClaimSplitReviewTests.rows(self, payment)
        proposal = history.propose(source, self.maker, applications=[payment.pk], allocations=rows,
            expected_version=0, evidence_reference="Complete invoice schedule", reason="Explicit split evidence")
        record = history.review(proposal, self.poster, approve=True, note="Checked both invoice shares")
        with CaptureQueriesContext(connections["finance"]) as queries:
            captured = self.capture()
            verified = budget_claim_sources.verified_claims(captured)
        self.assertEqual(len(queries), 1)
        original = captured["payload"]["claim_sources"][0]
        self.assertEqual(len(original["lines"]), 2)
        self.assertEqual(captured["payload"]["controls"]["debit"], "400.00")
        claim = next(line["claim_attribution"] for line in original["lines"] if line["id"] == source.pk)
        self.assertEqual(claim["invoice_slices"], history.allocation_rows(record))
        self.assertEqual(verified[source.pk]["invoice_slices"], claim["invoice_slices"])

    def test_period_view_retains_reviewed_claim_graph_without_original_activity(self):
        from .budget_native_periods import reframe
        source, payment = self.legacy()
        approved = history.review(self.proposal(source, [payment]), self.poster,
            approve=True, note='Reviewed period dependency')
        parent = capture_service.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date.min, period_end=date(2026, 9, 5))
        with CaptureQueriesContext(connections['finance']) as finance, CaptureQueriesContext(connections['default']) as default:
            derived = reframe(parent, period_start=date(2026, 9, 4), period_end=date(2026, 9, 5))
            verified = budget_claim_sources.verified_claims(derived)
        self.assertEqual((len(finance), len(default)), (0, 0))
        self.assertEqual(derived['payload'], self.capture()['payload'])
        self.assertEqual(derived['payload']['controls']['debit'], '400.00')
        self.assertEqual([row['id'] for row in derived['payload']['claim_sources']], [source.entry_id])
        self.assertEqual(verified[source.pk]['public_id'], str(approved.public_id))

    def test_shared_historical_payment_retains_both_independent_members(self):
        first, second, payment, args = self.schedule()
        proposal = shared_claim_proposals.propose(**args)
        records = shared_claim_proposals.review(proposal, self.poster, approve=True,
            note="Reviewed complete shared payment")
        with CaptureQueriesContext(connections["finance"]) as queries:
            captured = self.capture()
            verified = budget_claim_sources.verified_claims(captured)
        self.assertEqual(len(queries), 1)
        sources = captured["payload"]["claim_sources"]
        self.assertEqual({item["id"] for item in sources}, {first.entry_id, second.entry_id})
        claims = [line["claim_attribution"] for item in sources for line in item["lines"] if line["claim_attribution"]]
        self.assertEqual({claim["public_id"] for claim in claims}, {str(record.public_id) for record in records})
        self.assertTrue(all(claim["shared_proposal"]["public_id"] == str(proposal.public_id) for claim in claims))
        self.assertEqual(captured["payload"]["controls"]["debit"], "500.00")
        self.assertEqual(sum(Decimal(claim["application_amounts"][str(payment.pk)]) for claim in claims), Decimal("500"))
        self.assertEqual(set(verified), {first.pk, second.pk})
        history.Head.objects.filter(source=second).delete()
        with self.assertRaises(ValidationError):
            budget_claim_sources.verified_claims(self.capture())

    def test_native_claim_link_retains_original_without_historical_head(self):
        original = self.post(self.entry("NATIVE-ORIGINAL", Decimal("1000")))
        source = original.lines.get(sequence=2)
        initial = capture_service.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 5))
        original_evidence = budget_attributions.financial_source(initial["payload"], original.pk)
        self.post(self.entry("NATIVE-PAYMENT", Decimal("400"), source=source, day=4))
        captured = self.capture()
        self.assertEqual([item["id"] for item in captured["payload"]["claim_sources"]], [original.pk])
        self.assertEqual(captured["payload"]["controls"]["debit"], "400.00")
        self.assertTrue(all(line["claim_attribution"] is None for line in captured["payload"]["claim_sources"][0]["lines"]))
        # A later native payment changes cohort coverage, not the original expense's
        # unchanged classification evidence. The payment does retain its original.
        self.assertEqual(original_evidence, budget_attributions.financial_source(captured["payload"], original.pk))
        self.assertEqual(budget_claim_sources.verified_claims(captured), {})

    def test_attribution_checks_claim_approval_before_submission_and_review(self):
        from .models import BudgetExpenditureAttribution
        self.maker.user_permissions.add(Permission.objects.get(content_type__app_label="accounting",
            codename="prepare_budget_attributions"))
        self.poster.user_permissions.add(Permission.objects.get(content_type__app_label="accounting",
            codename="review_budget_attributions"))
        source, payment = self.legacy()
        approved = history.review(self.proposal(source, [payment]), self.poster,
            approve=True, note="Reconciled historical settlement")
        rows = [dict(line_id=line.pk, amount=str(line.debit or line.credit),
            disposition="unresolved" if line.pk == payment.pk else "exclude",
            purpose="unresolved" if line.pk == payment.pk else "counterpart",
            basis="Verified claim link; Budget source components still require independent review")
            for line in payment.entry.lines.order_by("sequence")]
        def propose():
            return budget_attributions.propose_batch(actor=self.maker, fund_id=self.fund.pk,
                period_start=date(2026, 9, 4), period_end=date(2026, 9, 5),
                expected_source_checksum=self.capture()["checksum"],
                proposals=[dict(entry_id=payment.entry_id, expected_latest=0, allocations=rows)],
                reason="Source-linked settlement review", evidence_reference="SYN-PAYMENT")
        history.Attribution.objects.filter(pk=approved.pk).update(reason="Invalid retained decision")
        with self.assertRaises(ValidationError):
            propose()
        self.assertFalse(BudgetExpenditureAttribution.objects.exists())
        history.Attribution.objects.filter(pk=approved.pk).update(reason=approved.reason)
        records = propose()
        history.Attribution.objects.filter(pk=approved.pk).update(reason="Invalid later decision")
        with self.assertRaises(ValidationError):
            budget_attributions.review_batch(batch_id=records[0].batch_id, actor=self.poster,
                approve=True, note="Must recheck exact retained decision")
        records[0].refresh_from_db()
        self.assertEqual(records[0].status, "submitted")
        history.Attribution.objects.filter(pk=approved.pk).update(reason=approved.reason)
        budget_attributions.review_batch(batch_id=records[0].batch_id, actor=self.poster,
            approve=True, note="Independently checked retained settlement source")

    def test_selected_journal_verification_does_not_adopt_unrelated_broken_heads(self):
        source, payment = self.legacy()
        approved = history.review(self.proposal(source, [payment]), self.poster,
            approve=True, note="Original historical claim review")
        unrelated = self.post(self.entry("UNRELATED", Decimal("25"), day=5, claim="UNRELATED"))
        history.Attribution.objects.filter(pk=approved.pk).update(reason="Broken unrelated decision")
        captured = self.capture()
        with self.assertRaises(ValidationError):
            budget_claim_sources.verified_claims(captured)
        self.assertEqual(budget_claim_sources.verified_claims(captured, entry_ids=[unrelated.pk]), {})
        with self.assertRaises(ValidationError):
            budget_claim_sources.verified_claims(captured, entry_ids=[payment.entry_id])

    def test_native_invoice_payment_retains_older_pin_after_compatible_successor(self):
        from .claim_splits import bind_allocation
        from .budget_claim_links import application_links
        source, historical_payment = self.legacy()
        invoices = split_fixtures.HistoricalClaimSplitReviewTests.rows(self, historical_payment)
        def propose(version):
            return history.propose(source, self.maker, applications=[historical_payment.pk], allocations=invoices,
                expected_version=version, evidence_reference="Retained invoice evidence", reason="Same invoice schedule")
        old = history.review(propose(0), self.poster, approve=True, note="Original reviewed invoices")
        original_evidence = budget_attributions.financial_source(self.capture()["payload"], source.entry_id)
        payment = self.entry("PINNED-PAYMENT", Decimal("50"), source=source, day=5)
        line = payment.lines.get(sequence=1)
        line.payable_allocation = bind_allocation(source, {invoices[0]["key"]: "50"})
        line.save()
        self.post(payment)
        before = self.capture()
        self.assertEqual(original_evidence, budget_attributions.financial_source(before["payload"], source.entry_id))
        self.assertEqual([record["public_id"] for record in
            budget_attributions.financial_source(before["payload"], payment.pk)["claim_pins"]], [str(old.public_id)])
        pending = propose(1)
        self.assertTrue(capture_service.is_current(before, self.maker))
        newer = history.review(pending, self.poster, approve=True, note="Compatible successor")
        with CaptureQueriesContext(connections["finance"]) as queries:
            captured = self.capture()
            verified = budget_claim_sources.verified_claims(captured)
            links = application_links(captured)
        self.assertEqual(len(queries), 1)
        self.assertEqual(verified[source.pk]["public_id"], str(newer.public_id))
        native = next(row for row in links["links"] if row["entry_id"] == payment.pk)
        self.assertEqual(native["amount"], "50.00")
        self.assertEqual(native["approval"]["public_id"], str(old.public_id))
        original = next(entry for entry in captured["payload"]["claim_sources"] if entry["id"] == source.entry_id)
        retained = next(item for item in original["lines"] if item["id"] == source.pk)
        self.assertEqual(retained["claim_attribution"]["public_id"], str(newer.public_id))
        self.assertEqual([item["public_id"] for item in retained["retained_claim_attributions"]], [str(old.public_id)])
        self.assertEqual(captured["payload"]["controls"]["debit"], "450.00")
        self.assertEqual(captured["payload"]["controls"]["lines"], 4)
        self.assertNotIn("_claim_versions", retained)
        line.refresh_from_db()
        self.assertEqual(line.payable_allocation["attribution"]["public_id"], str(old.public_id))
        history.Attribution.objects.filter(pk=old.pk).update(reason="Altered retained older decision")
        with self.assertRaises(ValidationError):
            budget_claim_sources.verified_claims(self.capture())
        history.Attribution.objects.filter(pk=old.pk).update(reason=old.reason)
        from .models import AccountingAuditEvent
        AccountingAuditEvent.objects.filter(entry=payment, action="posted").update(snapshot={})
        with self.assertRaises(ValidationError):
            budget_claim_sources.verified_claims(self.capture())
        # Earlier retained evidence remains self-contained after live evidence damage.
        self.assertEqual(budget_claim_sources.verified_claims(captured)[source.pk]["public_id"], str(newer.public_id))

    def test_shared_reversal_retains_complete_older_approval_group(self):
        from .services import create_reversal
        from .budget_claim_links import application_links
        first, second, payment, args = self.schedule()
        old = shared_claim_proposals.review(shared_claim_proposals.propose(**args), self.poster,
            approve=True, note="Original shared decision")
        returned = create_reversal(payment.entry, self.maker, reference="PINNED-SHARED-RETURN",
            entry_date=date(2026, 9, 6), period=self.period, reason="Actual linked bank return")
        self.post(returned)
        args.update(expected_approvals={str(record.source_id): record.version for record in old},
            expected_version=1, reason="Compatible updated evidence")
        newer = shared_claim_proposals.review(shared_claim_proposals.propose(**args), self.poster,
            approve=True, note="Compatible shared successor")
        with CaptureQueriesContext(connections["finance"]) as queries:
            captured = capture_service.capture(actor=self.maker, fund_id=self.fund.pk,
                period_start=date(2026, 9, 6), period_end=date(2026, 9, 6))
            verified = budget_claim_sources.verified_claims(captured)
            links = application_links(captured)
        self.assertEqual(len(queries), 1)
        all_entries = budget_attributions.source_entries(captured["payload"])
        source_lines = [line for entry in all_entries.values() for line in entry["lines"]
                        if line["id"] in (first.pk, second.pk)]
        self.assertEqual({line["claim_attribution"]["public_id"] for line in source_lines},
                         {str(record.public_id) for record in newer})
        self.assertEqual({record["public_id"] for line in source_lines for record in line["retained_claim_attributions"]},
                         {str(record.public_id) for record in old})
        self.assertEqual(captured["payload"]["controls"]["debit"], "500.00")
        self.assertEqual(captured["payload"]["controls"]["lines"], 2)
        self.assertEqual(set(verified), {first.pk, second.pk})
        self.assertEqual(sum(Decimal(row["signed_amount"]) for row in links["links"]), Decimal("-500"))
        self.assertEqual({row["approval"]["public_id"] for row in links["links"]}, {str(record.public_id) for record in old})
        history.Attribution.objects.filter(pk=old[1].pk).update(reason="Changed older group member")
        damaged = capture_service.capture(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2026, 9, 6), period_end=date(2026, 9, 6))
        with self.assertRaises(ValidationError):
            budget_claim_sources.verified_claims(damaged)


@skipUnless(connections["finance"].vendor == "mysql", "Requires native consistent reads during shared approval")
class BudgetClaimCaptureConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = BudgetClaimSourceTests.setUp
    entry = BudgetClaimSourceTests.entry
    post = BudgetClaimSourceTests.post
    legacy = BudgetClaimSourceTests.legacy
    detail = BudgetClaimSourceTests.detail
    proposal = BudgetClaimSourceTests.proposal
    sources_and_payment = BudgetClaimSourceTests.sources_and_payment
    schedule = BudgetClaimSourceTests.schedule
    capture = BudgetClaimSourceTests.capture

    def test_shared_approval_cannot_yield_half_a_captured_claim_group(self):
        first, second, payment, args = self.schedule()
        proposal = shared_claim_proposals.propose(**args)
        barrier = Barrier(2, timeout=30)
        def run(number):
            close_old_connections()
            try:
                barrier.wait()
                if number == 1:
                    shared_claim_proposals.review(proposal, self.poster, approve=True,
                        note="Independent concurrent complete review")
                    return "approved"
                payload = self.capture()["payload"]
                claims = [line["claim_attribution"] for entry in payload["claim_sources"]
                          for line in entry["lines"] if line["claim_attribution"]]
                self.assertIn(len(claims), (0, 2))
                if claims:
                    self.assertEqual({claim["source_id"] for claim in claims}, {first.pk, second.pk})
                    self.assertEqual({claim["shared_proposal_id"] for claim in claims}, {proposal.pk})
                    self.assertEqual(sum(Decimal(claim["application_amounts"][str(payment.pk)])
                                         for claim in claims), Decimal("500"))
                self.assertEqual(payload["controls"]["debit"], "500.00")
                return "coherent"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(run, (1, 2))), ["approved", "coherent"])
