from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from . import test_payable_claims
from .claim_attributions import propose, review, current, serial_snapshot
from .models import JournalEntry, JournalLine, JournalSubsidiaryLine, PostingMapping, PayableClaimAttribution, PayableClaimAttributionHead
from .payables import claim_rows, _capacity
from .services import create_reversal, subsidiary_schedule_rows


class ClaimAttributionTests(TestCase):
    databases = {"default", "finance"}
    setUp = test_payable_claims.PayableClaimTests.setUp
    entry = test_payable_claims.PayableClaimTests.entry
    post = test_payable_claims.PayableClaimTests.post

    def legacy(self, *, payment_amount="400", legacy_detail=True):
        original = self.entry("HISTORICAL", Decimal("1000"))
        source = original.lines.get(sequence=2)
        source.payable_party_key = source.payable_claim_reference = ""
        source.save()
        if legacy_detail:
            self.detail(source)
        self.post(original)
        payment = self.entry("OLD-PAYMENT", Decimal(payment_amount), source=source, day=4)
        applied = payment.lines.get(sequence=1)
        applied.payable_origin = None
        applied.save()
        if legacy_detail:
            self.detail(applied)
        self.post(payment)
        return source, applied

    def detail(self, line):
        return JournalSubsidiaryLine.objects.create(entry=line.entry, journal_line=line,
            category=JournalSubsidiaryLine.PAYABLE, reference_key="legacy-vendor", reference_label="Old vendor label",
            source_code="legacy", source_reference=line.entry.reference, debit=line.debit, credit=line.credit)

    def proposal(self, source, applications, **kwargs):
        args = {"party_key": "supplier-001", "claim_reference": "HIST-001",
            "applications": [line.pk for line in applications], "evidence_reference": "Reviewed old invoice/payment schedule",
            "reason": "Identify the original invoice and all its prior applications", "expected_version": 0}
        args.update(kwargs)
        return propose(source, self.maker, **args)

    def test_old_payee_projection_new_application_and_reversal_preserve_sources(self):
        source, applied = self.legacy()
        old_snapshot = serial_snapshot(source, [applied.pk])
        record = self.proposal(source, [applied])
        with self.assertRaisesMessage(ValidationError, "different authorized reviewer"):
            review(record, self.maker, approve=True, note="Own approval")
        review(record, self.poster, approve=True, note="Reconciled source credit and payment")
        self.assertEqual(JournalEntry.objects.count(), 2)
        self.assertEqual(serial_snapshot(source, [applied.pk]), old_snapshot)
        self.assertEqual(claim_rows(self.department.pk, date(2026, 9, 3))[0]["outstanding"], Decimal("1000"))
        row = claim_rows(self.department.pk, date(2026, 9, 5))[0]
        self.assertEqual((row["claim_reference"], row["party_key"], row["outstanding"]), ("HIST-001", "supplier-001", Decimal("600")))
        PostingMapping.objects.create(**self.owner, category=PostingMapping.PAYABLE, source_code="*",
            label="Payable control", account=self.accounts["payable"])
        from reporting.datasets import PostedPayableScheduleDataset
        payload = PostedPayableScheduleDataset().payload(self.department, date(2026, 9, 1), date(2026, 9, 5), {})
        self.assertEqual(payload.control_status, "reconciled")
        self.assertEqual(payload.control_totals["subsidiary_balance"], Decimal("600"))
        self.assertEqual({row["reference_key"] for row in payload.rows}, {"supplier-001"})
        self.assertTrue(all(item["snapshot"]["source_snapshot"]["claim_attribution"]["version"] == 1 for item in payload.sources))
        self.post(self.entry("NEW-PAYMENT", Decimal("200"), source=source, day=5))
        undo = create_reversal(applied.entry, self.maker, reference="OLD-RETURN", entry_date=date(2026, 9, 6),
            period=self.period, reason="Actual return of historical payment")
        self.post(undo)
        self.assertEqual(undo.lines.get(sequence=1).payable_origin_id, source.pk)
        self.assertEqual(claim_rows(self.department.pk, date(2026, 9, 6))[0]["outstanding"], Decimal("800"))
        self.assertEqual(sum(row["balance"] for row in subsidiary_schedule_rows(self.department.pk,
            JournalSubsidiaryLine.PAYABLE, date(2026, 9, 6))), Decimal("800"))
        self.assertEqual(serial_snapshot(source, [applied.pk]), old_snapshot)
        with self.assertRaisesMessage(ValidationError, "later financial reversal"):
            replacement = self.proposal(source, [], expected_version=1)
            review(replacement, self.poster, approve=True, note="Cannot detach the returned application")

    def test_reviewed_successor_changes_metadata_without_rewriting_old_output(self):
        source, applied = self.legacy(legacy_detail=False)
        record = review(self.proposal(source, [applied]), self.poster, approve=True, note="Confirmed")
        self.client.force_login(self.poster)
        url = reverse("accounting:payable_claim_export")
        first = self.client.get(url, {"as_of": "2026-09-05"})
        self.assertEqual(first.status_code, 200)
        retained_path = Path(self.temp) / first["X-GRAND-Export-Relative-Path"]
        retained = retained_path.read_bytes()
        self.assertIn(b"HIST-001", retained)
        corrected = self.proposal(source, [applied], expected_version=1, claim_reference="HIST-CORRECTED",
            reason="Correct a transposed invoice reference from the retained invoice")
        review(corrected, self.poster, approve=True, note="Checked exact invoice identity")
        record.refresh_from_db()
        self.assertEqual(record.claim_reference, "HIST-001")
        self.assertEqual(current(source).claim_reference, "HIST-CORRECTED")
        second = self.client.get(url, {"as_of": "2026-09-05"})
        self.assertIn(b"HIST-CORRECTED", second.content)
        self.assertNotEqual(first["X-GRAND-Export-Relative-Path"], second["X-GRAND-Export-Relative-Path"])
        self.assertEqual(retained_path.read_bytes(), retained)
        self.assertFalse(JournalSubsidiaryLine.objects.exists())
        self.assertEqual(_capacity(source), Decimal("600"))
        PayableClaimAttribution.objects.filter(pk=corrected.pk).update(reason="Tampered approval evidence")
        with self.assertRaisesMessage(ValidationError, "no longer reproduces"):
            _capacity(source)

    def test_overapplication_duplicate_identity_and_stale_review_are_rejected(self):
        source, applied = self.legacy(payment_amount="1200")
        record = self.proposal(source, [applied])
        with self.assertRaisesMessage(ValidationError, "dated capacity"):
            review(record, self.poster, approve=True, note="Overapplied source")
        self.assertFalse(PayableClaimAttributionHead.objects.exists())
        record.refresh_from_db()
        self.assertEqual(record.status, record.SUBMITTED)
        self.post(self.entry("NAMED", Decimal("1000"), claim="HIST-001"))
        candidate = self.proposal(source, [])
        with self.assertRaisesMessage(ValidationError, "already recognized"):
            review(candidate, self.poster, approve=True, note="Duplicate invoice")
        first = self.proposal(source, [], claim_reference="OTHER")
        stale = self.proposal(source, [], claim_reference="OTHER")
        review(first, self.poster, approve=True, note="An independent unconsumed claim")
        with self.assertRaisesMessage(ValidationError, "approved first"):
            review(stale, self.poster, approve=True, note="Stale proposal")
        with self.assertRaisesMessage(ValidationError, "already recognized"):
            self.post(self.entry("DUPLICATE-NATIVE", Decimal("1000"), claim="other"))

    def test_existing_reversal_must_be_resolved_and_retained(self):
        source, applied = self.legacy()
        undo = create_reversal(applied.entry, self.maker, reference="OLD-UNDO", entry_date=date(2026, 9, 6),
            period=self.period, reason="Historical payment reversal")
        with self.assertRaisesMessage(ValidationError, "outstanding reversal draft"):
            self.proposal(source, [applied])
        self.post(undo)
        with self.assertRaisesMessage(ValidationError, "Include every exact posted reversal"):
            self.proposal(source, [applied])
        credit = undo.lines.get(sequence=1)
        review(self.proposal(source, [applied, credit]), self.poster, approve=True, note="Original payment and exact reversal checked")
        self.assertEqual(_capacity(source), Decimal("1000"))
        # A financial reversal prepared after attribution uses the original claim.
        next_undo = create_reversal(undo, self.maker, reference="UNDO-UNDO", entry_date=date(2026, 9, 7),
            period=self.period, reason="Restore the original payment")
        self.post(next_undo)
        self.assertEqual(_capacity(source), Decimal("600"))
