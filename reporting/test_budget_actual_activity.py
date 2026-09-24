from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import JournalEntry, JournalLine, LedgerAccount, ResponsibilityCenter
from accounting.services import create_reversal, post_entry, submit_entry
from . import test_finance_reporting as fixtures
from .datasets import BudgetVersusPostedActualDataset
from .models import ReportDefinition
from .services import create_manual_run


class BudgetActualActivityTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(fixtures.FinanceAccountabilityReportingTests.setUpTestData.__func__)
    employee = classmethod(fixtures.FinanceAccountabilityReportingTests.employee.__func__)

    def setUp(self):
        owner = {"department_id": self.accounting.pk, "department_label": self.accounting.name}
        self.center = ResponsibilityCenter.objects.create(
            **owner, code="GSO", name="General Services Office",
            office_id=self.requesting.pk, office_code=self.requesting.slug,
        )
        self.expense = LedgerAccount.objects.create(
            **owner, code="5-02-03", title="Office operations", account_type="expense", normal_balance="debit",
        )
        self.equity = LedgerAccount.objects.create(
            **owner, code="E-ACTUAL", title="Accumulated surplus", account_type="equity", normal_balance="credit",
        )
        for actor, permission in ((self.accounting_preparer, "prepare_journal_entries"),
                                  (self.accounting_reviewer, "post_journal_entries")):
            actor.user_permissions.add(Permission.objects.get(
                content_type__app_label="accounting", codename=permission,
            ))

    def journal(self, reference, amount, *, source_type="adjustment", when=date(2027, 3, 1),
                closing=False, account=None, posted=True):
        entry = JournalEntry.objects.create(
            department_id=self.accounting.pk, department_label=self.accounting.name,
            reference=reference, entry_date=when, period=self.period, fund=self.fund,
            source_type=source_type, description="Synthetic expense; the word closing does not classify it",
            created_by_id=self.accounting_preparer.pk, created_by_label=self.accounting_preparer.username,
        )
        expense = account or self.expense
        JournalLine.objects.create(
            entry=entry, sequence=1, account=expense, responsibility_center=self.center,
            debit=Decimal("0") if closing else Decimal(amount),
            credit=Decimal(amount) if closing else Decimal("0"),
        )
        JournalLine.objects.create(
            entry=entry, sequence=2, account=self.equity,
            debit=Decimal(amount) if closing else Decimal("0"),
            credit=Decimal("0") if closing else Decimal(amount),
        )
        if posted:
            submit_entry(entry, self.accounting_preparer)
            entry = post_entry(entry, self.accounting_reviewer)
        return entry

    def reverse(self, entry, reference, when=date(2027, 3, 31)):
        reversal = create_reversal(
            entry, self.accounting_preparer, reference=reference, entry_date=when,
            period=self.period, reason="Synthetic exact correction with retained original",
        )
        submit_entry(reversal, self.accounting_preparer)
        return post_entry(reversal, self.accounting_reviewer)

    def payload(self, end=date(2027, 3, 31)):
        return BudgetVersusPostedActualDataset().payload(self.budget, date(2027, 1, 1), end, {})

    def report(self):
        definition = ReportDefinition.objects.get(department=self.budget, dataset_key="finance_budget_vs_posted_actual")
        return create_manual_run(definition, definition.current_template, "xlsx",
                                 date(2027, 1, 1), date(2027, 3, 31), {}, self.budget_preparer)

    def test_closing_and_its_reversal_chain_preserve_activity_and_retained_outputs(self):
        original = self.journal("ACTUAL-20000", "20000")
        before = self.report()
        original_bytes = Path(before.output_file.path).read_bytes()
        original_snapshot = before.dataset_snapshot
        closing = self.journal("ACTUAL-CLOSE", "20000", source_type=JournalEntry.CLOSING,
                               when=date(2027, 3, 31), closing=True)
        closed = self.report()
        self.assertEqual(closed.control_totals["posted_actual"], "20000.00")
        self.assertEqual(closed.control_totals["mapped_actual"], "20000.00")
        self.assertEqual(closed.control_totals["excluded_expense_entry_count"], 1)
        source = closed.source_records.get(source_public_id=closing.public_id)
        self.assertEqual(source.amount, Decimal("0.00"))
        self.assertEqual(source.snapshot["excluded_expense_movement"], "-20000.00")
        self.assertEqual(source.snapshot["statement_origin_public_id"], str(closing.public_id))
        self.assertFalse(source.snapshot["expense_activity_included"])
        self.assertEqual(closed.control_status, "reconciled")
        self.assertEqual(closed.control_totals["posted_expense_ledger_movement"], "0.00")
        from openpyxl import load_workbook
        with closed.output_file.open("rb") as stream:
            workbook_rows = list(load_workbook(stream, data_only=True).active.values)
        header = next(row for row in workbook_rows if "Posted actual expense" in row)
        amount_column = header.index("Posted actual expense")
        self.assertTrue(any("5-02-03" in row and row[amount_column] == 20000 for row in workbook_rows))

        reopened = self.reverse(closing, "ACTUAL-REOPEN")
        reclosed = self.reverse(reopened, "ACTUAL-RECLOSE")
        after = self.report()
        self.assertEqual(after.control_totals["posted_actual"], "20000.00")
        self.assertEqual(after.control_totals["excluded_expense_entry_count"], 3)
        self.assertEqual(after.control_totals["excluded_expense_movement"], "-20000.00")
        for entry in (closing, reopened, reclosed):
            evidence = after.source_records.get(source_public_id=entry.public_id)
            self.assertEqual(evidence.snapshot["statement_source_type"], "closing")
            self.assertEqual(evidence.snapshot["statement_origin_public_id"], str(closing.public_id))
        # Ordinary expense corrections remain period activity; closing history cannot mask them.
        self.reverse(original, "ACTUAL-CORRECTION")
        corrected = self.report()
        self.assertEqual(corrected.control_totals["posted_actual"], "0.00")
        self.assertEqual(corrected.control_totals["excluded_expense_entry_count"], 3)
        before.refresh_from_db()
        self.assertEqual(before.dataset_snapshot, original_snapshot)
        self.assertEqual(Path(before.output_file.path).read_bytes(), original_bytes)
        self.assertEqual(JournalEntry.objects.get(pk=original.pk).status, JournalEntry.POSTED)

    def test_zero_activity_and_only_excluded_sources_are_valid_without_false_mapping_errors(self):
        empty = self.payload()
        self.assertEqual(empty.control_totals["posted_actual"], Decimal("0.00"))
        self.assertEqual(empty.control_status, "reconciled")
        self.assertIn("No posted", empty.rows[0]["mapping_status"])
        unmatched = LedgerAccount.objects.create(
            department_id=self.accounting.pk, department_label=self.accounting.name,
            code="EXCLUDED-ONLY", title="Historical expense", account_type="expense", normal_balance="debit",
        )
        opening = self.journal("ACTUAL-OPEN", "800", source_type="opening", account=unmatched)
        result = self.payload()
        self.assertEqual(result.control_totals["posted_actual"], Decimal("0.00"))
        self.assertEqual(result.control_totals["mapping_exception_count"], 0)
        self.assertEqual(result.control_totals["excluded_expense_entry_count"], 1)
        self.assertTrue(any(source["source_public_id"] == str(opening.public_id) for source in result.sources))

    def test_dated_corrections_drafts_and_explicit_legacy_purposes_remain_distinct(self):
        original = self.journal("ACTUAL-DATED", "200")
        self.reverse(original, "ACTUAL-LATER-CORRECTION", when=date(2027, 3, 20))
        self.journal("ACTUAL-DRAFT", "999", posted=False)
        self.journal("ACTUAL-FUTURE", "75", when=date(2027, 3, 25))
        legacy = self.journal("ACTUAL-LEGACY-EQUITY", "30", posted=False)
        # Explicit retained legacy purpose; current posting controls disallow expense lines
        # in direct-equity journals. Reading history must not relabel that purpose.
        JournalEntry.objects.filter(pk=legacy.pk).update(source_type=JournalEntry.PRIOR_ERROR, status=JournalEntry.POSTED)
        early = self.payload(date(2027, 3, 10))
        self.assertEqual(early.control_totals["posted_actual"], Decimal("200.00"))
        self.assertEqual(early.control_totals["excluded_expense_entry_count"], 1)
        late = self.payload()
        self.assertEqual(late.control_totals["posted_actual"], Decimal("75.00"))
        self.assertEqual(late.control_totals["excluded_expense_entry_count"], 1)

    def test_invalid_retained_reversal_lineage_fails_closed(self):
        original = self.journal("ACTUAL-LINEAGE", "200")
        reversal = self.reverse(original, "ACTUAL-LINEAGE-REV")
        JournalEntry.objects.filter(pk=original.pk).update(reversal_of_id=reversal.pk)
        with self.assertRaisesMessage(ValidationError, "cycle"):
            self.payload()
        JournalEntry.objects.filter(pk=original.pk).update(reversal_of_id=None, department_id=self.budget.pk)
        with self.assertRaisesMessage(ValidationError, "owning office"):
            self.payload()
