from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from . import budget_attributions as service
from . import test_budget_attributions as fixtures
from .models import JournalEntry, JournalLine, BudgetExpenditureAttribution as Attribution
from .services import create_reversal, submit_entry, post_entry


class BudgetAttributionReversalTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.BudgetAttributionTests.setUpTestData.__func__)
    employee = classmethod(fixtures.BudgetAttributionTests.employee.__func__)
    setUp = fixtures.BudgetAttributionTests.setUp
    make_call = fixtures.BudgetAttributionTests.make_call
    make_version = fixtures.BudgetAttributionTests.make_version
    add_line = fixtures.BudgetAttributionTests.add_line
    add_ceiling = fixtures.BudgetAttributionTests.add_ceiling
    grant = fixtures.BudgetAttributionTests.grant
    attribute_grant = fixtures.BudgetAttributionTests.attribute_grant
    journal = fixtures.BudgetAttributionTests.journal
    capture = fixtures.BudgetAttributionTests.capture
    rows = fixtures.BudgetAttributionTests.rows
    propose = fixtures.BudgetAttributionTests.propose
    review = fixtures.BudgetAttributionTests.review

    def reverse(self, entry, reference="REVERSAL"):
        reversal = create_reversal(entry, self.maker, reference=reference,
            period=self.entry.period, entry_date=date(2026, 6, 30), reason="Synthetic exact source correction")
        submit_entry(reversal, self.maker)
        return post_entry(reversal, self.checker)

    def submit_rows(self, entry, rows, latest=0):
        return self.propose(proposals=[dict(entry_id=entry.pk, expected_latest=latest, allocations=rows)])

    def test_exact_reviewed_reversal_and_changed_predecessor_preserve_old_capture(self):
        original = self.review(self.propose())[0]
        reversal = self.reverse(self.entry)
        rows = service.reversal_allocations(self.capture(), reversal.pk)
        included = next(row for row in rows if row["disposition"] == "include")
        self.assertEqual(included["signed_amount"], "-100.00")
        changed = deepcopy(rows)
        changed[0]["basis"] = "Rewrite the inherited basis"
        with self.assertRaises(ValidationError):
            self.submit_rows(reversal, changed)
        reversed_record = self.review(self.submit_rows(reversal, rows))[0]
        self.assertEqual(reversed_record.source_snapshot["reversal_attributions"][0]["attribution"]["public_id"], str(original.public_id))
        old = self.capture()
        old_checksum = reversed_record.source_checksum
        revised = self.rows()
        revised[0]["basis"] = "Corrected source evidence reference"
        self.review(self.submit_rows(self.entry, revised, latest=1))
        with self.assertRaises(ValidationError):
            service.reviewed_allocations(self.capture())
        self.assertEqual(len(service.reviewed_allocations(old)), 2)
        self.assertEqual(Attribution.objects.get(pk=reversed_record.pk).source_checksum, old_checksum)
        fresh_rows = service.reversal_allocations(self.capture(), reversal.pk)
        self.review(self.submit_rows(reversal, fresh_rows, latest=1))
        self.assertEqual(len(service.reviewed_allocations(self.capture())), 2)

    def test_outside_period_predecessor_is_captured_and_can_be_inherited(self):
        old = self.journal("OLD-ORIGINAL", date(2025, 12, 31), Decimal("100"))
        captured = self.capture(period_start=date(2025, 1, 1), period_end=date(2025, 12, 31))
        records = service.propose_batch(actor=self.maker, fund_id=self.fund.pk,
            period_start=date(2025, 1, 1), period_end=date(2025, 12, 31),
            expected_source_checksum=captured["checksum"],
            proposals=[dict(entry_id=old.pk, expected_latest=0, allocations=self.rows(old))],
            reason="Prior-period attribution", evidence_reference="SYN-OLD")
        self.review(records)
        reversal = self.reverse(old)
        current = self.capture()
        self.assertNotIn(old.pk, [entry["id"] for entry in current["payload"]["journals"]])
        rows = service.reversal_allocations(current, reversal.pk)
        self.review(self.submit_rows(reversal, rows))
        result = next(row for row in service.reviewed_allocations(self.capture()) if row["entry_id"] == reversal.pk)
        self.assertEqual(next(row["signed_amount"] for row in result["allocations"] if row["disposition"] == "include"), "-100.00")

    def test_reversing_a_reversal_retains_the_full_reviewed_chain(self):
        self.review(self.propose())
        first = self.reverse(self.entry, "FIRST-REVERSAL")
        self.review(self.submit_rows(first, service.reversal_allocations(self.capture(), first.pk)))
        second = self.reverse(first, "SECOND-REVERSAL")
        rows = service.reversal_allocations(self.capture(), second.pk)
        self.assertEqual(next(row["signed_amount"] for row in rows if row["disposition"] == "include"), "100.00")
        record = self.review(self.submit_rows(second, rows))[0]
        self.assertEqual(len(record.source_snapshot["reversal_attributions"]), 2)
        self.assertEqual(len(service.reviewed_allocations(self.capture())), 3)

    def test_duplicate_lines_require_bijective_explicit_pairing(self):
        parent = JournalEntry.objects.create(department_id=self.accounting_office.pk,
            department_label=self.accounting_office.name, period=self.entry.period, fund=self.fund,
            reference="DUPLICATE-LINES", entry_date=date(2026, 6, 30), description="Synthetic duplicate financial lines",
            created_by_id=self.maker.pk, created_by_label=self.maker.username)
        for sequence in (1, 2):
            JournalLine.objects.create(entry=parent, sequence=sequence, account=self.account,
                responsibility_center=self.center, debit=50)
        JournalLine.objects.create(entry=parent, sequence=3, account=self.offset, credit=100)
        submit_entry(parent, self.maker)
        post_entry(parent, self.checker)
        source_lines = list(parent.lines.order_by("sequence"))
        rows = [dict(self.rows()[0], line_id=line.pk, amount="50") for line in source_lines[:2]]
        rows.append(dict(self.rows()[1], line_id=source_lines[2].pk))
        self.review(self.submit_rows(parent, rows))
        reversal = self.reverse(parent)
        with self.assertRaises(ValidationError):
            service.reversal_allocations(self.capture(), reversal.pk)
        reverse_lines = list(reversal.lines.order_by("sequence"))
        pairs = {child.pk: original.pk for child, original in zip(reverse_lines, source_lines)}
        wrong = dict(pairs)
        wrong[reverse_lines[1].pk] = source_lines[0].pk
        with self.assertRaises(ValidationError):
            service.reversal_allocations(self.capture(), reversal.pk, pairs=wrong)
        inherited = service.reversal_allocations(self.capture(), reversal.pk, pairs=pairs)
        self.review(self.submit_rows(reversal, inherited))

    def test_predecessor_and_dependent_reversal_cannot_silently_rebase_one_batch(self):
        self.review(self.propose())
        reversal = self.reverse(self.entry)
        rows = service.reversal_allocations(self.capture(), reversal.pk)
        with self.assertRaises(ValidationError):
            self.propose(proposals=[dict(entry_id=self.entry.pk, expected_latest=1, allocations=self.rows()),
                                   dict(entry_id=reversal.pk, expected_latest=0, allocations=rows)])
        pending = self.submit_rows(reversal, rows)
        self.review(self.submit_rows(self.entry, self.rows(), latest=1))
        with self.assertRaises(ValidationError):
            self.review(pending)
        self.assertEqual(Attribution.objects.get(pk=pending[0].pk).status, Attribution.SUBMITTED)
