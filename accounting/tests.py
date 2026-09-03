from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connections
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from departments.models import Department
from profiles.models import EmployeeProfile
from finance.models import FinanceConfigurationItem, FinanceConfigurationRelease, FinanceWorkflowExemption
from vouchers.models import (
    DisbursementVoucher, FinanceFoundationIssuanceBoundary, PaymentInstrument, VoucherCase,
)

from .access import can_post_journals, can_prepare_journals, can_view_accounting
from .models import (
    AccountingAuditEvent, AccountingPeriod, FiscalYear, FiscalYearReadinessApproval,
    BankOutstandingItem, BankStatementBatch, BankStatementMatch,
    Fund, FundingSource, JournalEntry, JournalLine, JournalSubsidiaryLine,
    LedgerAccount, OpeningBalanceBatch, OpeningBalanceRow,
    PostingMapping, ProgramActivityProject, ResponsibilityCenter,
)
from .services import (
    adopt_configuration_release, begin_foundation_amendment, create_reversal, decide_readiness_layer,
    auto_match_bank_statement, bank_outstanding_carry_candidates, bank_reconciliation_snapshot,
    classify_bank_outstanding,
    control_reconciliation_snapshot,
    correct_opening_batch, correct_opening_row, decide_opening_batch, discard_draft, ensure_readiness_layers,
    evaluate_fiscal_year_readiness, post_entry, post_opening_batch, reconcile_opening_batch,
    run_control_reconciliation, stage_opening_csv, submit_entry, submit_opening_batch, transition_fiscal_year,
    decide_bank_reconciliation, stage_bank_statement_csv, submit_bank_reconciliation,
    match_bank_statement_row, unclassify_bank_outstanding, unmatch_bank_statement_row, validate_opening_batch,
)
from .foundation_exports import build_foundation_register


class StandaloneAccountingTests(TestCase):
    databases = {"default", "finance"}

    @classmethod
    def setUpTestData(cls):
        cls.accounting_department = Department.objects.create(name="Municipal Accounting Office", slug="accounting")
        cls.other_department = Department.objects.create(name="Human Resources", slug="hr")
        cls.preparer = cls._employee("ledger.preparer", cls.accounting_department)
        cls.poster = cls._employee("ledger.poster", cls.accounting_department)
        cls.setup_approver = cls._employee("setup.approver", cls.accounting_department)
        cls.viewer = cls._employee("ledger.viewer", cls.accounting_department)
        cls.outsider = cls._employee("other.viewer", cls.other_department)
        cls.superuser = cls._employee("platform.admin", cls.accounting_department, is_superuser=True, is_staff=True)
        cls._grant(
            cls.preparer, "view_accounting_workspace", "prepare_journal_entries",
            "manage_accounting_setup", "prepare_opening_balances", "view_bank_reconciliation",
            "prepare_bank_reconciliation", "export_bank_reconciliation",
        )
        cls._grant(
            cls.poster, "view_accounting_workspace", "post_journal_entries",
            "post_opening_balances", "view_general_ledger", "reconcile_control_accounts",
        )
        cls._grant(
            cls.setup_approver, "view_accounting_workspace", "approve_fiscal_readiness",
            "approve_opening_balances", "view_bank_reconciliation", "approve_bank_reconciliation",
        )
        cls._grant(cls.viewer, "view_accounting_workspace")
        cls._grant(cls.outsider, "view_accounting_workspace")

        owner = {"department_id": cls.accounting_department.pk, "department_label": cls.accounting_department.name}
        cls.period = AccountingPeriod.objects.create(
            **owner, fiscal_year=2027, period_number=1, label="January", starts_on=date(2027, 1, 1), ends_on=date(2027, 1, 31),
        )
        cls.fund = Fund.objects.create(**owner, code="SYN-GF", name="Synthetic General Fund")
        cls.center = ResponsibilityCenter.objects.create(**owner, code="SYN-ACCT", name="Synthetic Accounting Office")
        cls.cash = LedgerAccount.objects.create(
            **owner, code="SYN-101", title="Synthetic Cash", account_type="asset", normal_balance="debit",
        )
        cls.revenue = LedgerAccount.objects.create(
            **owner, code="SYN-401", title="Synthetic Revenue", account_type="revenue", normal_balance="credit",
        )
        cls.payable = LedgerAccount.objects.create(
            **owner, code="SYN-201", title="Synthetic Accounts Payable", account_type="liability", normal_balance="credit",
        )

    @classmethod
    def _employee(cls, username, department, **kwargs):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.test", password="accounting-test-password", **kwargs,
        )
        profile, _ = EmployeeProfile.objects.get_or_create(user=user)
        profile.assigned_department = department
        profile.save(update_fields=("assigned_department",))
        return get_user_model().objects.get(pk=user.pk)

    @classmethod
    def _grant(cls, user, *codenames):
        permissions = Permission.objects.filter(content_type__app_label="accounting", codename__in=codenames)
        if permissions.count() != len(codenames):
            raise AssertionError("Accounting permissions were not created in GRAND's core database.")
        user.user_permissions.add(*permissions)

    def _entry(self, *, reference="SYN-JEV-0001", balanced=True, creator=None):
        creator = creator or self.preparer
        entry = JournalEntry.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            reference=reference,
            entry_date=date(2027, 1, 15),
            period=self.period,
            fund=self.fund,
            description="Synthetic standalone accounting test",
            created_by_id=creator.pk,
            created_by_label=creator.username,
        )
        JournalLine.objects.create(
            entry=entry, sequence=1, account=self.cash, responsibility_center=self.center,
            debit=Decimal("100.00"), credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            entry=entry, sequence=2, account=self.revenue, responsibility_center=self.center,
            debit=Decimal("0.00"), credit=Decimal("100.00" if balanced else "90.00"),
        )
        return entry

    def _fiscal_foundation(self, year=2027):
        fiscal_year = FiscalYear.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            year=year,
            label=f"FY {year}",
            starts_on=date(year, 1, 1),
            ends_on=date(year, 12, 31),
            business_date=date(year, 1, 1),
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        self.period.fiscal_year_record = fiscal_year
        self.period.full_clean()
        self.period.save(update_fields=("fiscal_year_record",))
        source = FundingSource.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            fiscal_year=fiscal_year,
            fund=self.fund,
            code="SYN-LOCAL",
            name="Synthetic local source",
            kind="local",
            authority_reference="Synthetic appropriation ordinance",
            effective_from=date(year, 1, 1),
        )
        ProgramActivityProject.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            fiscal_year=fiscal_year,
            code="SYN-MFO-01",
            name="Synthetic public service MFO",
            kind="mfo",
            responsibility_center=self.center,
            funding_source=source,
            authority_reference="Synthetic approved budget",
            effective_from=date(year, 1, 1),
        )
        return fiscal_year

    def _zero_opening(self, fiscal_year, *, source_reference="SYN-ZERO-OPENING", status=OpeningBalanceBatch.RECONCILED):
        return OpeningBalanceBatch.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            fiscal_year=fiscal_year,
            period=self.period,
            title="Synthetic explicit zero opening",
            source_reference=source_reference,
            expected_row_count=0,
            expected_debit=Decimal("0.00"),
            expected_credit=Decimal("0.00"),
            is_zero_balance_declaration=True,
            status=status,
            validation_summary={"valid": True, "row_count": 0, "debit": "0.00", "credit": "0.00"},
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )

    def _opening_file(self, *, invalid_account=False):
        account_code = "BAD-ACCOUNT" if invalid_account else self.revenue.code
        content = (
            "fund_code,account_code,responsibility_center_code,debit,credit,subsidiary_reference,memo\n"
            f"{self.fund.code},{self.cash.code},{self.center.code},100.00,,SYN-CASH,Opening cash\n"
            f"{self.fund.code},{account_code},{self.center.code},,100.00,SYN-EQUITY,Opening offset\n"
        )
        return SimpleUploadedFile("synthetic-opening.csv", content.encode("utf-8"), content_type="text/csv")

    def _opening_batch(self, fiscal_year, *, source_reference="SYN-OPEN-001"):
        return OpeningBalanceBatch.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            fiscal_year=fiscal_year,
            period=self.period,
            title="Synthetic controlled opening schedule",
            source_reference=source_reference,
            expected_row_count=2,
            expected_debit=Decimal("100.00"),
            expected_credit=Decimal("100.00"),
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )

    def test_typed_fiscal_year_requires_independent_layered_readiness_before_activation(self):
        fiscal_year = self._fiscal_foundation()
        self._grant(self.preparer, "approve_fiscal_readiness")
        transition_fiscal_year(fiscal_year, "submit", self.preparer)
        with self.assertRaisesMessage(ValidationError, "different"):
            transition_fiscal_year(fiscal_year, "approve", self.preparer)
        transition_fiscal_year(fiscal_year, "approve", self.setup_approver)
        self._zero_opening(fiscal_year)
        fiscal_year.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "five readiness layers"):
            transition_fiscal_year(fiscal_year, "activate", self.setup_approver)

        readiness = evaluate_fiscal_year_readiness(fiscal_year)
        self.assertEqual(len(readiness["layers"]), 5)
        for result in readiness["layers"]:
            decide_readiness_layer(
                result["record"], self.setup_approver,
                decision=FiscalYearReadinessApproval.APPROVED,
                evidence_note=f"Synthetic {result['record'].layer} acceptance evidence.",
            )
        transition_fiscal_year(fiscal_year, "activate", self.setup_approver)
        fiscal_year.refresh_from_db()
        self.assertEqual(fiscal_year.status, FiscalYear.ACTIVE)
        self.assertTrue(evaluate_fiscal_year_readiness(fiscal_year)["ready"])
        self.assertTrue(AccountingAuditEvent.objects.filter(action="fiscal_year_activate").exists())

    def test_budget_readiness_cannot_be_approved_without_funding_and_program_classification(self):
        fiscal_year = FiscalYear.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            year=2028,
            label="FY 2028",
            starts_on=date(2028, 1, 1),
            ends_on=date(2028, 12, 31),
            business_date=date(2028, 1, 1),
            created_by_id=self.preparer.pk,
        )
        ensure_readiness_layers(fiscal_year)
        budget_layer = next(
            item["record"] for item in evaluate_fiscal_year_readiness(fiscal_year)["layers"]
            if item["record"].layer == FiscalYearReadinessApproval.BUDGET
        )
        with self.assertRaisesMessage(ValidationError, "funding source"):
            decide_readiness_layer(
                budget_layer, self.setup_approver,
                decision=FiscalYearReadinessApproval.APPROVED,
                evidence_note="Premature synthetic acceptance.",
            )

    def test_classifications_enforce_department_and_fiscal_year_boundaries(self):
        fiscal_year = self._fiscal_foundation()
        foreign_fund = Fund.objects.create(
            department_id=self.other_department.pk,
            department_label=self.other_department.name,
            code="HR-FUND",
            name="Foreign department fund",
        )
        source = FundingSource(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            fiscal_year=fiscal_year,
            fund=foreign_fund,
            code="BAD-SOURCE",
            name="Invalid cross-department source",
            effective_from=date(2027, 1, 1),
        )
        with self.assertRaisesMessage(ValidationError, "fund must belong"):
            source.full_clean()

    def test_approved_setup_release_is_adopted_by_snapshot_without_cross_database_relations(self):
        release = FinanceConfigurationRelease.objects.create(
            department=self.accounting_department,
            code="fy-2027-classifications",
            version=2,
            title="Synthetic approved FY 2027 classifications",
            fiscal_year=2027,
            status="approved",
            effective_from=date(2027, 1, 1),
            created_by=self.preparer,
            approved_by=self.setup_approver,
        )
        item_values = (
            ("fund", "GF-ADOPT", "Adopted General Fund", {"category": "general"}),
            ("funding_source", "LOCAL-ADOPT", "Adopted local revenue", {"kind": "local", "fund_code": "GF-ADOPT"}),
            ("ppa_mfo", "MFO-ADOPT", "Adopted public service MFO", {"kind": "mfo", "funding_source_code": "LOCAL-ADOPT"}),
        )
        for category, code, label, configuration in item_values:
            FinanceConfigurationItem.objects.create(
                department=self.accounting_department,
                release=release,
                category=category,
                code=code,
                version=1,
                label=label,
                configuration=configuration,
                status="approved",
                effective_from=date(2027, 1, 1),
                created_by=self.preparer,
            )
        fiscal_year, counts = adopt_configuration_release(release, self.preparer)
        self.assertEqual(fiscal_year.source_release_id, release.pk)
        self.assertEqual(len(fiscal_year.source_checksum), 64)
        self.assertEqual(counts["funding_sources"], 1)
        self.assertEqual(counts["classifications"], 1)
        self.period.refresh_from_db()
        self.assertEqual(self.period.fiscal_year_record, fiscal_year)
        self.assertNotIn("department", [field.name for field in FiscalYear._meta.fields])
        self.assertTrue(AccountingAuditEvent.objects.filter(action="configuration_release_adopted").exists())
        self.assertTrue(FinanceFoundationIssuanceBoundary.objects.filter(
            department=self.accounting_department,
            fiscal_year=release.fiscal_year,
        ).exists())

    def test_successor_release_for_governed_year_requires_reason_and_reopens_readiness_before_issue(self):
        fiscal_year = self._fiscal_foundation()
        ensure_readiness_layers(fiscal_year)
        fiscal_year.status = FiscalYear.ACTIVE
        fiscal_year.source_checksum = "0" * 64
        fiscal_year.save(update_fields=("status", "source_checksum"))
        FiscalYearReadinessApproval.objects.filter(fiscal_year=fiscal_year).update(
            status=FiscalYearReadinessApproval.APPROVED,
            evidence_note="Synthetic prior approval",
            decided_by_id=self.setup_approver.pk,
            decided_by_label=self.setup_approver.username,
        )
        release = FinanceConfigurationRelease.objects.create(
            department=self.accounting_department,
            code="fy-2027-successor",
            version=3,
            title="Synthetic successor classifications",
            fiscal_year=2027,
            status="approved",
            effective_from=date(2027, 1, 1),
            created_by=self.preparer,
            approved_by=self.setup_approver,
        )
        FinanceConfigurationItem.objects.create(
            department=self.accounting_department,
            release=release,
            category="fund",
            code="GF-SUCCESSOR",
            version=1,
            label="Successor General Fund",
            configuration={"category": "general"},
            status="approved",
            effective_from=date(2027, 1, 1),
            created_by=self.preparer,
        )
        with self.assertRaisesMessage(ValidationError, "Explain why"):
            adopt_configuration_release(release, self.preparer)

        adopted, counts = adopt_configuration_release(
            release,
            self.preparer,
            change_reason="Adopt the corrected approved classification release before any DV or check issue.",
        )
        adopted.refresh_from_db()
        self.assertEqual(adopted.status, FiscalYear.DRAFT)
        self.assertEqual(adopted.source_release_id, release.pk)
        self.assertEqual(counts["funds"], 1)
        self.assertTrue(adopted.readiness_layers.filter(status=FiscalYearReadinessApproval.PENDING).exists())
        self.assertTrue(AccountingAuditEvent.objects.filter(action="foundation_amended").exists())

    def test_guided_setup_renders_for_manager_and_independent_approver(self):
        fiscal_year = self._fiscal_foundation()
        ensure_readiness_layers(fiscal_year)
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("accounting:setup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Typed fiscal years and readiness")
        self.assertContains(response, "Budget approval")
        self.assertContains(response, "Synthetic public service MFO")

        self.client.force_login(self.setup_approver)
        response = self.client.get(reverse("accounting:setup"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Approve year")
        self.assertNotContains(response, "Adopt / reconcile")

    def test_foundation_register_export_is_filtered_archived_audited_and_spreadsheet_safe(self):
        fiscal_year = self._fiscal_foundation()
        ensure_readiness_layers(fiscal_year)
        FiscalYearReadinessApproval.objects.filter(
            fiscal_year=fiscal_year,
            layer=FiscalYearReadinessApproval.TREASURY,
        ).update(
            status=FiscalYearReadinessApproval.RETURNED,
            evidence_note="=REVIEW_REQUIRED",
            decided_by_id=self.setup_approver.pk,
            decided_by_label=self.setup_approver.username,
        )
        other_owner = {
            "department_id": self.other_department.pk,
            "department_label": self.other_department.name,
        }
        Fund.objects.create(**other_owner, code="HR-PRIVATE", name="Other office private fund")
        self.client.force_login(self.preparer)

        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            response = self.client.get(
                reverse("accounting:foundation_register_export"),
                {"fiscal_year": fiscal_year.pk},
            )
            content = response.content.decode("utf-8-sig")
            event = AccountingAuditEvent.objects.get(action="foundation_register_exported")
            archived_path = Path(export_root) / event.snapshot["relative_path"]

            self.assertEqual(response.status_code, 200)
            self.assertIn("finance-fiscal-foundation-2027.csv", response["Content-Disposition"])
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            self.assertTrue(archived_path.exists())
            self.assertTrue(Path(str(archived_path) + ".manifest.json").exists())
            self.assertEqual(archived_path.read_bytes(), response.content)
            self.assertIn("fiscal_year,2027", content)
            self.assertIn("program_classification,2027", content)
            self.assertIn("readiness,2027", content)
            self.assertIn("'=REVIEW_REQUIRED", content)
            self.assertNotIn("HR-PRIVATE", content)
            self.assertEqual(event.snapshot["fiscal_year_public_id"], str(fiscal_year.public_id))
            self.assertEqual(event.snapshot["record_counts"]["fiscal_year"], 1)
            self.assertEqual(event.snapshot["record_counts"]["readiness"], 5)

    def test_foundation_register_rejects_viewer_and_cross_department_year_filter(self):
        other_year = FiscalYear.objects.create(
            department_id=self.other_department.pk,
            department_label=self.other_department.name,
            year=2028,
            label="Private HR FY 2028",
            starts_on=date(2028, 1, 1),
            ends_on=date(2028, 12, 31),
            business_date=date(2028, 1, 1),
            created_by_id=self.outsider.pk,
            created_by_label=self.outsider.username,
        )
        self.client.force_login(self.viewer)
        forbidden = self.client.get(reverse("accounting:foundation_register_export"))
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_login(self.preparer)
        hidden = self.client.get(
            reverse("accounting:foundation_register_export"),
            {"fiscal_year": other_year.pk},
        )
        self.assertEqual(hidden.status_code, 404)
        with self.assertRaises(PermissionDenied):
            build_foundation_register(self.other_department, self.preparer, fiscal_year=other_year)

    def test_guided_period_form_requires_and_pins_the_typed_fiscal_year(self):
        fiscal_year = self._fiscal_foundation()
        self.client.force_login(self.preparer)
        response = self.client.post(reverse("accounting:setup_create", args=("periods",)), {
            "fiscal_year_record": fiscal_year.pk,
            "period_number": 2,
            "label": "February",
            "starts_on": "2027-02-01",
            "ends_on": "2027-02-28",
            "is_adjustment_period": False,
        })
        self.assertEqual(response.status_code, 302)
        period = AccountingPeriod.objects.get(department_id=self.accounting_department.pk, period_number=2)
        self.assertEqual(period.fiscal_year_record, fiscal_year)
        self.assertEqual(period.fiscal_year, 2027)

    def test_guided_foundation_edit_is_allowed_before_voucher_issue_and_reopens_readiness(self):
        fiscal_year = self._fiscal_foundation()
        ensure_readiness_layers(fiscal_year)
        fiscal_year.status = FiscalYear.ACTIVE
        fiscal_year.save(update_fields=("status",))
        FiscalYearReadinessApproval.objects.filter(fiscal_year=fiscal_year).update(
            status=FiscalYearReadinessApproval.APPROVED,
            evidence_note="Synthetic prior approval",
            decided_by_id=self.setup_approver.pk,
            decided_by_label=self.setup_approver.username,
        )
        program = fiscal_year.program_classifications.get(code="SYN-MFO-01")
        self.client.force_login(self.preparer)
        response = self.client.post(reverse("accounting:setup_edit", args=("programs", program.pk)), {
            "fiscal_year": fiscal_year.pk,
            "code": program.code,
            "name": "Corrected synthetic public service MFO",
            "kind": program.kind,
            "parent": "",
            "responsibility_center": self.center.pk,
            "funding_source": program.funding_source_id,
            "authority_reference": "Synthetic approved correction",
            "effective_from": "2027-01-01",
            "effective_to": "",
            "is_active": "on",
            "change_reason": "Correct the approved synthetic classification before any DV or check is issued.",
        })
        self.assertEqual(response.status_code, 302)
        program.refresh_from_db()
        fiscal_year.refresh_from_db()
        self.assertEqual(program.name, "Corrected synthetic public service MFO")
        self.assertEqual(fiscal_year.status, FiscalYear.DRAFT)
        self.assertEqual(
            fiscal_year.readiness_layers.get(layer=FiscalYearReadinessApproval.BUDGET).status,
            FiscalYearReadinessApproval.PENDING,
        )
        self.assertTrue(FinanceFoundationIssuanceBoundary.objects.filter(
            department=self.accounting_department,
            fiscal_year=fiscal_year.year,
        ).exists())
        event = AccountingAuditEvent.objects.get(action="foundation_amended")
        self.assertEqual(event.snapshot["before"]["name"], "Synthetic public service MFO")
        self.assertEqual(event.snapshot["after"]["name"], "Corrected synthetic public service MFO")
        self.assertEqual(event.snapshot["issuance_boundary_scopes"], [{
            "department_id": self.accounting_department.pk,
            "fiscal_year": fiscal_year.year,
        }])

    def test_guided_period_move_locks_and_reopens_original_and_proposed_years(self):
        original_year = self._fiscal_foundation()
        proposed_year = FiscalYear.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            year=2028,
            label="FY 2028",
            starts_on=date(2028, 1, 1),
            ends_on=date(2028, 12, 31),
            business_date=date(2028, 1, 1),
            status=FiscalYear.ACTIVE,
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        original_year.status = FiscalYear.ACTIVE
        original_year.save(update_fields=("status",))
        ensure_readiness_layers(original_year)
        ensure_readiness_layers(proposed_year)
        FiscalYearReadinessApproval.objects.filter(
            fiscal_year__in=(original_year, proposed_year),
        ).update(
            status=FiscalYearReadinessApproval.APPROVED,
            evidence_note="Synthetic prior approval",
            decided_by_id=self.setup_approver.pk,
            decided_by_label=self.setup_approver.username,
        )

        self.client.force_login(self.preparer)
        response = self.client.post(reverse("accounting:setup_edit", args=("periods", self.period.pk)), {
            "fiscal_year_record": proposed_year.pk,
            "period_number": 1,
            "label": "January 2028",
            "starts_on": "2028-01-01",
            "ends_on": "2028-01-31",
            "is_adjustment_period": False,
            "change_reason": "Move the period to the corrected fiscal year before any DV or check is issued.",
        })

        self.assertEqual(response.status_code, 302)
        self.period.refresh_from_db()
        original_year.refresh_from_db()
        proposed_year.refresh_from_db()
        self.assertEqual(self.period.fiscal_year_record, proposed_year)
        self.assertEqual(self.period.fiscal_year, proposed_year.year)
        self.assertEqual(original_year.status, FiscalYear.DRAFT)
        self.assertEqual(proposed_year.status, FiscalYear.DRAFT)
        self.assertEqual(
            list(FinanceFoundationIssuanceBoundary.objects.filter(
                department=self.accounting_department,
                fiscal_year__in=(2027, 2028),
            ).order_by("fiscal_year").values_list("fiscal_year", flat=True)),
            [2027, 2028],
        )
        event = AccountingAuditEvent.objects.get(action="foundation_amended")
        self.assertEqual(event.snapshot["issuance_boundary_scopes"], [
            {"department_id": self.accounting_department.pk, "fiscal_year": 2027},
            {"department_id": self.accounting_department.pk, "fiscal_year": 2028},
        ])

    def test_foundation_edit_is_blocked_after_disbursement_voucher_issue(self):
        fiscal_year = self._fiscal_foundation()
        release = FinanceConfigurationRelease.objects.create(
            department=self.accounting_department,
            code="fy-2027-issued",
            version=1,
            title="Synthetic issued-voucher setup",
            fiscal_year=2027,
            status="active",
            effective_from=date(2027, 1, 1),
            created_by=self.preparer,
        )
        fiscal_year.source_release_id = release.pk
        fiscal_year.source_release_code = release.code
        fiscal_year.source_release_version = release.version
        fiscal_year.save(update_fields=("source_release_id", "source_release_code", "source_release_version"))
        case = VoucherCase.objects.create(
            reference_code="SYN-MOD-BLOCK",
            requesting_department=self.accounting_department,
            current_department=self.accounting_department,
            configuration_release=release,
            payee_name="Synthetic modification boundary payee",
            particulars="Synthetic issued DV modification boundary",
            created_by=self.preparer,
        )
        DisbursementVoucher.objects.create(
            case=case,
            dv_number="SYN-DV-MOD-BLOCK",
            voucher_date=date(2027, 2, 1),
            gross_amount=Decimal("100.00"),
            total_deductions=Decimal("0.00"),
            net_amount=Decimal("100.00"),
            prepared_by=self.preparer,
            prepared_at=timezone.now(),
        )
        program = fiscal_year.program_classifications.get(code="SYN-MFO-01")
        with self.assertRaisesMessage(ValidationError, "modification window is closed"):
            begin_foundation_amendment(program, self.preparer, "Attempted change after DV issue")

    def test_foundation_edit_is_blocked_after_check_issue_even_if_check_is_later_cancelled(self):
        fiscal_year = self._fiscal_foundation()
        release = FinanceConfigurationRelease.objects.create(
            department=self.accounting_department,
            code="fy-2027-check-issued",
            version=1,
            title="Synthetic issued-check setup",
            fiscal_year=2027,
            status="active",
            effective_from=date(2027, 1, 1),
            created_by=self.preparer,
        )
        fiscal_year.source_release_id = release.pk
        fiscal_year.source_release_code = release.code
        fiscal_year.source_release_version = release.version
        fiscal_year.save(update_fields=("source_release_id", "source_release_code", "source_release_version"))
        case = VoucherCase.objects.create(
            reference_code="SYN-CHECK-MOD-BLOCK",
            requesting_department=self.accounting_department,
            current_department=self.accounting_department,
            configuration_release=release,
            payee_name="Synthetic issued-check payee",
            particulars="Synthetic issued check modification boundary",
            created_by=self.preparer,
        )
        PaymentInstrument.objects.create(
            case=case,
            bank_account_code="SYN-BANK",
            check_number="SYN-CHECK-001",
            amount=Decimal("100.00"),
            status=PaymentInstrument.CANCELLED,
            issued_by=self.preparer,
            issued_at=timezone.now(),
            cancelled_by=self.preparer,
            cancelled_at=timezone.now(),
            cancellation_reason="Synthetic spoilage after issuance",
        )
        program = fiscal_year.program_classifications.get(code="SYN-MFO-01")
        with self.assertRaisesMessage(ValidationError, "modification window is closed"):
            begin_foundation_amendment(program, self.preparer, "Attempted change after check issue")

    def test_opening_csv_rejects_bad_rows_and_guided_correction_revalidates_with_zero_difference(self):
        fiscal_year = self._fiscal_foundation()
        batch = self._opening_batch(fiscal_year)
        staged = stage_opening_csv(batch, self.preparer, self._opening_file(invalid_account=True))
        self.assertEqual(staged.status, OpeningBalanceBatch.DRAFT)
        self.assertEqual(staged.validation_summary["error_row_count"], 1)
        rejected = staged.rows.get(validation_status=OpeningBalanceRow.ERROR)
        self.assertIn("BAD-ACCOUNT", rejected.validation_errors[0])

        correct_opening_row(
            rejected,
            self.preparer,
            values={
                "raw_fund_code": self.fund.code,
                "raw_account_code": self.revenue.code,
                "raw_responsibility_center_code": self.center.code,
                "raw_debit": "",
                "raw_credit": "100.00",
                "subsidiary_reference": "SYN-EQUITY",
                "memo": "Corrected opening offset",
            },
            reason="Correct the synthetic account code against the reviewed opening schedule.",
        )
        validated = validate_opening_batch(batch, self.preparer)
        self.assertEqual(validated.status, OpeningBalanceBatch.VALIDATED)
        self.assertEqual(validated.validation_summary["debit"], "100.00")
        self.assertEqual(validated.validation_summary["credit"], "100.00")
        self.assertEqual(validated.rows.filter(validation_status=OpeningBalanceRow.VALID).count(), 2)
        self.assertTrue(validated.events.filter(action="row_corrected").exists())

    def test_opening_batch_requires_independent_approval_then_posts_and_reconciles_generated_jevs(self):
        fiscal_year = self._fiscal_foundation()
        fiscal_year.status = FiscalYear.APPROVED
        fiscal_year.save(update_fields=("status",))
        batch = self._opening_batch(fiscal_year, source_reference="SYN-OPEN-POST")
        stage_opening_csv(batch, self.preparer, self._opening_file())
        submitted = submit_opening_batch(batch, self.preparer)
        self._grant(self.preparer, "approve_opening_balances")
        with self.assertRaisesMessage(ValidationError, "different"):
            decide_opening_batch(
                submitted,
                self.preparer,
                decision=OpeningBalanceBatch.APPROVED,
                evidence_note="Synthetic self-approval attempt.",
            )
        approved = decide_opening_batch(
            submitted,
            self.setup_approver,
            decision=OpeningBalanceBatch.APPROVED,
            evidence_note="Reviewed synthetic schedule and matching control totals.",
        )
        posted = post_opening_batch(approved, self.poster)
        self.assertEqual(posted.status, OpeningBalanceBatch.POSTED)
        self.assertEqual(posted.postings.count(), 1)
        entry = posted.postings.get().entry
        self.assertEqual(entry.status, JournalEntry.POSTED)
        self.assertEqual(entry.source_type, "opening")
        self.assertEqual(entry.totals, (Decimal("100.00"), Decimal("100.00")))

        reconciled, summary = reconcile_opening_batch(posted, self.poster)
        self.assertTrue(summary["reconciled"])
        self.assertEqual(reconciled.status, OpeningBalanceBatch.RECONCILED)
        ensure_readiness_layers(fiscal_year)
        accounting_check = next(
            result for result in evaluate_fiscal_year_readiness(fiscal_year)["layers"]
            if result["record"].layer == FiscalYearReadinessApproval.ACCOUNTING
        )
        self.assertTrue(accounting_check["checks_passed"])
        self.assertTrue(reconciled.events.filter(action="reconciled").exists())

    def test_declared_opening_controls_can_be_corrected_with_reason_before_submission(self):
        fiscal_year = self._fiscal_foundation()
        batch = self._opening_batch(fiscal_year, source_reference="SYN-OPEN-CONTROL-FIX")
        corrected = correct_opening_batch(
            batch,
            self.preparer,
            values={
                "fiscal_year": fiscal_year,
                "period": self.period,
                "title": "Synthetic corrected opening schedule",
                "source_reference": "SYN-OPEN-CONTROL-FIX-V2",
                "expected_row_count": 2,
                "expected_debit": Decimal("100.00"),
                "expected_credit": Decimal("100.00"),
                "is_zero_balance_declaration": False,
            },
            reason="Correct the declared source reference and totals before independent review.",
        )
        self.assertEqual(corrected.source_reference, "SYN-OPEN-CONTROL-FIX-V2")
        self.assertEqual(corrected.state_version, 2)
        event = corrected.events.get(action="controls_corrected")
        self.assertEqual(event.snapshot["before"]["source_reference"], "SYN-OPEN-CONTROL-FIX")
        self.assertEqual(event.snapshot["after"]["source_reference"], "SYN-OPEN-CONTROL-FIX-V2")

    def test_approved_opening_batch_can_be_returned_for_correction_before_posting(self):
        fiscal_year = self._fiscal_foundation()
        batch = self._opening_batch(fiscal_year, source_reference="SYN-OPEN-RETURN")
        stage_opening_csv(batch, self.preparer, self._opening_file())
        submitted = submit_opening_batch(batch, self.preparer)
        approved = decide_opening_batch(
            submitted,
            self.setup_approver,
            decision=OpeningBalanceBatch.APPROVED,
            evidence_note="Synthetic pre-posting approval.",
        )
        returned = decide_opening_batch(
            approved,
            self.setup_approver,
            decision=OpeningBalanceBatch.RETURNED,
            evidence_note="Return the approved schedule after detecting a source-reference correction before posting.",
        )
        self.assertEqual(returned.status, OpeningBalanceBatch.RETURNED)
        self.assertIsNone(returned.approved_by_id)
        self.assertTrue(returned.events.filter(action="returned").exists())
        with self.assertRaisesMessage(ValidationError, "independently approved"):
            post_opening_batch(returned, self.poster)

    def test_explicit_zero_opening_follows_approval_posting_and_reconciliation_without_fake_rows(self):
        fiscal_year = self._fiscal_foundation()
        fiscal_year.status = FiscalYear.APPROVED
        fiscal_year.save(update_fields=("status",))
        batch = self._zero_opening(
            fiscal_year,
            source_reference="SYN-ZERO-WORKFLOW",
            status=OpeningBalanceBatch.DRAFT,
        )
        validated = validate_opening_batch(batch, self.preparer)
        submitted = submit_opening_batch(validated, self.preparer)
        approved = decide_opening_batch(
            submitted,
            self.setup_approver,
            decision=OpeningBalanceBatch.APPROVED,
            evidence_note="Confirmed the synthetic year has no brought-forward balances.",
        )
        posted = post_opening_batch(approved, self.poster)
        self.assertFalse(posted.postings.exists())
        reconciled, summary = reconcile_opening_batch(posted, self.poster)
        self.assertEqual(reconciled.status, OpeningBalanceBatch.RECONCILED)
        self.assertEqual(summary["posted_row_count"], 0)
        self.assertEqual(summary["debit_difference"], "0.00")

    def test_opening_workspace_is_guided_and_department_scoped(self):
        fiscal_year = self._fiscal_foundation()
        batch = self._opening_batch(fiscal_year, source_reference="SYN-OPEN-UI")
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("accounting:opening_workspace"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opening balances and control totals")
        self.assertContains(response, "SYN-OPEN-UI")
        response = self.client.get(reverse("accounting:opening_detail", args=(batch.public_id,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Declared and staged controls")
        self.assertContains(response, "Export controlled CSV")
        stage_opening_csv(batch, self.preparer, self._opening_file())
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            response = self.client.get(reverse("accounting:opening_export", args=(batch.public_id,)))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            exported = response.content.decode("utf-8")
            self.assertIn("opening_balance_row", exported)
            self.assertIn("SYN-OPEN-UI", exported)
            self.assertIn(self.cash.code, exported)
            artifacts = list(Path(export_root).rglob("*.csv"))
            self.assertEqual(len(artifacts), 1)
            self.assertIn(self.accounting_department.slug, artifacts[0].parts)
            self.assertIn(slugify(self.preparer.username), artifacts[0].parts)
            manifest = json.loads(Path(str(artifacts[0]) + ".manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["sha256"], response["X-GRAND-Export-SHA256"])
            self.assertEqual(manifest["metadata"]["batch_public_id"], str(batch.public_id))
            self.assertTrue(batch.events.filter(action="exported", actor_id=self.preparer.pk).exists())
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("accounting:opening_workspace"))
        self.assertNotContains(response, "SYN-OPEN-UI")
        response = self.client.get(reverse("accounting:opening_export", args=(batch.public_id,)))
        self.assertEqual(response.status_code, 404)

    def test_opening_starter_csv_is_available_and_plain(self):
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("accounting:opening_starter"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("opening-balance-starter.csv", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("fund_code,account_code,responsibility_center_code,debit,credit,subsidiary_reference,memo", content)
        self.assertIn("Replace/remove this sample opening row.", content)

    def test_accounting_models_are_routed_only_to_finance_database(self):
        self.assertEqual(JournalEntry.objects.db, "finance")
        self.assertEqual(AccountingPeriod.objects.db, "finance")
        self.assertEqual(Department.objects.db, "default")
        self.assertIn("accounting_journalentry", connections["finance"].introspection.table_names())
        self.assertNotIn("accounting_journalentry", connections["default"].introspection.table_names())

    def test_permissions_are_explicit_and_do_not_use_superuser_bypass(self):
        self.assertTrue(can_prepare_journals(self.preparer))
        self.assertFalse(can_post_journals(self.preparer))
        self.assertTrue(can_post_journals(self.poster))
        self.assertTrue(can_view_accounting(self.viewer))
        self.assertFalse(can_view_accounting(self.superuser))

    def test_balanced_entry_submits_and_independent_user_posts(self):
        entry = self._entry()
        submit_entry(entry, self.preparer)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.SUBMITTED)
        post_entry(entry, self.poster)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.POSTED)
        self.assertEqual(entry.posted_by_id, self.poster.pk)
        self.assertEqual(list(entry.audit_events.values_list("action", flat=True)), ["posted", "submitted"])

    def test_unbalanced_entry_is_rejected_before_submission(self):
        entry = self._entry(reference="SYN-JEV-0002", balanced=False)
        with self.assertRaisesMessage(ValidationError, "must balance"):
            submit_entry(entry, self.preparer)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.DRAFT)
        self.assertFalse(AccountingAuditEvent.objects.filter(entry=entry).exists())

    def test_maker_checker_prevents_preparer_from_posting_own_entry(self):
        entry = self._entry(reference="SYN-JEV-0003")
        submit_entry(entry, self.preparer)
        with self.assertRaisesMessage(ValidationError, "preparer cannot post"):
            post_entry(entry, self.preparer)

    def test_admin_exemption_allows_self_posting_and_is_snapshotted_in_ledger_audit(self):
        entry = self._entry(reference="SYN-JEV-EXEMPT")
        submit_entry(entry, self.preparer)
        policy = FinanceWorkflowExemption.objects.create(
            department=self.accounting_department,
            control_code=FinanceWorkflowExemption.JOURNAL_PREPARER_SELF_POSTING,
            subject_user=self.preparer,
            rationale="Synthetic staffing exception approved for UAT.",
            effective_from=date(2026, 1, 1),
            created_by=self.superuser,
        )
        post_entry(entry, self.preparer)
        entry.refresh_from_db()
        event = entry.audit_events.get(action="posted")
        self.assertEqual(entry.status, JournalEntry.POSTED)
        self.assertEqual(event.snapshot["workflow_exemption"]["policy_id"], policy.pk)

    def test_posted_entry_and_lines_are_immutable(self):
        entry = self._entry(reference="SYN-JEV-0004")
        submit_entry(entry, self.preparer)
        post_entry(entry, self.poster)
        entry.description = "Attempted overwrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            entry.save()
        line = entry.lines.first()
        line.memo = "Attempted overwrite"
        with self.assertRaisesMessage(ValidationError, "only while the entry is a draft"):
            line.save()

    def test_posted_entry_correction_creates_separately_approved_reversal(self):
        entry = self._entry(reference="SYN-JEV-REV-ORIGINAL")
        submit_entry(entry, self.preparer)
        post_entry(entry, self.poster)
        entry.refresh_from_db()

        reversal = create_reversal(
            entry,
            self.preparer,
            reference="SYN-JEV-REV-0001",
            entry_date=date(2027, 1, 20),
            period=self.period,
            reason="Synthetic correction with traceable lineage",
        )

        self.assertEqual(reversal.status, JournalEntry.DRAFT)
        self.assertEqual(reversal.reversal_of, entry)
        self.assertEqual(reversal.source_type, "reversal")
        original_lines = list(entry.lines.order_by("sequence"))
        reversal_lines = list(reversal.lines.order_by("sequence"))
        self.assertEqual(len(reversal_lines), len(original_lines))
        for original, reversed_line in zip(original_lines, reversal_lines):
            self.assertEqual(reversed_line.debit, original.credit)
            self.assertEqual(reversed_line.credit, original.debit)
            self.assertEqual(reversed_line.account_id, original.account_id)
        entry.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.POSTED)
        self.assertTrue(entry.audit_events.filter(action="reversal_prepared").exists())
        self.assertTrue(reversal.audit_events.filter(action="prepared_from_reversal").exists())

        with self.assertRaisesMessage(ValidationError, "already been prepared"):
            create_reversal(
                entry,
                self.preparer,
                reference="SYN-JEV-REV-0002",
                entry_date=date(2027, 1, 21),
                period=self.period,
                reason="Duplicate correction attempt",
            )

        discard_draft(reversal, self.preparer, "Wrong reversal reference")
        replacement = create_reversal(
            entry,
            self.preparer,
            reference="SYN-JEV-REV-0002",
            entry_date=date(2027, 1, 21),
            period=self.period,
            reason="Replacement correction attempt",
        )
        submit_entry(replacement, self.preparer)
        post_entry(replacement, self.poster)
        replacement.refresh_from_db()
        self.assertEqual(replacement.status, JournalEntry.POSTED)

    def test_subsidiary_detail_reverses_with_the_posted_control_line(self):
        entry = JournalEntry.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            reference="SYN-JEV-SUB-ORIGINAL",
            entry_date=date(2027, 1, 15), period=self.period, fund=self.fund,
            description="Synthetic payable recognition", created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        JournalLine.objects.create(
            entry=entry, sequence=1, account=self.cash, responsibility_center=self.center,
            debit=Decimal("100.00"), credit=Decimal("0.00"),
        )
        payable_line = JournalLine.objects.create(
            entry=entry, sequence=2, account=self.payable,
            debit=Decimal("0.00"), credit=Decimal("100.00"),
        )
        detail = JournalSubsidiaryLine.objects.create(
            entry=entry, journal_line=payable_line, category=JournalSubsidiaryLine.PAYABLE,
            reference_key="party-001", reference_label="Synthetic Supplier",
            source_code="ordinary-supplier", source_reference="synthetic-source",
            debit=Decimal("0.00"), credit=Decimal("100.00"),
        )
        submit_entry(entry, self.preparer)
        post_entry(entry, self.poster)

        reversal = create_reversal(
            entry, self.preparer, reference="SYN-JEV-SUB-REVERSAL",
            entry_date=date(2027, 1, 20), period=self.period,
            reason="Reverse the synthetic supplier recognition",
        )
        reversed_detail = reversal.subsidiary_lines.get()
        self.assertEqual(reversed_detail.reference_key, detail.reference_key)
        self.assertEqual(reversed_detail.debit, Decimal("100.00"))
        self.assertEqual(reversed_detail.credit, Decimal("0.00"))
        self.assertEqual(reversed_detail.source_snapshot["reversal_of_subsidiary_line"], detail.pk)

    def test_control_reconciliation_records_balanced_run_and_exposes_missing_detail(self):
        as_of_date = timezone.localdate()
        reconciliation_period = AccountingPeriod.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            fiscal_year=as_of_date.year,
            period_number=12,
            label="Synthetic reconciliation period",
            starts_on=date(as_of_date.year, 1, 1),
            ends_on=date(as_of_date.year, 12, 31),
        )
        PostingMapping.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            category=PostingMapping.PAYABLE, source_code="ordinary-supplier",
            label="Ordinary supplier payable", account=self.payable,
        )
        entry = JournalEntry.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            reference="SYN-JEV-SUB-CONTROL",
            entry_date=as_of_date, period=reconciliation_period, fund=self.fund,
            description="Synthetic subsidiary control", created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        JournalLine.objects.create(
            entry=entry, sequence=1, account=self.cash, debit=Decimal("100.00"), credit=Decimal("0.00"),
        )
        payable_line = JournalLine.objects.create(
            entry=entry, sequence=2, account=self.payable, debit=Decimal("0.00"), credit=Decimal("100.00"),
        )
        JournalSubsidiaryLine.objects.create(
            entry=entry, journal_line=payable_line, category=JournalSubsidiaryLine.PAYABLE,
            reference_key="party-002", reference_label="Reconciliation Supplier",
            source_code="ordinary-supplier", source_reference="synthetic-reconciliation-source",
            debit=Decimal("0.00"), credit=Decimal("100.00"),
        )
        submit_entry(entry, self.preparer)
        post_entry(entry, self.poster)

        snapshot, checksum = control_reconciliation_snapshot(
            self.accounting_department.pk, as_of_date,
        )
        self.assertTrue(snapshot["balanced"])
        self.assertEqual(Decimal(snapshot["rows"][0]["difference"]), Decimal("0.00"))
        run = run_control_reconciliation(
            self.accounting_department, self.poster, as_of_date,
        )
        self.assertEqual(run.result_checksum, checksum)
        with self.assertRaisesMessage(ValidationError, "immutable"):
            run.save()

        unmatched = JournalEntry.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            reference="SYN-JEV-SUB-UNMATCHED",
            entry_date=as_of_date, period=reconciliation_period, fund=self.fund,
            description="Synthetic manual control posting", created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        JournalLine.objects.create(
            entry=unmatched, sequence=1, account=self.cash, debit=Decimal("10.00"), credit=Decimal("0.00"),
        )
        JournalLine.objects.create(
            entry=unmatched, sequence=2, account=self.payable, debit=Decimal("0.00"), credit=Decimal("10.00"),
        )
        submit_entry(unmatched, self.preparer)
        post_entry(unmatched, self.poster)
        exception, _checksum = control_reconciliation_snapshot(
            self.accounting_department.pk, as_of_date,
        )
        self.assertFalse(exception["balanced"])
        self.assertEqual(Decimal(exception["absolute_difference_total"]), Decimal("10.00"))

        self.client.force_login(self.poster)
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            workspace = self.client.get(
                reverse("accounting:subsidiary_controls"), {"as_of": as_of_date.isoformat()},
            )
            schedule = self.client.get(
                reverse("accounting:subsidiary_export", args=(JournalSubsidiaryLine.PAYABLE,)),
                {"as_of": as_of_date.isoformat()},
            )
            evidence = self.client.get(
                reverse("accounting:subsidiary_reconciliation_export", args=(run.public_id,)),
            )
            self.assertContains(workspace, "Reconciliation Supplier")
            self.assertContains(workspace, "10.00")
            for response in (schedule, evidence):
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["X-GRAND-Export-Archived"], "true")
                artifact = Path(export_root) / response["X-GRAND-Export-Relative-Path"]
                self.assertTrue(artifact.exists())
                self.assertTrue(Path(str(artifact) + ".manifest.json").exists())

    def test_generated_journal_header_and_existing_lines_cannot_be_rewritten(self):
        entry = self._entry(reference="SYN-JEV-GENERATED")
        entry.source_type = "voucher"
        entry.source_reference = "synthetic-source-request"
        entry.source_snapshot = {"checksum": "synthetic"}
        entry.save()

        entry.description = "Attempted source rewrite"
        with self.assertRaisesMessage(ValidationError, "Source-generated journal headers are immutable"):
            entry.save()
        line = entry.lines.first()
        line.memo = "Attempted generated-line rewrite"
        with self.assertRaisesMessage(ValidationError, "Generated journal lines cannot be edited"):
            line.save()

    def test_workspace_and_entry_are_department_scoped(self):
        entry = self._entry(reference="SYN-JEV-0005")
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("accounting:workspace"))
        self.assertContains(response, entry.reference)
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("accounting:entry_detail", args=(entry.public_id,)))
        self.assertEqual(response.status_code, 404)

    def test_workflow_actions_are_post_only_and_role_bound(self):
        entry = self._entry(reference="SYN-JEV-0006")
        self.client.force_login(self.preparer)
        self.assertEqual(self.client.get(reverse("accounting:entry_submit", args=(entry.public_id,))).status_code, 405)
        self.assertEqual(self.client.post(reverse("accounting:entry_post", args=(entry.public_id,))).status_code, 403)

    def test_guided_forms_create_journal_and_line_in_finance_database(self):
        self.client.force_login(self.preparer)
        response = self.client.post(reverse("accounting:entry_create"), {
            "reference": "SYN-JEV-FORM",
            "entry_date": "2027-01-20",
            "period": self.period.pk,
            "fund": self.fund.pk,
            "source_type": "manual",
            "description": "Synthetic form-created journal",
        })
        self.assertEqual(response.status_code, 302)
        entry = JournalEntry.objects.get(reference="SYN-JEV-FORM")
        response = self.client.post(reverse("accounting:line_create", args=(entry.public_id,)), {
            "sequence": 1,
            "account": self.cash.pk,
            "responsibility_center": self.center.pk,
            "debit": "25.00",
            "credit": "0.00",
            "memo": "Synthetic debit",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(entry.lines.filter(sequence=1, debit=Decimal("25.00")).exists())

    def test_period_close_is_blocked_until_unposted_work_is_cleared(self):
        self._entry(reference="SYN-JEV-OPEN")
        self.client.force_login(self.preparer)
        response = self.client.post(reverse("accounting:period_close", args=(self.period.pk,)), follow=True)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, AccountingPeriod.OPEN)
        self.assertContains(response, "unposted journal")

    def test_ledger_shows_posted_entries_only(self):
        posted = self._entry(reference="SYN-JEV-POSTED")
        draft = self._entry(reference="SYN-JEV-DRAFT")
        submit_entry(posted, self.preparer)
        post_entry(posted, self.poster)
        self.client.force_login(self.poster)
        response = self.client.get(reverse("accounting:ledger"))
        self.assertContains(response, posted.reference)
        self.assertNotContains(response, draft.reference)

    def test_ledger_and_trial_balance_exports_are_trace_sync_ready(self):
        posted = self._entry(reference="SYN-JEV-EXPORT")
        submit_entry(posted, self.preparer)
        post_entry(posted, self.poster)
        self.client.force_login(self.poster)
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            ledger = self.client.get(reverse("accounting:ledger_export"), {"account": self.cash.pk})
            trial = self.client.get(reverse("accounting:trial_balance_export"))
            self.assertEqual(ledger.status_code, 200)
            self.assertEqual(trial.status_code, 200)
            self.assertEqual(ledger["X-GRAND-Export-Archived"], "true")
            self.assertEqual(trial["X-GRAND-Export-Archived"], "true")
            self.assertIn("SYN-JEV-EXPORT", ledger.content.decode("utf-8"))
            self.assertIn("SYN-101", trial.content.decode("utf-8"))
            for response in (ledger, trial):
                artifact = Path(export_root) / response["X-GRAND-Export-Relative-Path"]
                self.assertTrue(artifact.exists())
                self.assertTrue(Path(str(artifact) + ".manifest.json").exists())
            self.assertTrue((Path(export_root) / "GRAND_EXPORT_ROOT.json").exists())
        self.assertEqual(AccountingAuditEvent.objects.filter(action="report_exported").count(), 2)

    def test_bank_reconciliation_uses_governed_opening_jev_as_book_baseline(self):
        PostingMapping.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            category=PostingMapping.BANK,
            source_code="SYN-BANK-OPENING",
            label="Synthetic bank account with governed opening baseline",
            account=self.cash,
        )
        fiscal_year = self._fiscal_foundation()
        fiscal_year.status = FiscalYear.APPROVED
        fiscal_year.save(update_fields=("status",))
        opening = self._opening_batch(fiscal_year, source_reference="SYN-OPEN-BANK-BASELINE")
        opening = stage_opening_csv(opening, self.preparer, self._opening_file())
        opening = submit_opening_batch(opening, self.preparer)
        opening = decide_opening_batch(
            opening,
            self.setup_approver,
            decision=OpeningBalanceBatch.APPROVED,
            evidence_note="Reviewed the synthetic opening bank and offset controls.",
        )
        opening = post_opening_batch(opening, self.poster)
        opening, opening_summary = reconcile_opening_batch(opening, self.poster)
        self.assertTrue(opening_summary["reconciled"])
        opening_bank_line = opening.postings.get().entry.lines.get(account=self.cash)

        payment = JournalEntry.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            reference="CHK-BASE-001",
            entry_date=date(2027, 1, 15),
            period=self.period,
            fund=self.fund,
            source_type="opening",
            description="Synthetic check CHK-BASE-001 after governed opening",
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        JournalLine.objects.create(
            entry=payment, sequence=1, account=self.payable,
            debit=Decimal("20.00"), credit=Decimal("0.00"), memo="Settle synthetic payable",
        )
        payment_bank_line = JournalLine.objects.create(
            entry=payment, sequence=2, account=self.cash,
            debit=Decimal("0.00"), credit=Decimal("20.00"), memo="Check CHK-BASE-001",
        )
        submit_entry(payment, self.preparer)
        post_entry(payment, self.poster)
        self.assertFalse(hasattr(payment, "opening_balance_posting"))

        batch = BankStatementBatch.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            statement_reference="SYN-BRS-OPENING-2027-01",
            bank_account_code="SYN-BANK-OPENING",
            bank_name="Synthetic Government Bank",
            account_number_masked="••••0001",
            fund=self.fund,
            period_start=date(2027, 1, 1),
            period_end=date(2027, 1, 31),
            received_on=date(2027, 2, 2),
            opening_balance=Decimal("100.00"),
            closing_balance=Decimal("80.00"),
            expected_row_count=1,
            expected_deposits=Decimal("0.00"),
            expected_withdrawals=Decimal("20.00"),
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        statement = (
            "transaction_date,bank_reference,description,withdrawal,deposit,running_balance\n"
            "2027-01-15,CHK-BASE-001,Synthetic cleared check,20.00,,80.00\n"
        )
        batch = stage_bank_statement_csv(
            batch,
            self.preparer,
            SimpleUploadedFile(
                "statement-opening-baseline.csv",
                statement.encode("utf-8"),
                content_type="text/csv",
            ),
        )
        row = batch.rows.get(source_version=batch.source_version)
        with self.assertRaisesMessage(ValidationError, "posted bank-account journal line"):
            match_bank_statement_row(
                row,
                opening_bank_line,
                self.preparer,
                reason="An opening baseline must never be treated as a bank transaction.",
            )
        self.assertEqual(auto_match_bank_statement(batch, self.preparer), 1)
        self.assertEqual(
            BankStatementMatch.objects.get(batch=batch).journal_line_id,
            payment_bank_line.pk,
        )
        snapshot, _checksum, _rows, _matches, _lines, _items = bank_reconciliation_snapshot(batch)
        self.assertEqual(snapshot["book_balance"], "80.00")
        self.assertEqual(snapshot["unclassified_ledger_line_count"], 0)
        self.assertEqual(snapshot["difference"], "0.00")
        self.assertTrue(snapshot["ready_for_review"])

    def test_bank_statement_versions_match_outstanding_items_and_close_zero_difference_independently(self):
        PostingMapping.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            category=PostingMapping.BANK,
            source_code="SYN-BANK-MAIN",
            label="Synthetic main depository account",
            account=self.cash,
        )
        deposit_entry = JournalEntry.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            reference="DEP-001",
            entry_date=date(2027, 1, 10),
            period=self.period,
            fund=self.fund,
            description="Synthetic cleared deposit DEP-001",
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        deposit_line = JournalLine.objects.create(
            entry=deposit_entry, sequence=1, account=self.cash,
            debit=Decimal("1000.00"), credit=Decimal("0.00"), memo="DEP-001 bank receipt",
        )
        JournalLine.objects.create(
            entry=deposit_entry, sequence=2, account=self.revenue,
            debit=Decimal("0.00"), credit=Decimal("1000.00"), memo="Synthetic collection",
        )
        JournalEntry.objects.filter(pk=deposit_entry.pk).update(status=JournalEntry.POSTED)

        check_entry = JournalEntry.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            reference="CHK-0099",
            entry_date=date(2027, 1, 28),
            period=self.period,
            fund=self.fund,
            description="Synthetic issued check not yet cleared",
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        JournalLine.objects.create(
            entry=check_entry, sequence=1, account=self.payable,
            debit=Decimal("200.00"), credit=Decimal("0.00"), memo="Settle payable",
        )
        check_bank_line = JournalLine.objects.create(
            entry=check_entry, sequence=2, account=self.cash,
            debit=Decimal("0.00"), credit=Decimal("200.00"), memo="Check CHK-0099",
        )
        JournalEntry.objects.filter(pk=check_entry.pk).update(status=JournalEntry.POSTED)

        batch = BankStatementBatch.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            statement_reference="SYN-BRS-2027-01",
            bank_account_code="SYN-BANK-MAIN",
            bank_name="Synthetic Government Bank",
            account_number_masked="••••0099",
            fund=self.fund,
            period_start=date(2027, 1, 1),
            period_end=date(2027, 1, 31),
            received_on=date(2027, 2, 2),
            opening_balance=Decimal("0.00"),
            closing_balance=Decimal("1000.00"),
            expected_row_count=1,
            expected_deposits=Decimal("1000.00"),
            expected_withdrawals=Decimal("0.00"),
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        statement = (
            "transaction_date,bank_reference,description,withdrawal,deposit,running_balance\n"
            "2027-01-10,DEP-001,Synthetic cleared deposit,,1000.00,1000.00\n"
        )
        staged = stage_bank_statement_csv(
            batch, self.preparer,
            SimpleUploadedFile("statement-v1.csv", statement.encode("utf-8"), content_type="text/csv"),
        )
        self.assertEqual(staged.status, BankStatementBatch.VALIDATED)
        self.assertEqual(auto_match_bank_statement(staged, self.preparer), 1)
        first_row = staged.rows.get(source_version=1)
        first_match = BankStatementMatch.objects.get(statement_row=first_row, status=BankStatementMatch.ACTIVE)
        self.assertEqual(first_match.journal_line_id, deposit_line.pk)

        unmatch_bank_statement_row(first_row, self.preparer, reason="Recheck against corrected bank description.")
        staged = stage_bank_statement_csv(
            staged, self.preparer,
            SimpleUploadedFile("statement-v2.csv", statement.encode("utf-8"), content_type="text/csv"),
            change_reason="Bank supplied a corrected descriptive statement copy; amounts are unchanged.",
        )
        self.assertEqual(staged.source_version, 2)
        self.assertTrue(BankStatementMatch.objects.filter(pk=first_match.pk, status=BankStatementMatch.SUPERSEDED).exists())
        self.assertEqual(auto_match_bank_statement(staged, self.preparer), 1)
        classify_bank_outstanding(
            staged, check_bank_line, self.preparer,
            explanation="Issued near month-end and absent from the January bank statement.",
            evidence_reference="Check register CHK-0099",
            expected_clearance_date=date(2027, 2, 10),
        )
        unclassify_bank_outstanding(
            staged, check_bank_line, self.preparer,
            reason="Replace the timing evidence with the reviewed check-register reference.",
        )
        classify_bank_outstanding(
            staged, check_bank_line, self.preparer,
            explanation="Issued near month-end and absent from the January bank statement.",
            evidence_reference="Reviewed check register CHK-0099",
            expected_clearance_date=date(2027, 2, 10),
        )
        snapshot, _checksum, _rows, _matches, _lines, _items = bank_reconciliation_snapshot(staged)
        self.assertEqual(snapshot["adjusted_bank_balance"], "800.00")
        self.assertEqual(snapshot["book_balance"], "800.00")
        self.assertEqual(snapshot["difference"], "0.00")
        self.assertTrue(snapshot["ready_for_review"])
        self.assertTrue(BankOutstandingItem.objects.filter(
            batch=staged, journal_line=check_bank_line, kind=BankOutstandingItem.OUTSTANDING_CHECK,
        ).exists())

        submitted = submit_bank_reconciliation(staged, self.preparer)
        self._grant(self.preparer, "approve_bank_reconciliation")
        with self.assertRaisesMessage(ValidationError, "independent"):
            decide_bank_reconciliation(
                submitted, self.preparer, decision=BankStatementBatch.RECONCILED,
                evidence_note="Synthetic self-review must fail.",
            )
        reconciled = decide_bank_reconciliation(
            submitted, self.setup_approver, decision=BankStatementBatch.RECONCILED,
            evidence_note="Reviewed synthetic statement, GL, check register, and adjusted-balance schedule.",
        )
        self.assertEqual(reconciled.status, BankStatementBatch.RECONCILED)
        self.assertTrue(reconciled.reconciliation_checksum)
        reconciled.bank_name = "Attempted rewrite"
        with self.assertRaisesMessage(ValidationError, "immutable"):
            reconciled.save(update_fields=("bank_name",))
        reconciled.refresh_from_db()

        self.client.force_login(self.preparer)
        starter = self.client.get(reverse("accounting:bank_reconciliation_starter"))
        self.assertEqual(starter.status_code, 200)
        self.assertIn("transaction_date,bank_reference", starter.content.decode("utf-8"))
        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            response = self.client.get(reverse("accounting:bank_reconciliation_export", args=(batch.public_id,)))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-GRAND-Export-Archived"], "true")
            exported = response.content.decode("utf-8")
            self.assertIn("statement_row", exported)
            self.assertIn("ledger_outstanding", exported)
            self.assertTrue(list(Path(export_root).rglob("*bank-reconciliation-*.csv")))
        detail = self.client.get(reverse("accounting:bank_reconciliation_detail", args=(batch.public_id,)))
        self.assertContains(detail, "Adjusted-balance control")
        self.assertContains(detail, "CHK-0099")

        february = BankStatementBatch.objects.create(
            department_id=self.accounting_department.pk,
            department_label=self.accounting_department.name,
            statement_reference="SYN-BRS-2027-02",
            bank_account_code="SYN-BANK-MAIN",
            bank_name="Synthetic Government Bank",
            account_number_masked="••••0099",
            fund=self.fund,
            period_start=date(2027, 2, 1),
            period_end=date(2027, 2, 28),
            received_on=date(2027, 3, 2),
            opening_balance=Decimal("1000.00"),
            closing_balance=Decimal("800.00"),
            expected_row_count=1,
            expected_deposits=Decimal("0.00"),
            expected_withdrawals=Decimal("200.00"),
            created_by_id=self.preparer.pk,
            created_by_label=self.preparer.username,
        )
        february_statement = (
            "transaction_date,bank_reference,description,withdrawal,deposit,running_balance\n"
            "2027-02-05,CHK-0099,Synthetic check cleared,200.00,,800.00\n"
        )
        february = stage_bank_statement_csv(
            february, self.preparer,
            SimpleUploadedFile(
                "statement-february.csv", february_statement.encode("utf-8"), content_type="text/csv",
            ),
        )
        candidates = bank_outstanding_carry_candidates(february)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].batch_id, reconciled.pk)

        carry_response = self.client.post(reverse(
            "accounting:bank_reconciliation_carry_forward", args=(february.public_id,),
        ))
        self.assertEqual(carry_response.status_code, 302)
        carried = BankOutstandingItem.objects.get(
            batch=february, journal_line=check_bank_line, status=BankOutstandingItem.ACTIVE,
        )
        self.assertEqual(carried.carried_from.batch_id, reconciled.pk)
        self.assertEqual(carried.expected_clearance_date, date(2027, 2, 10))
        self.assertGreater(carried.age_days, 0)
        self.assertEqual(bank_outstanding_carry_candidates(february), [])
        carried_detail = self.client.get(reverse(
            "accounting:bank_reconciliation_detail", args=(february.public_id,),
        ))
        self.assertContains(carried_detail, "Carried from")
        self.assertContains(carried_detail, "SYN-BRS-2027-01")
        self.assertContains(carried_detail, "Past the recorded expected-clearance date")

        original_carried_checksum = carried.source_checksum
        carried = classify_bank_outstanding(
            february, check_bank_line, self.preparer,
            explanation="Updated after the February ageing review; the check remains a valid timing item.",
            evidence_reference="Reviewed check register CHK-0099 and February ageing note",
            expected_clearance_date=date(2027, 3, 10),
        )
        self.assertEqual(carried.carried_from.batch_id, reconciled.pk)
        self.assertEqual(carried.source_snapshot["replaces_item_checksum"], original_carried_checksum)

        february_row = february.rows.get(source_version=february.source_version)
        match_bank_statement_row(
            february_row, check_bank_line, self.preparer,
            reason="Matched to CHK-0099 after comparing the February bank statement and check register.",
        )
        january_item = BankOutstandingItem.objects.get(
            batch=reconciled, journal_line=check_bank_line, status=BankOutstandingItem.CLEARED,
        )
        carried.refresh_from_db()
        self.assertEqual(carried.status, BankOutstandingItem.CLEARED)
        self.assertEqual(carried.cleared_by_match_id, january_item.cleared_by_match_id)

        unmatch_bank_statement_row(
            february_row, self.preparer,
            reason="The first clearance link used the wrong supporting annotation; review and rematch.",
        )
        january_item.refresh_from_db()
        carried.refresh_from_db()
        self.assertEqual(january_item.status, BankOutstandingItem.ACTIVE)
        self.assertEqual(carried.status, BankOutstandingItem.ACTIVE)
        self.assertIsNone(carried.cleared_by_match_id)
        match_bank_statement_row(
            february_row, check_bank_line, self.preparer,
            reason="Rematched CHK-0099 using the corrected February bank annotation.",
        )
        january_snapshot_after_clearance, january_checksum_after_clearance, *_ = bank_reconciliation_snapshot(
            reconciled,
        )
        self.assertTrue(january_snapshot_after_clearance["ready_for_review"])
        self.assertEqual(january_checksum_after_clearance, reconciled.reconciliation_checksum)
        february_snapshot, _checksum, _rows, _matches, _lines, _items = bank_reconciliation_snapshot(february)
        self.assertEqual(february_snapshot["carried_forward_count"], 0)
        self.assertEqual(february_snapshot["adjusted_bank_balance"], "800.00")
        self.assertEqual(february_snapshot["book_balance"], "800.00")
        self.assertEqual(february_snapshot["difference"], "0.00")
        self.assertTrue(february_snapshot["ready_for_review"])

        with tempfile.TemporaryDirectory() as export_root, self.settings(GRAND_EXPORT_ROOT=export_root):
            exported_response = self.client.get(reverse(
                "accounting:bank_reconciliation_export", args=(february.public_id,),
            ))
            exported_text = exported_response.content.decode("utf-8")
            self.assertIn("carried_from_statement", exported_text)
            self.assertIn("cleared_by_statement", exported_text)
            self.assertIn("cleared_prior_statements", exported_text)
            self.assertIn("SYN-BRS-2027-01", exported_text)
            january_export = self.client.get(reverse(
                "accounting:bank_reconciliation_export", args=(reconciled.public_id,),
            )).content.decode("utf-8")
            self.assertIn("SYN-BRS-2027-02", january_export)

        submitted_february = submit_bank_reconciliation(february, self.preparer)
        reconciled_february = decide_bank_reconciliation(
            submitted_february, self.setup_approver, decision=BankStatementBatch.RECONCILED,
            evidence_note="Reviewed February statement, prior-item lineage, clearance, and zero-difference control.",
        )
        self.assertEqual(reconciled_february.status, BankStatementBatch.RECONCILED)
