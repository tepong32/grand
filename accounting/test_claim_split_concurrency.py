from decimal import Decimal
from unittest import skipUnless

from django.db import connections
from django.test import TransactionTestCase

from . import test_claim_attribution_concurrency, test_claim_splits
from .models import JournalEntry, PayableClaimAttributionHead
from .services import submit_entry, post_entry


@skipUnless(connections["finance"].vendor == "mysql", "Requires native MySQL row locks")
class HistoricalClaimSplitConcurrencyTests(TransactionTestCase):
    databases = {"default", "finance"}
    setUp = test_claim_splits.HistoricalClaimSplitReviewTests.setUp
    entry = test_claim_splits.HistoricalClaimSplitReviewTests.entry
    post = test_claim_splits.HistoricalClaimSplitReviewTests.post
    legacy = test_claim_splits.HistoricalClaimSplitReviewTests.legacy
    detail = test_claim_splits.HistoricalClaimSplitReviewTests.detail
    rows = test_claim_splits.HistoricalClaimSplitReviewTests.rows
    proposal = test_claim_splits.HistoricalClaimSplitReviewTests.proposal
    race = test_claim_attribution_concurrency.ClaimAttributionConcurrencyTests.race
    approve = test_claim_attribution_concurrency.ClaimAttributionConcurrencyTests.approve

    def test_split_approval_and_native_recognition_share_invoice_identity_lock(self):
        source, payment = self.legacy()
        proposal = self.proposal(source, payment)
        native = self.entry("NEW-SPLIT-RECOGNITION", Decimal("600"), claim="SPLIT-01")
        submit_entry(native, self.maker)
        results = self.race([lambda actor: self.approve(proposal.pk, actor),
            lambda actor: post_entry(JournalEntry.objects.get(pk=native.pk), actor)])
        self.assertTrue(any("already recognized" in result for result in results), results)
        self.assertEqual(PayableClaimAttributionHead.objects.count()
            + JournalEntry.objects.filter(pk=native.pk, status=JournalEntry.POSTED).count(), 1)

    def test_two_split_approvals_cannot_allocate_the_same_historical_payment(self):
        source, payment = self.legacy()
        other = self.entry("OTHER-SPLIT-CREDIT", Decimal("1000"))
        other_source = other.lines.get(sequence=2)
        other_source.payable_party_key = other_source.payable_claim_reference = ""
        other_source.save()
        self.post(other)
        rows = self.rows(payment)
        rows[0]["claim_reference"] = "OTHER-01"
        rows[1]["claim_reference"] = "OTHER-02"
        first, second = self.proposal(source, payment), self.proposal(other_source, payment, rows=rows)
        results = self.race([lambda actor: self.approve(first.pk, actor), lambda actor: self.approve(second.pk, actor)])
        self.assertTrue(any("already belongs" in result for result in results), results)
        self.assertEqual(PayableClaimAttributionHead.objects.count(), 1)

    def test_two_applications_cannot_spend_the_same_invoice_capacity(self):
        from .claim_attributions import review
        from .test_claim_split_applications import InvoiceApplicationTests
        source, payment = self.legacy()
        record = review(self.proposal(source, payment), self.poster, approve=True, note="Reconciled invoices")
        key = str(record.invoice_slices.order_by("key").first().key)
        first = InvoiceApplicationTests.application(self, source, "FIRST-INVOICE-PAYMENT", {key: "250"})
        second = InvoiceApplicationTests.application(self, source, "SECOND-INVOICE-PAYMENT", {key: "250"})
        for entry in (first, second):
            submit_entry(entry, self.maker)
        results = self.race([lambda actor: post_entry(JournalEntry.objects.get(pk=first.pk), actor),
            lambda actor: post_entry(JournalEntry.objects.get(pk=second.pk), actor)])
        self.assertTrue(any("dated capacity" in result for result in results), results)
        self.assertEqual(JournalEntry.objects.filter(pk__in=[first.pk, second.pk], status=JournalEntry.POSTED).count(), 1)

    def test_invoice_amendment_and_posting_cannot_retain_incompatible_shares(self):
        from .claim_attributions import review
        from .test_claim_split_applications import InvoiceApplicationTests
        source, payment = self.legacy()
        record = review(self.proposal(source, payment), self.poster, approve=True, note="Original invoice schedule")
        key = str(record.invoice_slices.order_by("key").first().key)
        changed = self.rows(payment)
        changed[0]["claim_reference"] = "CORRECTED-INVOICE"
        amendment = self.proposal(source, payment, rows=changed, expected_version=record.version)
        entry = InvoiceApplicationTests.application(self, source, "RETAINED-INVOICE-APPLICATION", {key: "100"})
        submit_entry(entry, self.maker)
        # Pending applications already retain their selected identity; an
        # amendment cannot invalidate them while posting checks the source lock.
        results = self.race([lambda actor: self.approve(amendment.pk, actor),
            lambda actor: post_entry(JournalEntry.objects.get(pk=entry.pk), actor)])
        self.assertTrue(any("already used" in result for result in results), results)

    def test_invoice_reservation_and_journal_payment_cannot_overcommit(self):
        import uuid
        from datetime import date
        from .claim_attributions import review
        from .payables import _reserve_claim
        from .test_claim_split_applications import InvoiceApplicationTests
        source, payment = self.legacy()
        record = review(self.proposal(source, payment), self.poster, approve=True, note="Invoice capacity")
        key = str(record.invoice_slices.order_by("key").first().key)
        entry = InvoiceApplicationTests.application(self, source, "INVOICE-RESERVATION-RACE", {key: "250"})
        submit_entry(entry, self.maker)
        results = self.race([lambda actor: _reserve_claim(source_id=source.pk, invoice_key=key,
            case_public_id=uuid.uuid4(), key="invoice-hold-race", amount="250", actor_id=actor.pk,
            department_id=self.department.pk, fund_code=self.fund.code, party_key="supplier-001", as_of=date(2026, 9, 5)),
            lambda actor: post_entry(JournalEntry.objects.get(pk=entry.pk), actor)])
        self.assertTrue(any("already applied or reserved" in result for result in results), results)

    def test_two_reservations_cannot_spend_the_same_invoice_capacity(self):
        import uuid
        from datetime import date
        from .claim_attributions import review
        from .payables import _reserve_claim
        source, payment = self.legacy()
        record = review(self.proposal(source, payment), self.poster, approve=True, note="Invoice capacity")
        key = str(record.invoice_slices.order_by("key").first().key)

        def reserve(actor):
            return _reserve_claim(source_id=source.pk, invoice_key=key, case_public_id=uuid.uuid4(), key=str(uuid.uuid4()),
                amount="250", actor_id=actor.pk, department_id=self.department.pk, fund_code=self.fund.code,
                party_key="supplier-001", as_of=date(2026, 9, 5))

        results = self.race([reserve, reserve])
        self.assertTrue(any("already applied or reserved" in result for result in results), results)
