from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounting.models import AccountingPeriod, FiscalYear, Fund, JournalEntry, JournalLine, LedgerAccount, ResponsibilityCenter
from budget.models import AppropriationAuthorization, AuthorizedAppropriationLine, BudgetCall, BudgetVersion
from departments.models import Department
from . import test_budget_actual_activity as activity
from .datasets import BudgetVersusPostedActualDataset


class BudgetActualOwnershipTests(TestCase):
    databases = {"default", "finance"}
    setUpTestData = classmethod(activity.BudgetActualActivityTests.setUpTestData.__func__)
    employee = classmethod(activity.BudgetActualActivityTests.employee.__func__)
    setUp = activity.BudgetActualActivityTests.setUp
    journal = activity.BudgetActualActivityTests.journal
    payload = activity.BudgetActualActivityTests.payload
    report = activity.BudgetActualActivityTests.report

    def other_ledger(self):
        department = Department.objects.create(name="Regional Accounting Office", slug="other-accounting")
        owner = {"department_id": department.pk, "department_label": department.name}
        year = FiscalYear.objects.create(**owner, year=2027, label="Other FY 2027",
            starts_on=date(2027, 1, 1), ends_on=date(2027, 12, 31), business_date=date(2027, 3, 31))
        period = AccountingPeriod.objects.create(**owner, fiscal_year=2027, fiscal_year_record=year,
            period_number=1, label="Q1", starts_on=year.starts_on, ends_on=date(2027, 3, 31))
        fund = Fund.objects.create(**owner, code="GF", name="Other General Fund")
        account = LedgerAccount.objects.create(**owner, code="5-02-03", title="Other expense",
            account_type="expense", normal_balance="debit")
        contra = LedgerAccount.objects.create(**owner, code="E-OTHER", title="Other equity",
            account_type="equity", normal_balance="credit")
        center = ResponsibilityCenter.objects.create(**owner, code="GSO", name="Other office")
        entry = JournalEntry.objects.create(**owner, period=period, fund=fund, reference="OTHER-900",
            entry_date=date(2027, 3, 1), source_type="adjustment", description="Synthetic separate ledger",
            created_by_id=self.accounting_preparer.pk, created_by_label="Synthetic retained actor")
        JournalLine.objects.create(entry=entry, sequence=1, account=account, responsibility_center=center,
            debit=Decimal("900"))
        JournalLine.objects.create(entry=entry, sequence=2, account=contra, credit=Decimal("900"))
        # Synthetic retained history, not a bypass in a production posting service.
        JournalEntry.objects.filter(pk=entry.pk).update(status=JournalEntry.POSTED)
        return department, year, entry

    def add_authority(self, year):
        owner = {"department_id": self.budget.pk, "department_label": self.budget.name}
        call = BudgetCall.objects.create(**owner, fiscal_year=year, title="Other explicit ledger",
            authority_reference="Synthetic call", instructions="Retained separate source",
            proposal_opens_on=date(2026, 8, 1), proposal_due_on=date(2026, 9, 30),
            created_by_id=self.budget_preparer.pk, created_by_label=self.budget_preparer.username)
        version = BudgetVersion.objects.create(**owner, fiscal_year=year, budget_call=call,
            kind=BudgetVersion.FINAL, title="Other authorized budget", change_explanation="Separate ledger",
            created_by_id=self.budget_preparer.pk, created_by_label=self.budget_preparer.username)
        authorization = AppropriationAuthorization.objects.create(**owner, version=version,
            ordinance_number="OTHER-ORD", ordinance_date=date(2026, 12, 15), effectivity_date=date(2027, 1, 1),
            signed_control_total=Decimal("1000"), created_by_id=self.budget_preparer.pk,
            created_by_label=self.budget_preparer.username)
        line = AuthorizedAppropriationLine.objects.create(**owner, authorization=authorization,
            source_line_id=123456, fund_code="GF", responsibility_center_code="GSO", account_code="5-02-03",
            expense_class="MOOE", appropriation_type="new", particulars="Other expense", amount=Decimal("1000"))
        AppropriationAuthorization.objects.filter(pk=authorization.pk).update(status=AppropriationAuthorization.AUTHORIZED)
        BudgetVersion.objects.filter(pk=version.pk).update(status=BudgetVersion.AUTHORIZED)
        return line

    def test_renamed_owner_uses_explicit_source_and_retains_scope_in_generated_evidence(self):
        self.journal("OWNER-200", "200")
        Department.objects.filter(pk=self.accounting.pk).update(name="Financial Records Unit", slug="records-unit")
        result = self.report()
        self.assertEqual(result.control_totals["posted_actual"], "200.00")
        self.assertEqual(result.control_status, "reconciled")
        self.assertEqual(result.control_totals["accounting_department_count"], 1)
        scope = result.control_totals["accounting_scopes"][0]
        self.assertEqual(scope["department_id"], self.accounting.pk)
        self.assertEqual(scope["fiscal_year_id"], self.fiscal_year.pk)
        source = result.source_records.get(source_model="AuthorizedAppropriationLine")
        self.assertEqual(source.snapshot["accounting_scope"], scope)

    def test_unrelated_named_accounting_ledger_never_blocks_or_supplies_budget_actuals(self):
        original = self.journal("OWNER-200", "200")
        _, _, foreign = self.other_ledger()
        result = self.payload()
        self.assertEqual(result.control_status, "reconciled")
        self.assertEqual(result.control_totals["posted_actual"], Decimal("200"))
        journal_ids = {item["source_pk"] for item in result.sources if item["source_model"] == "JournalEntry"}
        self.assertEqual(journal_ids, {str(original.pk)})
        self.assertNotIn(str(foreign.pk), journal_ids)

    def test_two_explicit_ledgers_with_identical_codes_are_mapped_separately(self):
        self.journal("OWNER-200", "200")
        other, year, _ = self.other_ledger()
        self.add_authority(year)
        result = self.payload()
        self.assertEqual(result.control_status, "reconciled")
        self.assertEqual(result.control_totals["posted_actual"], Decimal("1100"))
        self.assertEqual(result.control_totals["mapped_actual"], Decimal("1100"))
        self.assertEqual(result.control_totals["accounting_department_count"], 2)
        rows = {row["accounting_department_id"]: row for row in result.rows}
        self.assertEqual(rows[self.accounting.pk]["posted_actual"], Decimal("200"))
        self.assertEqual(rows[other.pk]["posted_actual"], Decimal("900"))
        self.assertIn(str(other.pk), rows[other.pk]["mapping_status"])
        generated = self.report()
        from openpyxl import load_workbook
        with generated.output_file.open("rb") as stream:
            workbook_rows = list(load_workbook(stream, data_only=True).active.values)
        header = next(row for row in workbook_rows if "Posted actual expense" in row)
        status_column = header.index("Actual mapping status")
        amount_column = header.index("Posted actual expense")
        self.assertTrue(any(row[amount_column] == 900 and f"ledger {other.pk}" in str(row[status_column])
                            for row in workbook_rows))
        self.assertTrue(any(row[amount_column] == 200 and f"ledger {self.accounting.pk}" in str(row[status_column])
                            for row in workbook_rows))

    def test_no_authority_does_not_guess_an_accounting_ledger(self):
        self.journal("OWNER-200", "200")
        AppropriationAuthorization.objects.filter(pk=self.appropriation_line.authorization_id).update(
            effectivity_date=date(2028, 1, 1))
        result = self.payload()
        self.assertEqual(result.control_status, "exception")
        self.assertEqual(result.control_totals["posted_actual"], Decimal("0"))
        self.assertEqual(result.control_totals["accounting_department_count"], 0)
        self.assertFalse(any(item["source_model"] == "JournalEntry" for item in result.sources))

    def test_inconsistent_budget_authority_ownership_is_rejected(self):
        foreign, _, _ = self.other_ledger()
        AppropriationAuthorization.objects.filter(pk=self.appropriation_line.authorization_id).update(
            department_id=foreign.pk)
        with self.assertRaisesMessage(ValidationError, "Budget authority"):
            self.payload()

    def test_selected_journal_cannot_use_a_foreign_classification_or_typed_year(self):
        entry = self.journal("OWNER-200", "200")
        _, year, foreign = self.other_ledger()
        JournalLine.objects.filter(entry=entry, sequence=1).update(account_id=foreign.lines.get(sequence=1).account_id)
        with self.assertRaisesMessage(ValidationError, "Accounting source"):
            self.payload()
        JournalLine.objects.filter(entry=entry, sequence=1).update(account_id=self.expense.pk)
        AccountingPeriod.objects.filter(pk=self.period.pk).update(fiscal_year_record_id=year.pk)
        with self.assertRaisesMessage(ValidationError, "Accounting source"):
            self.payload()

    def test_each_owner_is_selected_only_for_its_own_authorized_years(self):
        self.journal("OWNER-200", "200")
        other, year, entry = self.other_ledger()
        FiscalYear.objects.filter(pk=year.pk).update(year=2026, starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31), business_date=date(2026, 3, 31))
        year.refresh_from_db()
        AccountingPeriod.objects.filter(pk=entry.period_id).update(fiscal_year=2026,
            starts_on=date(2026, 1, 1), ends_on=date(2026, 3, 31))
        JournalEntry.objects.filter(pk=entry.pk).update(entry_date=date(2026, 3, 1))
        authority_line = self.add_authority(year)
        AppropriationAuthorization.objects.filter(pk=authority_line.authorization_id).update(
            ordinance_date=date(2025, 12, 15), effectivity_date=date(2026, 1, 1))
        # A valid separate 2027 posting in this ledger has no selected 2027 authority.
        owner = {"department_id": other.pk, "department_label": other.name}
        period = AccountingPeriod.objects.create(**owner, fiscal_year=2027, period_number=1,
            label="Unselected year", starts_on=date(2027, 1, 1), ends_on=date(2027, 3, 31))
        extra = JournalEntry.objects.create(**owner, period=period, fund=entry.fund,
            reference="UNSELECTED-777", entry_date=date(2027, 3, 1), source_type="adjustment",
            description="Synthetic unselected owner/year pair", created_by_id=self.accounting_preparer.pk,
            created_by_label="Synthetic retained actor")
        original_lines = list(entry.lines.order_by("sequence"))
        JournalLine.objects.create(entry=extra, sequence=1, account=original_lines[0].account,
            responsibility_center=original_lines[0].responsibility_center, debit=Decimal("777"))
        JournalLine.objects.create(entry=extra, sequence=2, account=original_lines[1].account, credit=Decimal("777"))
        JournalEntry.objects.filter(pk=extra.pk).update(status=JournalEntry.POSTED)
        result = BudgetVersusPostedActualDataset().payload(self.budget, date(2026, 1, 1), date(2027, 3, 31), {})
        self.assertEqual(result.control_status, "reconciled")
        self.assertEqual(result.control_totals["posted_actual"], Decimal("1100"))
        self.assertFalse(any(source["source_pk"] == str(extra.pk) and source["source_model"] == "JournalEntry"
                             for source in result.sources))

    def test_legacy_period_without_typed_link_keeps_explicit_owner_and_year(self):
        self.journal("OWNER-200", "200")
        AccountingPeriod.objects.filter(pk=self.period.pk).update(fiscal_year_record_id=None)
        result = self.payload()
        self.assertEqual(result.control_status, "reconciled")
        self.assertEqual(result.control_totals["posted_actual"], Decimal("200"))
        self.assertIsNone(AccountingPeriod.objects.get(pk=self.period.pk).fiscal_year_record_id)

    def test_missing_explicit_owner_does_not_fall_back_to_named_accounting_office(self):
        self.journal("OWNER-200", "200")
        FiscalYear.objects.filter(pk=self.fiscal_year.pk).update(department_id=9999999)
        with self.assertRaisesMessage(ValidationError, "Accounting owner"):
            self.payload()
