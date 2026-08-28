from __future__ import annotations

import uuid
import os
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from departments.models import Department
from finance.models import (
    FinanceConfigurationRelease, FinanceDocumentRule, FinanceParty, FinancePartyClaimant,
    FinanceTemplateVersion,
)


MONEY = {"max_digits": 18, "decimal_places": 2, "default": Decimal("0.00")}


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
    authoritative_obligation_public_id = models.UUIDField(null=True, blank=True, unique=True)
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
            ("track_wet_signatures", "Can track wet signature circulation"),
            ("link_tracepoint_custody", "Can link voucher cases to TracePoint custody items"),
            ("validate_accounting_voucher", "Can validate accounting vouchers and JEV references"),
            ("issue_payment_instruments", "Can issue checks and payment instruments"),
            ("finalize_bank_advice", "Can finalize accountant bank advice"),
            ("release_payment_instruments", "Can release checks and payment instruments"),
            ("manage_payment_exceptions", "Can cancel and replace payment instruments"),
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
                    "authoritative_obligation_public_id", "authoritative_obligation_number",
                    "authoritative_obligation_checksum", "authoritative_obligation_amount",
                )
                if any(getattr(previous, field) != getattr(self, field) for field in immutable):
                    raise ValidationError("Voucher identity and transaction type are immutable.")


class BudgetObligation(models.Model):
    case = models.OneToOneField(VoucherCase, on_delete=models.PROTECT, related_name="obligation")
    obr_number = models.CharField(max_length=60, unique=True)
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

    case = models.OneToOneField(VoucherCase, on_delete=models.PROTECT, related_name="payable_intake")
    claim_reference = models.CharField(max_length=120)
    invoice_number = models.CharField(max_length=120, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    claim_amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    procurement_reference = models.CharField(max_length=180, blank=True)
    delivery_reference = models.CharField(max_length=180, blank=True)
    inspection_acceptance_reference = models.CharField(max_length=180, blank=True)
    evidence_reference = models.TextField()
    duplicate_warning = models.TextField(blank=True)
    duplicate_review_note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    decision_reason = models.TextField(blank=True)
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
        if self.case_id and self.claim_amount != self.case.authoritative_obligation_amount:
            raise ValidationError(
                "The payable amount must equal the currently linked obligation amount. "
                "Record a governed obligation adjustment before intake when the final claim changes."
            )


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
    KIND_CHOICES = ((RECOGNITION, "Voucher recognition JEV"),)
    PENDING = "pending"
    MATERIALIZED = "materialized"
    POSTED = "posted"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (PENDING, "Waiting for JEV creation"),
        (MATERIALIZED, "Draft JEV created"),
        (POSTED, "JEV posted"),
        (FAILED, "Needs intervention"),
        (CANCELLED, "Cancelled"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="posting_requests")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=RECOGNITION)
    version = models.PositiveSmallIntegerField(default=1)
    jev_number = models.CharField(max_length=60)
    jev_date = models.DateField()
    finance_department_id = models.PositiveBigIntegerField()
    finance_department_label = models.CharField(max_length=160)
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
        )

    def __str__(self):
        return f"{self.jev_number} · {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "case_id", "kind", "version", "jev_number", "jev_date", "finance_department_id",
                "finance_department_label", "payload", "payload_checksum", "requested_by_id", "requested_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Posting request evidence is immutable. Create a new version instead.")
        return super().save(*args, **kwargs)


class PaymentInstrument(models.Model):
    DRAFT = "draft"
    ISSUED = "issued"
    ADVISED = "advised"
    RELEASED = "released"
    CANCELLED = "cancelled"
    STATUS_CHOICES = ((DRAFT, "Draft"), (ISSUED, "Issued"), (ADVISED, "Included in finalized advice"), (RELEASED, "Released"), (CANCELLED, "Cancelled / spoiled"))

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    case = models.ForeignKey(VoucherCase, on_delete=models.PROTECT, related_name="payment_instruments")
    bank_account_code = models.CharField(max_length=80)
    check_number = models.CharField(max_length=60)
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
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

    class Meta:
        ordering = ("check_number", "pk")
        constraints = (models.UniqueConstraint(fields=("bank_account_code", "check_number"), name="unique_check_per_bank_account"),)

    def __str__(self):
        return f"{self.check_number} — {self.amount}"


class BankAdviceBatch(models.Model):
    DRAFT = "draft"
    FINALIZED = "finalized"
    STATUS_CHOICES = ((DRAFT, "Draft"), (FINALIZED, "Finalized"))

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    advice_number = models.CharField(max_length=60, unique=True)
    advice_date = models.DateField()
    bank_account_code = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_bank_advice_batches")
    created_at = models.DateTimeField(auto_now_add=True)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="finalized_bank_advice_batches")
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-advice_date", "-pk")


class BankAdviceItem(models.Model):
    batch = models.ForeignKey(BankAdviceBatch, on_delete=models.PROTECT, related_name="items")
    instrument = models.OneToOneField(PaymentInstrument, on_delete=models.PROTECT, related_name="advice_item")


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
