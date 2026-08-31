from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounting.models import (
    AccountingPeriod, FiscalYear, Fund, JournalEntry, JournalLine, JournalSubsidiaryLine,
    LedgerAccount, PostingMapping, ResponsibilityCenter,
)
from budget.models import (
    AllotmentMovement, AllotmentReleaseOrder, AppropriationAuthorization,
    AuthorizedAppropriationLine, BudgetCall, BudgetVersion, ObligationMovement,
    ObligationRequest,
)
from departments.models import Department
from vouchers.models import (
    BankAdviceBatch, BankAdviceItem, DisbursementVoucher, PaymentInstrument, VoucherCase,
)

from .datasets import build_dataset_with_evidence
from .models import (
    FinanceStatementLine, FinanceStatementMapping, ReportDefinition, ReportRun,
    ReportTemplateVersion,
)
from .presets import seed_finance_presets
from .services import create_manual_run, transition_run
from .statement_services import review_statement_mapping, submit_statement_mapping


FINANCE_REPORT_MEDIA_ROOT = tempfile.mkdtemp(prefix="grand-finance-report-tests-")


@override_settings(MEDIA_ROOT=FINANCE_REPORT_MEDIA_ROOT)
class FinanceAccountabilityReportingTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="f9-accounting")
        cls.budget = Department.objects.create(name="Municipal Budget Office", slug="f9-budget")
        cls.requesting = Department.objects.create(name="General Services Office", slug="f9-gso")
        cls.accounting_preparer = cls.employee(
            cls.accounting, "f9.accounting.preparer",
            "view_reporting_workspace", "generate_reports", "download_reports",
            "manage_report_definitions",
        )
        cls.accounting_reviewer = cls.employee(
            cls.accounting, "f9.accounting.reviewer",
            "view_reporting_workspace", "review_reports", "approve_reports",
            "download_reports", "view_department_reports",
        )
        cls.budget_preparer = cls.employee(
            cls.budget, "f9.budget.preparer",
            "view_reporting_workspace", "generate_reports", "download_reports",
        )
        cls.accounting.deptHead_or_oic = cls.accounting_reviewer
        cls.accounting.save(update_fields=("deptHead_or_oic",))
        cls.budget.deptHead_or_oic = cls.budget_preparer
        cls.budget.save(update_fields=("deptHead_or_oic",))

        owner = {"department_id": cls.accounting.pk, "department_label": cls.accounting.name}
        cls.fiscal_year = FiscalYear.objects.create(
            **owner, year=2027, label="FY 2027", starts_on=date(2027, 1, 1),
            ends_on=date(2027, 12, 31), business_date=date(2027, 3, 31),
            status=FiscalYear.ACTIVE,
        )
        cls.period = AccountingPeriod.objects.create(
            **owner, fiscal_year=2027, fiscal_year_record=cls.fiscal_year, period_number=1,
            label="First quarter", starts_on=date(2027, 1, 1), ends_on=date(2027, 3, 31),
        )
        cls.fund = Fund.objects.create(**owner, code="GF", name="General Fund")
        cls.cash = LedgerAccount.objects.create(
            **owner, code="10101010", title="Cash in bank", account_type="asset", normal_balance="debit",
        )
        cls.revenue = LedgerAccount.objects.create(
            **owner, code="40101010", title="Local revenue", account_type="revenue", normal_balance="credit",
        )
        cls.entry = JournalEntry.objects.create(
            **owner, reference="JEV-F9-0001", entry_date=date(2027, 1, 15), period=cls.period,
            fund=cls.fund, source_type="manual", description="Synthetic balanced accountability entry",
            status=JournalEntry.DRAFT, created_by_id=cls.accounting_preparer.pk,
            created_by_label=cls.accounting_preparer.username,
            posted_by_id=cls.accounting_reviewer.pk, posted_by_label=cls.accounting_reviewer.username,
            posted_at=timezone.now(),
        )
        JournalLine.objects.create(entry=cls.entry, sequence=1, account=cls.cash, debit=Decimal("1250.00"))
        JournalLine.objects.create(entry=cls.entry, sequence=2, account=cls.revenue, credit=Decimal("1250.00"))
        JournalEntry.objects.filter(pk=cls.entry.pk).update(status=JournalEntry.POSTED)
        cls.entry.refresh_from_db()

        call = BudgetCall.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            fiscal_year=cls.fiscal_year, title="FY 2027 Budget Call",
            authority_reference="Synthetic reviewed budget call", instructions="Synthetic instructions",
            proposal_opens_on=date(2026, 8, 1), proposal_due_on=date(2026, 9, 30),
            status=BudgetCall.PUBLISHED, created_by_id=cls.budget_preparer.pk,
            created_by_label=cls.budget_preparer.username,
        )
        version = BudgetVersion.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            budget_call=call, fiscal_year=cls.fiscal_year, kind=BudgetVersion.FINAL, version=1,
            title="FY 2027 Authorized Budget", change_explanation="Synthetic final authority",
            status=BudgetVersion.AUTHORIZED, created_by_id=cls.budget_preparer.pk,
            created_by_label=cls.budget_preparer.username,
        )
        authorization = AppropriationAuthorization.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name, version=version,
            authority_type=AppropriationAuthorization.ORDINANCE,
            ordinance_number="SYN-ORD-2027-001", ordinance_date=date(2026, 12, 15),
            effectivity_date=date(2027, 1, 1), review_status=AppropriationAuthorization.FAVORABLE,
            review_reference="Synthetic favorable review", review_date=date(2026, 12, 28),
            evidence_reference="Synthetic retained ordinance and schedule",
            signed_control_total=Decimal("100000.00"), status=AppropriationAuthorization.DRAFT,
            snapshot_checksum="a" * 64, created_by_id=cls.budget_preparer.pk,
            created_by_label=cls.budget_preparer.username,
        )
        cls.appropriation_line = AuthorizedAppropriationLine.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            authorization=authorization, source_line_id=9001, fund_code="GF",
            responsibility_center_code="GSO", program_code="GSO-OPS",
            funding_source_code="LOCAL", account_code="5-02-03",
            expense_class="MOOE", appropriation_type="new",
            particulars="Synthetic office operations", amount=Decimal("100000.00"),
        )
        AppropriationAuthorization.objects.filter(pk=authorization.pk).update(status=AppropriationAuthorization.AUTHORIZED)
        authorization.refresh_from_db()
        order = AllotmentReleaseOrder.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            authorization=authorization, fiscal_year=cls.fiscal_year,
            order_number="ARO-F9-0001", kind=AllotmentReleaseOrder.INITIAL,
            release_date=date(2027, 1, 5), effective_date=date(2027, 1, 5),
            authority_reference="Synthetic allotment authority",
            evidence_reference="Synthetic signed allotment schedule", purpose="Quarterly operations",
            signed_control_total=Decimal("80000.00"), status=AllotmentReleaseOrder.POSTED,
            snapshot_checksum="b" * 64, created_by_id=cls.budget_preparer.pk,
            created_by_label=cls.budget_preparer.username,
        )
        AllotmentMovement.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            order=order, source_line_id=8001, appropriation_line=cls.appropriation_line,
            movement_type="release", amount=Decimal("80000.00"),
            release_effect=Decimal("80000.00"), hold_effect=Decimal("0.00"),
            effective_date=date(2027, 1, 5), order_number_snapshot=order.order_number,
            authority_reference_snapshot=order.authority_reference,
        )
        obligation = ObligationRequest.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            authorization=authorization, fiscal_year=cls.fiscal_year,
            requesting_department_id=cls.requesting.pk, requesting_department_label=cls.requesting.name,
            kind=ObligationRequest.ORIGINAL, form_type=ObligationRequest.OBR,
            request_reference="REQ-F9-0001", obligation_number="OBR-F9-0001",
            obligation_date=date(2027, 2, 10), claimant_payee="Synthetic Supplier",
            particulars="Synthetic accountable obligation", evidence_reference="Synthetic retained support",
            signed_control_total=Decimal("50000.00"), status=ObligationRequest.CERTIFIED,
            snapshot_checksum="c" * 64, created_by_id=cls.budget_preparer.pk,
            created_by_label=cls.budget_preparer.username,
        )
        ObligationMovement.objects.create(
            department_id=cls.budget.pk, department_label=cls.budget.name,
            request=obligation, source_line_id=7001, appropriation_line=cls.appropriation_line,
            movement_type="obligate", amount=Decimal("50000.00"),
            obligation_effect=Decimal("50000.00"), effective_date=date(2027, 2, 10),
            obligation_number_snapshot=obligation.obligation_number,
            requesting_department_snapshot=cls.requesting.name,
            claimant_payee_snapshot=obligation.claimant_payee,
            particulars_snapshot=obligation.particulars,
        )
        seed_finance_presets()
        cls.accounting_definition = ReportDefinition.objects.get(
            department=cls.accounting, dataset_key="finance_posted_trial_balance",
        )
        cls.budget_definition = ReportDefinition.objects.get(
            department=cls.budget, dataset_key="finance_budget_accountability",
        )

    @classmethod
    def employee(cls, department, username, *permissions):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="finance-report-test",
        )
        user.employeeprofile.assigned_department = department
        user.employeeprofile.save(update_fields=("assigned_department",))
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="reporting", codename__in=permissions,
        ))
        return user

    def generate_accounting(self, actor=None):
        return create_manual_run(
            self.accounting_definition, self.accounting_definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, actor or self.accounting_preparer,
        )

    def test_trial_balance_run_pins_reconciled_controls_and_source_drillthrough(self):
        run = self.generate_accounting()
        self.assertEqual(run.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertTrue(run.control_gate_required)
        self.assertEqual(run.control_totals["debit"], "1250.00")
        self.assertEqual(run.control_totals["credit"], "1250.00")
        self.assertEqual(run.source_record_count, 1)
        self.assertEqual(len(run.dataset_checksum), 64)
        self.assertEqual(len(run.control_checksum), 64)
        self.assertEqual(len(run.reproduction_key), 64)
        source = run.source_records.get()
        self.assertEqual(source.source_reference, self.entry.reference)
        self.assertEqual(source.snapshot["debit"], "1250.00")
        self.assertEqual(source.snapshot["credit"], "1250.00")
        self.assertEqual(source.source_url, reverse("accounting:entry_detail", args=(self.entry.public_id,)))
        source.amount = Decimal("1.00")
        with self.assertRaisesMessage(ValidationError, "immutable"):
            source.save()

    def test_governed_statement_starters_generate_balanced_explained_statements(self):
        position_mapping = FinanceStatementMapping.objects.get(
            department=self.accounting, statement_type=FinanceStatementMapping.POSITION,
        )
        performance_mapping = FinanceStatementMapping.objects.get(
            department=self.accounting, statement_type=FinanceStatementMapping.PERFORMANCE,
        )
        self.assertEqual(position_mapping.status, FinanceStatementMapping.STARTER)
        self.assertEqual(performance_mapping.status, FinanceStatementMapping.STARTER)
        self.assertEqual(position_mapping.lines.count(), 3)
        self.assertEqual(performance_mapping.lines.count(), 2)

        position_definition = ReportDefinition.objects.get(
            department=self.accounting, dataset_key="finance_statement_position",
        )
        position = create_manual_run(
            position_definition, position_definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.accounting_preparer,
        )
        self.assertEqual(position.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertEqual(position.control_totals["assets"], "1250.00")
        self.assertEqual(position.control_totals["liabilities"], "0.00")
        self.assertEqual(position.control_totals["equity"], "0.00")
        self.assertEqual(position.control_totals["unclosed_operating_result"], "1250.00")
        self.assertEqual(position.control_totals["equation_difference"], "0.00")
        self.assertEqual(position.parameters["_statement_mapping_snapshot"]["version"], 1)
        self.assertEqual(position.parameters["_statement_mapping_checksum"], position_mapping.snapshot_checksum)
        self.assertEqual(position.source_records.get().source_reference, self.entry.reference)

        performance_definition = ReportDefinition.objects.get(
            department=self.accounting, dataset_key="finance_statement_performance",
        )
        performance = create_manual_run(
            performance_definition, performance_definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.accounting_preparer,
        )
        self.assertEqual(performance.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertEqual(performance.control_totals["revenue"], "1250.00")
        self.assertEqual(performance.control_totals["expense"], "0.00")
        self.assertEqual(performance.control_totals["operating_result"], "1250.00")
        self.client.force_login(self.accounting_preparer)
        detail = self.client.get(position_mapping.get_absolute_url())
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "How to maintain a statement mapping")
        self.assertContains(detail, "Coverage passes")
        self.client.force_login(self.budget_preparer)
        self.assertEqual(
            self.client.get(reverse("reporting:statement_mapping_list")).status_code, 403,
        )

    def test_statement_mapping_requires_independent_activation_and_is_immutable(self):
        starter = FinanceStatementMapping.objects.get(
            department=self.accounting, statement_type=FinanceStatementMapping.POSITION,
        )
        successor = FinanceStatementMapping.objects.create(
            department=self.accounting, statement_type=FinanceStatementMapping.POSITION,
            version=2, title="Locally reviewed position mapping", status=FinanceStatementMapping.DRAFT,
            supersedes=starter, authority_reference="Synthetic reviewed COA/GAM statement authority",
            local_acceptance_note="Compared to the signed synthetic local position statement.",
            created_by=self.accounting_preparer,
        )
        FinanceStatementLine.objects.create(
            mapping=successor, position=10, section_code="assets", section_title="Assets",
            line_code="cash", line_title="Cash and cash equivalents",
            selector_type=FinanceStatementLine.ACCOUNT_CODES, account_codes=[self.cash.code],
        )
        submit_statement_mapping(successor, self.accounting_preparer)
        successor.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "preparer or submitter"):
            review_statement_mapping(successor, self.accounting_preparer, approve=True)
        review_statement_mapping(
            successor, self.accounting_reviewer, approve=True,
            note="Synthetic independent account coverage and signed-reference comparison passed.",
        )
        successor.refresh_from_db()
        starter.refresh_from_db()
        self.assertEqual(successor.status, FinanceStatementMapping.ACTIVE)
        self.assertEqual(starter.status, FinanceStatementMapping.STARTER)
        self.assertEqual(len(successor.snapshot_checksum), 64)
        successor.title = "Silent rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            successor.save()

        owner = {"department_id": self.accounting.pk, "department_label": self.accounting.name}
        receivable = LedgerAccount.objects.create(
            **owner, code="10301010", title="Receivable", account_type="asset", normal_balance="debit",
        )
        entry = JournalEntry.objects.create(
            **owner, reference="JEV-F9-NEW-ASSET", entry_date=date(2027, 2, 20),
            period=self.period, fund=self.fund, source_type="manual", description="New unmapped asset",
            status=JournalEntry.DRAFT, created_by_id=self.accounting_preparer.pk,
            created_by_label=self.accounting_preparer.username, posted_by_id=self.accounting_reviewer.pk,
            posted_by_label=self.accounting_reviewer.username, posted_at=timezone.now(),
        )
        JournalLine.objects.create(entry=entry, sequence=1, account=receivable, debit=Decimal("25.00"))
        JournalLine.objects.create(entry=entry, sequence=2, account=self.revenue, credit=Decimal("25.00"))
        JournalEntry.objects.filter(pk=entry.pk).update(status=JournalEntry.POSTED)
        definition = ReportDefinition.objects.get(
            department=self.accounting, dataset_key="finance_statement_position",
        )
        run = create_manual_run(
            definition, definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.accounting_preparer,
        )
        self.assertEqual(run.parameters["_statement_mapping_snapshot"]["version"], 2)
        self.assertEqual(run.control_status, ReportRun.CONTROL_EXCEPTION)
        self.assertEqual(run.control_totals["unmapped_account_codes"], [receivable.code])

    def test_reporting_workspace_explains_latest_statement_measures(self):
        definition = ReportDefinition.objects.get(
            department=self.accounting, dataset_key="finance_statement_position",
        )
        run = create_manual_run(
            definition, definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.accounting_preparer,
        )
        self.client.force_login(self.accounting_preparer)
        response = self.client.get(reverse("reporting:workspace"))
        self.assertContains(response, "Explained Finance measures")
        self.assertContains(response, "Assets")
        self.assertContains(response, "Source freshness")
        self.assertContains(response, str(run.period_end.year))

    def test_budget_accountability_uses_cumulative_authority_and_posted_movements(self):
        adapter, rows, totals, evidence = build_dataset_with_evidence(
            self.budget_definition, date(2027, 1, 1), date(2027, 3, 31),
            {"_definition_snapshot": {
                "dataset_key": self.budget_definition.dataset_key,
                "selected_fields": self.budget_definition.selected_fields,
                "filters": {}, "group_by": [], "totals": self.budget_definition.totals,
                "sort_by": [],
            }},
        )
        self.assertEqual(adapter.key, "finance_budget_accountability")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["appropriation"], Decimal("100000.00"))
        self.assertEqual(rows[0]["released_allotment"], Decimal("80000.00"))
        self.assertEqual(rows[0]["obligation"], Decimal("50000.00"))
        self.assertEqual(rows[0]["unobligated_allotment"], Decimal("30000.00"))
        self.assertEqual(totals["obligation"], Decimal("50000.00"))
        self.assertEqual(evidence["control_status"], ReportRun.CONTROL_RECONCILED)
        self.assertEqual(len(evidence["sources"]), 3)

    def test_candidate_definition_blocks_official_approval_until_confirmed_successor(self):
        template = self.accounting_definition.current_template
        template.fidelity_status = ReportTemplateVersion.OFFICIAL
        template.fidelity_notes = "Compared with synthetic current form and redacted completed sample."
        template.fidelity_validated_by = self.accounting_reviewer
        template.fidelity_validated_at = timezone.now()
        template.full_clean()
        template.save(update_fields=(
            "fidelity_status", "fidelity_notes", "fidelity_validated_by", "fidelity_validated_at",
        ))
        candidate = self.generate_accounting()
        transition_run(candidate, "review", self.accounting_reviewer, "Controls traced.")
        with self.assertRaisesMessage(ValueError, "local applicability"):
            transition_run(candidate, "approve", self.accounting_reviewer, "Official approval.")
        self.accounting_definition.applicability_status = ReportDefinition.APPLICABILITY_CONFIRMED
        self.accounting_definition.authority_reference = "Synthetic locally reviewed GAM and LGU procedure reference."
        self.accounting_definition.local_acceptance_note = "Confirmed for synthetic UAT by the named Accounting owner."
        self.accounting_definition.full_clean()
        self.accounting_definition.save()
        successor = self.generate_accounting()
        transition_run(successor, "review", self.accounting_reviewer, "Controls traced.")
        transition_run(successor, "approve", self.accounting_reviewer, "Synthetic official acceptance.")
        successor.refresh_from_db()
        self.assertEqual(successor.status, ReportRun.APPROVED)

    def test_control_exception_cannot_enter_review(self):
        broken = JournalEntry.objects.create(
            department_id=self.accounting.pk, department_label=self.accounting.name,
            reference="JEV-F9-BROKEN", entry_date=date(2027, 2, 1), period=self.period,
            fund=self.fund, source_type="manual", description="Synthetic broken posting evidence",
            status=JournalEntry.DRAFT, created_by_id=self.accounting_preparer.pk,
            created_by_label=self.accounting_preparer.username,
            posted_by_id=self.accounting_reviewer.pk, posted_by_label=self.accounting_reviewer.username,
            posted_at=timezone.now(),
        )
        JournalLine.objects.create(entry=broken, sequence=1, account=self.cash, debit=Decimal("10.00"))
        JournalEntry.objects.filter(pk=broken.pk).update(status=JournalEntry.POSTED)
        run = self.generate_accounting()
        self.assertEqual(run.control_status, ReportRun.CONTROL_EXCEPTION)
        with self.assertRaisesMessage(ValueError, "must reconcile"):
            transition_run(run, "review", self.accounting_reviewer)

    def test_control_export_and_reproduction_receipt_are_tracesync_archived(self):
        run = self.generate_accounting()
        self.client.force_login(self.accounting_preparer)
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            control = self.client.get(reverse("reporting:run_control_export", args=(run.public_id,)))
            receipt = self.client.get(reverse("reporting:run_reproduction_receipt", args=(run.public_id,)))
            self.assertEqual(control.status_code, 200)
            self.assertEqual(receipt.status_code, 200)
            self.assertEqual(control["X-GRAND-Export-Archived"], "true")
            self.assertEqual(receipt["X-GRAND-Export-Archived"], "true")
            parsed = json.loads(receipt.content)
            self.assertEqual(parsed["checksums"]["dataset_sha256"], run.dataset_checksum)
            self.assertEqual(parsed["checksums"]["reproduction_key"], run.reproduction_key)
            self.assertEqual(parsed["sources"][0]["reference"], self.entry.reference)
            root = Path(export_root)
            self.assertTrue((root / "GRAND_EXPORT_ROOT.json").exists())
            self.assertEqual(len(list(root.rglob("*.manifest.json"))), 2)

    def test_posted_general_ledger_retains_line_level_controls_and_entry_sources(self):
        definition = ReportDefinition.objects.get(
            department=self.accounting, dataset_key="finance_posted_general_ledger",
        )
        run = create_manual_run(
            definition, definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.accounting_preparer,
        )
        self.assertEqual(run.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertEqual(run.row_count, 2)
        self.assertEqual(run.control_totals["debit"], "1250.00")
        self.assertEqual(run.control_totals["credit"], "1250.00")
        self.assertEqual(run.source_record_count, 1)
        source = run.source_records.get()
        self.assertEqual(source.source_reference, self.entry.reference)
        self.assertEqual(len(source.snapshot["lines"]), 2)

    def test_payable_schedule_must_reconcile_to_its_mapped_gl_control(self):
        owner = {"department_id": self.accounting.pk, "department_label": self.accounting.name}
        payable = LedgerAccount.objects.create(
            **owner, code="20101010", title="Accounts payable",
            account_type="liability", normal_balance="credit",
        )
        PostingMapping.objects.create(
            **owner, category=PostingMapping.PAYABLE, source_code="ordinary-supplier",
            label="Ordinary supplier payable", account=payable,
        )
        entry = JournalEntry.objects.create(
            **owner, reference="JEV-F9-AP-0001", entry_date=date(2027, 2, 15),
            period=self.period, fund=self.fund, source_type="voucher",
            source_reference="CASE-F9-AP-1", description="Synthetic payable recognition",
            status=JournalEntry.DRAFT, created_by_id=self.accounting_preparer.pk,
            created_by_label=self.accounting_preparer.username,
            posted_by_id=self.accounting_reviewer.pk,
            posted_by_label=self.accounting_reviewer.username, posted_at=timezone.now(),
        )
        JournalLine.objects.create(
            entry=entry, sequence=1, account=self.cash, debit=Decimal("200.00"),
        )
        payable_line = JournalLine.objects.create(
            entry=entry, sequence=2, account=payable, credit=Decimal("200.00"),
        )
        JournalSubsidiaryLine.objects.create(
            entry=entry, journal_line=payable_line, category=JournalSubsidiaryLine.PAYABLE,
            reference_key="party-f9", reference_label="Synthetic Supplier",
            source_code="ordinary-supplier", source_reference="CASE-F9-AP-1",
            credit=Decimal("200.00"),
        )
        JournalEntry.objects.filter(pk=entry.pk).update(status=JournalEntry.POSTED)
        definition = ReportDefinition.objects.get(
            department=self.accounting, dataset_key="finance_posted_payable_schedule",
        )
        run = create_manual_run(
            definition, definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.accounting_preparer,
        )
        self.assertEqual(run.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertEqual(run.control_totals["subsidiary_balance"], "200.00")
        self.assertEqual(run.control_totals["gl_control_balance"], "200.00")
        self.assertEqual(run.source_records.get().snapshot["reference_key"], "party-f9")

        broken = JournalEntry.objects.create(
            **owner, reference="JEV-F9-AP-BROKEN", entry_date=date(2027, 2, 16),
            period=self.period, fund=self.fund, source_type="manual",
            description="Synthetic control posting without subsidiary detail",
            status=JournalEntry.DRAFT, created_by_id=self.accounting_preparer.pk,
            created_by_label=self.accounting_preparer.username,
            posted_by_id=self.accounting_reviewer.pk,
            posted_by_label=self.accounting_reviewer.username, posted_at=timezone.now(),
        )
        JournalLine.objects.create(entry=broken, sequence=1, account=self.cash, debit=Decimal("50.00"))
        JournalLine.objects.create(entry=broken, sequence=2, account=payable, credit=Decimal("50.00"))
        JournalEntry.objects.filter(pk=broken.pk).update(status=JournalEntry.POSTED)
        exception_run = create_manual_run(
            definition, definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.accounting_preparer,
        )
        self.assertEqual(exception_run.control_status, ReportRun.CONTROL_EXCEPTION)
        self.assertEqual(exception_run.control_totals["difference"], "50.00")
        with self.assertRaisesMessage(ValueError, "must reconcile"):
            transition_run(exception_run, "review", self.accounting_reviewer)

        withholding_definition = ReportDefinition.objects.get(
            department=self.accounting, dataset_key="finance_posted_withholding_schedule",
        )
        withholding_run = create_manual_run(
            withholding_definition, withholding_definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 3, 31), {}, self.accounting_preparer,
        )
        self.assertEqual(withholding_run.control_status, ReportRun.CONTROL_EXCEPTION)
        self.assertIn("mapping is not configured", withholding_run.control_message)

    def test_budget_vs_actual_requires_exact_classification_mapping(self):
        owner = {"department_id": self.accounting.pk, "department_label": self.accounting.name}
        center = ResponsibilityCenter.objects.create(
            **owner, code="GSO", name="General Services Office",
            office_id=self.requesting.pk, office_code=self.requesting.slug,
        )
        expense = LedgerAccount.objects.create(
            **owner, code="5-02-03", title="Office operations",
            account_type="expense", normal_balance="debit",
        )
        entry = JournalEntry.objects.create(
            **owner, reference="JEV-F9-ACTUAL-1", entry_date=date(2027, 2, 20),
            period=self.period, fund=self.fund, source_type="voucher",
            source_reference="CASE-F9-ACTUAL-1", description="Synthetic posted actual",
            status=JournalEntry.DRAFT, created_by_id=self.accounting_preparer.pk,
            created_by_label=self.accounting_preparer.username,
            posted_by_id=self.accounting_reviewer.pk,
            posted_by_label=self.accounting_reviewer.username, posted_at=timezone.now(),
        )
        JournalLine.objects.create(
            entry=entry, sequence=1, account=expense, responsibility_center=center,
            debit=Decimal("20000.00"),
        )
        JournalLine.objects.create(entry=entry, sequence=2, account=self.cash, credit=Decimal("20000.00"))
        JournalEntry.objects.filter(pk=entry.pk).update(status=JournalEntry.POSTED)
        definition = ReportDefinition.objects.get(
            department=self.budget, dataset_key="finance_budget_vs_posted_actual",
        )
        adapter, rows, totals, evidence = build_dataset_with_evidence(
            definition, date(2027, 1, 1), date(2027, 3, 31),
            {"_definition_snapshot": {
                "dataset_key": definition.dataset_key,
                "selected_fields": definition.selected_fields, "filters": {}, "group_by": [],
                "totals": definition.totals, "sort_by": [],
            }},
        )
        self.assertEqual(adapter.key, "finance_budget_vs_posted_actual")
        self.assertEqual(rows[0]["posted_actual"], Decimal("20000.00"))
        self.assertEqual(rows[0]["balance_vs_actual"], Decimal("60000.00"))
        self.assertEqual(totals["posted_actual"], Decimal("20000.00"))
        self.assertEqual(evidence["control_status"], ReportRun.CONTROL_RECONCILED)
        self.assertEqual(evidence["control_totals"]["mapping_exception_count"], 0)

        unmatched = LedgerAccount.objects.create(
            **owner, code="5-02-99", title="Unmapped expense",
            account_type="expense", normal_balance="debit",
        )
        broken = JournalEntry.objects.create(
            **owner, reference="JEV-F9-ACTUAL-2", entry_date=date(2027, 2, 21),
            period=self.period, fund=self.fund, source_type="manual",
            description="Synthetic unmatched actual", status=JournalEntry.DRAFT,
            created_by_id=self.accounting_preparer.pk,
            created_by_label=self.accounting_preparer.username,
            posted_by_id=self.accounting_reviewer.pk,
            posted_by_label=self.accounting_reviewer.username, posted_at=timezone.now(),
        )
        JournalLine.objects.create(
            entry=broken, sequence=1, account=unmatched, responsibility_center=center,
            debit=Decimal("100.00"),
        )
        JournalLine.objects.create(entry=broken, sequence=2, account=self.cash, credit=Decimal("100.00"))
        JournalEntry.objects.filter(pk=broken.pk).update(status=JournalEntry.POSTED)
        _adapter, _rows, _totals, exception = build_dataset_with_evidence(
            definition, date(2027, 1, 1), date(2027, 3, 31),
            {"_definition_snapshot": {
                "dataset_key": definition.dataset_key,
                "selected_fields": definition.selected_fields, "filters": {}, "group_by": [],
                "totals": definition.totals, "sort_by": [],
            }},
        )
        self.assertEqual(exception["control_status"], ReportRun.CONTROL_EXCEPTION)
        self.assertEqual(exception["control_totals"]["unmapped_actual"], Decimal("100.00"))

    def test_treasury_register_reconciles_issue_advice_release_and_receipt_evidence(self):
        treasury = Department.objects.create(name="Municipal Treasury Office", slug="f9-treasury")
        treasury_preparer = self.employee(
            treasury, "f9.treasury.preparer",
            "view_reporting_workspace", "generate_reports", "download_reports",
        )
        treasury.deptHead_or_oic = treasury_preparer
        treasury.save(update_fields=("deptHead_or_oic",))
        seed_finance_presets()
        instrument_time = timezone.make_aware(datetime(2027, 3, 5, 10, 30))
        case = VoucherCase.objects.create(
            reference_code="CASE-F9-TRSY-1", transaction_type="ordinary-supplier-claim",
            requesting_department=self.requesting, current_department=treasury,
            payee_name="Synthetic Supplier", particulars="Synthetic released disbursement",
            authoritative_obligation_amount=Decimal("1000.00"),
            current_stage=VoucherCase.COMPLETED, created_by=treasury_preparer,
            completed_at=instrument_time,
        )
        DisbursementVoucher.objects.create(
            case=case, dv_number="DV-F9-TRSY-1", voucher_date=date(2027, 3, 1),
            gross_amount=Decimal("1000.00"), total_deductions=Decimal("100.00"),
            net_amount=Decimal("900.00"), prepared_by=treasury_preparer,
            prepared_at=instrument_time,
        )
        advice = BankAdviceBatch.objects.create(
            advice_number="ADV-F9-1", advice_date=date(2027, 3, 5),
            bank_account_code="GF-CHECKING", status=BankAdviceBatch.ACKNOWLEDGED,
            accounting_department=self.accounting, preparation_note="Synthetic retained advice",
            authority_reference="Synthetic authority", local_applicability_note="Synthetic UAT",
            item_count=1, total_amount=Decimal("900.00"), snapshot_checksum="d" * 64,
            created_by=treasury_preparer, review_submitted_by=treasury_preparer,
            review_submitted_at=instrument_time, approved_by=self.accounting_reviewer,
            approved_at=instrument_time, bank_submitted_by=treasury_preparer,
            bank_submitted_at=instrument_time, submission_reference="SUB-F9-1",
            acknowledged_by=self.accounting_reviewer, acknowledged_at=instrument_time,
            acknowledgement_reference="ACK-F9-1",
        )
        instrument = PaymentInstrument.objects.create(
            case=case, bank_account_code="GF-CHECKING", fund_code="GF",
            check_number="CHK-F9-0001", amount=Decimal("900.00"),
            status=PaymentInstrument.RELEASED, issued_by=treasury_preparer,
            issued_at=instrument_time, released_by=treasury_preparer,
            released_at=instrument_time, released_to="Authorized claimant",
            receipt_reference="RCPT-F9-1", current_advice_batch=advice,
        )
        BankAdviceItem.objects.create(
            batch=advice, instrument=instrument,
            instrument_public_id_snapshot=instrument.public_id,
            check_number_snapshot=instrument.check_number, fund_code_snapshot=instrument.fund_code,
            amount_snapshot=instrument.amount, issued_at_snapshot=instrument.issued_at,
        )
        definition = ReportDefinition.objects.get(
            department=treasury, dataset_key="finance_payment_instrument_register",
        )
        run = create_manual_run(
            definition, definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 12, 31), {}, treasury_preparer,
        )
        self.assertEqual(run.control_status, ReportRun.CONTROL_RECONCILED)
        self.assertEqual(run.control_totals["issued_amount"], "900.00")
        self.assertEqual(run.control_totals["released_amount"], "900.00")
        self.assertEqual(run.source_record_count, 1)
        self.assertEqual(run.source_records.get().source_reference, "CHK-F9-0001")
        self.assertEqual(run.dataset_snapshot["rows"][0]["receipt_reference"], "RCPT-F9-1")

        incomplete_case = VoucherCase.objects.create(
            reference_code="CASE-F9-TRSY-BROKEN", transaction_type="ordinary-supplier-claim",
            requesting_department=self.requesting, current_department=treasury,
            payee_name="Incomplete synthetic payee", particulars="Missing DV source evidence",
            authoritative_obligation_amount=Decimal("10.00"),
            current_stage=VoucherCase.TREASURY_CHECK_PREPARATION, created_by=treasury_preparer,
        )
        PaymentInstrument.objects.create(
            case=incomplete_case, bank_account_code="GF-CHECKING", fund_code="GF",
            check_number="CHK-F9-BROKEN", amount=Decimal("10.00"),
            status=PaymentInstrument.ISSUED, issued_by=treasury_preparer,
            issued_at=instrument_time,
        )
        exception_run = create_manual_run(
            definition, definition.current_template, "xlsx",
            date(2027, 1, 1), date(2027, 12, 31), {}, treasury_preparer,
        )
        self.assertEqual(exception_run.status, ReportRun.GENERATED)
        self.assertEqual(exception_run.control_status, ReportRun.CONTROL_EXCEPTION)
        self.assertEqual(exception_run.control_totals["evidence_exception_count"], 1)


def tearDownModule():
    shutil.rmtree(FINANCE_REPORT_MEDIA_ROOT, ignore_errors=True)
