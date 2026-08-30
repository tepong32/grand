from datetime import date
from decimal import Decimal
import io
from pathlib import Path
import tempfile

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from departments.models import Department
from accounting.models import (
    AccountingPeriod, Fund, JournalEntry, JournalSubsidiaryLine, LedgerAccount,
    PostingMapping, ResponsibilityCenter,
)
from accounting.services import post_entry, submit_entry
from finance.models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceNumberingSequence,
    FinanceParty, FinancePartyClaimant, FinancePostingRule, FinancePostingRuleLine,
    FinanceSignatory, FinanceTemplateVersion, FinanceTransactionVariant, FinanceWorkflowExemption,
)
from finance.services import preflight_finance_template
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName
from records.services import RecordWorkflowError, source_department
from tracepoint.models import PacketItem, TrackedPacket

from .access import can_view_workbench
from .models import (
    PayableIntake, PaymentInstrument, VoucherCase, VoucherEvent, VoucherNonFinancialAmendment,
    VoucherNumberIssue, VoucherPostingRequest, VoucherPrintJob,
)
from .posting import materialize_voucher_journal, reconcile_posted_voucher_entry
from .services import (
    amend_nonfinancial_voucher, approve_override, cancel_check, certify_budget, create_budget_case,
    finalize_bank_advice, generate_shadow_dv, issue_check, link_tracepoint_item, prepare_voucher, record_signature_return,
    release_check, request_override, return_case, submit_checks_for_advice,
    validate_accounting, assemble_finance_packet, prepare_controlled_dv_print, record_dv_printed,
)


class VoucherWorkflowTests(TestCase):
    databases = {"default", "finance"}
    @classmethod
    def setUpClass(cls):
        cls._media_directory = tempfile.TemporaryDirectory()
        cls._export_directory = tempfile.TemporaryDirectory()
        cls._media_override = override_settings(
            MEDIA_ROOT=cls._media_directory.name,
            GRAND_EXPORT_ROOT=cls._export_directory.name,
        )
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        cls._export_directory.cleanup()
        cls._media_directory.cleanup()

    @classmethod
    def setUpTestData(cls):
        cls.budget = Department.objects.create(name="Municipal Budget Office", slug="voucher-budget")
        cls.accounting = Department.objects.create(name="Municipal Accounting Office", slug="voucher-accounting")
        cls.treasury = Department.objects.create(name="Municipal Treasury Office", slug="voucher-treasury")
        cls.requesting = Department.objects.create(name="General Services Office", slug="voucher-gso")

        cls.budget_user = cls.employee("budget.clerk", cls.budget, "view_voucher_workbench", "initiate_budget_case", "certify_budget_obligation", "return_voucher_case", "view_voucher_audit")
        cls.preparer = cls.employee("accounting.preparer", cls.accounting, "view_voucher_workbench", "prepare_disbursement_voucher", "control_dv_printing", "amend_nonfinancial_voucher", "track_wet_signatures", "link_tracepoint_custody", "validate_accounting_voucher", "finalize_bank_advice", "return_voucher_case", "view_voucher_audit")
        cls.validator = cls.employee("accounting.validator", cls.accounting, "view_voucher_workbench", "validate_accounting_voucher", "finalize_bank_advice", "approve_control_overrides", "return_voucher_case", "view_voucher_audit")
        cls.treasury_user = cls.employee("treasury.cashier", cls.treasury, "view_voucher_workbench", "issue_payment_instruments", "release_payment_instruments", "manage_payment_exceptions", "return_voucher_case", "view_voucher_audit")
        cls.requesting_user = cls.employee(
            "gso.requester", cls.requesting, "view_voucher_workbench", "initiate_payable_case", "view_voucher_audit",
        )
        cls.outsider = cls.employee("mpdo.viewer", cls.requesting)
        cls.superuser = cls.employee("platform.superuser", cls.accounting, is_superuser=True)
        cls.preparer.user_permissions.add(Permission.objects.get(content_type__app_label="finance", codename="manage_finance_templates"))
        cls.preparer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="tracepoint",
            codename__in=("view_tracepoint_workspace", "prepare_tracked_packets", "print_packet_labels"),
        ))
        cls.preparer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="accounting",
            codename__in=("view_accounting_workspace", "prepare_journal_entries", "manage_accounting_setup"),
        ))
        cls.validator.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="accounting",
            codename__in=("view_accounting_workspace", "post_journal_entries", "view_general_ledger"),
        ))

        owner = {"department_id": cls.accounting.pk, "department_label": cls.accounting.name}
        cls.accounting_period = AccountingPeriod.objects.create(
            **owner, fiscal_year=2026, period_number=8, label="August",
            starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
        )
        cls.accounting_fund = Fund.objects.create(**owner, code="general-fund", name="Synthetic General Fund")
        cls.accounting_center = ResponsibilityCenter.objects.create(**owner, code="gso", name="Synthetic GSO")
        cls.expense_account = LedgerAccount.objects.create(
            **owner, code="5-02-03", title="Synthetic office supplies expense", account_type="expense", normal_balance="debit",
        )
        cls.payable_account = LedgerAccount.objects.create(
            **owner, code="2-01-01", title="Synthetic accounts payable", account_type="liability", normal_balance="credit",
        )
        cls.withholding_account = LedgerAccount.objects.create(
            **owner, code="2-02-EWT", title="Synthetic withholding payable", account_type="liability", normal_balance="credit",
        )
        PostingMapping.objects.create(
            **owner, category=PostingMapping.PAYABLE, source_code="ordinary-supplier-claim",
            label="Ordinary supplier net payable", account=cls.payable_account,
        )
        PostingMapping.objects.create(
            **owner, category=PostingMapping.DEDUCTION, source_code="ewt",
            label="Expanded withholding tax", account=cls.withholding_account,
        )

        cls.release = FinanceConfigurationRelease.objects.create(
            department=cls.accounting, code="synthetic-pilot", version=1, title="Synthetic voucher pilot setup",
            fiscal_year=timezone.localdate().year, status="active", effective_from=date(2026, 1, 1),
            created_by=cls.preparer, activated_by=cls.validator, activated_at=timezone.now(),
        )
        for category, code, label in (
            ("transaction_type", "ordinary-supplier-claim", "Ordinary supplier claim"),
            ("fund", "general-fund", "General Fund"),
            ("responsibility_center", "gso", "General Services Office"),
            ("account_classification", "5-02-03", "Office supplies expense"),
            ("tax_rule", "ewt", "Expanded withholding tax"),
            ("document_requirement", "invoice", "Sales invoice"),
            ("bank_account", "gf-lbp", "General Fund — LandBank"),
        ):
            FinanceConfigurationItem.objects.create(
                department=cls.accounting, release=cls.release, category=category, code=code,
                version=1, label=label, status="active", effective_from=date(2026, 1, 1), created_by=cls.preparer,
            )
        cls.transaction_variant = FinanceTransactionVariant.objects.create(
            department=cls.accounting, release=cls.release, code="ordinary-supplier-claim",
            label="Ordinary supplier claim", kind=FinanceTransactionVariant.ORDINARY_SUPPLIER,
            description="Synthetic supplier payable route.",
            authority_reference="Synthetic locally reviewed accounting basis.",
            effective_from=date(2026, 1, 1), status="active", created_by=cls.preparer,
        )
        cls.recognition_rule = FinancePostingRule.objects.create(
            variant=cls.transaction_variant, code="ordinary-supplier-recognition",
            title="Recognize ordinary supplier claim", event_kind=FinancePostingRule.RECOGNITION,
            recognition_point=FinancePostingRule.DV_VALIDATION,
            description="Debit reviewed allocations and credit deductions plus the net payable.",
            authority_reference="Synthetic locally reviewed recognition policy.", created_by=cls.preparer,
        )
        FinancePostingRuleLine.objects.bulk_create((
            FinancePostingRuleLine(
                rule=cls.recognition_rule, sequence=10, label="Reviewed allocations",
                side=FinancePostingRuleLine.DEBIT,
                account_source=FinancePostingRuleLine.ALLOCATION_ACCOUNTS,
                amount_source=FinancePostingRuleLine.EACH_ALLOCATION,
            ),
            FinancePostingRuleLine(
                rule=cls.recognition_rule, sequence=20, label="Deductions payable",
                side=FinancePostingRuleLine.CREDIT,
                account_source=FinancePostingRuleLine.DEDUCTION_MAPPINGS,
                amount_source=FinancePostingRuleLine.EACH_DEDUCTION,
            ),
            FinancePostingRuleLine(
                rule=cls.recognition_rule, sequence=30, label="Net transaction payable",
                side=FinancePostingRuleLine.CREDIT,
                account_source=FinancePostingRuleLine.PAYABLE_MAPPING,
                amount_source=FinancePostingRuleLine.NET,
            ),
        ))
        for document_type, prefix in (("obr", "OBR-"), ("disbursement-voucher", "DV-")):
            FinanceNumberingSequence.objects.create(
                department=cls.accounting, release=cls.release, fiscal_year=timezone.localdate().year,
                document_type=document_type, prefix=prefix, padding=5, next_number=1,
                status="active", created_by=cls.preparer,
            )
        for role, name, position in (
            ("department-head", "Synthetic Department Head", "Department Head"),
            ("municipal-accountant", "Synthetic Municipal Accountant", "Municipal Accountant"),
        ):
            FinanceSignatory.objects.create(
                department=cls.accounting, release=cls.release, role_code=role, display_name=name,
                position_title=position, valid_from=date(2026, 1, 1), status="active", created_by=cls.preparer,
            )
        cls.party = FinanceParty.objects.create(
            department=cls.accounting, release=cls.release, code="synthetic-supplier", version=1,
            display_name="Synthetic Office Supply Co.", party_type=FinanceParty.SUPPLIER,
            effective_from=date(2026, 1, 1), status="active", created_by=cls.preparer,
        )
        cls.claimant = FinancePartyClaimant.objects.create(
            party=cls.party, display_name="Synthetic Authorized Claimant", relationship="Authorized representative",
            valid_from=date(2026, 1, 1), status="active", created_by=cls.preparer,
        )

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Voucher"
        for index, name in enumerate(FinanceTemplateVersion.REQUIRED_NAMES, start=1):
            if name == "GRAND_LINE_ITEMS":
                coordinate = "$A$12:$D$20"
            else:
                row = ((index - 1) // 4) + 1
                column = ((index - 1) % 4) + 1
                coordinate = f"${chr(64 + column)}${row}"
            workbook.defined_names.add(DefinedName(name, attr_text=f"'Voucher'!{coordinate}"))
        sheet.print_area = "A1:H30"
        stream = io.BytesIO(); workbook.save(stream)
        cls.template = FinanceTemplateVersion.objects.create(
            department=cls.accounting, release=cls.release, document_type="disbursement-voucher", version=1,
            title="Synthetic controlled DV", workbook=SimpleUploadedFile("synthetic-dv.xlsx", stream.getvalue()),
            controlled_print_required=False, effective_from=date(2026, 1, 1), created_by=cls.preparer,
        )
        preflight_finance_template(cls.template, cls.preparer)
        cls.template.status = "active"; cls.template.save(update_fields=("status",))

    @classmethod
    def employee(cls, username, department, *permissions, is_superuser=False):
        user = get_user_model().objects.create_user(
            username=username, email=f"{username}@example.gov", password="voucher-test-password",
            is_superuser=is_superuser, is_staff=is_superuser,
        )
        user.employeeprofile.assigned_department = department
        user.employeeprofile.position_title = "Synthetic Test Officer"
        user.employeeprofile.save()
        if permissions:
            user.user_permissions.add(*Permission.objects.filter(content_type__app_label="vouchers", codename__in=permissions))
        return user

    def create_case(self, key="create-case"):
        return create_budget_case(
            actor=self.budget_user, requesting_department=self.requesting, payee=self.party,
            particulars="Synthetic office supply payment", transaction_type="ordinary-supplier-claim",
            idempotency_key=key,
        )

    def budget_certify(self, case, key="budget-certify"):
        return certify_budget(
            case=case, actor=self.budget_user, obligation_date=date(2026, 8, 25),
            budget_source_reference="SYNTHETIC-APPROPRIATION-01",
            allocations=[{"fund_code": "general-fund", "responsibility_center_code": "gso", "account_code": "5-02-03", "amount": Decimal("1000.00")}],
            expected_version=case.state_version, idempotency_key=key,
        )

    def accounting_prepare(self, case, key="prepare-dv"):
        case.refresh_from_db()
        return prepare_voucher(
            case=case, actor=self.preparer, voucher_date=date(2026, 8, 25), gross_amount=Decimal("1000.00"),
            deductions=[{"code": "ewt", "description": "Expanded withholding tax", "amount": Decimal("100.00")}],
            line_description="Synthetic office supplies", line_account_code="5-02-03", document_codes=["invoice"],
            expected_version=case.state_version, idempotency_key=key,
        )

    def return_signatures(self, case):
        for index, task in enumerate(case.signature_tasks.order_by("sequence"), start=1):
            case.refresh_from_db()
            record_signature_return(
                case=case, task=task, actor=self.preparer, note="Wet-signed paper returned",
                expected_version=case.state_version, idempotency_key=f"signature-{index}",
            )
        case.refresh_from_db()
        return case

    def ready_for_treasury(self):
        case = self.create_case()
        self.budget_certify(case)
        self.accounting_prepare(case)
        self.return_signatures(case)
        validate_accounting(
            case=case, actor=self.validator, jev_number="JEV-00001", jev_date=date(2026, 8, 25), note="Validated",
            expected_version=case.state_version, idempotency_key="validate-accounting",
        )
        case.refresh_from_db()
        request = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        entry, _created = materialize_voucher_journal(request, self.preparer)
        same_entry, duplicate_created = materialize_voucher_journal(request, self.preparer)
        self.assertFalse(duplicate_created)
        self.assertEqual(same_entry.pk, entry.pk)
        self.assertEqual(
            JournalEntry.objects.filter(source_type="voucher", source_reference=str(request.public_id)).count(),
            1,
        )
        submit_entry(entry, self.preparer)
        entry.refresh_from_db()
        post_entry(entry, self.validator)
        entry.refresh_from_db()
        reconcile_posted_voucher_entry(entry, self.validator)
        case.refresh_from_db()
        return case

    def test_complete_supplier_disbursement_route_uses_one_shared_case(self):
        case = self.ready_for_treasury()
        posting_request = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        linked_entry = JournalEntry.objects.get(public_id=posting_request.accounting_entry_public_id)
        self.assertEqual(posting_request.status, VoucherPostingRequest.POSTED)
        self.assertEqual(posting_request.posting_rule, self.recognition_rule)
        self.assertEqual(posting_request.posting_rule_snapshot["event_kind"], FinancePostingRule.RECOGNITION)
        self.assertEqual(posting_request.payload["posting_rule_checksum"], posting_request.posting_rule_checksum)
        self.assertEqual(linked_entry.source_snapshot["posting_rule_checksum"], posting_request.posting_rule_checksum)
        self.assertEqual(linked_entry.source_snapshot["posting_policy_mode"], "governed_snapshot")
        self.assertEqual(linked_entry.status, JournalEntry.POSTED)
        self.assertEqual(linked_entry.source_snapshot["voucher_case"], str(case.public_id))
        self.assertEqual(linked_entry.totals, (Decimal("1000.00"), Decimal("1000.00")))
        subsidiary = linked_entry.subsidiary_lines.order_by("category")
        self.assertEqual(subsidiary.count(), 2)
        payable = subsidiary.get(category=JournalSubsidiaryLine.PAYABLE)
        withholding = subsidiary.get(category=JournalSubsidiaryLine.WITHHOLDING)
        self.assertEqual(payable.reference_key, f"finance-party:{self.party.code}")
        self.assertEqual(payable.reference_label, self.party.display_name)
        self.assertEqual(payable.credit, Decimal("900.00"))
        self.assertEqual(withholding.reference_key, "ewt")
        self.assertEqual(withholding.credit, Decimal("100.00"))
        self.assertEqual(case.events.filter(action="grand_jev_posted").count(), 1)
        first = issue_check(
            case=case, actor=self.treasury_user, bank_account_code="gf-lbp", check_number="000101", amount=Decimal("400.00"),
            expected_version=case.state_version, idempotency_key="issue-check-1",
        )
        case.refresh_from_db()
        second = issue_check(
            case=case, actor=self.treasury_user, bank_account_code="gf-lbp", check_number="000102", amount=Decimal("500.00"),
            expected_version=case.state_version, idempotency_key="issue-check-2",
        )
        case.refresh_from_db()
        submit_checks_for_advice(case=case, actor=self.treasury_user, expected_version=case.state_version, idempotency_key="submit-checks")
        case.refresh_from_db()
        batch = finalize_bank_advice(
            case=case, actor=self.validator, advice_number="ADV-00001", advice_date=date(2026, 8, 25),
            expected_version=case.state_version, idempotency_key="finalize-advice",
        )
        self.assertEqual(batch.items.count(), 2)
        case.refresh_from_db(); first.refresh_from_db(); second.refresh_from_db()
        release_check(case=case, instrument=first, actor=self.treasury_user, claimant=self.claimant, receipt_reference="RECEIPT-1", expected_version=case.state_version, idempotency_key="release-1")
        case.refresh_from_db()
        release_check(case=case, instrument=second, actor=self.treasury_user, claimant=self.claimant, receipt_reference="RECEIPT-2", expected_version=case.state_version, idempotency_key="release-2")
        case.refresh_from_db()

        self.assertEqual(case.current_stage, VoucherCase.COMPLETED)
        self.assertEqual(case.payment_instruments.filter(status=PaymentInstrument.RELEASED).count(), 2)
        self.assertEqual(case.obligation.certified_amount, case.disbursement_voucher.gross_amount)
        self.assertEqual(case.disbursement_voucher.net_amount, Decimal("900.00"))
        self.assertEqual(case.events.filter(action="disbursement_completed").count(), 1)
        self.assertTrue(all(event.actor_department_id for event in case.events.all()))

    def test_dv_validation_does_not_collapse_prior_accrual_into_recognition(self):
        case = self.create_case("accrual-route-create")
        self.budget_certify(case, "accrual-route-budget")
        self.accounting_prepare(case, "accrual-route-prepare")
        self.return_signatures(case)
        PayableIntake.objects.create(
            case=case, claim_reference="SYN-ACCRUAL-CLAIM", claim_amount=Decimal("1000.00"),
            initial_allocation_amount=Decimal("1000.00"), initial_relationship_type=PayableIntake.FULL,
            evidence_reference="Synthetic reviewed accrual evidence.", status=PayableIntake.READY,
            recognition_decision=PayableIntake.ACCRUE_BEFORE_SETTLEMENT,
            recognition_basis="Synthetic policy requires recognition before settlement.",
            obligation_adjustment_decision=PayableIntake.NO_ADJUSTMENT,
            obligation_adjustment_basis="No obligation adjustment is required.",
            prepared_by=self.requesting_user,
        )
        with self.assertRaisesMessage(ValidationError, "requires an earlier accrual JEV"):
            validate_accounting(
                case=case, actor=self.validator, jev_number="JEV-ACCRUAL-WRONG",
                jev_date=date(2026, 8, 25), note="Must not collapse the accounting event.",
                expected_version=case.state_version, idempotency_key="accrual-route-validation",
            )
        self.assertFalse(case.posting_requests.exists())

    def test_posting_rule_snapshot_rejects_tampering(self):
        case = self.create_case("posting-snapshot-create")
        self.budget_certify(case, "posting-snapshot-budget")
        self.accounting_prepare(case, "posting-snapshot-prepare")
        self.return_signatures(case)
        validate_accounting(
            case=case, actor=self.validator, jev_number="JEV-SNAPSHOT-01",
            jev_date=date(2026, 8, 25), note="Pin governed posting evidence.",
            expected_version=case.state_version, idempotency_key="posting-snapshot-validation",
        )
        request = case.posting_requests.get()
        request.posting_rule_snapshot["title"] = "Silently changed rule"
        with self.assertRaisesMessage(ValidationError, "checksum does not match"):
            request.full_clean()
        VoucherPostingRequest.objects.filter(pk=request.pk).update(
            posting_rule_snapshot=request.posting_rule_snapshot,
        )
        request.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "posting-rule checksum"):
            materialize_voucher_journal(request, self.preparer)
        request.refresh_from_db()
        self.assertEqual(request.status, VoucherPostingRequest.FAILED)
        self.assertFalse(JournalEntry.objects.filter(source_reference=str(request.public_id)).exists())

    def test_posted_jev_requires_reversal_instead_of_voucher_rewrite(self):
        case = self.ready_for_treasury()
        with self.assertRaisesMessage(ValidationError, "already has a posted JEV"):
            return_case(
                case=case,
                actor=self.validator,
                target_stage=VoucherCase.ACCOUNTING_VALIDATION,
                reason="Attempted rewrite after ledger posting",
                expected_version=case.state_version,
                idempotency_key="posted-jev-return-denied",
            )

    def test_discarded_generated_jev_leaves_repair_route_back_to_validation(self):
        case = self.create_case("discard-source-create")
        self.budget_certify(case, "discard-source-budget")
        self.accounting_prepare(case, "discard-source-prepare")
        self.return_signatures(case)
        validate_accounting(
            case=case,
            actor=self.validator,
            jev_number="JEV-DISCARD-01",
            jev_date=date(2026, 8, 25),
            note="Synthetic draft requiring correction",
            expected_version=case.state_version,
            idempotency_key="discard-source-validate",
        )
        case.refresh_from_db()
        posting_request = case.posting_requests.get(kind=VoucherPostingRequest.RECOGNITION)
        entry, _created = materialize_voucher_journal(posting_request, self.preparer)

        self.client.force_login(self.preparer)
        response = self.client.post(
            reverse("accounting:entry_discard", args=(entry.public_id,)),
            {"reason": "Correct the source voucher and regenerate"},
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        posting_request.refresh_from_db()
        self.assertEqual(entry.status, JournalEntry.VOIDED)
        self.assertEqual(posting_request.status, VoucherPostingRequest.CANCELLED)

        return_case(
            case=case,
            actor=self.validator,
            target_stage=VoucherCase.ACCOUNTING_VALIDATION,
            reason="Correct the source voucher before a new posting request",
            expected_version=case.state_version,
            idempotency_key="discard-source-return",
        )
        case.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_VALIDATION)

    def test_segregation_of_duties_requires_separately_approved_override(self):
        case = self.create_case("sod-create")
        self.budget_certify(case, "sod-budget")
        self.accounting_prepare(case, "sod-prepare")
        self.return_signatures(case)
        with self.assertRaises(ValidationError):
            validate_accounting(
                case=case, actor=self.preparer, jev_number="JEV-SOD", jev_date=date(2026, 8, 25), note="",
                expected_version=case.state_version, idempotency_key="sod-denied",
            )
        override = request_override(case=case, actor=self.preparer, action_code="accounting-self-validation", reason="Emergency staffing shortage")
        approve_override(override=override, actor=self.validator)
        validate_accounting(
            case=case, actor=self.preparer, jev_number="JEV-SOD", jev_date=date(2026, 8, 25), note="Emergency override used",
            expected_version=case.state_version, idempotency_key="sod-approved",
        )
        override.refresh_from_db(); case.refresh_from_db()
        self.assertEqual(override.status, "used")
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_POSTING)
        self.assertEqual(case.posting_requests.get().status, VoucherPostingRequest.PENDING)

    def test_admin_exemption_allows_dv_preparer_self_validation_with_audit_evidence(self):
        case = self.create_case("policy-validation-create")
        self.budget_certify(case, "policy-validation-budget")
        self.accounting_prepare(case, "policy-validation-prepare")
        self.return_signatures(case)
        policy = FinanceWorkflowExemption.objects.create(
            department=self.accounting,
            control_code=FinanceWorkflowExemption.DV_PREPARER_SELF_VALIDATION,
            subject_user=self.preparer,
            rationale="Synthetic small-office validation exemption.",
            effective_from=date(2026, 1, 1),
            created_by=self.validator,
        )
        validate_accounting(
            case=case,
            actor=self.preparer,
            jev_number="JEV-POLICY-01",
            jev_date=date(2026, 8, 25),
            note="Validated under configured UAT exemption",
            expected_version=case.state_version,
            idempotency_key="policy-self-validation",
        )
        event = case.events.get(action="accounting_validated")
        self.assertEqual(event.metadata["workflow_exemption"]["policy_id"], policy.pk)

    def test_admin_exemption_allows_budget_certifier_to_prepare_same_dv(self):
        self.budget_user.user_permissions.add(Permission.objects.get(
            content_type__app_label="vouchers", codename="prepare_disbursement_voucher",
        ))
        case = self.create_case("policy-budget-create")
        self.budget_certify(case, "policy-budget-certify")
        policy = FinanceWorkflowExemption.objects.create(
            department=self.budget,
            control_code=FinanceWorkflowExemption.BUDGET_CERTIFIER_DV_PREPARATION,
            subject_user=self.budget_user,
            rationale="Synthetic combined Budget/DV role for UAT.",
            effective_from=date(2026, 1, 1),
            created_by=self.validator,
        )
        case.refresh_from_db()
        prepare_voucher(
            case=case,
            actor=self.budget_user,
            voucher_date=date(2026, 8, 25),
            gross_amount=Decimal("1000.00"),
            deductions=[],
            line_description="Synthetic office supplies",
            line_account_code="5-02-03",
            document_codes=["invoice"],
            expected_version=case.state_version,
            idempotency_key="policy-budget-prepare",
        )
        event = case.events.get(action="dv_prepared")
        self.assertEqual(event.metadata["workflow_exemption"]["policy_id"], policy.pk)

    def test_explicit_permissions_do_not_follow_superuser_status(self):
        self.assertFalse(can_view_workbench(self.superuser))
        with self.assertRaises(PermissionDenied):
            create_budget_case(
                actor=self.superuser, requesting_department=self.requesting, payee=self.party,
                particulars="Not authorized", transaction_type="ordinary-supplier-claim", idempotency_key="superuser-denied",
            )

    def test_stale_version_and_idempotent_numbering_protect_concurrent_actions(self):
        case = self.create_case("version-create")
        self.budget_certify(case, "version-budget")
        case.refresh_from_db()
        issued = VoucherNumberIssue.objects.get(case=case, document_type="obr")
        certify_budget(
            case=case, actor=self.budget_user, obligation_date=date(2026, 8, 25), budget_source_reference="ignored",
            allocations=[{"fund_code": "general-fund", "responsibility_center_code": "gso", "account_code": "", "amount": Decimal("5.00")}],
            expected_version=0, idempotency_key="version-budget",
        )
        self.assertEqual(VoucherNumberIssue.objects.filter(case=case, document_type="obr").count(), 1)
        self.assertEqual(VoucherNumberIssue.objects.get(case=case, document_type="obr").pk, issued.pk)
        with self.assertRaises(ValidationError):
            prepare_voucher(
                case=case, actor=self.preparer, voucher_date=date(2026, 8, 25), gross_amount=Decimal("1000.00"),
                deductions=[], line_description="Stale page", line_account_code="5-02-03", document_codes=["invoice"],
                expected_version=0, idempotency_key="wrong-version",
            )

    def test_return_and_cancel_preserve_case_and_check_history(self):
        case = self.ready_for_treasury()
        check = issue_check(
            case=case, actor=self.treasury_user, bank_account_code="gf-lbp", check_number="000201", amount=Decimal("900.00"),
            expected_version=case.state_version, idempotency_key="cancel-issue",
        )
        case.refresh_from_db()
        cancel_check(
            case=case, instrument=check, actor=self.treasury_user, reason="Synthetic spoiled check",
            expected_version=case.state_version, idempotency_key="cancel-check",
        )
        case.refresh_from_db(); check.refresh_from_db()
        self.assertEqual(check.status, PaymentInstrument.CANCELLED)
        self.assertEqual(case.current_stage, VoucherCase.TREASURY_CHECK_PREPARATION)
        self.assertTrue(case.events.filter(action="check_cancelled", reason="Synthetic spoiled check").exists())
        with self.assertRaises(ValidationError):
            issue_check(
                case=case, actor=self.treasury_user, bank_account_code="gf-lbp", check_number="000201", amount=Decimal("900.00"),
                expected_version=case.state_version, idempotency_key="reuse-cancelled-number",
            )
        replacement = issue_check(
            case=case, actor=self.treasury_user, bank_account_code="gf-lbp", check_number="000202", amount=Decimal("900.00"),
            replaces=check, expected_version=case.state_version, idempotency_key="replacement-check",
        )
        self.assertEqual(replacement.replaces, check)

    def test_date_and_signatory_amendment_keeps_amounts_and_posted_jev_before_check(self):
        case = self.ready_for_treasury()
        original_output = generate_shadow_dv(
            case=case,
            actor=self.preparer,
            idempotency_key="nonfinancial-original-output",
        )
        case.refresh_from_db()
        self.client.force_login(self.preparer)
        self.assertContains(
            self.client.get(reverse("vouchers:case_detail", args=(case.public_id,))),
            "Correct DV date / signatories",
        )
        voucher = case.disbursement_voucher
        original_voucher_id = voucher.pk
        original_dv_number = voucher.dv_number
        original_amounts = (voucher.gross_amount, voucher.total_deductions, voucher.net_amount)
        posting_request = case.posting_requests.get(status=VoucherPostingRequest.POSTED)
        entry = JournalEntry.objects.get(public_id=posting_request.accounting_entry_public_id)
        original_entry_snapshot = entry.source_snapshot.copy()
        municipal_accountant = FinanceSignatory.objects.get(
            department=self.accounting,
            release=self.release,
            role_code="municipal-accountant",
            display_name="Synthetic Municipal Accountant",
        )
        acting_head = FinanceSignatory.objects.create(
            department=self.accounting,
            release=self.release,
            role_code="department-head",
            display_name="Synthetic Acting Department Head",
            position_title="Acting Department Head",
            acting=True,
            valid_from=date(2026, 8, 26),
            status="active",
            created_by=self.preparer,
        )

        amendment = amend_nonfinancial_voucher(
            case=case,
            actor=self.preparer,
            voucher_date=date(2026, 8, 26),
            signatories=[acting_head, municipal_accountant],
            reason="Acting department head designated for the revised document date",
            expected_version=case.state_version,
            idempotency_key="nonfinancial-amendment",
        )
        case.refresh_from_db()
        voucher.refresh_from_db()
        entry.refresh_from_db()
        posting_request.refresh_from_db()
        self.assertEqual(case.current_stage, VoucherCase.AWAITING_SIGNATURES)
        self.assertEqual(voucher.pk, original_voucher_id)
        self.assertEqual(voucher.dv_number, original_dv_number)
        self.assertEqual((voucher.gross_amount, voucher.total_deductions, voucher.net_amount), original_amounts)
        self.assertEqual(voucher.voucher_date, date(2026, 8, 26))
        self.assertEqual(entry.status, JournalEntry.POSTED)
        self.assertEqual(entry.source_snapshot, original_entry_snapshot)
        self.assertEqual(posting_request.status, VoucherPostingRequest.POSTED)
        self.assertEqual(amendment.financial_snapshot["net_amount"], "900.00")
        original_output.refresh_from_db()
        self.assertEqual(original_output.status, "superseded")
        self.assertEqual(
            case.signature_tasks.filter(round_number=amendment.signature_round_number).count(),
            2,
        )

        replacement_output = generate_shadow_dv(
            case=case,
            actor=self.preparer,
            idempotency_key="nonfinancial-replacement-output",
        )
        self.assertEqual(replacement_output.version, original_output.version + 1)
        self.assertEqual(replacement_output.input_snapshot["signature_round"], amendment.signature_round_number)
        self.assertIn(
            "Synthetic Acting Department Head",
            [item["display_name"] for item in replacement_output.input_snapshot["signatories"]],
        )
        case.refresh_from_db()

        for index, task in enumerate(
            case.signature_tasks.filter(round_number=amendment.signature_round_number).order_by("sequence"),
            start=1,
        ):
            case.refresh_from_db()
            record_signature_return(
                case=case,
                task=task,
                actor=self.preparer,
                note="Replacement wet signature returned",
                expected_version=case.state_version,
                idempotency_key=f"amendment-signature-{index}",
            )
        case.refresh_from_db()
        amendment.refresh_from_db()
        self.assertEqual(amendment.status, VoucherNonFinancialAmendment.COMPLETED)
        self.assertEqual(case.current_stage, VoucherCase.TREASURY_CHECK_PREPARATION)

        issue_check(
            case=case,
            actor=self.treasury_user,
            bank_account_code="gf-lbp",
            check_number="000250",
            amount=Decimal("900.00"),
            expected_version=case.state_version,
            idempotency_key="amendment-check-issued",
        )
        case.refresh_from_db()
        self.assertNotContains(
            self.client.get(reverse("vouchers:case_detail", args=(case.public_id,))),
            "Correct DV date / signatories",
        )
        with self.assertRaisesMessage(ValidationError, "check has already been issued"):
            amend_nonfinancial_voucher(
                case=case,
                actor=self.preparer,
                voucher_date=date(2026, 8, 27),
                signatories=[acting_head, municipal_accountant],
                reason="Attempted amendment after check issuance",
                expected_version=case.state_version,
                idempotency_key="amendment-after-check-denied",
            )

    def test_accounting_correction_keeps_dv_number_and_creates_new_signature_round(self):
        case = self.create_case("correction-create")
        self.budget_certify(case, "correction-budget")
        self.accounting_prepare(case, "correction-prepare-1")
        original_number = case.disbursement_voucher.dv_number
        self.return_signatures(case)
        return_case(
            case=case, actor=self.validator, target_stage=VoucherCase.ACCOUNTING_PREPARATION,
            reason="Correct the supporting description", expected_version=case.state_version,
            idempotency_key="correction-return",
        )
        case.refresh_from_db()
        prepare_voucher(
            case=case, actor=self.preparer, voucher_date=date(2026, 8, 25), gross_amount=Decimal("1000.00"),
            deductions=[{"code": "ewt", "description": "Expanded withholding tax", "amount": Decimal("100.00")}],
            line_description="Corrected synthetic office supplies", line_account_code="5-02-03", document_codes=["invoice"],
            expected_version=case.state_version, idempotency_key="correction-prepare-2",
        )
        case.refresh_from_db()
        self.assertEqual(case.disbursement_voucher.dv_number, original_number)
        self.assertEqual(case.signature_tasks.values("round_number").distinct().count(), 2)
        self.assertTrue(case.events.filter(action="dv_corrected", metadata__signature_round=2).exists())
        self.assertEqual(VoucherNumberIssue.objects.filter(case=case, document_type="disbursement-voucher").count(), 1)

    def test_workspace_and_case_ui_are_permission_aware_and_selection_driven(self):
        self.client.force_login(self.requesting_user)
        response = self.client.get(reverse("vouchers:case_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.party.display_name)
        self.assertContains(response, "Ordinary supplier claim")
        self.client.force_login(self.budget_user)
        self.assertEqual(self.client.get(reverse("vouchers:case_create")).status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("vouchers:workspace")).status_code, 403)

    def test_workspace_presentation_follows_the_assigned_finance_department(self):
        for user, title in (
            (self.budget_user, "Budget voucher workspace"),
            (self.preparer, "Accounting disbursement workspace"),
            (self.treasury_user, "Treasury disbursement workspace"),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("vouchers:workspace"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, title)
                self.assertContains(response, "Shared case history")

    def test_department_home_surfaces_the_matching_finance_queue(self):
        for user, card_title in (
            (self.budget_user, "Budget Voucher Workspace"),
            (self.preparer, "Accounting Disbursement Workspace"),
            (self.treasury_user, "Treasury Disbursement Workspace"),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("department_dashboard"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, card_title)
                self.assertContains(response, "Open Your Finance Queue")

    def test_read_only_uat_viewer_can_preview_offices_without_action_authority(self):
        call_command("configure_finance_roles", uat_viewer=[self.outsider.username])
        self.outsider.refresh_from_db()
        self.assertTrue(self.outsider.groups.filter(name="Finance UAT Viewer").exists())
        self.assertFalse(self.outsider.has_perm("vouchers.initiate_budget_case"))

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("vouchers:workspace") + "?office=treasury")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Treasury disbursement workspace")
        self.assertContains(response, "Read-only Finance UAT viewer")
        self.assertContains(response, "Preview office experience")
        self.assertEqual(self.client.get(reverse("vouchers:case_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("finance:workspace")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounting:workspace")).status_code, 200)

    def test_admin_exposes_curated_read_only_finance_evidence_only(self):
        voucher_models = {
            model._meta.model_name
            for model in admin.site._registry
            if model._meta.app_label == "vouchers"
        }
        finance_models = {
            model._meta.model_name
            for model in admin.site._registry
            if model._meta.app_label == "finance"
        }
        self.assertEqual(
            voucher_models,
            {"vouchercase", "voucherevent", "vouchernonfinancialamendment"},
        )
        self.assertEqual(
            finance_models,
            {"financeconfigurationrelease", "financeworkflowexemption", "financeauditevent"},
        )

    def test_shadow_dv_output_pins_template_snapshot_and_checksum(self):
        case = self.create_case("output-create")
        self.budget_certify(case, "output-budget")
        self.accounting_prepare(case, "output-prepare")
        case.refresh_from_db()
        output = generate_shadow_dv(case=case, actor=self.preparer, idempotency_key="output-generate")
        self.assertEqual(output.status, "shadow")
        self.assertEqual(output.template, self.template)
        self.assertEqual(len(output.checksum), 64)
        self.assertEqual(output.input_snapshot["dv_number"], case.disbursement_voucher.dv_number)
        self.assertEqual(output.input_snapshot["template_checksum"], self.template.workbook_checksum)
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("vouchers:output_download", kwargs={"public_id": case.public_id, "output_pk": output.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-GRAND-Output-Mode"], "shadow")
        self.assertEqual(response["X-GRAND-SHA256"], output.checksum)
        with self.assertRaises(RecordWorkflowError):
            source_department(output)

    def test_controlled_print_reprint_and_tracepoint_packet_gate_wet_signatures(self):
        self.template.controlled_print_required = True
        self.template.form_status = FinanceTemplateVersion.STARTER
        self.template.form_reference = "Editable DV starter for synthetic local comparison"
        self.template.default_copy_count = 2
        self.template.printer_instructions = "Accounting printer 1 · A4 bond · single-sided"
        self.template.save(update_fields=(
            "controlled_print_required", "form_status", "form_reference",
            "default_copy_count", "printer_instructions",
        ))
        case = self.create_case("f61-print-create")
        self.budget_certify(case, "f61-print-budget")
        self.accounting_prepare(case, "f61-print-dv")
        case.refresh_from_db()
        first_task = case.signature_tasks.filter(status="pending").first()
        with self.assertRaisesMessage(ValidationError, "Prepare and record the current signing copies"):
            record_signature_return(
                case=case, task=first_task, actor=self.preparer, note="Attempted before printing",
                expected_version=case.state_version, idempotency_key="f61-too-early-signature",
            )

        first_job = prepare_controlled_dv_print(
            case=case, actor=self.preparer, replacement_reason="",
            expected_version=case.state_version, idempotency_key="f61-ready-v1",
        )
        self.assertEqual(first_job.status, VoucherPrintJob.READY_TO_PRINT)
        self.assertEqual(first_job.output_checksum, first_job.output.checksum)
        self.assertEqual(first_job.archive_manifest["sha256"], first_job.output_checksum)
        self.assertTrue((Path(self._export_directory.name) / first_job.archive_manifest["relative_path"]).exists())
        case.refresh_from_db()
        first_job = record_dv_printed(
            case=case, actor=self.preparer, copy_count=2,
            printer_or_form_stock="Accounting printer 1 · A4 bond · single-sided",
            print_note="Alignment checked against the starter comparison copy.",
            expected_version=case.state_version, idempotency_key="f61-printed-v1",
        )
        case.refresh_from_db()
        first_job = assemble_finance_packet(
            case=case, actor=self.preparer, expected_document_count=4, expected_page_count=12,
            confidentiality=TrackedPacket.RESTRICTED,
            assembly_note="Two signing copies and referenced supporting papers counted.",
            expected_version=case.state_version, idempotency_key="f61-packet-v1",
        )
        case.refresh_from_db(); first_job.refresh_from_db()
        self.assertEqual(first_job.status, VoucherPrintJob.AWAITING_SIGNATURES)
        self.assertEqual(first_job.tracepoint_item, case.tracepoint_item)
        self.assertEqual(first_job.tracepoint_item.current_packet.checkpoints.count(), 2)
        self.assertNotIn("1000.00", first_job.tracepoint_item.current_packet.contents_manifest)
        self.assertEqual(first_job.custody_manifest["copy_count"], 2)

        replacement = prepare_controlled_dv_print(
            case=case, actor=self.preparer,
            replacement_reason="First copies were smudged during alignment checking; mark them do-not-sign.",
            expected_version=case.state_version, idempotency_key="f61-ready-v2",
        )
        first_job.refresh_from_db(); first_job.output.refresh_from_db(); case.refresh_from_db()
        self.assertEqual(first_job.status, VoucherPrintJob.SUPERSEDED)
        self.assertEqual(first_job.output.status, "superseded")
        self.assertEqual(replacement.version, 2)
        self.assertGreater(replacement.signature_round, first_job.signature_round)
        self.assertFalse(case.signature_tasks.filter(
            round_number=first_job.signature_round, status="pending",
        ).exists())

        replacement = record_dv_printed(
            case=case, actor=self.preparer, copy_count=2,
            printer_or_form_stock="Accounting printer 1 · A4 bond · single-sided",
            print_note="Replacement copies clear and aligned.",
            expected_version=case.state_version, idempotency_key="f61-printed-v2",
        )
        case.refresh_from_db()
        replacement = assemble_finance_packet(
            case=case, actor=self.preparer, expected_document_count=4, expected_page_count=12,
            confidentiality=TrackedPacket.RESTRICTED,
            assembly_note="Replacement signing copies placed in the existing controlled packet.",
            expected_version=case.state_version, idempotency_key="f61-packet-v2",
        )
        for index, task in enumerate(
            case.signature_tasks.filter(round_number=replacement.signature_round).order_by("sequence"),
            start=1,
        ):
            case.refresh_from_db()
            record_signature_return(
                case=case, task=task, actor=self.preparer, note="Signed replacement returned in packet.",
                expected_version=case.state_version, idempotency_key=f"f61-return-v2-{index}",
            )
        case.refresh_from_db(); replacement.refresh_from_db()
        self.assertEqual(replacement.status, VoucherPrintJob.SIGNED_PACKET_RETURNED)
        self.assertEqual(case.current_stage, VoucherCase.ACCOUNTING_VALIDATION)
        self.assertTrue(case.events.filter(action="finance_packet_assembled").exists())

        amendment = amend_nonfinancial_voucher(
            case=case,
            actor=self.preparer,
            voucher_date=date(2026, 8, 26),
            signatories=list(FinanceSignatory.objects.filter(release=self.release, status="active")),
            reason="Correct the DV date before check issuance and replace the signed paper packet.",
            expected_version=case.state_version,
            idempotency_key="f61-amend-after-return",
        )
        case.refresh_from_db(); replacement.refresh_from_db()
        self.assertEqual(replacement.status, VoucherPrintJob.SUPERSEDED)
        self.assertEqual(case.current_stage, VoucherCase.AWAITING_SIGNATURES)
        self.client.force_login(self.preparer)
        response = self.client.get(reverse("vouchers:case_detail", args=(case.public_id,)))
        self.assertContains(response, "Prepare replacement signing copy")

        successor = prepare_controlled_dv_print(
            case=case, actor=self.preparer, replacement_reason="",
            expected_version=case.state_version, idempotency_key="f61-ready-v3-after-amendment",
        )
        self.assertEqual(successor.supersedes, replacement)
        self.assertEqual(successor.signature_round, amendment.signature_round_number)
        self.assertEqual(successor.supersession_reason, replacement.supersession_reason)

    def test_tracepoint_link_records_only_custody_reference_not_financial_fields(self):
        case = self.create_case("tracepoint-create")
        packet = TrackedPacket.objects.create(
            tracking_number="TP-SYNTHETIC-001", title="Synthetic voucher bundle", contents_manifest="One synthetic voucher",
            status=TrackedPacket.ACTIVE, origin_department=self.accounting, prepared_by=self.preparer,
            final_destination_department=self.accounting, current_holder=self.preparer,
            current_department=self.accounting, activated_at=timezone.now(),
        )
        item = PacketItem.objects.create(
            reference_number="TP-ITEM-001", origin_packet=packet, current_packet=packet,
            title="Synthetic voucher item", created_by=self.preparer,
        )
        link_tracepoint_item(
            case=case, item=item, actor=self.preparer, expected_version=case.state_version,
            idempotency_key="link-tracepoint",
        )
        case.refresh_from_db()
        self.assertEqual(case.tracepoint_item, item)
        self.assertFalse(any(field.name in {"gross_amount", "net_amount", "certified_amount"} for field in PacketItem._meta.fields))
        self.assertTrue(case.events.filter(action="tracepoint_item_linked", metadata__reference_number="TP-ITEM-001").exists())
