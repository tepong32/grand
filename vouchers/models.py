from __future__ import annotations

import hashlib
import json
import uuid
import os
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from departments.models import Department
from finance.models import (
    FinanceConfigurationItem, FinanceConfigurationRelease, FinanceDocumentRule, FinanceParty, FinancePartyClaimant,
    FinanceNumberingSequence, FinancePostingRule, FinanceTemplateVersion, FinanceTransactionVariant,
)


MONEY = {"max_digits": 18, "decimal_places": 2, "default": Decimal("0.00")}


def voucher_tax_evidence_checksum(*, voucher, tax_rule_checksum, tax_base, amount, payee_name, payee_tax_identifier):
    payload = {
        "voucher_number": voucher.dv_number,
        "voucher_date": voucher.voucher_date.isoformat(),
        "tax_rule_checksum": tax_rule_checksum,
        "tax_base": str(Decimal(tax_base).quantize(Decimal("0.01"))),
        "amount": str(Decimal(amount).quantize(Decimal("0.01"))),
        "payee_name": payee_name,
        "payee_tax_identifier": payee_tax_identifier,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def voucher_output_path(instance, filename):
    safe_name = os.path.basename(filename)
    return f"vouchers/outputs/{instance.case.reference_code}/{instance.output_type}/v{instance.version}/{safe_name}"


class VoucherCase(models.Model):
    BINDING_NOT_APPLICABLE = "not_applicable"
    BINDING_PENDING = "pending"
    BINDING_LINKED = "linked"
    BINDING_FAILED = "failed"
    BINDING_CHOICES = (
        (BINDING_NOT_APPLICABLE, "Legacy / not linked"),
        (BINDING_PENDING, "Authoritative obligation link pending"),
        (BINDING_LINKED, "Authoritative obligation linked"),
        (BINDING_FAILED, "Authoritative obligation link needs reconciliation"),
    )
    BUDGET_DRAFT = "budget_draft"
    PAYABLE_PREPARATION = "payable_preparation"
    PAYABLE_REVIEW = "payable_review"
    ACCOUNTING_PREPARATION = "accounting_preparation"
    AWAITING_SIGNATURES = "awaiting_signatures"
    ACCOUNTING_VALIDATION = "accounting_validation"
    ACCOUNTING_POSTING = "accounting_posting"
    ACCOUNTING_EVENT_POSTING = "accounting_event_posting"
    ACCOUNTING_RETURNED_ITEM = "accounting_returned_item"
    TREASURY_CHECK_PREPARATION = "treasury_check_preparation"
    ACCOUNTING_BANK_ADVICE = "accounting_bank_advice"
    TREASURY_RELEASE = "treasury_release"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STAGE_CHOICES = (
        (BUDGET_DRAFT, "Budget allocation draft"),
        (PAYABLE_PREPARATION, "Requesting-office payable preparation"),
        (PAYABLE_REVIEW, "Accounting payable-readiness review"),
        (ACCOUNTING_PREPARATION, "Accounting DV preparation"),
        (AWAITING_SIGNATURES, "Awaiting wet signatures"),
        (ACCOUNTING_VALIDATION, "Accounting validation"),
        (ACCOUNTING_POSTING, "Accounting JEV posting"),
        (ACCOUNTING_EVENT_POSTING, "Accounting payment-event JEV posting"),
        (ACCOUNTING_RETURNED_ITEM, "Accounting returned-instrument review"),
        (TREASURY_CHECK_PREPARATION, "Treasury check preparation"),
        (ACCOUNTING_BANK_ADVICE, "Accounting bank advice"),
        (TREASURY_RELEASE, "Treasury check release"),
        (COMPLETED, "Released / completed"),
        (CANCELLED, "Cancelled"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    reference_code = models.CharField(max_length=40, unique=True, db_index=True)
    transaction_type = models.SlugField(max_length=80, default="ordinary-supplier-claim")
    requesting_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="requested_voucher_cases")
    current_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="current_voucher_cases")
    configuration_release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, null=True, blank=True, related_name="voucher_cases")
    voucher_template = models.ForeignKey(FinanceTemplateVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="voucher_cases")
    tracepoint_item = models.OneToOneField("tracepoint.PacketItem", on_delete=models.PROTECT, null=True, blank=True, related_name="voucher_case")
    payee = models.ForeignKey(FinanceParty, on_delete=models.PROTECT, null=True, blank=True, related_name="voucher_cases")
    payee_name = models.CharField(max_length=220)
    particulars = models.TextField()
    authoritative_obligation_public_id = models.UUIDField(null=True, blank=True, db_index=True)
    authoritative_obligation_number = models.CharField(max_length=100, blank=True)
    authoritative_obligation_checksum = models.CharField(max_length=64, blank=True)
    authoritative_obligation_amount = models.DecimalField(**MONEY)
    obligation_binding_status = models.CharField(max_length=20, choices=BINDING_CHOICES, default=BINDING_NOT_APPLICABLE)
    obligation_binding_error = models.TextField(blank=True)
    current_stage = models.CharField(max_length=40, choices=STAGE_CHOICES, default=BUDGET_DRAFT, db_index=True)
    state_version = models.PositiveIntegerField(default=0)
    shadow_mode = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_voucher_cases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-updated_at", "-pk")
        permissions = (
            ("view_voucher_workbench", "Can access the voucher workbench"),
            ("initiate_budget_case", "Can initiate budget voucher cases"),
            ("initiate_payable_case", "Can initiate payable cases from certified obligations"),
            ("review_payable_intake", "Can review payable readiness independently"),
            ("certify_budget_obligation", "Can certify budget obligations"),
            ("prepare_disbursement_voucher", "Can prepare disbursement vouchers"),
            ("control_dv_printing", "Can prepare and record controlled DV signing copies"),
            ("track_wet_signatures", "Can track wet signature circulation"),
            ("link_tracepoint_custody", "Can link voucher cases to TracePoint custody items"),
            ("validate_accounting_voucher", "Can validate accounting vouchers and JEV references"),
            ("issue_payment_instruments", "Can issue checks and payment instruments"),
            ("finalize_bank_advice", "Can finalize accountant bank advice"),
            ("view_bank_advice", "Can view bank-advice and returned-instrument evidence"),
            ("prepare_bank_advice", "Can prepare versioned bank-advice batches"),
            ("approve_bank_advice", "Can independently review bank-advice batches"),
            ("submit_bank_advice", "Can record bank-advice submission evidence"),
            ("acknowledge_bank_advice", "Can record bank acknowledgement or return evidence"),
            ("review_returned_instruments", "Can decide the Accounting treatment of returned instruments"),
            ("export_bank_advice", "Can export bank-advice and returned-item evidence"),
            ("release_payment_instruments", "Can release checks and payment instruments"),
            ("manage_payment_exceptions", "Can cancel and replace payment instruments"),
            ("view_cash_position", "Can view Treasury cash positions and instrument ageing"),
            ("prepare_cash_position", "Can prepare Treasury cash policies and positions"),
            ("approve_cash_position", "Can independently approve Treasury cash policies and positions"),
            ("export_cash_position", "Can export Treasury cash-position evidence"),
            ("return_voucher_case", "Can return a voucher case for correction"),
            ("amend_nonfinancial_voucher", "Can amend voucher dates and signatories before check issuance"),
            ("view_voucher_audit", "Can view voucher audit history"),
            ("approve_control_overrides", "Can approve voucher control overrides"),
        )

    def __str__(self):
        return f"{self.reference_code} — {self.payee_name}"

    def get_absolute_url(self):
        return reverse("vouchers:case_detail", kwargs={"public_id": self.public_id})

    def clean(self):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous:
                immutable = (
                    "public_id", "reference_code", "created_by_id", "created_at", "transaction_type",
                )
                if any(getattr(previous, field) != getattr(self, field) for field in immutable):
                    raise ValidationError("Voucher identity and transaction type are immutable.")


class VoucherCaseSavedView(models.Model):
    """Private, non-authoritative filters for the existing shared-case workbench."""

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="voucher_case_saved_views",
    )
    name = models.CharField(max_length=80)
    name_key = models.CharField(max_length=80, editable=False)
    filters = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name_key", "pk")
        constraints = (
            models.UniqueConstraint(fields=("owner", "name_key"), name="unique_private_voucher_case_view_name"),
        )

    def __str__(self):
        return self.name

    def clean(self):
        self.name = " ".join((self.name or "").split())
        if not self.name:
            raise ValidationError({"name": "Enter a short name for this private view."})
        self.name_key = self.name.casefold()[:80]
        if not isinstance(self.filters, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in self.filters.items()
        ):
            raise ValidationError({"filters": "Saved case-view filters must be plain text values."})

    def save(self, *args, **kwargs):
        self.name = " ".join((self.name or "").split())
        self.name_key = self.name.casefold()[:80]
        return super().save(*args, **kwargs)


class BudgetObligation(models.Model):
    case = models.OneToOneField(VoucherCase, on_delete=models.PROTECT, related_name="obligation")
    obr_number = models.CharField(max_length=60, db_index=True)
    obligation_date = models.DateField()
    budget_source_reference = models.CharField(max_length=160)
    certified_amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    certified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="certified_budget_obligations")
    certified_at = models.DateTimeField()
    source_kind = models.CharField(max_length=24, default="legacy_shadow")

    def __str__(self):
        return self.obr_number


class BudgetAllocationLine(models.Model):
    obligation = models.ForeignKey(BudgetObligation, on_delete=models.PROTECT, related_name="allocation_lines")
    fund_code = models.CharField(max_length=80)
    responsibility_center_code = models.CharField(max_length=80)
    account_code = models.CharField(max_length=80, blank=True)
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])

    class Meta:
        ordering = ("pk",)


class PayableIntake(models.Model):
    """Pinned requesting-office readiness evidence; authoritative source files remain in their owning systems."""

    DRAFT = "draft"
    FOR_REVIEW = "for_review"
    RETURNED = "returned"
    READY = "ready"
    STATUS_CHOICES = (
        (DRAFT, "Draft evidence intake"), (FOR_REVIEW, "For Accounting review"),
        (RETURNED, "Returned for correction"), (READY, "Payment-ready for DV preparation"),
    )
    FULL = "full"
    PARTIAL = "partial"
    PROGRESS = "progress"
    FINAL = "final"
    RELATIONSHIP_CHOICES = (
        (FULL, "One-time / full claim"),
        (PARTIAL, "Partial claim; balance remains"),
        (PROGRESS, "Progress billing; balance remains"),
        (FINAL, "Final claim; consume remaining balance"),
    )
    RECOGNIZE_WITH_DV = "recognize_with_dv"
    ACCRUE_BEFORE_SETTLEMENT = "accrue_before_settlement"
    SETTLE_EXISTING_PAYABLE = "settle_existing_payable"
    LIQUIDATION_DECISION = "liquidation_decision"
    RECOGNITION_CHOICES = (
        (RECOGNIZE_WITH_DV, "Recognize through the governed DV/JEV route"),
        (ACCRUE_BEFORE_SETTLEMENT, "Accrue payable before settlement"),
        (SETTLE_EXISTING_PAYABLE, "Settle a previously recognized payable"),
        (LIQUIDATION_DECISION, "Liquidation / non-payment recognition decision"),
    )
    NO_ADJUSTMENT = "no_adjustment"
    ADJUSTMENT_REFLECTED = "adjustment_reflected"
    BALANCE_RETAINED = "balance_retained"
    ADJUSTMENT_CHOICES = (
        (NO_ADJUSTMENT, "No obligation adjustment required"),
        (ADJUSTMENT_REFLECTED, "Governed pre-DV obligation adjustment reflected"),
        (BALANCE_RETAINED, "Partial/progress balance intentionally retained"),
    )

    case = models.OneToOneField(VoucherCase, on_delete=models.PROTECT, related_name="payable_intake")
    claim_reference = models.CharField(max_length=120)
    invoice_number = models.CharField(max_length=120, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    claim_amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    initial_allocation_amount = models.DecimalField(
        **MONEY, validators=[MinValueValidator(Decimal("0.01"))],
    )
    initial_relationship_type = models.CharField(
        max_length=16, choices=RELATIONSHIP_CHOICES, default=FULL,
    )
    relationship_policy_snapshot = models.JSONField(default=dict, blank=True)
    procurement_reference = models.CharField(max_length=180, blank=True)
    delivery_reference = models.CharField(max_length=180, blank=True)
    inspection_acceptance_reference = models.CharField(max_length=180, blank=True)
    evidence_reference = models.TextField()
    duplicate_warning = models.TextField(blank=True)
    duplicate_review_note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    decision_reason = models.TextField(blank=True)
    recognition_decision = models.CharField(max_length=32, choices=RECOGNITION_CHOICES, blank=True)
    recognition_basis = models.TextField(blank=True)
    obligation_adjustment_decision = models.CharField(max_length=32, choices=ADJUSTMENT_CHOICES, blank=True)
    obligation_adjustment_basis = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_payable_intakes",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_payable_intakes",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_payable_intakes")
    prepared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-prepared_at", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("case", "claim_reference"), name="unique_case_payable_claim_reference",
            ),
        )

    def clean(self):
        if self.initial_allocation_amount > self.claim_amount:
            raise ValidationError({
                "initial_allocation_amount": "The initial obligation allocation cannot exceed the payable claim control total."
            })
        if self.status == self.READY:
            missing = []
            if not self.recognition_decision:
                missing.append("recognition decision")
            if not self.recognition_basis.strip():
                missing.append("recognition basis")
            if not self.obligation_adjustment_decision:
                missing.append("obligation adjustment decision")
            if not self.obligation_adjustment_basis.strip():
                missing.append("obligation adjustment basis")
            if missing:
                raise ValidationError("Payment-ready intake is missing its " + ", ".join(missing) + ".")


class PayableDocumentEvidence(models.Model):
    PENDING = "pending"
    PRESENT = "present"
    NOT_APPLICABLE = "not_applicable"
    WAIVED = "waived"
    STATUS_CHOICES = (
        (PENDING, "Pending"), (PRESENT, "Present and referenced"),
        (NOT_APPLICABLE, "Condition not applicable"), (WAIVED, "Waived by reviewed authority"),
    )

    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="payable_document_evidence")
    source_rule = models.ForeignKey(FinanceDocumentRule, on_delete=models.PROTECT, related_name="payable_evidence")
    rule_public_id_snapshot = models.UUIDField()
    requirement_code = models.SlugField(max_length=80)
    requirement_label = models.CharField(max_length=180)
    evidence_kind = models.CharField(max_length=32)
    required = models.BooleanField()
    waiver_allowed = models.BooleanField()
    condition_description = models.TextField(blank=True)
    authority_reference = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    evidence_reference = models.TextField(blank=True)
    decision_note = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="recorded_payable_document_evidence",
    )
    recorded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("source_rule__display_order", "requirement_code")
        constraints = (
            models.UniqueConstraint(fields=("case", "requirement_code"), name="unique_payable_requirement_per_case"),
        )

    def clean(self):
        if self.status == self.PRESENT and not self.evidence_reference.strip():
            raise ValidationError({"evidence_reference": "Reference the reviewed evidence that is present."})
        if self.status == self.WAIVED:
            if not self.waiver_allowed:
                raise ValidationError({"status": "This requirement cannot be waived under the configured rule."})
            if not self.decision_note.strip():
                raise ValidationError({"decision_note": "Record the specific waiver decision and authority."})
        if self.status == self.NOT_APPLICABLE:
            if self.required:
                raise ValidationError({"status": "A required item must be present or use an explicitly allowed waiver."})
            if not self.decision_note.strip():
                raise ValidationError({"decision_note": "Explain why the configured condition does not apply."})


class DisbursementVoucher(models.Model):
    case = models.OneToOneField(VoucherCase, on_delete=models.PROTECT, related_name="disbursement_voucher")
    dv_number = models.CharField(max_length=60, unique=True)
    voucher_date = models.DateField()
    gross_amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    total_deductions = models.DecimalField(**MONEY)
    net_amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_disbursement_vouchers")
    prepared_at = models.DateTimeField()

    def clean(self):
        if self.net_amount != self.gross_amount - self.total_deductions:
            raise ValidationError({"net_amount": "Net amount must equal gross amount less total deductions."})


class VoucherLineItem(models.Model):
    voucher = models.ForeignKey(DisbursementVoucher, on_delete=models.PROTECT, related_name="line_items")
    description = models.CharField(max_length=240)
    account_code = models.CharField(max_length=80, blank=True)
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])


class VoucherDeduction(models.Model):
    voucher = models.ForeignKey(DisbursementVoucher, on_delete=models.PROTECT, related_name="deductions")
    code = models.CharField(max_length=80)
    description = models.CharField(max_length=180)
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    tax_rule_item = models.ForeignKey(
        FinanceConfigurationItem, on_delete=models.PROTECT, null=True, blank=True,
        related_name="voucher_deduction_snapshots",
    )
    tax_base = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    tax_rule_snapshot = models.JSONField(default=dict, blank=True)
    tax_rule_checksum = models.CharField(max_length=64, blank=True)
    tax_evidence_checksum = models.CharField(max_length=64, blank=True)
    payee_name_snapshot = models.CharField(max_length=220, blank=True)
    payee_tax_identifier_snapshot = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("voucher", "tax_rule_item"),
                condition=models.Q(tax_rule_item__isnull=False),
                name="unique_voucher_tax_rule",
            ),
        )

    def clean(self):
        governed = bool(
            self.tax_rule_item_id or self.tax_rule_snapshot or self.tax_rule_checksum
            or self.tax_evidence_checksum
        )
        if not governed:
            if self.tax_base is not None or self.payee_tax_identifier_snapshot or self.payee_name_snapshot:
                raise ValidationError("Tax evidence must be pinned to a governed Finance Setup tax rule.")
            return
        if not all((
            self.tax_rule_item_id, self.tax_rule_snapshot, self.tax_rule_checksum,
            self.tax_evidence_checksum, self.tax_base,
        )):
            raise ValidationError("A governed tax deduction requires its rule, base, snapshot, and checksum together.")
        if self.tax_rule_item.category != "tax_rule":
            raise ValidationError({"tax_rule_item": "Choose a Finance Setup tax or deduction rule."})
        if self.tax_rule_item.release_id != self.voucher.case.configuration_release_id:
            raise ValidationError({"tax_rule_item": "Use a tax rule from the voucher's pinned Finance Setup release."})
        encoded = json.dumps(self.tax_rule_snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != self.tax_rule_checksum:
            raise ValidationError("The immutable tax-rule checksum does not match its snapshot.")
        if self.tax_rule_snapshot.get("item_public_id") != str(self.tax_rule_item.public_id):
            raise ValidationError("The pinned tax-rule identity does not match its snapshot.")
        from finance.models import finance_tax_rule_snapshot
        live_snapshot, live_checksum = finance_tax_rule_snapshot(self.tax_rule_item)
        if self.tax_rule_snapshot != live_snapshot or self.tax_rule_checksum != live_checksum:
            raise ValidationError("The pinned tax rule no longer matches its approved Finance Setup source.")
        try:
            rate = Decimal(str(self.tax_rule_snapshot["rate_percent"]))
        except (InvalidOperation, KeyError, TypeError, ValueError):
            raise ValidationError("The pinned tax rule has no valid percentage rate.")
        rounding = {
            "half_up": ROUND_HALF_UP, "down": ROUND_DOWN, "up": ROUND_UP,
        }.get(self.tax_rule_snapshot.get("rounding_mode"))
        if not rounding:
            raise ValidationError("The pinned tax rule has no supported cent-rounding instruction.")
        expected = (self.tax_base * rate / Decimal("100")).quantize(
            Decimal("0.01"), rounding=rounding,
        )
        if self.amount != expected:
            raise ValidationError({"amount": f"The deduction must equal the reviewed base × rate: {expected:.2f}."})
        if not self.payee_name_snapshot.strip():
            raise ValidationError("A governed tax deduction requires the payee name snapshot.")
        if self.tax_rule_snapshot.get("requires_tax_identifier") and not self.payee_tax_identifier_snapshot.strip():
            raise ValidationError("The selected tax rule requires the payee's governed tax identifier.")
        expected_evidence_checksum = voucher_tax_evidence_checksum(
            voucher=self.voucher, tax_rule_checksum=self.tax_rule_checksum,
            tax_base=self.tax_base, amount=self.amount,
            payee_name=self.payee_name_snapshot,
            payee_tax_identifier=self.payee_tax_identifier_snapshot,
        )
        if self.tax_evidence_checksum != expected_evidence_checksum:
            raise ValidationError("The immutable voucher tax-evidence checksum does not match its facts.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Voucher deduction evidence is immutable. Return the pre-check case and recreate the DV evidence.")
        self.full_clean()
        return super().save(*args, **kwargs)


class VoucherDocumentCheck(models.Model):
    voucher = models.ForeignKey(DisbursementVoucher, on_delete=models.PROTECT, related_name="document_checks")
    requirement_code = models.CharField(max_length=80)
    label = models.CharField(max_length=180)
    present = models.BooleanField(default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="verified_voucher_documents")
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (models.UniqueConstraint(fields=("voucher", "requirement_code"), name="unique_voucher_document_requirement"),)


class WetSignatureTask(models.Model):
    PENDING = "pending"
    SIGNED_RETURNED = "signed_returned"
    DECLINED = "declined"
    STATUS_CHOICES = ((PENDING, "Awaiting wet signature"), (SIGNED_RETURNED, "Signed and returned"), (DECLINED, "Declined / returned"))

    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="signature_tasks")
    round_number = models.PositiveSmallIntegerField(default=1)
    sequence = models.PositiveSmallIntegerField()
    role_code = models.SlugField(max_length=80)
    signatory_name_snapshot = models.CharField(max_length=180)
    position_snapshot = models.CharField(max_length=180, blank=True)
    custody_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voucher_signature_custody_tasks",
    )
    custody_instructions = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=PENDING)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="recorded_wet_signatures")
    recorded_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("round_number", "sequence", "pk")
        constraints = (models.UniqueConstraint(fields=("case", "round_number", "sequence"), name="unique_voucher_signature_sequence"),)


class AccountingValidation(models.Model):
    ACCEPTED = "accepted"
    RETURNED = "returned"
    DECISION_CHOICES = ((ACCEPTED, "Accepted"), (RETURNED, "Returned for correction"))

    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="accounting_validations")
    decision = models.CharField(max_length=16, choices=DECISION_CHOICES)
    jev_number = models.CharField(max_length=60, blank=True)
    jev_date = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True)
    validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accounting_validations")
    validated_at = models.DateTimeField()


class VoucherNonFinancialAmendment(models.Model):
    AWAITING_SIGNATURES = "awaiting_signatures"
    COMPLETED = "completed"
    STATUS_CHOICES = (
        (AWAITING_SIGNATURES, "Awaiting replacement signatures"),
        (COMPLETED, "Completed"),
    )

    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="nonfinancial_amendments")
    version = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=AWAITING_SIGNATURES)
    prior_stage = models.CharField(max_length=40, choices=VoucherCase.STAGE_CHOICES)
    resume_stage = models.CharField(max_length=40, choices=VoucherCase.STAGE_CHOICES)
    signature_round_number = models.PositiveSmallIntegerField()
    old_voucher_date = models.DateField()
    new_voucher_date = models.DateField()
    old_signatories = models.JSONField(default=list)
    new_signatories = models.JSONField(default=list)
    financial_snapshot = models.JSONField(default=dict)
    reason = models.TextField()
    amended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voucher_nonfinancial_amendments")
    amended_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-version", "-pk")
        constraints = (
            models.UniqueConstraint(fields=("case", "version"), name="unique_voucher_nonfinancial_amendment_version"),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "case_id", "version", "prior_stage", "resume_stage", "signature_round_number",
                "old_voucher_date", "new_voucher_date", "old_signatories", "new_signatories",
                "financial_snapshot", "reason", "amended_by_id", "amended_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Non-financial amendment evidence is immutable.")
        return super().save(*args, **kwargs)


class VoucherPostingRequest(models.Model):
    RECOGNITION = "recognition"
    ADJUSTMENT = "adjustment"
    LIQUIDATION = "liquidation"
    PAYMENT = "payment"
    REMITTANCE = "remittance"
    CANCELLATION = "cancellation"
    REVERSAL = "reversal"
    REPLACEMENT = "replacement"
    KIND_CHOICES = FinancePostingRule.EVENT_KIND_CHOICES
    PENDING = "pending"
    MATERIALIZED = "materialized"
    POSTED = "posted"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_REQUIRED = "not_required"
    STATUS_CHOICES = (
        (PENDING, "Waiting for JEV creation"),
        (MATERIALIZED, "Draft JEV created"),
        (POSTED, "JEV posted"),
        (FAILED, "Needs intervention"),
        (CANCELLED, "Cancelled"),
        (NOT_REQUIRED, "No journal entry required"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="posting_requests")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=RECOGNITION)
    version = models.PositiveSmallIntegerField(default=1)
    jev_number = models.CharField(max_length=60, null=True, blank=True)
    jev_date = models.DateField()
    origin_stage = models.CharField(max_length=40, choices=VoucherCase.STAGE_CHOICES, blank=True)
    resume_stage = models.CharField(max_length=40, choices=VoucherCase.STAGE_CHOICES, blank=True)
    trigger_key = models.CharField(max_length=180, blank=True)
    finance_department_id = models.PositiveBigIntegerField()
    finance_department_label = models.CharField(max_length=160)
    posting_rule = models.ForeignKey(
        FinancePostingRule, on_delete=models.PROTECT, null=True, blank=True,
        related_name="voucher_posting_requests",
        help_text="Nullable only for posting requests created before governed F7 posting rules.",
    )
    posting_rule_public_id_snapshot = models.CharField(max_length=36, blank=True)
    posting_rule_snapshot = models.JSONField(default=dict, blank=True)
    posting_rule_checksum = models.CharField(max_length=64, blank=True)
    payload = models.JSONField(default=dict)
    payload_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    accounting_entry_public_id = models.UUIDField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voucher_posting_requests")
    requested_at = models.DateTimeField(auto_now_add=True)
    materialized_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-requested_at", "-pk")
        constraints = (
            models.UniqueConstraint(fields=("case", "kind", "version"), name="unique_voucher_posting_version"),
            models.UniqueConstraint(fields=("finance_department_id", "jev_number"), name="unique_voucher_jev_number"),
            models.UniqueConstraint(
                fields=("case", "kind", "trigger_key"),
                condition=~models.Q(trigger_key=""),
                name="unique_voucher_posting_trigger",
            ),
        )

    def __str__(self):
        return f"{self.jev_number or self.get_kind_display()} · {self.get_status_display()}"

    def clean(self):
        governed = bool(self.posting_rule_id or self.posting_rule_snapshot or self.posting_rule_checksum)
        if governed:
            if not self.posting_rule_id or not self.posting_rule_snapshot or not self.posting_rule_checksum:
                raise ValidationError("A governed posting request must pin the rule, its snapshot, and its checksum together.")
            if self.posting_rule_public_id_snapshot != str(self.posting_rule.public_id):
                raise ValidationError("The pinned posting-rule identity does not match the selected governed rule.")
            encoded = json.dumps(
                self.posting_rule_snapshot, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
            if hashlib.sha256(encoded).hexdigest() != self.posting_rule_checksum:
                raise ValidationError("The pinned posting-rule snapshot checksum does not match its content.")
            if self.kind != self.posting_rule_snapshot.get("event_kind"):
                raise ValidationError("The posting request event does not match the pinned posting rule.")
            effect = self.posting_rule_snapshot.get("accounting_effect", FinancePostingRule.JOURNAL_ENTRY)
            if effect == FinancePostingRule.JOURNAL_ENTRY and not self.jev_number:
                raise ValidationError("A journal-producing posting request requires a controlled JEV number.")
            if effect == FinancePostingRule.NO_ENTRY and self.jev_number:
                raise ValidationError("A no-entry accounting decision cannot reserve a JEV number.")
            if self.status == self.NOT_REQUIRED and effect != FinancePostingRule.NO_ENTRY:
                raise ValidationError("Only an explicit no-entry rule may close without a JEV.")
            if effect == FinancePostingRule.NO_ENTRY and self.status != self.NOT_REQUIRED:
                raise ValidationError("An explicit no-entry accounting decision must close as no journal entry required.")
        if self.resume_stage and self.resume_stage not in dict(VoucherCase.STAGE_CHOICES):
            raise ValidationError("Choose a valid workflow stage to resume after posting.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "case_id", "kind", "version", "jev_number", "jev_date", "origin_stage", "resume_stage",
                "trigger_key", "finance_department_id",
                "finance_department_label", "posting_rule_id", "posting_rule_public_id_snapshot",
                "posting_rule_snapshot", "posting_rule_checksum", "payload", "payload_checksum",
                "requested_by_id", "requested_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Posting request evidence is immutable. Create a new version instead.")
        return super().save(*args, **kwargs)


class PaymentInstrument(models.Model):
    DRAFT = "draft"
    ISSUED = "issued"
    ADVISED = "advised"
    RELEASED = "released"
    BANK_RETURNED = "bank_returned"
    CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (DRAFT, "Draft"), (ISSUED, "Issued"),
        (ADVISED, "Included in an approved advice"),
        (RELEASED, "Released"),
        (BANK_RETURNED, "Returned by bank after release"),
        (CANCELLED, "Cancelled / spoiled"),
    )

    NORMAL = "normal"
    UNCLAIMED = "unclaimed"
    STALE = "stale"
    RETURNED = "returned"
    OPERATIONAL_STATUS_CHOICES = (
        (NORMAL, "No open exception"),
        (UNCLAIMED, "Unclaimed / awaiting claimant action"),
        (STALE, "Stale / release blocked"),
        (RETURNED, "Returned by bank / resolution required"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="payment_instruments")
    bank_account_code = models.CharField(max_length=80)
    fund_code = models.CharField(max_length=80, blank=True)
    check_number = models.CharField(max_length=60)
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    operational_status = models.CharField(max_length=16, choices=OPERATIONAL_STATUS_CHOICES, default=NORMAL)
    replaces = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="replacement")
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="issued_payment_instruments")
    issued_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="cancelled_payment_instruments")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="released_payment_instruments")
    released_at = models.DateTimeField(null=True, blank=True)
    released_to = models.CharField(max_length=220, blank=True)
    released_to_claimant = models.ForeignKey(FinancePartyClaimant, on_delete=models.PROTECT, null=True, blank=True, related_name="released_payment_instruments")
    receipt_reference = models.CharField(max_length=120, blank=True)
    current_advice_batch = models.ForeignKey(
        "BankAdviceBatch", on_delete=models.PROTECT, null=True, blank=True,
        related_name="current_instruments",
        help_text="Latest governed advice version carrying this instrument.",
    )

    class Meta:
        ordering = ("check_number", "pk")
        constraints = (models.UniqueConstraint(fields=("bank_account_code", "check_number"), name="unique_check_per_bank_account"),)

    def __str__(self):
        return f"{self.check_number} — {self.amount}"


class BankAdviceBatch(models.Model):
    DRAFT = "draft"
    FOR_REVIEW = "for_review"
    REVIEW_RETURNED = "review_returned"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    RETURNED = "returned"
    SUPERSEDED = "superseded"
    FINALIZED = "finalized"  # Compatibility with pre-F8.4 rows during migration.
    STATUS_CHOICES = (
        (DRAFT, "Prepared draft"),
        (FOR_REVIEW, "For independent Accounting review"),
        (REVIEW_RETURNED, "Returned by Accounting reviewer"),
        (APPROVED, "Approved for bank submission"),
        (SUBMITTED, "Submitted to bank"),
        (ACKNOWLEDGED, "Acknowledged by bank"),
        (RETURNED, "Returned by bank for correction"),
        (SUPERSEDED, "Superseded by corrected version"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    advice_number = models.CharField(max_length=60)
    advice_date = models.DateField()
    bank_account_code = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    version = models.PositiveIntegerField(default=1)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor",
    )
    configuration_release = models.ForeignKey(
        FinanceConfigurationRelease, on_delete=models.PROTECT, null=True, blank=True,
        related_name="bank_advice_batches",
    )
    accounting_department = models.ForeignKey(
        Department, on_delete=models.PROTECT, null=True, blank=True,
        related_name="bank_advice_batches",
    )
    preparation_note = models.TextField(blank=True)
    authority_reference = models.TextField(blank=True)
    local_applicability_note = models.TextField(blank=True)
    item_count = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(**MONEY)
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_bank_advice_batches")
    created_at = models.DateTimeField(auto_now_add=True)
    review_submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="review_submitted_bank_advice_batches",
    )
    review_submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="approved_bank_advice_batches",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    bank_submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="bank_submitted_advice_batches",
    )
    bank_submitted_at = models.DateTimeField(null=True, blank=True)
    submission_reference = models.CharField(max_length=160, blank=True)
    submission_evidence_reference = models.TextField(blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="acknowledged_bank_advice_batches",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_reference = models.CharField(max_length=160, blank=True)
    acknowledgement_evidence_reference = models.TextField(blank=True)
    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="returned_bank_advice_batches",
    )
    returned_at = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(blank=True)
    return_evidence_reference = models.TextField(blank=True)
    state_version = models.PositiveIntegerField(default=1)
    # Retained for reproducibility of batches finalized before F8.4.
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="finalized_bank_advice_batches")
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-advice_date", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("advice_number", "version"), name="unique_bank_advice_number_version",
            ),
        )

    def __str__(self):
        return f"{self.advice_number} · v{self.version} · {self.bank_account_code}"

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "advice_number", "advice_date", "bank_account_code", "version", "supersedes_id",
                "configuration_release_id", "accounting_department_id", "preparation_note",
                "authority_reference", "local_applicability_note", "item_count", "total_amount",
                "snapshot_checksum", "created_by_id", "created_at",
            )
            if prior.status != self.DRAFT and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("A submitted bank-advice version is immutable. Prepare a reasoned successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Bank-advice history cannot be deleted. Prepare a successor version instead.")


class BankAdviceItem(models.Model):
    batch = models.ForeignKey(BankAdviceBatch, on_delete=models.PROTECT, related_name="items")
    instrument = models.ForeignKey(PaymentInstrument, on_delete=models.PROTECT, related_name="advice_items")
    instrument_public_id_snapshot = models.UUIDField(null=True, blank=True)
    check_number_snapshot = models.CharField(max_length=60, blank=True)
    fund_code_snapshot = models.CharField(max_length=80, blank=True)
    amount_snapshot = models.DecimalField(**MONEY)
    issued_at_snapshot = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("check_number_snapshot", "pk")
        constraints = (
            models.UniqueConstraint(fields=("batch", "instrument"), name="unique_instrument_per_advice_version"),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Bank-advice item snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Bank-advice item history cannot be deleted.")


class BankAdviceEvent(models.Model):
    batch = models.ForeignKey(BankAdviceBatch, on_delete=models.PROTECT, related_name="events")
    instrument = models.ForeignKey(
        PaymentInstrument, on_delete=models.PROTECT, null=True, blank=True,
        related_name="bank_advice_events",
    )
    action = models.CharField(max_length=80)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bank_advice_events")
    actor_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="bank_advice_events")
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Bank-advice history is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Bank-advice history cannot be deleted.")


class TreasuryCashPolicy(models.Model):
    OBSERVE = "observe"
    ENFORCE = "enforce"
    MODE_CHOICES = (
        (OBSERVE, "Observe and report only"),
        (ENFORCE, "Enforce cash availability at instrument issue"),
    )
    DRAFT = "draft"
    FOR_REVIEW = "for_review"
    ACTIVE = "active"
    RETURNED = "returned"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Draft"), (FOR_REVIEW, "For independent review"),
        (ACTIVE, "Active"), (RETURNED, "Returned for correction"),
        (SUPERSEDED, "Superseded"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    configuration_release = models.ForeignKey(
        FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="treasury_cash_policies",
    )
    treasury_department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="treasury_cash_policies",
    )
    bank_account_code = models.CharField(max_length=80)
    fund_code = models.CharField(max_length=80)
    mode = models.CharField(max_length=12, choices=MODE_CHOICES, default=OBSERVE)
    minimum_reserve = models.DecimalField(**MONEY)
    position_max_age_days = models.PositiveSmallIntegerField(default=35)
    unclaimed_after_days = models.PositiveSmallIntegerField(default=30)
    stale_after_days = models.PositiveSmallIntegerField(default=180)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    authority_reference = models.TextField()
    local_applicability_note = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    version = models.PositiveIntegerField(default=1)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_treasury_cash_policies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_treasury_cash_policies",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="approved_treasury_cash_policies",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    state_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("-effective_from", "bank_account_code", "fund_code", "-version")
        constraints = (
            models.UniqueConstraint(
                fields=("configuration_release", "bank_account_code", "fund_code", "version"),
                name="unique_treasury_cash_policy_version",
            ),
        )

    def __str__(self):
        return f"{self.bank_account_code} · {self.fund_code} · v{self.version}"

    def clean(self):
        if self.minimum_reserve < 0:
            raise ValidationError({"minimum_reserve": "The minimum reserve cannot be negative."})
        if self.stale_after_days <= self.unclaimed_after_days:
            raise ValidationError({"stale_after_days": "The stale threshold must be later than the unclaimed threshold."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the start date."})
        if self.supersedes_id and (
            self.supersedes.configuration_release_id != self.configuration_release_id
            or self.supersedes.bank_account_code != self.bank_account_code
            or self.supersedes.fund_code != self.fund_code
        ):
            raise ValidationError({"supersedes": "A successor must cover the same release, bank account, and fund."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = (
                "configuration_release_id", "treasury_department_id", "bank_account_code", "fund_code",
                "mode", "minimum_reserve", "position_max_age_days", "unclaimed_after_days",
                "stale_after_days", "effective_from", "effective_to", "authority_reference",
                "local_applicability_note", "version", "supersedes_id",
            )
            if prior and prior.status in (self.FOR_REVIEW, self.ACTIVE, self.RETURNED, self.SUPERSEDED) and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted, returned, or active cash-control policy evidence is immutable. Prepare a successor version.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "configuration_release_id", "treasury_department_id", "bank_account_code", "fund_code",
                "mode", "minimum_reserve", "position_max_age_days", "unclaimed_after_days",
                "stale_after_days", "effective_from", "effective_to", "authority_reference",
                "local_applicability_note", "version", "supersedes_id",
            )
            if prior.status in (self.FOR_REVIEW, self.ACTIVE, self.RETURNED, self.SUPERSEDED) and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted, returned, or active cash-control policy evidence is immutable. Prepare a successor version.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Cash-policy history is retained. Supersede the policy instead of deleting it.")


class TreasuryCashPosition(models.Model):
    DRAFT = "draft"
    FOR_REVIEW = "for_review"
    APPROVED = "approved"
    RETURNED = "returned"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Draft"), (FOR_REVIEW, "For independent review"),
        (APPROVED, "Approved"), (RETURNED, "Returned for correction"),
        (SUPERSEDED, "Superseded"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    policy = models.ForeignKey(TreasuryCashPolicy, on_delete=models.PROTECT, related_name="positions")
    as_of_date = models.DateField()
    reconciliation_public_id = models.UUIDField()
    reconciliation_checksum = models.CharField(max_length=64)
    reconciliation_period_end = models.DateField()
    reconciled_book_balance = models.DecimalField(**MONEY)
    confirmed_inflows = models.DecimalField(**MONEY)
    confirmed_outflows = models.DecimalField(**MONEY)
    other_holds = models.DecimalField(**MONEY)
    evidence_reference = models.TextField()
    preparation_note = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    version = models.PositiveIntegerField(default=1)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor",
    )
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_treasury_cash_positions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_treasury_cash_positions",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="approved_treasury_cash_positions",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    state_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("-as_of_date", "-version", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("policy", "as_of_date", "version"), name="unique_treasury_cash_position_version",
            ),
        )

    @property
    def approved_available_cash(self):
        return (
            self.reconciled_book_balance + self.confirmed_inflows - self.confirmed_outflows
            - self.other_holds - self.policy.minimum_reserve
        )

    def __str__(self):
        return f"{self.policy} · {self.as_of_date}"

    def clean(self):
        if min(self.confirmed_inflows, self.confirmed_outflows, self.other_holds) < 0:
            raise ValidationError("Cash-position additions, deductions, and holds cannot be negative.")
        if self.as_of_date < self.reconciliation_period_end:
            raise ValidationError({"as_of_date": "The cash position cannot predate its reconciled bank evidence."})
        if self.supersedes_id and self.supersedes.policy_id != self.policy_id:
            raise ValidationError({"supersedes": "A successor position must use the same cash-control policy."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = (
                "policy_id", "as_of_date", "reconciliation_public_id", "reconciliation_checksum",
                "reconciliation_period_end", "reconciled_book_balance", "confirmed_inflows",
                "confirmed_outflows", "other_holds", "evidence_reference", "preparation_note",
                "version", "supersedes_id", "snapshot_checksum",
            )
            if prior and prior.status in (self.FOR_REVIEW, self.APPROVED, self.RETURNED, self.SUPERSEDED) and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted, returned, or approved cash-position evidence is immutable. Prepare a successor snapshot.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "policy_id", "as_of_date", "reconciliation_public_id", "reconciliation_checksum",
                "reconciliation_period_end", "reconciled_book_balance", "confirmed_inflows",
                "confirmed_outflows", "other_holds", "evidence_reference", "preparation_note",
                "version", "supersedes_id", "snapshot_checksum",
            )
            if prior.status in (self.FOR_REVIEW, self.APPROVED, self.RETURNED, self.SUPERSEDED) and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted, returned, or approved cash-position evidence is immutable. Prepare a successor snapshot.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Cash-position history is retained. Prepare a successor instead of deleting it.")


class TreasuryCashReservation(models.Model):
    RESERVED = "reserved"
    CONSUMED = "consumed"
    RELEASED = "released"
    STATUS_CHOICES = (
        (RESERVED, "Reserved at issue"), (CONSUMED, "Consumed by release"),
        (RELEASED, "Released after cancellation"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    position = models.ForeignKey(TreasuryCashPosition, on_delete=models.PROTECT, related_name="reservations")
    instrument = models.OneToOneField(PaymentInstrument, on_delete=models.PROTECT, related_name="cash_reservation")
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=RESERVED)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_treasury_cash_reservations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="closed_treasury_cash_reservations",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            if prior.status != self.RESERVED:
                raise ValidationError("A closed cash reservation is immutable.")
            immutable = ("position_id", "instrument_id", "amount", "created_by_id", "created_at")
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Cash-reservation source evidence is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Cash reservations cannot be deleted.")


class PaymentInstrumentException(models.Model):
    UNCLAIMED = "unclaimed"
    STALE = "stale"
    RETURNED = "returned"
    KIND_CHOICES = (
        (UNCLAIMED, "Unclaimed instrument"),
        (STALE, "Stale instrument"),
        (RETURNED, "Returned by bank"),
    )
    OPEN = "open"
    RESOLVED = "resolved"
    STATUS_CHOICES = ((OPEN, "Open"), (RESOLVED, "Resolved"))

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    instrument = models.ForeignKey(PaymentInstrument, on_delete=models.PROTECT, related_name="exceptions")
    policy = models.ForeignKey(TreasuryCashPolicy, on_delete=models.PROTECT, related_name="instrument_exceptions")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    observed_on = models.DateField()
    reason = models.TextField()
    evidence_reference = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=OPEN)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_payment_instrument_exceptions",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="resolved_payment_instrument_exceptions",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True)

    class Meta:
        ordering = ("-observed_on", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("instrument", "kind"), condition=models.Q(status="open"),
                name="unique_open_instrument_exception_kind",
            ),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            if prior.status == self.RESOLVED:
                raise ValidationError("Resolved instrument exceptions are immutable.")
            immutable = (
                "instrument_id", "policy_id", "kind", "observed_on", "reason",
                "evidence_reference", "opened_by_id", "opened_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Instrument exception source evidence is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Instrument exception history cannot be deleted.")


class ReturnedInstrumentReview(models.Model):
    AWAITING_REVIEW = "awaiting_review"
    RETURNED_FOR_CLARIFICATION = "returned"
    AWAITING_POSTING = "awaiting_posting"
    READY_FOR_TREASURY = "ready_for_treasury"
    CLOSED = "closed"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (AWAITING_REVIEW, "Awaiting independent Accounting review"),
        (RETURNED_FOR_CLARIFICATION, "Returned to Treasury for clarification"),
        (AWAITING_POSTING, "Awaiting returned-item JEV posting"),
        (READY_FOR_TREASURY, "Accounting complete; replacement authorized"),
        (CLOSED, "Accounting complete; no replacement"),
        (SUPERSEDED, "Superseded by clarified version"),
    )
    REISSUE = "reissue"
    CLOSE_WITHOUT_REISSUE = "close"
    OUTCOME_CHOICES = (
        (REISSUE, "Authorize a controlled replacement instrument"),
        (CLOSE_WITHOUT_REISSUE, "Close without a replacement instrument"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    exception = models.ForeignKey(
        PaymentInstrumentException, on_delete=models.PROTECT, related_name="accounting_reviews",
    )
    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="returned_instrument_reviews")
    instrument = models.ForeignKey(
        PaymentInstrument, on_delete=models.PROTECT, related_name="returned_accounting_reviews",
    )
    original_payment_request = models.ForeignKey(
        VoucherPostingRequest, on_delete=models.PROTECT, null=True, blank=True,
        related_name="returned_instrument_source_reviews",
    )
    posting_request = models.OneToOneField(
        VoucherPostingRequest, on_delete=models.PROTECT, null=True, blank=True,
        related_name="returned_instrument_review",
    )
    status = models.CharField(max_length=28, choices=STATUS_CHOICES, default=AWAITING_REVIEW)
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES, blank=True)
    treasury_evidence_reference = models.TextField()
    treasury_note = models.TextField()
    accounting_decision_reason = models.TextField(blank=True)
    accounting_evidence_reference = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor",
    )
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_returned_instrument_reviews",
    )
    prepared_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_returned_instrument_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="closed_returned_instrument_reviews",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    state_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("-prepared_at", "-version", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("exception", "version"), name="unique_returned_instrument_review_version",
            ),
        )

    def __str__(self):
        return f"{self.instrument.check_number} · returned review v{self.version}"

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "exception_id", "case_id", "instrument_id", "original_payment_request_id",
                "treasury_evidence_reference", "treasury_note", "version", "supersedes_id",
                "prepared_by_id", "prepared_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Returned-instrument source evidence is immutable. Prepare a clarified successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Returned-instrument Accounting history cannot be deleted.")


class TreasuryCashEvent(models.Model):
    policy = models.ForeignKey(
        TreasuryCashPolicy, on_delete=models.PROTECT, null=True, blank=True, related_name="events",
    )
    position = models.ForeignKey(
        TreasuryCashPosition, on_delete=models.PROTECT, null=True, blank=True, related_name="events",
    )
    instrument = models.ForeignKey(
        PaymentInstrument, on_delete=models.PROTECT, null=True, blank=True, related_name="cash_events",
    )
    action = models.CharField(max_length=80)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="treasury_cash_events")
    actor_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="treasury_cash_events")
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Treasury cash history is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Treasury cash history cannot be deleted.")


class VoucherTask(models.Model):
    OPEN = "open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = ((OPEN, "Open"), (COMPLETED, "Completed"), (CANCELLED, "Cancelled"))

    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="tasks")
    stage = models.CharField(max_length=40, choices=VoucherCase.STAGE_CHOICES)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="voucher_tasks")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="voucher_tasks")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class FinanceFoundationIssuanceBoundary(models.Model):
    """Shared transaction-store lock for one Finance office and fiscal year."""

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_foundation_issuance_boundaries",
    )
    fiscal_year = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("department__name", "fiscal_year")
        constraints = (
            models.UniqueConstraint(
                fields=("department", "fiscal_year"),
                name="unique_finance_foundation_issuance_boundary",
            ),
        )

    def __str__(self):
        return f"{self.department} · FY {self.fiscal_year} issuance boundary"

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Finance issuance-boundary locks are permanent coordination records."
        )


class VoucherNumberIssue(models.Model):
    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="number_issues")
    sequence = models.ForeignKey("finance.FinanceNumberingSequence", on_delete=models.PROTECT, related_name="voucher_number_issues")
    document_type = models.SlugField(max_length=80)
    numeric_value = models.PositiveBigIntegerField()
    formatted_value = models.CharField(max_length=60)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voucher_number_issues")
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=("sequence", "numeric_value"), name="unique_issued_finance_number"),
            models.UniqueConstraint(fields=("case", "document_type"), name="unique_case_document_number"),
        )


class ControlOverride(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    USED = "used"
    REJECTED = "rejected"
    STATUS_CHOICES = ((PENDING, "Pending"), (APPROVED, "Approved"), (USED, "Used"), (REJECTED, "Rejected"))

    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="control_overrides")
    action_code = models.SlugField(max_length=80)
    reason = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_voucher_overrides")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_voucher_overrides")
    approved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING)


class VoucherEvent(models.Model):
    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="events")
    action = models.CharField(max_length=80)
    from_stage = models.CharField(max_length=40, blank=True)
    to_stage = models.CharField(max_length=40, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voucher_events")
    actor_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="voucher_events")
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    state_version = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = (models.UniqueConstraint(fields=("case", "idempotency_key"), name="unique_voucher_action_idempotency"),)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Voucher events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Voucher events cannot be deleted.")


class VoucherOutput(models.Model):
    SHADOW = "shadow"
    OFFICIAL = "official"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = ((SHADOW, "Shadow comparison"), (OFFICIAL, "Official"), (SUPERSEDED, "Superseded"))

    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="outputs")
    output_type = models.SlugField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    template = models.ForeignKey(FinanceTemplateVersion, on_delete=models.PROTECT, related_name="voucher_outputs")
    file = models.FileField(upload_to=voucher_output_path, max_length=500)
    checksum = models.CharField(max_length=64)
    input_snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=SHADOW)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="generated_voucher_outputs")
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("output_type", "-version")
        constraints = (models.UniqueConstraint(fields=("case", "output_type", "version"), name="unique_voucher_output_version"),)

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = ("case_id", "output_type", "version", "template_id", "checksum", "input_snapshot", "generated_by_id", "generated_at")
            if any(getattr(prior, field) != getattr(self, field) for field in immutable) or prior.file.name != self.file.name:
                raise ValidationError("Generated voucher output evidence is immutable. Create a new version.")
        return super().save(*args, **kwargs)


class TreasuryRemittanceBatch(models.Model):
    """Controlled cross-voucher settlement of posted deduction/withholding liabilities."""

    DRAFT = "draft"
    RETURNED = "returned"
    FOR_REVIEW = "for_review"
    APPROVED = "approved"
    ACCOUNTING_POSTING = "accounting_posting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (DRAFT, "Draft"), (RETURNED, "Returned for correction"),
        (FOR_REVIEW, "For Accounting review"), (APPROVED, "Approved for remittance"),
        (ACCOUNTING_POSTING, "Released; Accounting posting"),
        (COMPLETED, "Remitted and posted"), (CANCELLED, "Cancelled before release"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference_code = models.CharField(max_length=60, unique=True)
    configuration_release = models.ForeignKey(
        FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="treasury_remittance_batches",
    )
    transaction_variant = models.ForeignKey(
        FinanceTransactionVariant, on_delete=models.PROTECT, related_name="treasury_remittance_batches",
    )
    recipient_party = models.ForeignKey(
        FinanceParty, on_delete=models.PROTECT, related_name="treasury_remittance_batches",
    )
    treasury_department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="treasury_remittance_batches",
    )
    finance_department_id = models.PositiveBigIntegerField()
    finance_department_label = models.CharField(max_length=160)
    fund_code = models.CharField(max_length=80)
    bank_account_code = models.CharField(max_length=80)
    remittance_date = models.DateField()
    payment_method = models.CharField(max_length=80)
    authority_reference = models.TextField()
    evidence_reference = models.TextField()
    release_reference = models.CharField(max_length=160, blank=True)
    acknowledgement_reference = models.CharField(max_length=160, blank=True)
    total_amount = models.DecimalField(**MONEY)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    state_version = models.PositiveIntegerField(default=0)
    posting_rule = models.ForeignKey(
        FinancePostingRule, on_delete=models.PROTECT, null=True, blank=True,
        related_name="treasury_remittance_batches",
    )
    posting_rule_snapshot = models.JSONField(default=dict, blank=True)
    posting_rule_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_remittance_batches")
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="submitted_remittance_batches")
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_remittance_batches")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="released_remittance_batches")
    released_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="cancelled_remittance_batches")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-remittance_date", "-pk")
        permissions = (
            ("view_remittance_workbench", "Can view the Treasury remittance workbench"),
            ("prepare_remittances", "Can prepare deduction and withholding remittances"),
            ("approve_remittances", "Can independently review remittances"),
            ("release_remittances", "Can record actual remittance release"),
            ("view_remittance_audit", "Can view remittance audit history"),
        )

    def __str__(self):
        return self.reference_code

    def get_absolute_url(self):
        return reverse("vouchers:remittance_detail", kwargs={"public_id": self.public_id})

    def clean(self):
        if self.configuration_release_id and self.transaction_variant_id:
            if self.transaction_variant.release_id != self.configuration_release_id:
                raise ValidationError("The remittance variant must belong to its pinned configuration release.")
        if self.configuration_release_id and self.recipient_party_id:
            if self.recipient_party.release_id != self.configuration_release_id or self.recipient_party.party_type != FinanceParty.AGENCY:
                raise ValidationError("Choose an active government agency from the pinned release.")
        if self.total_amount < Decimal("0.00"):
            raise ValidationError({"total_amount": "The remittance total cannot be negative."})
        governed = bool(self.posting_rule_id or self.posting_rule_snapshot or self.posting_rule_checksum)
        if governed and not all((self.posting_rule_id, self.posting_rule_snapshot, self.posting_rule_checksum)):
            raise ValidationError("The remittance posting rule, snapshot, and checksum must be pinned together.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "reference_code", "configuration_release_id", "transaction_variant_id",
                "recipient_party_id", "treasury_department_id", "finance_department_id",
                "finance_department_label", "fund_code", "bank_account_code", "remittance_date",
                "payment_method", "authority_reference", "evidence_reference", "total_amount",
                "posting_rule_id", "posting_rule_snapshot", "posting_rule_checksum", "created_by_id", "created_at",
            )
            if prior.status not in {self.DRAFT, self.RETURNED} and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("An approved or released remittance schedule is immutable. Use the governed return, cancellation, reversal, or adjustment route.")
        return super().save(*args, **kwargs)


class TreasuryRemittanceLine(models.Model):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REMOVED = "removed"
    STATUS_CHOICES = ((ACTIVE, "Active"), (SUPERSEDED, "Superseded"), (REMOVED, "Removed"))

    batch = models.ForeignKey(TreasuryRemittanceBatch, on_delete=models.PROTECT, related_name="lines")
    lineage_key = models.UUIDField(default=uuid.uuid4)
    version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    supersedes = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor")
    fund_code = models.CharField(max_length=80)
    account_code = models.CharField(max_length=80)
    account_title = models.CharField(max_length=180)
    reference_key = models.CharField(max_length=100)
    reference_label = models.CharField(max_length=220)
    deduction_code = models.CharField(max_length=80)
    source_as_of_date = models.DateField()
    available_balance_snapshot = models.DecimalField(**MONEY)
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    source_checksum = models.CharField(max_length=64)
    tax_rule_snapshot = models.JSONField(default=dict, blank=True)
    tax_rule_checksum = models.CharField(max_length=64, blank=True)
    change_reason = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_remittance_lines")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("lineage_key", "version")
        constraints = (
            models.UniqueConstraint(fields=("batch", "lineage_key", "version"), name="unique_remittance_line_version"),
            models.UniqueConstraint(fields=("batch", "lineage_key"), condition=models.Q(status="active"), name="unique_active_remittance_line"),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Remittance allocation versions are immutable. Create a reasoned successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Remittance allocation evidence cannot be deleted.")


class RemittanceNumberIssue(models.Model):
    batch = models.ForeignKey(TreasuryRemittanceBatch, on_delete=models.PROTECT, related_name="number_issues")
    sequence = models.ForeignKey(FinanceNumberingSequence, on_delete=models.PROTECT, related_name="remittance_number_issues")
    document_type = models.SlugField(max_length=80)
    numeric_value = models.PositiveBigIntegerField()
    formatted_value = models.CharField(max_length=60)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="remittance_number_issues")
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=("sequence", "numeric_value"), name="unique_issued_remittance_number"),
            models.UniqueConstraint(fields=("batch", "document_type"), name="unique_remittance_document_number"),
        )


class RemittancePostingRequest(models.Model):
    PENDING = "pending"
    MATERIALIZED = "materialized"
    POSTED = "posted"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (PENDING, "Waiting for JEV creation"), (MATERIALIZED, "Draft JEV created"),
        (POSTED, "JEV posted"), (FAILED, "Needs intervention"), (CANCELLED, "Cancelled"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    batch = models.ForeignKey(TreasuryRemittanceBatch, on_delete=models.PROTECT, related_name="posting_requests")
    version = models.PositiveSmallIntegerField(default=1)
    jev_number = models.CharField(max_length=60)
    jev_date = models.DateField()
    finance_department_id = models.PositiveBigIntegerField()
    finance_department_label = models.CharField(max_length=160)
    posting_rule = models.ForeignKey(FinancePostingRule, on_delete=models.PROTECT, related_name="remittance_posting_requests")
    posting_rule_snapshot = models.JSONField(default=dict)
    posting_rule_checksum = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    payload_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    accounting_entry_public_id = models.UUIDField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="remittance_posting_requests")
    requested_at = models.DateTimeField(auto_now_add=True)
    materialized_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-requested_at", "-pk")
        constraints = (
            models.UniqueConstraint(fields=("batch", "version"), name="unique_remittance_posting_version"),
            models.UniqueConstraint(fields=("finance_department_id", "jev_number"), name="unique_remittance_jev_number"),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "batch_id", "version", "jev_number", "jev_date", "finance_department_id",
                "finance_department_label", "posting_rule_id", "posting_rule_snapshot",
                "posting_rule_checksum", "payload", "payload_checksum", "requested_by_id", "requested_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Remittance posting evidence is immutable. Create a successor request.")
        return super().save(*args, **kwargs)


class RemittanceEvent(models.Model):
    batch = models.ForeignKey(TreasuryRemittanceBatch, on_delete=models.PROTECT, related_name="events")
    action = models.CharField(max_length=80)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="remittance_events")
    actor_department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="remittance_events")
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24, blank=True)
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    state_version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Remittance events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Remittance events cannot be deleted.")


class TaxFilingEvidence(models.Model):
    """Reviewed evidence that a governed tax remittance was filed outside GRAND."""

    DRAFT = "draft"
    RETURNED = "returned"
    FOR_REVIEW = "for_review"
    VERIFIED = "verified"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Draft evidence"), (RETURNED, "Returned for correction"),
        (FOR_REVIEW, "For independent review"), (VERIFIED, "Evidence verified"),
        (SUPERSEDED, "Superseded by amendment"),
    )
    ORIGINAL = "original"
    AMENDED = "amended"
    FILING_TYPE_CHOICES = ((ORIGINAL, "Original filing"), (AMENDED, "Amended filing"))
    GRAND_REPORT = "grand_report"
    EXTERNAL_SCHEDULE = "external_schedule"
    SOURCE_MODE_CHOICES = (
        (GRAND_REPORT, "Approved GRAND tax report"),
        (EXTERNAL_SCHEDULE, "Advanced: external reviewed schedule"),
    )
    LEGACY_EVIDENCE_SCHEMA = 1
    CURRENT_EVIDENCE_SCHEMA = 2

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    batch = models.ForeignKey(
        TreasuryRemittanceBatch, on_delete=models.PROTECT, related_name="tax_filing_evidence",
    )
    version = models.PositiveSmallIntegerField(default=1)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor",
    )
    filing_type = models.CharField(max_length=12, choices=FILING_TYPE_CHOICES, default=ORIGINAL)
    return_form_code = models.CharField(max_length=40)
    tax_period_start = models.DateField()
    tax_period_end = models.DateField()
    filing_date = models.DateField()
    submission_channel = models.CharField(max_length=120)
    filing_reference = models.CharField(max_length=160)
    payment_confirmation_reference = models.CharField(max_length=160)
    source_mode = models.CharField(max_length=24, choices=SOURCE_MODE_CHOICES, default=GRAND_REPORT)
    source_report_run_public_id = models.UUIDField(null=True, blank=True)
    source_report_snapshot = models.JSONField(default=dict, blank=True)
    source_schedule_reference = models.CharField(max_length=220, blank=True)
    source_schedule_checksum = models.CharField(max_length=64, blank=True)
    external_source_basis = models.TextField(blank=True)
    evidence_reference = models.TextField()
    tax_scope_snapshot = models.JSONField(default=dict)
    evidence_schema_version = models.PositiveSmallIntegerField(default=CURRENT_EVIDENCE_SCHEMA)
    evidence_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    state_version = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_tax_filing_evidence",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_tax_filing_evidence",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_tax_filing_evidence",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-filing_date", "-pk")
        constraints = (
            models.UniqueConstraint(fields=("batch", "version"), name="unique_tax_filing_evidence_version"),
            models.UniqueConstraint(
                fields=("batch",), condition=models.Q(status__in=("draft", "returned", "for_review", "verified")),
                name="unique_current_tax_filing_evidence",
            ),
        )

    def __str__(self):
        return f"{self.batch.reference_code} · {self.return_form_code} · v{self.version}"

    def clean(self):
        if self.tax_period_start and self.tax_period_end and self.tax_period_start > self.tax_period_end:
            raise ValidationError({"tax_period_end": "The tax period end cannot precede its start."})
        if self.filing_date and self.tax_period_end and self.filing_date < self.tax_period_start:
            raise ValidationError({"filing_date": "The filing date cannot precede the tax period start."})
        if self.evidence_schema_version not in {self.LEGACY_EVIDENCE_SCHEMA, self.CURRENT_EVIDENCE_SCHEMA}:
            raise ValidationError({"evidence_schema_version": "Unsupported filing-evidence checksum schema."})
        if self.evidence_checksum and (len(self.source_schedule_checksum) != 64 or any(
            character.lower() not in "0123456789abcdef" for character in self.source_schedule_checksum
        )):
            raise ValidationError({"source_schedule_checksum": "Enter the 64-character SHA-256 of the reviewed source schedule."})
        if self.evidence_checksum and self.source_mode == self.GRAND_REPORT:
            if not self.source_report_run_public_id or not self.source_report_snapshot:
                raise ValidationError("Select an approved, reconciled GRAND tax report.")
            if self.external_source_basis.strip():
                raise ValidationError({"external_source_basis": "The external-source basis is only used for an external schedule."})
        elif self.evidence_checksum and self.source_mode == self.EXTERNAL_SCHEDULE:
            if self.source_report_run_public_id or self.source_report_snapshot:
                raise ValidationError("An external schedule cannot also claim a GRAND report-run identity.")
            if not self.source_schedule_reference.strip():
                raise ValidationError({"source_schedule_reference": "Enter the reviewed external schedule reference."})
            if not self.external_source_basis.strip():
                raise ValidationError({"external_source_basis": "Explain why an external schedule is the reviewed source instead of an approved GRAND report."})

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            evidence_fields = (
                "batch_id", "version", "supersedes_id", "filing_type", "return_form_code",
                "tax_period_start", "tax_period_end", "filing_date", "submission_channel",
                "filing_reference", "payment_confirmation_reference", "source_schedule_reference",
                "source_mode", "source_report_run_public_id", "source_report_snapshot",
                "source_schedule_checksum", "external_source_basis", "evidence_reference", "tax_scope_snapshot",
                "evidence_schema_version", "evidence_checksum", "created_by_id", "created_at",
            )
            if prior.status not in {self.DRAFT, self.RETURNED} and any(
                getattr(prior, field) != getattr(self, field) for field in evidence_fields
            ):
                raise ValidationError("Submitted tax filing evidence is immutable. Return it or create an amended successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Tax filing evidence cannot be deleted. Retain it or create an amended successor.")


class VoucherPrintJob(models.Model):
    READY_TO_PRINT = "ready_to_print"
    PRINTED = "printed"
    AWAITING_SIGNATURES = "awaiting_signatures"
    SIGNED_PACKET_RETURNED = "signed_packet_returned"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (READY_TO_PRINT, "Ready to print"),
        (PRINTED, "Printed copies recorded"),
        (AWAITING_SIGNATURES, "Awaiting wet signatures"),
        (SIGNED_PACKET_RETURNED, "Signed packet returned"),
        (SUPERSEDED, "Superseded — do not sign"),
    )

    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="print_jobs")
    version = models.PositiveIntegerField()
    output = models.OneToOneField(VoucherOutput, on_delete=models.PROTECT, related_name="print_job")
    output_checksum = models.CharField(max_length=64)
    signature_round = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=28, choices=STATUS_CHOICES, default=READY_TO_PRINT, db_index=True)
    copy_count = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    printer_or_form_stock = models.CharField(max_length=180, blank=True)
    print_note = models.TextField(blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_voucher_print_jobs",
    )
    prepared_at = models.DateTimeField(auto_now_add=True)
    printed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="printed_voucher_print_jobs",
    )
    printed_at = models.DateTimeField(null=True, blank=True)
    tracepoint_item = models.ForeignKey(
        "tracepoint.PacketItem", on_delete=models.PROTECT, null=True, blank=True,
        related_name="voucher_print_jobs",
    )
    packet_reference = models.CharField(max_length=80, blank=True)
    archive_manifest = models.JSONField(default=dict, blank=True)
    custody_manifest = models.JSONField(default=dict, blank=True)
    custody_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="assembled_voucher_print_jobs",
    )
    custody_confirmed_at = models.DateTimeField(null=True, blank=True)
    signed_returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="returned_voucher_print_jobs",
    )
    signed_returned_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_print_job",
    )
    supersession_reason = models.TextField(blank=True)

    class Meta:
        ordering = ("-version", "-pk")
        constraints = (
            models.UniqueConstraint(fields=("case", "version"), name="unique_voucher_print_job_version"),
            models.UniqueConstraint(
                fields=("case",),
                condition=models.Q(status__in=("ready_to_print", "printed", "awaiting_signatures")),
                name="unique_active_voucher_print_job",
            ),
        )

    def clean(self):
        if self.output_id and self.case_id and self.output.case_id != self.case_id:
            raise ValidationError("The print job output must belong to the same voucher case.")
        if self.output_id and self.output_checksum != self.output.checksum:
            raise ValidationError("The print job checksum must match its immutable controlled output.")
        if not self.archive_manifest or self.archive_manifest.get("sha256") != self.output_checksum:
            raise ValidationError("A controlled signing copy requires its matching TraceSync-ready archive manifest.")
        if self.status in {self.PRINTED, self.AWAITING_SIGNATURES, self.SIGNED_PACKET_RETURNED}:
            if not self.copy_count or not self.printed_by_id or not self.printed_at:
                raise ValidationError("Printed signing copies require copy count, operator, and server time.")
        if self.status in {self.AWAITING_SIGNATURES, self.SIGNED_PACKET_RETURNED}:
            if not self.tracepoint_item_id or not self.packet_reference or not self.custody_confirmed_at:
                raise ValidationError("Signature circulation requires a verified TracePoint packet item.")
        if self.status == self.SIGNED_PACKET_RETURNED and not self.signed_returned_at:
            raise ValidationError("A returned signed packet requires its server receipt time.")
        if self.status == self.SUPERSEDED and not self.supersession_reason.strip():
            raise ValidationError("A superseded signing copy requires a reason.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "case_id", "version", "output_id", "output_checksum", "signature_round",
                "archive_manifest", "prepared_by_id", "prepared_at", "supersedes_id",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Print identity and source evidence are immutable. Create a successor print job.")
            if prior.printed_at and any(
                getattr(prior, field) != getattr(self, field)
                for field in ("copy_count", "printer_or_form_stock", "print_note", "printed_by_id", "printed_at")
            ):
                raise ValidationError("Recorded print evidence is immutable.")
            if prior.tracepoint_item_id and any(
                getattr(prior, field) != getattr(self, field)
                for field in ("tracepoint_item_id", "packet_reference", "custody_manifest", "custody_confirmed_by_id", "custody_confirmed_at")
            ):
                raise ValidationError("Recorded packet assembly evidence is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Print job evidence cannot be deleted.")
