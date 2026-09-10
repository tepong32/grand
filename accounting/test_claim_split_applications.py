import csv
import io
from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from . import test_claim_splits
from .claim_attributions import review, serial_snapshot, current
from .claim_splits import bind_allocation
from .models import JournalEntry, PostingMapping
from .payables import claim_rows
from .services import create_reversal, submit_entry, post_entry


class InvoiceApplicationTests(TestCase):
    databases = {"default", "finance"}
    setUp = test_claim_splits.HistoricalClaimSplitReviewTests.setUp
    entry = test_claim_splits.HistoricalClaimSplitReviewTests.entry
    post = test_claim_splits.HistoricalClaimSplitReviewTests.post
    legacy = test_claim_splits.HistoricalClaimSplitReviewTests.legacy
    detail = test_claim_splits.HistoricalClaimSplitReviewTests.detail
    rows = test_claim_splits.HistoricalClaimSplitReviewTests.rows
    proposal = test_claim_splits.HistoricalClaimSplitReviewTests.proposal

    def approved(self):
        source, payment = self.legacy()
        record = review(self.proposal(source, payment), self.poster, approve=True, note="Checked invoice schedule")
        return source, payment, record

    def application(self, source, reference, shares, *, day=5):
        entry = self.entry(reference, sum((Decimal(value) for value in shares.values()), Decimal("0.00")), source=source, day=day)
        line = entry.lines.get(sequence=1)
        line.payable_allocation = bind_allocation(source, shares)
        line.save()
        return entry

    def balances(self, day):
        return [row["outstanding"] for row in claim_rows(self.department.pk, date(2026, 9, day))]

    def test_http_invoice_application_historical_and_native_returns_and_outputs(self):
        source, old_payment, record = self.approved()
        before = serial_snapshot(source, [old_payment.pk])
        first = record.invoice_slices.order_by("key").first()
        draft = self.entry("INVOICE-PAYMENT", Decimal("300"), source=source, day=5)
        draft.lines.get(sequence=1).delete()
        self.client.force_login(self.maker)
        response = self.client.post(reverse("accounting:line_create", args=[draft.public_id]), {
            "sequence": 1, "account": source.account_id, "debit": "300", "credit": "0",
            "payable_invoice": first.pk, "memo": "Payment of first invoice"})
        self.assertEqual(response.status_code, 302)
        posted = self.post(draft)
        line = posted.lines.get(sequence=1)
        self.assertEqual(line.payable_origin_id, source.pk)
        self.assertEqual(line.payable_allocation["shares"], {str(first.key): "300.00"})
        self.assertEqual(self.balances(5), [Decimal("60"), Decimal("240")])
        old_return = create_reversal(old_payment.entry, self.maker, reference="OLD-INVOICE-RETURN",
            entry_date=date(2026, 9, 6), period=self.period, reason="Historical payment returned")
        self.post(old_return)
        self.assertEqual(old_return.lines.count(), old_payment.entry.lines.count())
        returned_line = old_return.lines.get(sequence=old_payment.sequence)
        self.assertEqual(list(returned_line.payable_allocation["shares"].values()), ["240.00", "160.00"])
        self.assertEqual(self.balances(6), [Decimal("300"), Decimal("400")])
        native_return = create_reversal(posted, self.maker, reference="NEW-INVOICE-RETURN",
            entry_date=date(2026, 9, 7), period=self.period, reason="New payment returned")
        self.assertEqual(native_return.lines.get(sequence=1).payable_allocation, line.payable_allocation)
        self.post(native_return)
        self.assertEqual(self.balances(7), [Decimal("600"), Decimal("400")])
        self.assertEqual(serial_snapshot(source, [old_payment.pk]), before)
        PostingMapping.objects.create(**self.owner, category=PostingMapping.PAYABLE, source_code="*",
            label="Payable control", account=self.accounts["payable"])
        from reporting.datasets import PostedPayableScheduleDataset
        payload = PostedPayableScheduleDataset().payload(self.department, date(2026, 9, 1), date(2026, 9, 7), {})
        self.assertEqual(payload.control_status, "reconciled")
        self.assertEqual(payload.control_totals["subsidiary_balance"], Decimal("1000"))
        self.assertEqual(sum(item["amount"] for item in payload.sources), Decimal("1000"))
        self.assertEqual(payload.control_totals["source_line_count"], 5)
        self.client.force_login(self.poster)
        response = self.client.get(reverse("accounting:payable_claim_export"), {"as_of": "2026-09-07"})
        exported = list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual([row["outstanding"] for row in exported], ["600.00", "400.00"])

    def test_parent_balance_cannot_cover_invoice_shortfall_or_earlier_date(self):
        source, payment, record = self.approved()
        key = str(record.invoice_slices.order_by("key").first().key)
        excess = self.application(source, "INVOICE-EXCESS", {key: "400"})
        submit_entry(excess, self.maker)
        with self.assertRaisesMessage(ValidationError, "SPLIT-01 exceeds its dated capacity"):
            post_entry(excess, self.poster)
        reversal = create_reversal(payment.entry, self.maker, reference="LATER-INVOICE-RETURN",
            entry_date=date(2026, 9, 8), period=self.period, reason="Actual later return")
        self.post(reversal)
        with self.assertRaisesMessage(ValidationError, "2026-09-05"):
            post_entry(excess, self.poster)
        self.post(self.application(source, "LATER-INVOICE-PAYMENT", {key: "400"}, day=9))
        self.assertEqual(self.balances(9), [Decimal("200"), Decimal("400")])

    def test_balanced_return_cannot_reassign_original_invoice_shares(self):
        source, payment, record = self.approved()
        keys = [str(item.key) for item in record.invoice_slices.order_by("key")]
        self.post(self.application(source, "ADDITIONAL-INVOICE-PAYMENT", dict.fromkeys(keys, "100")))
        reversal = create_reversal(payment.entry, self.maker, reference="WRONG-INVOICE-RETURN",
            entry_date=date(2026, 9, 6), period=self.period, reason="Return old payment")
        line = reversal.lines.get(sequence=payment.sequence)
        line.payable_allocation["shares"] = dict.fromkeys(keys, "200.00")
        with self.assertRaisesMessage(ValidationError, "Generated journal lines cannot be edited"):
            line.save()
        # Bypass the editor guard only in this test to exercise posting defenses.
        type(line).objects.filter(pk=line.pk).update(payable_allocation=line.payable_allocation)
        with self.assertRaisesMessage(ValidationError, "original invoice shares"):
            submit_entry(reversal, self.maker)
        reversal.refresh_from_db()
        self.assertEqual(reversal.status, JournalEntry.DRAFT)

    def test_used_allocation_cannot_be_changed_and_unqualified_application_fails(self):
        source, payment, record = self.approved()
        key = str(record.invoice_slices.order_by("key").first().key)
        self.post(self.application(source, "RETAINED-INVOICE-PAYMENT", {key: "100"}))
        changed = self.rows(payment)
        changed[0]["claim_reference"] = "RELABELED"
        successor = self.proposal(source, payment, rows=changed, expected_version=record.version)
        with self.assertRaisesMessage(ValidationError, "already used"):
            review(successor, self.poster, approve=True, note="Cannot relabel used invoice")
        self.assertEqual(current(source).pk, record.pk)
        bare = self.entry("UNQUALIFIED-INVOICE-PAYMENT", Decimal("10"), source=source, day=5)
        with self.assertRaisesMessage(ValidationError, "approved invoice allocation evidence"):
            submit_entry(bare, self.maker)
        native = self.application(source, "TAMPERED-INVOICE-PAYMENT", {key: "10"})
        line = native.lines.get(sequence=1)
        line.payable_allocation = deepcopy(line.payable_allocation)
        line.payable_allocation["shares"][key] = "9.00"
        line.save()
        with self.assertRaisesMessage(ValidationError, "financial line amount exactly"):
            submit_entry(native, self.maker)

    def test_original_credit_can_be_reversed_only_after_applications_are_restored(self):
        source, payment, record = self.approved()
        reverse_source = create_reversal(source.entry, self.maker, reference="CANCEL-SPLIT-CREDIT",
            entry_date=date(2026, 9, 7), period=self.period, reason="Cancel original recognition")
        submit_entry(reverse_source, self.maker)
        with self.assertRaises(ValidationError):
            post_entry(reverse_source, self.poster)
        old_return = create_reversal(payment.entry, self.maker, reference="RESTORE-OLD-PAYMENT",
            entry_date=date(2026, 9, 6), period=self.period, reason="Restore payment before cancellation")
        self.post(old_return)
        post_entry(reverse_source, self.poster)
        self.assertEqual(self.balances(7), [Decimal("0"), Decimal("0")])

    def test_posted_invoice_shares_must_reproduce_independent_posting_evidence(self):
        source, payment, record = self.approved()
        keys = [str(item.key) for item in record.invoice_slices.order_by("key")]
        posted = self.post(self.application(source, "SEALED-INVOICE-PAYMENT", dict.fromkeys(keys, "100")))
        line = posted.lines.get(sequence=1)
        evidence = deepcopy(line.payable_allocation)
        evidence["shares"] = {keys[0]: "120.00", keys[1]: "80.00"}
        type(line).objects.filter(pk=line.pk).update(payable_allocation=evidence)
        with self.assertRaisesMessage(ValidationError, "independent posting evidence"):
            self.balances(5)

    def test_recovered_invoice_hold_rechecks_invoice_capacity_on_requested_date(self):
        import uuid
        from .payables import _reserve_claim, _capacity
        source, payment, record = self.approved()
        key = str(record.invoice_slices.order_by("key").first().key)
        restored = create_reversal(payment.entry, self.maker, reference="RESTORED-BEFORE-HOLD",
            entry_date=date(2026, 9, 8), period=self.period, reason="Actual later payment return")
        self.post(restored)
        args = dict(source_id=source.pk, invoice_key=key, case_public_id=uuid.uuid4(), key="recover-invoice-hold",
            amount="400", actor_id=self.poster.pk, department_id=self.department.pk,
            fund_code=self.fund.code, party_key="supplier-001")
        held = _reserve_claim(**args, as_of=date(2026, 9, 8))
        with self.assertRaisesMessage(ValidationError, "retained claim reservation cannot fit"):
            _reserve_claim(**args, as_of=date(2026, 9, 5))
        self.assertEqual(_reserve_claim(**args, as_of=date(2026, 9, 8)).pk, held.pk)
        self.assertEqual(_capacity(source, invoice_key=key), Decimal("200"))
