from __future__ import annotations

import json
import shutil
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounting.models import AccountingPeriod, FiscalYear, Fund, JournalEntry, JournalLine, LedgerAccount
from budget.models import (
    AllotmentMovement, AllotmentReleaseOrder, AppropriationAuthorization,
    AuthorizedAppropriationLine, BudgetCall, BudgetVersion, ObligationMovement,
    ObligationRequest,
)
from departments.models import Department

from .datasets import build_dataset_with_evidence
from .models import ReportDefinition, ReportRun, ReportTemplateVersion
from .presets import seed_finance_presets
from .services import create_manual_run, transition_run


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


def tearDownModule():
    shutil.rmtree(FINANCE_REPORT_MEDIA_ROOT, ignore_errors=True)
