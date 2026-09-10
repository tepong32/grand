import hashlib
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from openpyxl import load_workbook

from accounting.models import AccountingPeriod, FiscalYear, Fund, JournalEntry, JournalLine, LedgerAccount, PostingMapping
from accounting.services import submit_entry, post_entry, create_reversal
from departments.models import Department
from .models import FinanceStatementMapping, FinanceStatementLine, ReportDefinition, ReportRun
from .presets import seed_finance_presets
from .services import create_manual_run
from .statement_services import submit_statement_mapping, review_statement_mapping


class CashFlowReportingTests(TestCase):
    databases = {"default", "finance"}

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="grand-cash-flow-tests-")
        settings_override = override_settings(MEDIA_ROOT=self.media)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media, True)
        self.department = Department.objects.create(name="Municipal Accounting Office", slug="cashflow-accounting")
        self.owner = {"department_id": self.department.pk, "department_label": self.department.name}
        actors = []
        for name, permissions in (("maker", ("prepare_journal_entries", "view_reporting_workspace", "generate_reports", "manage_report_definitions")),
                                  ("checker", ("post_journal_entries", "view_reporting_workspace", "approve_reports", "review_reports"))):
            actor = get_user_model().objects.create_user(username=f"cashflow.{name}",
                email=f"cashflow.{name}@example.test", password="Synthetic-cashflow")
            actor.employeeprofile.assigned_department = self.department
            actor.employeeprofile.save(update_fields=("assigned_department",))
            actor.user_permissions.add(*Permission.objects.filter(codename__in=permissions,
                content_type__app_label__in=("accounting", "reporting")))
            actors.append(actor)
        self.maker, self.checker = actors
        self.department.deptHead_or_oic = self.checker
        self.department.save(update_fields=("deptHead_or_oic",))
        self.periods = {}
        for year in (2026, 2027):
            fiscal = FiscalYear.objects.create(**self.owner, year=year, label=f"FY {year}",
                starts_on=date(year, 1, 1), ends_on=date(year, 12, 31), business_date=date(year, 3, 31), status=FiscalYear.ACTIVE)
            self.periods[year] = AccountingPeriod.objects.create(**self.owner, fiscal_year=year,
                fiscal_year_record=fiscal, period_number=1, label="First quarter",
                starts_on=date(year, 1, 1), ends_on=date(year, 3, 31))
        self.fund = Fund.objects.create(**self.owner, code="GF", name="General Fund")
        self.accounts = {}
        for code, kind in (("cash", "asset"), ("cash2", "asset"), ("ppe", "asset"), ("depreciation", "asset"),
                           ("equity", "equity"), ("revenue", "revenue"), ("expense", "expense"),
                           ("payable", "liability"), ("loan", "liability")):
            self.accounts[code] = LedgerAccount.objects.create(**self.owner, code=code, title=code,
                account_type=kind, normal_balance="debit" if kind in ("asset", "expense") else "credit")
        for code in ("cash", "cash2"):
            PostingMapping.objects.create(**self.owner, category=PostingMapping.BANK,
                source_code=code, label=code, account=self.accounts[code])
        seed_finance_presets()
        mapping = FinanceStatementMapping.objects.create(department=self.department,
            statement_type=FinanceStatementMapping.CASH_FLOW, version=1, title="Synthetic cash scope",
            authority_reference="Synthetic reviewed cash inventory", local_acceptance_note="Both synthetic cash accounts checked",
            created_by=self.maker)
        FinanceStatementLine.objects.create(mapping=mapping, position=1, section_code="cash",
            section_title="Cash and cash equivalents", line_code="cash", line_title="Cash accounts",
            selector_type=FinanceStatementLine.ACCOUNT_CODES, account_codes=["cash", "cash2"])
        submit_statement_mapping(mapping, self.maker)
        review_statement_mapping(mapping, self.checker, approve=True, note="Synthetic independent scope check")
        self.post("OPEN-2026", [("cash", 400, 0, ""), ("equity", 0, 400, "")], year=2026, opening=True)

    def post(self, reference, lines, *, year=2027, opening=False):
        entry = JournalEntry.objects.create(**self.owner, reference=reference, fund=self.fund,
            entry_date=date(year, 1, 1) if opening else date(year, 3, 1), period=self.periods[year],
            source_type="opening" if opening else "manual", description="Synthetic cash-flow transaction",
            created_by_id=self.maker.pk, created_by_label=self.maker.username)
        for sequence, (account, debit, credit, purpose) in enumerate(lines, 1):
            JournalLine.objects.create(entry=entry, sequence=sequence, account=self.accounts[account],
                debit=Decimal(debit), credit=Decimal(credit), cash_flow_category=purpose)
        submit_entry(entry, self.maker)
        return post_entry(entry, self.checker)

    def report(self):
        definition = ReportDefinition.objects.get(department=self.department, dataset_key="finance_statement_cash_flow")
        return create_manual_run(definition, definition.current_template, "xlsx", date(2027, 1, 1),
            date(2027, 3, 31), {}, self.maker)

    def test_direct_cash_flow_exports_mixed_repayment_transfers_accrual_and_reversal(self):
        self.post("TAX-RECEIPT", [("cash", 1000, 0, "op_taxes"), ("revenue", 0, 1000, "")])
        self.post("ASSET-ACCRUAL", [("ppe", 600, 0, ""), ("payable", 0, 600, "")])
        payment = self.post("ASSET-PAYMENT", [("payable", 200, 0, ""), ("cash", 0, 200, "inv_assets")])
        self.post("BORROWING", [("cash", 500, 0, "fin_borrowings"), ("loan", 0, 500, "")])
        self.post("MIXED-REPAYMENT", [("loan", 80, 0, ""), ("expense", 10, 0, ""),
            ("cash", 0, 80, "fin_principal"), ("cash", 0, 10, "op_interest_out")])
        self.post("INTERNAL-TRANSFER", [("cash2", 150, 0, "internal"), ("cash", 0, 150, "internal")])
        self.post("DEPRECIATION", [("expense", 30, 0, ""), ("depreciation", 0, 30, "")])
        self.post("EXCHANGE", [("cash", 5, 0, "exchange"), ("revenue", 0, 5, "")])
        run = self.report()
        self.assertEqual(run.control_status, ReportRun.CONTROL_RECONCILED)
        controls = run.control_totals["funds"]["GF"]["current"]
        self.assertEqual((controls["opening_cash"], controls["net_cash_flows"], controls["closing_cash"]),
            ("400.00", "1210.00", "1615.00"))
        workbook = load_workbook(run.output_file.path, data_only=True)
        rows = list(workbook.active.values)
        self.assertTrue(any("operating_net" in row and 990 in row for row in rows))
        self.assertTrue(any("closing" in row and 1615 in row and 400 in row for row in rows))
        workbook.close()
        old_bytes = Path(run.output_file.path).read_bytes()
        reversal = create_reversal(payment, self.maker, reference="RETURN-ASSET-PAYMENT",
            entry_date=date(2027, 3, 20), period=self.periods[2027], reason="Synthetic bank return")
        submit_entry(reversal, self.maker)
        post_entry(reversal, self.checker)
        self.assertEqual(reversal.lines.get(account=self.accounts["cash"]).cash_flow_category, "inv_assets")
        corrected = self.report()
        self.assertEqual(corrected.control_totals["funds"]["GF"]["current"]["closing_cash"], "1815.00")
        self.assertEqual(corrected.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertEqual(Path(run.output_file.path).read_bytes(), old_bytes)
        self.assertEqual(hashlib.sha256(old_bytes).hexdigest(), run.checksum)

    def test_unclassified_cash_requires_actual_reversal_and_classified_replacement(self):
        entry = self.post("UNCLASSIFIED", [("cash", 50, 0, ""), ("revenue", 0, 50, "")])
        self.assertEqual(self.report().control_status, ReportRun.CONTROL_EXCEPTION)
        reversal = create_reversal(entry, self.maker, reference="REVERSE-UNCLASSIFIED",
            entry_date=date(2027, 3, 20), period=self.periods[2027], reason="Synthetic purpose correction")
        submit_entry(reversal, self.maker)
        post_entry(reversal, self.checker)
        self.post("CLASSIFIED", [("cash", 50, 0, "op_other_in"), ("revenue", 0, 50, "")])
        self.assertEqual(self.report().control_status, ReportRun.CONTROL_RECONCILED)

    def test_internal_label_cannot_hide_external_receipt(self):
        self.post("NOT-INTERNAL", [("cash", 30, 0, "internal"), ("revenue", 0, 30, "")])
        run = self.report()
        self.assertEqual(run.control_status, ReportRun.CONTROL_EXCEPTION)
        self.assertEqual(run.control_totals["funds"]["GF"]["current"]["invalid_internal_transfers"], ["NOT-INTERNAL"])
