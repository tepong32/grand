from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connections
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from profiles.models import EmployeeProfile
from finance.models import FinanceConfigurationItem, FinanceConfigurationRelease, FinanceWorkflowExemption
from vouchers.models import DisbursementVoucher, PaymentInstrument, VoucherCase

from .access import can_post_journals, can_prepare_journals, can_view_accounting
from .models import (
    AccountingAuditEvent, AccountingPeriod, FiscalYear, FiscalYearReadinessApproval,
    Fund, FundingSource, JournalEntry, JournalLine, LedgerAccount,
    ProgramActivityProject, ResponsibilityCenter,
)
from .services import (
    adopt_configuration_release, begin_foundation_amendment, create_reversal, decide_readiness_layer,
    discard_draft, ensure_readiness_layers,
    evaluate_fiscal_year_readiness, post_entry, submit_entry, transition_fiscal_year,
)


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
        cls._grant(cls.preparer, "view_accounting_workspace", "prepare_journal_entries", "manage_accounting_setup")
        cls._grant(cls.poster, "view_accounting_workspace", "post_journal_entries", "view_general_ledger")
        cls._grant(cls.setup_approver, "view_accounting_workspace", "approve_fiscal_readiness")
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

    def test_typed_fiscal_year_requires_independent_layered_readiness_before_activation(self):
        fiscal_year = self._fiscal_foundation()
        self._grant(self.preparer, "approve_fiscal_readiness")
        transition_fiscal_year(fiscal_year, "submit", self.preparer)
        with self.assertRaisesMessage(ValidationError, "different"):
            transition_fiscal_year(fiscal_year, "approve", self.preparer)
        transition_fiscal_year(fiscal_year, "approve", self.setup_approver)
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
        event = AccountingAuditEvent.objects.get(action="foundation_amended")
        self.assertEqual(event.snapshot["before"]["name"], "Synthetic public service MFO")
        self.assertEqual(event.snapshot["after"]["name"], "Corrected synthetic public service MFO")

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
