from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from .claim_splits import normalize_allocations


def line(pk, debit, credit, day, *, reversal_of=None):
    return SimpleNamespace(pk=pk, debit=Decimal(debit), credit=Decimal(credit),
        sequence=1, account_id=7, entry_id=pk,
        entry=SimpleNamespace(entry_date=date(2026, 9, day), reversal_of_id=reversal_of))


class HistoricalClaimAllocationCalculations(SimpleTestCase):
    def setUp(self):
        self.source = line(1, "0", "1000", 1)
        self.payment = line(2, "200", "0", 2)
        self.rows = [
            {"key": "00000000-0000-0000-0000-000000000001", "party_key": "supplier-a",
             "claim_reference": "INV-01", "recognized": "600", "applications": {"2": "120"}},
            {"key": "00000000-0000-0000-0000-000000000002", "party_key": "supplier-b",
             "claim_reference": "INV-02", "recognized": "400", "applications": {"2": "80"}},
        ]

    def test_two_invoices_and_prior_payment_reconcile_without_changing_inputs(self):
        before = deepcopy(self.rows)
        result = normalize_allocations(self.source, [self.payment], list(reversed(self.rows)))
        self.assertEqual([Decimal(row["recognized"]) - Decimal(row["applications"]["2"])
                          for row in result], [Decimal("480"), Decimal("320")])
        self.assertEqual(result[0]["recognized"], "600.00")
        self.assertEqual(self.rows, before)
        self.assertEqual(self.source.credit, Decimal("1000"))
        self.assertEqual(self.payment.debit, Decimal("200"))

    def test_parent_credit_and_every_payment_must_be_fully_allocated(self):
        for field, value, message in (("recognized", "599.99", "liability credit exactly"),
                                     ("applications", {"2": "119.99"}, "application in full")):
            with self.subTest(field=field):
                rows = deepcopy(self.rows)
                rows[0][field] = value
                with self.assertRaisesMessage(ValidationError, message):
                    normalize_allocations(self.source, [self.payment], rows)
        with self.assertRaisesMessage(ValidationError, "application in full"):
            normalize_allocations(self.source, [self.payment, line(3, "10", "0", 3)], self.rows)

    def test_one_invoice_cannot_borrow_another_invoices_capacity(self):
        payment = line(2, "700", "0", 2)
        self.rows[0]["applications"]["2"] = "601"
        self.rows[1]["applications"]["2"] = "99"
        with self.assertRaisesMessage(ValidationError, "INV-01 exceeds its dated capacity"):
            normalize_allocations(self.source, [payment], self.rows)

    def test_later_return_does_not_repair_an_earlier_invoice_shortfall(self):
        payment = line(2, "700", "0", 2)
        returned = line(3, "0", "700", 4, reversal_of=2)
        self.rows[0]["applications"] = {"2": "601", "3": "601"}
        self.rows[1]["applications"] = {"2": "99", "3": "99"}
        with self.assertRaisesMessage(ValidationError, "2026-09-02"):
            normalize_allocations(self.source, [payment, returned], self.rows)

    def test_exact_return_preserves_shares_and_rejects_balanced_reassignment(self):
        second = line(3, "200", "0", 3)
        returned = line(4, "0", "200", 4, reversal_of=2)
        self.rows[0]["applications"].update({"3": "100", "4": "120"})
        self.rows[1]["applications"].update({"3": "100", "4": "80"})
        result = normalize_allocations(self.source, [self.payment, second, returned], self.rows)
        self.assertEqual(result[0]["applications"]["4"], "120.00")
        self.rows[0]["applications"]["4"] = "100"
        self.rows[1]["applications"]["4"] = "100"
        with self.assertRaisesMessage(ValidationError, "original invoice share exactly"):
            normalize_allocations(self.source, [self.payment, second, returned], self.rows)

    def test_original_credit_reversal_restores_each_recognized_share(self):
        reversal = line(3, "1000", "0", 3, reversal_of=1)
        self.rows[0]["applications"] = {"3": "600"}
        self.rows[1]["applications"] = {"3": "400"}
        result = normalize_allocations(self.source, [reversal], self.rows)
        self.assertEqual([row["applications"]["3"] for row in result], ["600.00", "400.00"])

    def test_invalid_money_and_duplicate_invoice_identity_are_rejected(self):
        for value in (True, 600.0, "NaN", "Infinity", "-1", "600.001", "10000000000000000"):
            with self.subTest(value=value):
                rows = deepcopy(self.rows)
                rows[0]["recognized"] = value
                with self.assertRaisesMessage(ValidationError, "exact, nonnegative centavos"):
                    normalize_allocations(self.source, [self.payment], rows)
        self.rows[1].update(party_key="SUPPLIER-A", claim_reference="inv-01")
        with self.assertRaisesMessage(ValidationError, "each invoice once"):
            normalize_allocations(self.source, [self.payment], self.rows)

    def test_unselected_and_duplicate_applications_are_rejected(self):
        self.rows[0]["applications"]["99"] = "1"
        with self.assertRaisesMessage(ValidationError, "only the selected"):
            normalize_allocations(self.source, [self.payment], self.rows)
        with self.assertRaisesMessage(ValidationError, "each historical application once"):
            normalize_allocations(self.source, [self.payment, self.payment], self.rows)


class HistoricalClaimAllocationJournalTests(TestCase):
    databases = {"default", "finance"}
    from . import test_claim_attributions as fixture_module
    setUp = fixture_module.ClaimAttributionTests.setUp
    entry = fixture_module.ClaimAttributionTests.entry
    post = fixture_module.ClaimAttributionTests.post
    legacy = fixture_module.ClaimAttributionTests.legacy
    detail = fixture_module.ClaimAttributionTests.detail

    def test_actual_posted_source_payment_and_return_are_unchanged(self):
        from .claim_attributions import serial_snapshot
        from .models import JournalEntry, PayableClaimAttribution
        from .services import create_reversal

        source, payment = self.legacy(payment_amount="200")
        reversal = create_reversal(payment.entry, self.maker, reference="SPLIT-OLD-RETURN",
            entry_date=date(2026, 9, 6), period=self.period, reason="Historical check returned")
        self.post(reversal)
        returned = reversal.lines.get(sequence=payment.sequence)
        before = serial_snapshot(source, [payment.pk, returned.pk])
        rows = [
            {"key": "00000000-0000-0000-0000-000000000001", "party_key": "supplier-a",
             "claim_reference": "INV-01", "recognized": "600",
             "applications": {str(payment.pk): "120", str(returned.pk): "120"}},
            {"key": "00000000-0000-0000-0000-000000000002", "party_key": "supplier-b",
             "claim_reference": "INV-02", "recognized": "400",
             "applications": {str(payment.pk): "80", str(returned.pk): "80"}},
        ]
        result = normalize_allocations(source, [payment, returned], rows)
        self.assertEqual([row["recognized"] for row in result], ["600.00", "400.00"])
        self.assertEqual(serial_snapshot(source, [payment.pk, returned.pk]), before)
        self.assertEqual(JournalEntry.objects.count(), 3)
        self.assertFalse(PayableClaimAttribution.objects.exists())
        self.assertFalse(source.claim_reservations.exists())


class HistoricalClaimSplitReviewTests(TestCase):
    databases = {"default", "finance"}
    from . import test_claim_attributions as fixture_module
    setUp = fixture_module.ClaimAttributionTests.setUp
    entry = fixture_module.ClaimAttributionTests.entry
    post = fixture_module.ClaimAttributionTests.post
    legacy = fixture_module.ClaimAttributionTests.legacy
    detail = fixture_module.ClaimAttributionTests.detail

    def rows(self, payment):
        return [
            {"key": "00000000-0000-0000-0000-000000000001", "party_key": "supplier-001",
             "claim_reference": "SPLIT-01", "recognized": "600", "applications": {str(payment.pk): "240"}},
            {"key": "00000000-0000-0000-0000-000000000002", "party_key": "supplier-002",
             "claim_reference": "SPLIT-02", "recognized": "400", "applications": {str(payment.pk): "160"}},
        ]

    def proposal(self, source, payment, *, rows=None, expected_version=0):
        from .claim_attributions import propose
        return propose(source, self.maker, applications=[payment.pk], allocations=self.rows(payment) if rows is None else rows,
            evidence_reference="Reconciled invoice and payment schedule", reason="Identify invoices in consolidated credit",
            expected_version=expected_version)

    def test_independent_approval_claim_csv_and_payable_controls_preserve_journals(self):
        import csv
        import io
        from django.urls import reverse
        from .claim_attributions import review, current, serial_snapshot, eligible_claims
        from .models import PostingMapping
        from .payables import claim_rows
        from reporting.datasets import PostedPayableScheduleDataset

        source, payment = self.legacy()
        before = serial_snapshot(source, [payment.pk])
        proposal = self.proposal(source, payment)
        with self.assertRaisesMessage(ValidationError, "different authorized reviewer"):
            review(proposal, self.maker, approve=True, note="Own approval")
        self.assertIsNone(current(source))
        self.client.force_login(self.poster)
        page = self.client.get(reverse("accounting:claim_attribution", args=[source.pk]))
        self.assertContains(page, "SPLIT-01")
        self.assertContains(page, "600.00")
        self.assertContains(page, "240.00")
        response = self.client.post(reverse("accounting:claim_attribution_review",
            args=[source.pk, proposal.public_id, "approve"]), {"note": "Checked each invoice and all prior payments"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(current(source).pk, proposal.pk)
        self.assertEqual(serial_snapshot(source, [payment.pk]), before)
        rows = claim_rows(self.department.pk, date(2026, 9, 5))
        self.assertEqual([(row["recognized"], row["outstanding"]) for row in rows],
            [(Decimal("600"), Decimal("360")), (Decimal("400"), Decimal("240"))])
        earlier = claim_rows(self.department.pk, date(2026, 9, 3))
        self.assertEqual([row["outstanding"] for row in earlier], [Decimal("600"), Decimal("400")])
        self.assertFalse(eligible_claims(self.department.pk).filter(pk=source.pk).exists())
        PostingMapping.objects.create(**self.owner, category=PostingMapping.PAYABLE, source_code="*",
            label="Payable control", account=self.accounts["payable"])
        payload = PostedPayableScheduleDataset().payload(self.department, date(2026, 9, 1), date(2026, 9, 5), {})
        self.assertEqual(payload.control_status, "reconciled")
        self.assertEqual(payload.control_totals["subsidiary_balance"], Decimal("600"))
        self.assertEqual(payload.control_totals["source_line_count"], 2)
        self.assertEqual(payload.control_totals["allocation_row_count"], 4)
        self.assertEqual(len(payload.sources), 4)
        self.assertEqual({item["source_pk"] for item in payload.sources}, {str(source.pk), str(payment.pk)})
        self.assertEqual(sum(item["amount"] for item in payload.sources), Decimal("600"))
        self.assertEqual({item["snapshot"]["source_snapshot"]["claim_slice"] for item in payload.sources},
            {row["key"] for row in self.rows(payment)})
        self.client.force_login(self.poster)
        response = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": "2026-09-05"})
        self.assertEqual(response.status_code, 200)
        csv_rows = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual([(row["recognized"], row["outstanding"]) for row in csv_rows], [("600.00", "360.00"), ("400.00", "240.00")])
        from pathlib import Path
        self.assertEqual((Path(self.temp) / response["X-GRAND-Export-Relative-Path"]).read_bytes(), response.content)

    def test_successor_retains_original_decision_and_rejects_stale_or_tampered_rows(self):
        from .claim_attributions import review, current, verify, allocation_rows
        from .models import PayableClaimSlice, PayableClaimAttribution

        source, payment = self.legacy()
        first = review(self.proposal(source, payment), self.poster, approve=True, note="First schedule")
        changed = self.rows(payment)
        changed[0]["claim_reference"] = "CORRECTED-01"
        successor = self.proposal(source, payment, rows=changed, expected_version=first.version)
        stale = self.proposal(source, payment, expected_version=first.version)
        review(successor, self.poster, approve=True, note="Checked corrected invoice reference")
        self.assertEqual(allocation_rows(verify(first))[0]["claim_reference"], "SPLIT-01")
        self.assertEqual(allocation_rows(current(source))[0]["claim_reference"], "CORRECTED-01")
        with self.assertRaisesMessage(ValidationError, "stale proposal"):
            review(stale, self.poster, approve=True, note="Must not replace the successor")
        review(stale, self.poster, approve=False, note="Prepare against the current schedule")
        member = PayableClaimSlice.objects.get(attribution=successor, claim_reference="CORRECTED-01")
        member.recognized = Decimal("700")
        with self.assertRaisesMessage(ValidationError, "Retain invoice allocations"):
            member.save()
        PayableClaimSlice.objects.filter(pk=member.pk).update(recognized=Decimal("700"))
        with self.assertRaisesMessage(ValidationError, "retained proposal"):
            current(source)
        first.refresh_from_db()
        self.assertEqual(first.status, PayableClaimAttribution.APPROVED)
        verify(first)

    def test_native_recognition_cannot_duplicate_approved_split_invoice(self):
        from .claim_attributions import review
        from .services import submit_entry, post_entry
        source, payment = self.legacy()
        review(self.proposal(source, payment), self.poster, approve=True, note="Checked")
        duplicate = self.entry("DUPLICATE-SPLIT", Decimal("600"), claim="split-01")
        submit_entry(duplicate, self.maker)
        with self.assertRaisesMessage(ValidationError, "already recognized"):
            post_entry(duplicate, self.poster)
        other = self.entry("OTHER-INVOICE", Decimal("50"), claim="different")
        submit_entry(other, self.maker)
        post_entry(other, self.poster)

    def test_approval_rechecks_duplicate_identity_and_proposed_allocation_digest(self):
        from .claim_attributions import review, current
        from .models import PayableClaimSlice
        source, payment = self.legacy()
        proposal = self.proposal(source, payment)
        self.post(self.entry("RECOGNIZED-FIRST", Decimal("600"), claim="SPLIT-01"))
        with self.assertRaisesMessage(ValidationError, "already recognized"):
            review(proposal, self.poster, approve=True, note="No duplicate recognition")
        self.assertIsNone(current(source))
        rows = self.rows(payment)
        rows[0]["claim_reference"] = "DISTINCT"
        proposal = self.proposal(source, payment, rows=rows)
        member = proposal.invoice_slices.get(claim_reference="DISTINCT")
        PayableClaimSlice.objects.filter(pk=member.pk).update(claim_reference="CHANGED-AFTER-PROPOSAL")
        with self.assertRaisesMessage(ValidationError, "retained proposal"):
            review(proposal, self.poster, approve=True, note="Must match the submitted schedule")
        self.assertIsNone(current(source))

    def test_split_cannot_relabel_named_or_reserved_whole_claim(self):
        import uuid
        from .claim_attributions import propose, review, current
        from .payables import _reserve_claim
        source, payment = self.legacy()
        first = propose(source, self.maker, party_key="supplier-001", claim_reference="WHOLE",
            applications=[payment.pk], evidence_reference="Whole schedule", reason="Whole claim", expected_version=0)
        review(first, self.poster, approve=True, note="Confirmed")
        _reserve_claim(source_id=source.pk, case_public_id=uuid.uuid4(), key="retained-before-split",
            amount=Decimal("100"), actor_id=self.poster.pk, department_id=self.department.pk,
            fund_code=self.fund.code, party_key="supplier-001", as_of=date(2026, 9, 5))
        proposed = self.proposal(source, payment, expected_version=first.version)
        with self.assertRaisesMessage(ValidationError, "cannot be relabelled"):
            review(proposed, self.poster, approve=True, note="Must preserve the old hold")
        self.assertEqual(current(source).pk, first.pk)
        native = self.entry("NAMED-CREDIT", Decimal("1000"), claim="NAMED")
        self.post(native)
        with self.assertRaisesMessage(ValidationError, "do not split a named claim"):
            self.proposal(native.lines.get(sequence=2), payment)
