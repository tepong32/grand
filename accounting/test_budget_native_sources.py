"""Source capture must retain missing attribution without certifying expenditure."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from . import budget_native_sources as sources
from . import test_budget_actuals as fixtures
from .models import Fund, JournalEntry, JournalLine, JournalSubsidiaryLine
from .services import create_reversal, submit_entry, post_entry


class NativeBudgetSourceTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.BudgetActualAdoptionTests.setUpTestData.__func__)
    employee = classmethod(fixtures.BudgetActualAdoptionTests.employee.__func__)
    setUp = fixtures.BudgetActualAdoptionTests.setUp
    make_call = fixtures.BudgetActualAdoptionTests.make_call
    make_version = fixtures.BudgetActualAdoptionTests.make_version
    add_line = fixtures.BudgetActualAdoptionTests.add_line
    add_ceiling = fixtures.BudgetActualAdoptionTests.add_ceiling
    grant = fixtures.BudgetActualAdoptionTests.grant
    journal = fixtures.BudgetActualAdoptionTests.journal

    def capture(self, **changes):
        args = dict(actor=self.maker, fund_id=self.fund.pk,
                    period_start=date(2026, 1, 1), period_end=date(2026, 6, 30))
        args.update(changes)
        return sources.capture(**args)

    def test_one_finance_read_retains_unassigned_and_all_sides(self):
        entry = self.journal("SOURCE", date(2026, 6, 30), Decimal("200"))
        # Reproduce the legacy omission; never an application repair of posted rows.
        JournalLine.objects.filter(entry=entry).update(responsibility_center=None)
        with CaptureQueriesContext(connections["finance"]) as queries:
            result = self.capture()
        self.assertEqual(len(queries), 1)
        self.assertEqual(result["payload"]["controls"], {
            "journals": 1, "lines": 2, "debit": "200.00", "credit": "200.00",
            "unassigned_lines": 2, "unresolved_lineage": 0})
        row = result["payload"]["journals"][0]
        self.assertEqual(len(row["lines"]), 2)
        self.assertIsNone(row["lines"][0]["center"]["id"])
        self.assertEqual(row["source_type"], "manual")
        self.assertNotIn("certified_total", result["payload"])
        self.assertEqual(sources.verify(result), result["payload"])
        self.assertEqual(self.capture()["checksum"], result["checksum"])
        result["captured_at"] = "changed"
        with self.assertRaises(ValidationError):
            sources.verify(result)

    def test_empty_scope_and_foreign_scope(self):
        result = self.capture()
        self.assertEqual(result["payload"]["journals"], [])
        self.assertEqual(result["payload"]["controls"]["journals"], 0)
        foreign = Fund.objects.create(department_id=self.budget_office.pk,
            department_label="Other ledger", code="FOREIGN", name="Other")
        with self.assertRaises(PermissionDenied):
            self.capture(fund_id=foreign.pk)
        with self.assertRaises(PermissionDenied):
            self.capture(actor=self.preparer)
        with self.assertRaises(ValidationError):
            self.capture(period_start=date(2026, 7, 1))

    def test_backdated_post_changes_fingerprint_without_rewriting_capture(self):
        captured = self.capture()
        frozen = deepcopy(captured)
        self.journal("BACKDATED", date(2026, 6, 30), Decimal("30"))
        self.assertFalse(sources.is_current(captured, self.maker))
        self.assertEqual(captured, frozen)
        self.assertTrue(sources.is_current(self.capture(), self.maker))
        tampered = deepcopy(captured)
        tampered["payload"]["controls"]["debit"] = "30.00"
        with self.assertRaises(ValidationError):
            sources.verify(tampered)

    def test_out_of_period_origin_is_evidence_not_period_activity(self):
        original = self.journal("OLD-CLOSING", date(2025, 12, 31), Decimal("80"), JournalEntry.CLOSING)
        inside = self.journal("IN-PERIOD", date(2026, 6, 30), Decimal("20"))
        reversal = create_reversal(original, self.maker, reference="REOPEN",
            period=inside.period, entry_date=date(2026, 6, 30), reason="Synthetic reopening")
        submit_entry(reversal, self.maker)
        post_entry(reversal, self.checker)
        captured = self.capture()
        payload = captured["payload"]
        self.assertEqual(payload["controls"]["debit"], "100.00")
        self.assertEqual([item["id"] for item in payload["lineage_sources"]], [original.pk])
        link = next(item for item in payload["journals"] if item["id"] == reversal.pk)["lineage"]
        self.assertEqual(link["origin_id"], original.pk)
        self.assertTrue(link["exact_mirror"])
        self.assertEqual(link["origin_source_type"], JournalEntry.CLOSING)
        self.journal("UNRELATED-PAST", date(2025, 12, 31), Decimal("900"))
        self.assertTrue(sources.is_current(captured, self.maker))

    def test_nonmirrored_or_cyclic_lineage_is_unresolved(self):
        original = self.journal("ORIGIN", date(2026, 6, 30), Decimal("10"))
        claimed = self.journal("WRONG-LINK", date(2026, 6, 30), Decimal("20"))
        JournalEntry.objects.filter(pk=claimed.pk).update(reversal_of=original)
        result = self.capture()["payload"]
        self.assertEqual(result["controls"]["unresolved_lineage"], 1)
        self.assertEqual(result["journals"][1]["lineage"]["issue"], "non_mirrored_reversal")
        JournalEntry.objects.filter(pk=original.pk).update(reversal_of=claimed)
        result = self.capture()["payload"]
        self.assertEqual(result["controls"]["unresolved_lineage"], 2)

    def test_current_account_metadata_and_source_evidence_change_fingerprint(self):
        entry = self.journal("METADATA", date(2026, 6, 30), Decimal("50"))
        captured = self.capture()
        JournalEntry.objects.filter(pk=entry.pk).update(source_snapshot={"explicit_purpose": "synthetic"})
        self.assertFalse(sources.is_current(captured, self.maker))
        captured = self.capture()
        # Direct update represents a changed setup observed after capture.
        type(self.account).objects.filter(pk=self.account.pk).update(title="Changed title")
        self.assertFalse(sources.is_current(captured, self.maker))

    def test_subsidiary_evidence_is_detached_and_does_not_multiply_lines(self):
        entry = self.journal("SUBSIDIARY", date(2026, 6, 30), Decimal("100"))
        line = entry.lines.get(sequence=1)
        JournalSubsidiaryLine.objects.create(entry=entry, journal_line=line, category="advance",
            reference_key="synthetic-officer", reference_label="Synthetic officer",
            source_code="synthetic", source_reference="SYN-SOURCE", debit=100,
            source_snapshot={"original_source": "retained-reference"})
        result = self.capture()
        captured_line = result["payload"]["journals"][0]["lines"][0]
        self.assertEqual(result["payload"]["controls"]["lines"], 2)
        self.assertEqual(captured_line["subsidiary"]["source_snapshot"],
                         {"original_source": "retained-reference"})
        captured_line["subsidiary"]["source_snapshot"]["original_source"] = "altered copy"
        self.assertEqual(JournalSubsidiaryLine.objects.get(journal_line=line).source_snapshot,
                         {"original_source": "retained-reference"})
        with self.assertRaises(ValidationError):
            sources.verify(result)

