from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from departments.models import Department


LIFECYCLE_CHOICES = (
    ("draft", "Draft"),
    ("submitted", "Submitted for review"),
    ("approved", "Approved"),
    ("scheduled", "Scheduled"),
    ("active", "Active"),
    ("superseded", "Superseded"),
    ("retired", "Retired"),
)
LOCKED_STATES = {"approved", "scheduled", "active", "superseded", "retired"}

TAX_FAMILY_CHOICES = (
    ("expanded_income", "Expanded / creditable income tax"),
    ("final_income", "Final income tax"),
    ("government_vat", "VAT withheld on government payment"),
    ("government_percentage", "Percentage tax withheld on government payment"),
    ("compensation", "Compensation withholding"),
    ("other", "Other locally confirmed tax"),
)
TAX_REPORTING_BASIS_CHOICES = (
    ("accounting_posting", "Posted recognition or reversal date"),
    ("voucher_date", "Disbursement Voucher date"),
    ("payment_release", "Actual payment-release date"),
)
TAX_ROUNDING_CHOICES = (
    ("half_up", "Nearest cent; half rounds up"),
    ("down", "Round down to the cent"),
    ("up", "Round up to the cent"),
)
TAX_APPLICABILITY_CHOICES = (
    ("candidate", "Starter / local confirmation pending"),
    ("locally_confirmed", "Locally confirmed for the stated scope"),
)


def normalized_tax_rule_configuration(configuration):
    """Return the small, stable configuration used by vouchers and reports."""
    configuration = configuration or {}
    if not configuration.get("reporting_enabled"):
        raise ValidationError("This deduction is not configured for controlled tax reporting.")
    family = str(configuration.get("tax_family") or "").strip()
    reporting_basis = str(configuration.get("reporting_basis") or "").strip()
    rounding_mode = str(configuration.get("rounding_mode") or "").strip()
    applicability = str(configuration.get("applicability_status") or "").strip()
    if family not in dict(TAX_FAMILY_CHOICES):
        raise ValidationError("Choose a supported tax family.")
    if reporting_basis not in dict(TAX_REPORTING_BASIS_CHOICES):
        raise ValidationError("Choose when this tax enters its controlled report period.")
    if rounding_mode not in dict(TAX_ROUNDING_CHOICES):
        raise ValidationError("Choose a supported cent-rounding rule.")
    if applicability not in dict(TAX_APPLICABILITY_CHOICES):
        raise ValidationError("Choose whether local applicability is still pending or confirmed.")
    try:
        rate = Decimal(str(configuration.get("rate_percent", "")))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Enter the reviewed tax rate as a percentage.") from exc
    if rate <= 0 or rate > Decimal("100"):
        raise ValidationError("The reviewed tax rate must be greater than zero and no more than 100 percent.")
    required_text = {
        "atc": "Enter the applicable alphanumeric tax code (ATC).",
        "return_form_code": "Enter the reviewed return or remittance form code.",
        "tax_base_label": "Describe the amount to which the rate applies.",
        "authority_reference": "Record the reviewed BIR/local authority reference.",
        "local_acceptance_note": "Record the local applicability decision and retained evidence.",
    }
    for key, message in required_text.items():
        if not str(configuration.get(key) or "").strip():
            raise ValidationError(message)
    return {
        "reporting_enabled": True,
        "tax_family": family,
        "atc": str(configuration["atc"]).strip().upper(),
        "rate_percent": format(rate.normalize(), "f"),
        "tax_base_label": str(configuration["tax_base_label"]).strip(),
        "return_form_code": str(configuration["return_form_code"]).strip().upper(),
        "certificate_form_code": str(configuration.get("certificate_form_code") or "").strip().upper(),
        "reporting_basis": reporting_basis,
        "rounding_mode": rounding_mode,
        "requires_tax_identifier": bool(configuration.get("requires_tax_identifier", True)),
        "authority_reference": str(configuration["authority_reference"]).strip(),
        "applicability_status": applicability,
        "local_acceptance_note": str(configuration["local_acceptance_note"]).strip(),
    }


def finance_tax_rule_snapshot(item):
    if item.category != "tax_rule":
        raise ValidationError("Choose a Finance Setup tax or deduction rule.")
    configuration = normalized_tax_rule_configuration(item.configuration)
    snapshot = {
        "item_public_id": str(item.public_id),
        "release_id": item.release_id,
        "release_code": item.release.code,
        "release_version": item.release.version,
        "code": item.code,
        "version": item.version,
        "label": item.label,
        **configuration,
    }
    checksum = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return snapshot, checksum


def finance_template_path(instance, filename):
    return f"finance/templates/{instance.department.slug}/{instance.document_type}/v{instance.version}/{filename}"


def finance_shadow_source_path(instance, filename):
    return (
        f"finance/shadow-sources/{instance.cycle.department.slug}/"
        f"{instance.cycle.code}/v{instance.version}/{filename}"
    )


class FinanceConfigurationRelease(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_releases")
    code = models.SlugField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=180)
    fiscal_year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default="draft")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    accounting_approval_note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_releases")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="submitted_finance_releases")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_finance_releases")
    approved_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="activated_finance_releases")
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fiscal_year", "code", "-version")
        constraints = (
            models.UniqueConstraint(fields=("department", "code", "version"), name="unique_finance_release_version"),
        )
        permissions = (
            ("view_finance_setup", "Can view Finance Setup Center"),
            ("manage_finance_configuration", "Can prepare finance configuration"),
            ("approve_finance_configuration", "Can approve finance configuration"),
            ("manage_finance_templates", "Can prepare finance workbook templates"),
            ("manage_finance_providers", "Can manage technical finance providers"),
        )

    def __str__(self):
        return f"{self.title} v{self.version}"

    def clean(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot be before the activation date."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status in LOCKED_STATES:
                governed = ("department_id", "code", "version", "title", "fiscal_year", "effective_from", "effective_to", "accounting_approval_note")
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Approved finance releases are immutable. Create a new release version.")


class FinanceConfigurationItem(models.Model):
    CATEGORY_CHOICES = (
        ("transaction_type", "Voucher / transaction type"),
        ("payee_classification", "Payee classification"),
        ("fund", "Fund"),
        ("funding_source", "Funding source"),
        ("responsibility_center", "Office / responsibility center"),
        ("ppa_mfo", "PPA / major final output"),
        ("project_activity", "Project / activity"),
        ("bank_account", "Bank / payment account"),
        ("payment_method", "Payment method"),
        ("account_classification", "Account / expenditure classification"),
        ("obligation_behavior", "OBR / obligation behavior"),
        ("tax_rule", "Tax / deduction / rounding rule"),
        ("document_requirement", "Supporting-document requirement"),
        ("approval_route", "Approval step / threshold / route"),
        ("confidentiality", "Confidentiality / retention setting"),
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_configuration_items")
    release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="items")
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    code = models.SlugField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    label = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True, help_text="Controlled, category-specific values; never paste credentials or production personal data.")
    status = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default="draft")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    supersedes = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_versions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_items")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("category", "code", "-version")
        constraints = (
            models.UniqueConstraint(fields=("department", "category", "code", "version"), name="unique_finance_item_version"),
        )

    def __str__(self):
        return f"{self.label} v{self.version}"

    def clean(self):
        if self.release_id and self.release.department_id != self.department_id:
            raise ValidationError({"release": "The release and configuration item must belong to the same finance office."})
        if not isinstance(self.configuration, dict):
            raise ValidationError({"configuration": "Configuration values must be a controlled key/value mapping."})
        if self.category == "tax_rule" and self.configuration.get("reporting_enabled"):
            try:
                normalized_tax_rule_configuration(self.configuration)
            except ValidationError as exc:
                raise ValidationError({"configuration": exc.messages}) from exc
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The retirement date cannot be before the effective date."})
        if self.supersedes_id:
            if self.supersedes_id == self.pk or self.supersedes.department_id != self.department_id or self.supersedes.category != self.category or self.supersedes.code != self.code:
                raise ValidationError({"supersedes": "A version may supersede only an earlier version of the same finance item."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and (prior.status in LOCKED_STATES or prior.release.status in LOCKED_STATES):
                governed = ("department_id", "release_id", "category", "code", "version", "label", "description", "configuration", "effective_from", "effective_to", "supersedes_id")
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Approved finance configuration is immutable. Create a new version.")


class FinanceTransactionVariant(models.Model):
    ORDINARY_SUPPLIER = "ordinary_supplier"
    PAYROLL = "payroll"
    REIMBURSEMENT = "reimbursement"
    UTILITY = "utility"
    FINANCIAL_ASSISTANCE = "financial_assistance"
    CASH_ADVANCE = "cash_advance"
    LIQUIDATION = "liquidation"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"
    KIND_CHOICES = (
        (ORDINARY_SUPPLIER, "Ordinary supplier / contractor"),
        (PAYROLL, "Payroll"),
        (REIMBURSEMENT, "Employee reimbursement"),
        (UTILITY, "Utility / recurring billing"),
        (FINANCIAL_ASSISTANCE, "Financial assistance"),
        (CASH_ADVANCE, "Cash advance"),
        (LIQUIDATION, "Cash advance liquidation"),
        (INFRASTRUCTURE, "Infrastructure / progress billing"),
        (OTHER, "Other locally approved variant"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_transaction_variants")
    release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="transaction_variants")
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=180)
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    description = models.TextField()
    authority_reference = models.TextField(
        help_text="Cite the reviewed COA/DBM/local authority and applicability decision; do not imply acceptance from a public source alone."
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default="draft")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_transaction_variants")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("label", "code")
        constraints = (
            models.UniqueConstraint(fields=("release", "code"), name="unique_finance_variant_per_release"),
        )

    def __str__(self):
        return self.label

    def clean(self):
        if self.release_id and self.release.department_id != self.department_id:
            raise ValidationError("The transaction variant and release must belong to the same finance office.")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the effective date."})
        if not self.authority_reference.strip():
            raise ValidationError({"authority_reference": "Record the reviewed authority and local applicability basis."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and (prior.status != "draft" or prior.release.status != "draft"):
                governed = (
                    "department_id", "release_id", "code", "label", "kind", "description",
                    "authority_reference", "effective_from", "effective_to",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Approved transaction variants are immutable. Create them in a successor release.")


class FinanceDocumentRule(models.Model):
    REQUEST = "request"
    PROCUREMENT = "procurement"
    CONTRACT = "contract"
    DELIVERY = "delivery"
    INSPECTION = "inspection_acceptance"
    INVOICE = "invoice_billing"
    PAYROLL = "payroll"
    TRAVEL = "travel_reimbursement"
    ASSISTANCE = "assistance_claim"
    LIQUIDATION = "liquidation"
    OTHER = "other"
    EVIDENCE_KIND_CHOICES = (
        (REQUEST, "Request / initiating authority"),
        (PROCUREMENT, "Procurement evidence"),
        (CONTRACT, "Contract / purchase order"),
        (DELIVERY, "Delivery / accomplishment evidence"),
        (INSPECTION, "Inspection / acceptance"),
        (INVOICE, "Invoice / billing"),
        (PAYROLL, "Payroll schedule / certification"),
        (TRAVEL, "Travel / reimbursement claim"),
        (ASSISTANCE, "Assistance eligibility / claim authority"),
        (LIQUIDATION, "Liquidation evidence"),
        (OTHER, "Other reviewed evidence"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    variant = models.ForeignKey(FinanceTransactionVariant, on_delete=models.PROTECT, related_name="document_rules")
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=180)
    evidence_kind = models.CharField(max_length=32, choices=EVIDENCE_KIND_CHOICES)
    required = models.BooleanField(default=True)
    waiver_allowed = models.BooleanField(default=False)
    condition_description = models.TextField(blank=True)
    authority_reference = models.TextField()
    display_order = models.PositiveSmallIntegerField(default=10)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_document_rules")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("display_order", "code")
        constraints = (
            models.UniqueConstraint(fields=("variant", "code"), name="unique_document_rule_per_variant"),
        )

    @property
    def department(self):
        return self.variant.department

    @property
    def release(self):
        return self.variant.release

    def __str__(self):
        return f"{self.variant.code}: {self.label}"

    def clean(self):
        if self.variant_id and self.variant.release.status != "draft":
            raise ValidationError("Document rules can be changed only inside a draft configuration release.")
        if not self.required and not self.condition_description.strip():
            raise ValidationError({
                "condition_description": "A conditional document rule must state when it applies."
            })
        if self.waiver_allowed and not self.authority_reference.strip():
            raise ValidationError({"authority_reference": "A permitted waiver requires its reviewed authority basis."})
        if self.required and not self.authority_reference.strip():
            raise ValidationError({"authority_reference": "A required document needs its reviewed authority basis."})
        if self.pk:
            prior = type(self).objects.select_related("variant__release").get(pk=self.pk)
            if prior.variant.release.status in LOCKED_STATES:
                raise ValidationError("Approved document rules are immutable. Use a successor release.")


class FinancePostingRule(models.Model):
    RECOGNITION = "recognition"
    ADJUSTMENT = "adjustment"
    LIQUIDATION = "liquidation"
    PAYMENT = "payment"
    REMITTANCE = "remittance"
    CANCELLATION = "cancellation"
    REVERSAL = "reversal"
    REPLACEMENT = "replacement"
    EVENT_KIND_CHOICES = (
        (RECOGNITION, "Recognize expense, asset, or payable"),
        (ADJUSTMENT, "Adjust an earlier recognition"),
        (LIQUIDATION, "Record liquidation"),
        (PAYMENT, "Settle payable / record payment"),
        (REMITTANCE, "Remit deductions or withholdings"),
        (CANCELLATION, "Record cancellation effect"),
        (REVERSAL, "Reverse an earlier entry"),
        (REPLACEMENT, "Record replacement effect"),
    )
    DELIVERY_ACCEPTANCE = "delivery_acceptance"
    BILLING_VALIDATION = "billing_validation"
    DV_VALIDATION = "dv_validation"
    PAYMENT_ISSUANCE = "payment_issuance"
    PAYMENT_RELEASE = "payment_release"
    PAYMENT_RETURN = "payment_return"
    PAYMENT_CANCELLATION = "payment_cancellation"
    PAYMENT_REPLACEMENT = "payment_replacement"
    DEDUCTION_REMITTANCE = "deduction_remittance"
    LIQUIDATION_ACCEPTANCE = "liquidation_acceptance"
    PERIOD_END = "period_end"
    OTHER = "other"
    RECOGNITION_POINT_CHOICES = (
        (DELIVERY_ACCEPTANCE, "Delivery / inspection acceptance"),
        (BILLING_VALIDATION, "Billing or claim validation"),
        (DV_VALIDATION, "DV Accounting validation"),
        (PAYMENT_ISSUANCE, "Check / payment-instrument issuance"),
        (PAYMENT_RELEASE, "Actual payment release"),
        (PAYMENT_RETURN, "Bank-returned payment instrument"),
        (PAYMENT_CANCELLATION, "Payment-instrument cancellation"),
        (PAYMENT_REPLACEMENT, "Replacement payment-instrument issuance"),
        (DEDUCTION_REMITTANCE, "Deduction / withholding remittance"),
        (LIQUIDATION_ACCEPTANCE, "Liquidation acceptance"),
        (PERIOD_END, "Period-end review"),
        (OTHER, "Other locally confirmed point"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    JOURNAL_ENTRY = "journal_entry"
    NO_ENTRY = "no_entry"
    ACCOUNTING_EFFECT_CHOICES = (
        (JOURNAL_ENTRY, "Create a governed journal entry"),
        (NO_ENTRY, "Record that no journal entry is required"),
    )
    variant = models.ForeignKey(
        FinanceTransactionVariant, on_delete=models.PROTECT, related_name="posting_rules",
    )
    code = models.SlugField(max_length=80)
    title = models.CharField(max_length=180)
    event_kind = models.CharField(max_length=24, choices=EVENT_KIND_CHOICES)
    recognition_point = models.CharField(max_length=32, choices=RECOGNITION_POINT_CHOICES)
    accounting_effect = models.CharField(
        max_length=16,
        choices=ACCOUNTING_EFFECT_CHOICES,
        default=JOURNAL_ENTRY,
        help_text="Choose an explicit no-entry decision when the reviewed local treatment has no ledger effect.",
    )
    description = models.TextField(help_text="Explain in ordinary Accounting language when this entry is used.")
    authority_reference = models.TextField(
        help_text="Reviewed COA/local accounting basis and local applicability or acceptance reference."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_posting_rules",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("variant__label", "event_kind", "code")
        constraints = (
            models.UniqueConstraint(
                fields=("variant", "event_kind"), name="unique_finance_posting_event_per_variant",
            ),
        )

    @property
    def department(self):
        return self.variant.department

    @property
    def release(self):
        return self.variant.release

    def __str__(self):
        return f"{self.variant.code} · {self.get_event_kind_display()}"

    def clean(self):
        if self.variant_id and self.variant.release.status != "draft":
            raise ValidationError("Posting rules can be changed only inside a draft configuration release.")
        if not self.description.strip():
            raise ValidationError({"description": "Explain when Accounting uses this entry."})
        if not self.authority_reference.strip():
            raise ValidationError({"authority_reference": "Record the reviewed accounting and local applicability basis."})
        if self.pk:
            prior = type(self).objects.select_related("variant__release").get(pk=self.pk)
            if prior.variant.release.status in LOCKED_STATES:
                raise ValidationError("Approved posting rules are immutable. Use a successor release.")


class FinancePostingRuleLine(models.Model):
    ALLOCATION_ACCOUNTS = "allocation_accounts"
    DEDUCTION_MAPPINGS = "deduction_mappings"
    PAYABLE_MAPPING = "payable_mapping"
    BANK_MAPPING = "bank_mapping"
    FIXED_ACCOUNT = "fixed_account"
    ACCOUNT_SOURCE_CHOICES = (
        (ALLOCATION_ACCOUNTS, "Each voucher allocation account"),
        (DEDUCTION_MAPPINGS, "Each deduction's configured payable account"),
        (PAYABLE_MAPPING, "Transaction's configured payable account"),
        (BANK_MAPPING, "Payment account's configured bank/cash account"),
        (FIXED_ACCOUNT, "One locally confirmed ledger account code"),
    )
    DEBIT = "debit"
    CREDIT = "credit"
    SIDE_CHOICES = ((DEBIT, "Debit"), (CREDIT, "Credit"))
    EACH_ALLOCATION = "each_allocation"
    EACH_DEDUCTION = "each_deduction"
    GROSS = "gross"
    NET = "net"
    TOTAL_DEDUCTIONS = "total_deductions"
    EVENT_AMOUNT = "event_amount"
    AMOUNT_SOURCE_CHOICES = (
        (EACH_ALLOCATION, "Each allocation amount"),
        (EACH_DEDUCTION, "Each deduction amount"),
        (GROSS, "Voucher gross amount"),
        (NET, "Voucher net amount"),
        (TOTAL_DEDUCTIONS, "Total deductions"),
        (EVENT_AMOUNT, "Current payment / cancellation / replacement / remittance amount"),
    )

    rule = models.ForeignKey(FinancePostingRule, on_delete=models.PROTECT, related_name="lines")
    sequence = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=180, help_text="Plain-language purpose shown to Accounting reviewers.")
    side = models.CharField(max_length=8, choices=SIDE_CHOICES)
    account_source = models.CharField(max_length=28, choices=ACCOUNT_SOURCE_CHOICES)
    amount_source = models.CharField(max_length=24, choices=AMOUNT_SOURCE_CHOICES)
    mapping_code = models.CharField(
        max_length=80, blank=True,
        help_text="Optional mapping override. Leave blank to use the transaction or payment-account code.",
    )
    ledger_account_code = models.CharField(
        max_length=80, blank=True,
        help_text="Required only for one locally confirmed fixed ledger account.",
    )
    memo = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ("sequence", "pk")
        constraints = (
            models.UniqueConstraint(fields=("rule", "sequence"), name="unique_finance_posting_rule_line_sequence"),
        )

    def __str__(self):
        return f"{self.rule.code} line {self.sequence} · {self.label}"

    def clean(self):
        if self.rule_id and self.rule.variant.release.status != "draft":
            raise ValidationError("Posting-rule lines can be changed only inside a draft configuration release.")
        if self.account_source == self.ALLOCATION_ACCOUNTS and self.amount_source != self.EACH_ALLOCATION:
            raise ValidationError({"amount_source": "Allocation accounts must use each allocation amount."})
        if self.account_source == self.DEDUCTION_MAPPINGS and self.amount_source != self.EACH_DEDUCTION:
            raise ValidationError({"amount_source": "Deduction mappings must use each deduction amount."})
        if self.account_source not in {self.ALLOCATION_ACCOUNTS, self.DEDUCTION_MAPPINGS} and self.amount_source in {
            self.EACH_ALLOCATION, self.EACH_DEDUCTION,
        }:
            raise ValidationError({
                "amount_source": "Choose gross, net, total deductions, or the current event amount for this account source."
            })
        if self.account_source == self.FIXED_ACCOUNT:
            if not self.ledger_account_code.strip():
                raise ValidationError({"ledger_account_code": "Enter the locally confirmed posting account code."})
        elif self.ledger_account_code.strip():
            raise ValidationError({"ledger_account_code": "Use this only with one fixed ledger account."})
        if self.account_source in {self.ALLOCATION_ACCOUNTS, self.DEDUCTION_MAPPINGS} and self.mapping_code.strip():
            raise ValidationError({"mapping_code": "This repeated source determines its own mapping code."})
        if self.pk:
            prior = type(self).objects.select_related("rule__variant__release").get(pk=self.pk)
            if prior.rule.variant.release.status in LOCKED_STATES:
                raise ValidationError("Approved posting-rule lines are immutable. Use a successor release.")


class FinanceSignatory(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_signatories")
    release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="signatories")
    role_code = models.SlugField(max_length=80)
    display_name = models.CharField(max_length=180)
    position_title = models.CharField(max_length=180)
    acting = models.BooleanField(default=False)
    custody_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="finance_signature_routes",
        help_text="Office that physically receives the paper for this signature. Leave blank to use the Finance office.",
    )
    custody_instructions = models.TextField(
        blank=True,
        help_text="Plain-language packet instruction, such as 'Leave with the Mayor's receiving clerk for signature.'",
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default="draft")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_signatories")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("role_code", "-valid_from")

    def clean(self):
        if self.release_id and self.release.department_id != self.department_id:
            raise ValidationError({"release": "Signatory and release must belong to the same finance office."})
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError({"valid_to": "The assignment end cannot precede its start."})
        if self.pk and type(self).objects.filter(pk=self.pk, status__in=LOCKED_STATES).exists():
            raise ValidationError("Approved signatory assignments are immutable. Create a replacement assignment.")


class FinanceParty(models.Model):
    SUPPLIER = "supplier"
    INDIVIDUAL = "individual"
    EMPLOYEE = "employee"
    AGENCY = "agency"
    PARTY_TYPE_CHOICES = (
        (SUPPLIER, "Supplier / contractor"),
        (INDIVIDUAL, "Individual claimant"),
        (EMPLOYEE, "Employee claimant"),
        (AGENCY, "Government agency / organization"),
    )

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_parties")
    release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="parties")
    code = models.SlugField(max_length=80)
    version = models.PositiveIntegerField(default=1)
    display_name = models.CharField(max_length=220)
    party_type = models.CharField(max_length=20, choices=PARTY_TYPE_CHOICES, default=SUPPLIER)
    address = models.TextField(blank=True)
    tax_identifier = models.CharField(max_length=40, blank=True, help_text="Store only when required by approved local policy.")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default="draft")
    supersedes = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_versions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_parties")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("display_name", "-version")
        constraints = (models.UniqueConstraint(fields=("department", "code", "version"), name="unique_finance_party_version"),)

    def __str__(self):
        return f"{self.display_name} ({self.code})"

    def clean(self):
        if self.release_id and self.release.department_id != self.department_id:
            raise ValidationError({"release": "The party and release must belong to the same finance office."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The retirement date cannot precede the effective date."})
        if self.supersedes_id and (
            self.supersedes_id == self.pk or self.supersedes.department_id != self.department_id or self.supersedes.code != self.code
        ):
            raise ValidationError({"supersedes": "A party version may supersede only the same controlled party."})
        if self.pk and type(self).objects.filter(pk=self.pk, status__in=LOCKED_STATES).exists():
            raise ValidationError("Approved parties are immutable. Create a replacement version.")


class FinancePartyClaimant(models.Model):
    party = models.ForeignKey(FinanceParty, on_delete=models.PROTECT, related_name="authorized_claimants")
    display_name = models.CharField(max_length=220)
    relationship = models.CharField(max_length=120, blank=True)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default="draft")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_claimants")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("display_name", "pk")

    def __str__(self):
        return f"{self.display_name} — {self.party.display_name}"

    def clean(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValidationError({"valid_to": "The authorization end cannot precede its start."})
        if self.pk and type(self).objects.filter(pk=self.pk, status__in=LOCKED_STATES).exists():
            raise ValidationError("Approved claimant entries are immutable. Create a replacement entry.")


class FinanceNumberingSequence(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_numbering_sequences")
    release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="numbering_sequences")
    fiscal_year = models.PositiveSmallIntegerField()
    document_type = models.SlugField(max_length=80)
    prefix = models.CharField(max_length=30, blank=True)
    padding = models.PositiveSmallIntegerField(default=6)
    next_number = models.PositiveBigIntegerField(default=1)
    status = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default="draft")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_sequences")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=("department", "fiscal_year", "document_type"), name="unique_finance_numbering_sequence"),
        )

    def clean(self):
        if self.release_id and self.release.department_id != self.department_id:
            raise ValidationError({"release": "Numbering sequence and release must belong to the same finance office."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = ("department_id", "release_id", "fiscal_year", "document_type", "prefix", "padding", "next_number")
            if prior and prior.status in LOCKED_STATES and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("Approved numbering policy is immutable; counters advance only through the future voucher service.")


class FinanceTemplateVersion(models.Model):
    STARTER = "starter"
    PILOT = "pilot"
    LOCALLY_ACCEPTED = "locally_accepted"
    FORM_STATUS_CHOICES = (
        (STARTER, "Editable starter — not yet locally accepted"),
        (PILOT, "Pilot comparison — acceptance pending"),
        (LOCALLY_ACCEPTED, "Locally accepted against recorded evidence"),
    )
    PAPER_SIZE_CHOICES = (("a4", "A4"), ("letter", "Letter"), ("legal", "Legal"))
    ORIENTATION_CHOICES = (("portrait", "Portrait"), ("landscape", "Landscape"))
    DOCUMENT_TYPE_CHOICES = (
        ("disbursement-voucher", "Disbursement voucher"),
        ("obr", "Obligation request / OBR"),
        ("bank-advice", "Accountant's bank advice"),
        ("check-register", "Check issuance register"),
        ("release-receipt", "Check release receipt"),
    )
    REQUIRED_NAMES = (
        "GRAND_DV_NUMBER", "GRAND_DV_DATE", "GRAND_PAYEE", "GRAND_PARTICULARS",
        "GRAND_GROSS_AMOUNT", "GRAND_TOTAL_DEDUCTIONS", "GRAND_NET_AMOUNT", "GRAND_LINE_ITEMS",
        "GRAND_PREPARED_BY", "GRAND_CERTIFIED_BY", "GRAND_APPROVED_BY",
    )
    TEMPLATE_SCHEMAS = {
        "disbursement-voucher": {"required": REQUIRED_NAMES, "table": "GRAND_LINE_ITEMS"},
        "obr": {"required": (
            "GRAND_OBR_NUMBER", "GRAND_OBR_DATE", "GRAND_PAYEE", "GRAND_PARTICULARS",
            "GRAND_FUND", "GRAND_RESPONSIBILITY_CENTER", "GRAND_ACCOUNT_CODE",
            "GRAND_OBLIGATED_AMOUNT", "GRAND_PREPARED_BY", "GRAND_CERTIFIED_BY",
        ), "table": None},
        "bank-advice": {"required": (
            "GRAND_ADVICE_NUMBER", "GRAND_ADVICE_DATE", "GRAND_BANK_ACCOUNT",
            "GRAND_CHECK_LINES", "GRAND_PREPARED_BY", "GRAND_APPROVED_BY",
        ), "table": "GRAND_CHECK_LINES"},
        "check-register": {"required": (
            "GRAND_REGISTER_DATE", "GRAND_BANK_ACCOUNT", "GRAND_CHECK_LINES",
            "GRAND_PREPARED_BY", "GRAND_CERTIFIED_BY",
        ), "table": "GRAND_CHECK_LINES"},
        "release-receipt": {"required": (
            "GRAND_RELEASE_DATE", "GRAND_DV_NUMBER", "GRAND_CHECK_NUMBER", "GRAND_PAYEE",
            "GRAND_CLAIMANT", "GRAND_NET_AMOUNT", "GRAND_RELEASED_BY", "GRAND_ACKNOWLEDGED_BY",
        ), "table": None},
    }
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_templates")
    release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="templates")
    document_type = models.SlugField(max_length=80, choices=DOCUMENT_TYPE_CHOICES, default="disbursement-voucher")
    version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=180)
    form_reference = models.CharField(
        max_length=180,
        blank=True,
        help_text="Familiar form number or local title shown to users. Do not call it official unless locally accepted.",
    )
    authority_reference = models.TextField(
        blank=True,
        help_text="Reviewed COA/DBM/local issuance or procedure used to assess this layout.",
    )
    comparison_reference = models.TextField(
        blank=True,
        help_text="Blank form, redacted sample, comparison record, and accepting office reference.",
    )
    form_status = models.CharField(max_length=24, choices=FORM_STATUS_CHOICES, default=STARTER)
    paper_size = models.CharField(max_length=12, choices=PAPER_SIZE_CHOICES, default="a4")
    orientation = models.CharField(max_length=12, choices=ORIENTATION_CHOICES, default="portrait")
    default_copy_count = models.PositiveSmallIntegerField(default=1)
    printer_instructions = models.TextField(
        blank=True,
        help_text="Ordinary operator guidance: paper stock, tray, duplex setting, margins, or copy handling.",
    )
    controlled_print_required = models.BooleanField(
        default=True,
        help_text="Require a recorded print version and TracePoint packet before wet-signature recording.",
    )
    workbook = models.FileField(upload_to=finance_template_path, max_length=500, validators=[FileExtensionValidator(("xlsx",))])
    mapping = models.JSONField(default=dict, blank=True)
    workbook_checksum = models.CharField(max_length=64, blank=True)
    mapping_checksum = models.CharField(max_length=64, blank=True)
    preflight_result = models.JSONField(default=dict, blank=True)
    preflighted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="preflighted_finance_templates")
    preflighted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=LIFECYCLE_CHOICES, default="draft")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_templates")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("document_type", "-version")
        constraints = (
            models.UniqueConstraint(fields=("department", "document_type", "version"), name="unique_finance_template_version"),
        )

    @property
    def preflight_passed(self):
        return bool(self.preflighted_at and self.preflight_result.get("passed"))

    @classmethod
    def schema_for(cls, document_type):
        return cls.TEMPLATE_SCHEMAS.get(document_type)

    def clean(self):
        if self.release_id and self.release.department_id != self.department_id:
            raise ValidationError({"release": "Template and release must belong to the same finance office."})
        if self.workbook and not self.workbook.name.lower().endswith(".xlsx"):
            raise ValidationError({"workbook": "Upload a macro-free .xlsx workbook. .xls and .xlsm are not accepted."})
        if self.workbook and getattr(self.workbook, "size", 0) > 10 * 1024 * 1024:
            raise ValidationError({"workbook": "Finance templates must be 10 MB or smaller."})
        if not isinstance(self.mapping, dict):
            raise ValidationError({"mapping": "Named-range mappings must be a controlled key/value object."})
        if not self.schema_for(self.document_type):
            raise ValidationError({"document_type": "Choose a supported controlled finance document type."})
        if self.status in LOCKED_STATES and not self.preflight_passed:
            raise ValidationError({"status": "A workbook must pass preflight before approval or activation."})
        if self.form_status == self.LOCALLY_ACCEPTED:
            if not self.authority_reference.strip() or not self.comparison_reference.strip():
                raise ValidationError(
                    "A locally accepted form needs both its reviewed authority and side-by-side comparison/acceptance reference."
                )
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status in LOCKED_STATES:
                fields = (
                    "department_id", "release_id", "document_type", "version", "title",
                    "form_reference", "authority_reference", "comparison_reference", "form_status",
                    "paper_size", "orientation", "default_copy_count", "printer_instructions",
                    "controlled_print_required", "mapping", "workbook_checksum", "mapping_checksum",
                    "preflight_result", "effective_from", "effective_to",
                )
                changed = any(getattr(prior, field) != getattr(self, field) for field in fields) or prior.workbook.name != self.workbook.name
                if changed:
                    raise ValidationError("Approved finance template versions are immutable. Upload a new version.")


class FinanceWorkflowExemption(models.Model):
    RELEASE_SELF_APPROVAL = "finance-release-self-approval"
    BUDGET_CERTIFIER_DV_PREPARATION = "budget-certifier-dv-preparation"
    DV_PREPARER_SELF_VALIDATION = "dv-preparer-self-validation"
    JOURNAL_PREPARER_SELF_POSTING = "journal-preparer-self-posting"
    CONTROL_CHOICES = (
        (RELEASE_SELF_APPROVAL, "Finance release preparer may approve the same release"),
        (BUDGET_CERTIFIER_DV_PREPARATION, "Budget certifier may prepare the same DV"),
        (DV_PREPARER_SELF_VALIDATION, "DV preparer may validate the same voucher"),
        (JOURNAL_PREPARER_SELF_POSTING, "Journal preparer may post the same JEV"),
    )

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="finance_workflow_exemptions",
        help_text="The exemption applies only while the actor is assigned to this department.",
    )
    control_code = models.SlugField(max_length=80, choices=CONTROL_CHOICES)
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="finance_workflow_exemptions",
        help_text="Choose either one named user or one role/group, never both.",
    )
    subject_group = models.ForeignKey(
        "auth.Group", on_delete=models.PROTECT, null=True, blank=True,
        related_name="finance_workflow_exemptions",
        help_text="A group-based exemption follows the assigned role without naming each employee.",
    )
    rationale = models.TextField(help_text="Document the approved operational basis and compensating review control.")
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_workflow_exemptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("department", "control_code", "-effective_from", "-pk")
        permissions = (("manage_workflow_exemptions", "Can manage governed finance workflow exemptions"),)
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(subject_user__isnull=False, subject_group__isnull=True)
                    | models.Q(subject_user__isnull=True, subject_group__isnull=False)
                ),
                name="finance_exemption_exactly_one_subject",
            ),
        )

    def __str__(self):
        subject = self.subject_user or self.subject_group
        return f"{self.get_control_code_display()} — {subject}"

    def clean(self):
        if bool(self.subject_user_id) == bool(self.subject_group_id):
            raise ValidationError("Choose exactly one exempt user or role/group.")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The exemption end date cannot precede its start date."})
        if self.subject_user_id:
            assigned_department_id = getattr(
                getattr(self.subject_user, "employeeprofile", None), "assigned_department_id", None,
            )
            if assigned_department_id != self.department_id:
                raise ValidationError({"subject_user": "The exempt user must currently belong to the selected department."})


class FinanceAuditEvent(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_audit_events")
    release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, null=True, blank=True, related_name="events")
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
    action = models.CharField(max_length=60)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="finance_audit_events")
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Finance audit events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Finance audit events cannot be deleted.")


class FinanceShadowCycle(models.Model):
    DRAFT = "draft"
    RUNNING = "running"
    RECONCILIATION_REVIEW = "reconciliation_review"
    RECONCILED = "reconciled"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (DRAFT, "Draft plan"),
        (RUNNING, "Shadow / parallel run in progress"),
        (RECONCILIATION_REVIEW, "Awaiting independent reconciliation"),
        (RECONCILED, "Independently reconciled"),
        (RETURNED, "Returned for another cycle"),
    )
    SHADOW = "shadow"
    PARALLEL = "parallel"
    RUN_KIND_CHOICES = (
        (SHADOW, "Limited shadow pilot"),
        (PARALLEL, "Controlled parallel run"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_shadow_cycles")
    code = models.SlugField(max_length=80)
    title = models.CharField(max_length=180)
    fiscal_year = models.PositiveSmallIntegerField()
    run_kind = models.CharField(max_length=16, choices=RUN_KIND_CHOICES, default=SHADOW)
    enabled_scope = models.TextField(help_text="State the offices, funds, transaction types, and dates included in this cycle.")
    source_system_label = models.CharField(max_length=120, default="Current locally authoritative process")
    source_extract_reference = models.TextField(help_text="Reference the redacted/read-only source extract or retained register; do not upload production data here.")
    source_checksum = models.CharField(max_length=64, blank=True, help_text="GRAND calculates this lock when a redacted CSV is staged.")
    source_schema_signature = models.CharField(max_length=64, blank=True, help_text="GRAND calculates this column-layout signature to detect drift.")
    planned_start = models.DateField()
    planned_end = models.DateField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=DRAFT)
    evidence_checksum = models.CharField(max_length=64, blank=True)
    predecessor = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_cycles")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_shadow_cycles")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="submitted_finance_shadow_cycles")
    submitted_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reconciled_finance_shadow_cycles")
    reconciled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fiscal_year", "-planned_start", "code")
        constraints = (
            models.UniqueConstraint(fields=("department", "code"), name="unique_finance_shadow_cycle_code"),
        )
        permissions = (
            ("manage_shadow_operation", "Can prepare finance shadow operation evidence"),
            ("review_shadow_reconciliation", "Can independently reconcile finance shadow operation"),
            ("authorize_finance_cutover", "Can authorize or decline finance cutover"),
        )

    def __str__(self):
        return f"{self.title} ({self.code})"

    def clean(self):
        if self.planned_end < self.planned_start:
            raise ValidationError({"planned_end": "The end date cannot be before the start date."})
        for field in ("source_checksum", "source_schema_signature"):
            value = getattr(self, field, "").lower()
            if value and (len(value) != 64 or any(character not in "0123456789abcdef" for character in value)):
                raise ValidationError({field: "Enter the 64-character SHA-256 value for the reviewed source."})
        if self.status != self.DRAFT and (not self.source_checksum or not self.source_schema_signature):
            raise ValidationError("Lock a redacted/read-only source before starting the shadow cycle.")
        if self.predecessor_id:
            if self.predecessor_id == self.pk or self.predecessor.department_id != self.department_id:
                raise ValidationError({"predecessor": "A predecessor must be an earlier cycle owned by the same Finance office."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status in {self.RECONCILIATION_REVIEW, self.RECONCILED}:
                governed = (
                    "department_id", "code", "title", "fiscal_year", "run_kind", "enabled_scope",
                    "source_system_label", "source_extract_reference", "source_checksum",
                    "source_schema_signature", "planned_start", "planned_end", "predecessor_id",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Submitted shadow-cycle evidence is immutable. Record corrections in a successor cycle.")

    def delete(self, *args, **kwargs):
        if self.status != self.DRAFT:
            raise ValidationError("A started shadow cycle cannot be deleted.")
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class FinanceShadowSourceVersion(models.Model):
    UPLOADED_CSV = "uploaded_csv"
    EXTERNAL_LOCK = "external_lock"
    INTAKE_CHOICES = (
        (UPLOADED_CSV, "Redacted CSV staged in GRAND"),
        (EXTERNAL_LOCK, "Externally calculated source lock"),
    )
    BASELINE = "baseline"
    MATCHED = "matched"
    DRIFT = "drift"
    SCHEMA_CHOICES = (
        (BASELINE, "Baseline; no predecessor to compare"),
        (MATCHED, "Matches predecessor layout"),
        (DRIFT, "Column layout changed"),
    )
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVIEW_CHOICES = (
        (NOT_REQUIRED, "No separate drift review required"),
        (PENDING, "Awaiting independent drift review"),
        (ACCEPTED, "Drift independently accepted for this cycle"),
        (REJECTED, "Drift rejected"),
    )

    cycle = models.ForeignKey(FinanceShadowCycle, on_delete=models.PROTECT, related_name="source_versions")
    version = models.PositiveIntegerField()
    intake_kind = models.CharField(max_length=20, choices=INTAKE_CHOICES)
    source_file = models.FileField(
        upload_to=finance_shadow_source_path, max_length=500, blank=True,
        validators=[FileExtensionValidator(("csv",))],
        help_text="Retained redacted/read-only CSV. GRAND does not execute or import its rows.",
    )
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    source_checksum = models.CharField(max_length=64)
    normalized_headers = models.JSONField(default=list, blank=True)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    schema_signature = models.CharField(max_length=64)
    predecessor_schema_signature = models.CharField(max_length=64, blank=True)
    schema_comparison = models.CharField(max_length=16, choices=SCHEMA_CHOICES)
    sensitive_header_warnings = models.JSONField(default=list, blank=True)
    redaction_confirmed = models.BooleanField(default=False)
    redaction_note = models.TextField()
    change_reason = models.TextField(blank=True)
    is_current = models.BooleanField(default=True)
    review_status = models.CharField(max_length=16, choices=REVIEW_CHOICES, default=NOT_REQUIRED)
    review_note = models.TextField(blank=True)
    staged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="staged_finance_shadow_sources",
    )
    staged_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_shadow_source_drifts",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-version", "-pk")
        constraints = (
            models.UniqueConstraint(fields=("cycle", "version"), name="unique_shadow_source_version"),
            models.UniqueConstraint(
                fields=("cycle",), condition=models.Q(is_current=True),
                name="unique_current_shadow_source_version",
            ),
        )

    def __str__(self):
        return f"{self.cycle.code} source v{self.version}"

    def clean(self):
        if self.cycle_id and self.cycle.status != FinanceShadowCycle.DRAFT:
            raise ValidationError("Source versions can be staged or reviewed only before the cycle starts.")
        for field in ("source_checksum", "schema_signature"):
            value = getattr(self, field, "").lower()
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValidationError({field: "A valid 64-character SHA-256 value is required."})
        if self.source_file and self.file_size > 5 * 1024 * 1024:
            raise ValidationError({"source_file": "The redacted CSV must be 5 MB or smaller."})
        if self.intake_kind == self.UPLOADED_CSV and not self.source_file:
            raise ValidationError({"source_file": "Choose the redacted CSV to stage."})
        if self.intake_kind == self.EXTERNAL_LOCK and self.source_file:
            raise ValidationError({"source_file": "An external lock does not retain a source file."})
        if not isinstance(self.normalized_headers, list) or not isinstance(self.sensitive_header_warnings, list):
            raise ValidationError("Source header evidence must be stored as a list.")
        if not self.redaction_confirmed or not self.redaction_note.strip():
            raise ValidationError("Confirm redaction and describe what was removed, masked, or intentionally retained.")
        if self.schema_comparison == self.DRIFT and self.review_status == self.NOT_REQUIRED:
            raise ValidationError("A changed column layout requires independent review.")
        if self.review_status in {self.ACCEPTED, self.REJECTED}:
            if not self.reviewed_by_id or not self.reviewed_at or not self.review_note.strip():
                raise ValidationError("A drift decision requires the reviewer, date, and plain-language basis.")
            if self.reviewed_by_id == self.staged_by_id:
                raise ValidationError("The person who staged the source cannot review its schema drift.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "cycle_id", "version", "intake_kind", "source_file", "original_filename", "file_size",
                "source_checksum", "normalized_headers", "row_count", "schema_signature",
                "predecessor_schema_signature", "schema_comparison", "sensitive_header_warnings",
                "redaction_confirmed", "redaction_note", "change_reason", "staged_by_id", "staged_at",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Staged source evidence is immutable. Stage a new version with a reason.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Source-version evidence is retained and cannot be deleted.")


class FinanceShadowComparison(models.Model):
    CASE = "case"
    BATCH = "batch"
    PERIOD = "period"
    REGISTER = "register"
    LEDGER = "ledger"
    REPORT = "report"
    LEVEL_CHOICES = (
        (CASE, "Case / transaction"),
        (BATCH, "Batch"),
        (PERIOD, "Period control"),
        (REGISTER, "Register"),
        (LEDGER, "Ledger"),
        (REPORT, "Report / statement"),
    )
    MATCHED = "matched"
    EXPLAINED = "explained"
    OPEN_DEFECT = "open_defect"
    OUTCOME_CHOICES = (
        (MATCHED, "Matched exactly"),
        (EXPLAINED, "Difference explained and accepted for review"),
        (OPEN_DEFECT, "Open defect / unresolved difference"),
    )

    cycle = models.ForeignKey(FinanceShadowCycle, on_delete=models.PROTECT, related_name="comparisons")
    comparison_level = models.CharField(max_length=16, choices=LEVEL_CHOICES)
    control_code = models.SlugField(max_length=80)
    label = models.CharField(max_length=180)
    source_reference = models.TextField()
    grand_reference = models.TextField()
    source_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    grand_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    source_count = models.PositiveIntegerField(null=True, blank=True)
    grand_count = models.PositiveIntegerField(null=True, blank=True)
    amount_difference = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, editable=False)
    count_difference = models.IntegerField(null=True, blank=True, editable=False)
    outcome = models.CharField(max_length=16, choices=OUTCOME_CHOICES)
    explanation = models.TextField(blank=True)
    evidence_reference = models.TextField()
    defect_owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="owned_finance_shadow_defects")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_shadow_comparisons")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("comparison_level", "control_code", "pk")
        constraints = (
            models.UniqueConstraint(fields=("cycle", "comparison_level", "control_code"), name="unique_shadow_comparison_control"),
        )

    def __str__(self):
        return f"{self.cycle.code}: {self.label}"

    def clean(self):
        if self.cycle_id and self.cycle.status not in {FinanceShadowCycle.DRAFT, FinanceShadowCycle.RUNNING}:
            raise ValidationError("Comparisons can be changed only while the shadow cycle is being prepared or run.")
        if (self.source_amount is None) != (self.grand_amount is None):
            raise ValidationError("Enter both source and GRAND amounts, or leave both blank for a count-only control.")
        if (self.source_count is None) != (self.grand_count is None):
            raise ValidationError("Enter both source and GRAND counts, or leave both blank for an amount-only control.")
        if self.source_amount is None and self.source_count is None:
            raise ValidationError("Compare an amount, an item count, or both.")
        amount_difference = None if self.source_amount is None else self.grand_amount - self.source_amount
        count_difference = None if self.source_count is None else self.grand_count - self.source_count
        differs = (amount_difference not in (None, 0)) or (count_difference not in (None, 0))
        if self.outcome == self.MATCHED and differs:
            raise ValidationError({"outcome": "Matched exactly is available only when every entered amount and count difference is zero."})
        if self.outcome in {self.EXPLAINED, self.OPEN_DEFECT} and not self.explanation.strip():
            raise ValidationError({"explanation": "Explain the difference or defect in ordinary office language."})
        if self.outcome == self.OPEN_DEFECT and not self.defect_owner_id:
            raise ValidationError({"defect_owner": "Assign an owner for an unresolved difference."})

    def save(self, *args, **kwargs):
        self.full_clean()
        self.amount_difference = None if self.source_amount is None else self.grand_amount - self.source_amount
        self.count_difference = None if self.source_count is None else self.grand_count - self.source_count
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.cycle.status not in {FinanceShadowCycle.DRAFT, FinanceShadowCycle.RUNNING}:
            raise ValidationError("Submitted comparison evidence cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceShadowReconciliationPlan(models.Model):
    CALENDAR_DAILY = "calendar_daily"
    BUSINESS_DAILY = "business_daily"
    CADENCE_CHOICES = (
        (CALENDAR_DAILY, "Every calendar day"),
        (BUSINESS_DAILY, "Every working day (Monday–Friday)"),
    )
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (DRAFT, "Draft local plan"),
        (SUBMITTED, "Awaiting independent approval"),
        (APPROVED, "Approved for this cycle"),
        (RETURNED, "Returned for correction"),
    )

    cycle = models.OneToOneField(
        FinanceShadowCycle, on_delete=models.PROTECT, related_name="reconciliation_plan",
    )
    cadence = models.CharField(max_length=20, choices=CADENCE_CHOICES)
    first_due_at = models.DateTimeField()
    grace_minutes = models.PositiveIntegerField(default=60)
    minimum_reviewed_runs = models.PositiveIntegerField(default=1)
    enabled_transaction_types = models.TextField(
        help_text="Name the transaction types covered by each scheduled comparison run.",
    )
    local_authority_reference = models.TextField()
    local_acceptance_note = models.TextField()
    critical_resolution_hours = models.PositiveIntegerField(default=4)
    critical_escalation_route = models.CharField(max_length=200)
    high_resolution_hours = models.PositiveIntegerField(default=8)
    high_escalation_route = models.CharField(max_length=200)
    medium_resolution_hours = models.PositiveIntegerField(default=24)
    medium_escalation_route = models.CharField(max_length=200)
    low_resolution_hours = models.PositiveIntegerField(default=72)
    low_escalation_route = models.CharField(max_length=200)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    evidence_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_shadow_reconciliation_plans",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_shadow_reconciliation_plans",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="approved_finance_shadow_reconciliation_plans",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.cycle.code} reconciliation plan"

    def clean(self):
        if self.cycle_id and self.cycle.status != FinanceShadowCycle.DRAFT:
            raise ValidationError("The reconciliation plan must be approved before the cycle starts.")
        if self.first_due_at and self.cycle_id:
            local_due = timezone.localtime(self.first_due_at).date()
            if not self.cycle.planned_start <= local_due <= self.cycle.planned_end:
                raise ValidationError({"first_due_at": "The first due time must fall inside the planned cycle dates."})
        if self.grace_minutes > 7 * 24 * 60:
            raise ValidationError({"grace_minutes": "The review grace period cannot exceed seven days."})
        if not 1 <= self.minimum_reviewed_runs <= 366:
            raise ValidationError({"minimum_reviewed_runs": "Enter between 1 and 366 required reviewed runs."})
        for severity in ("critical", "high", "medium", "low"):
            hours = getattr(self, f"{severity}_resolution_hours")
            route = getattr(self, f"{severity}_escalation_route", "")
            if not 1 <= hours <= 24 * 90:
                raise ValidationError({f"{severity}_resolution_hours": "Enter a target from 1 hour through 90 days."})
            if not route.strip():
                raise ValidationError({f"{severity}_escalation_route": "Name the locally accepted person, role, or office escalation route."})
        if self.status in {self.SUBMITTED, self.APPROVED} and not self.evidence_checksum:
            raise ValidationError("Submitted reconciliation plans require a checksum-backed snapshot.")
        if self.status == self.APPROVED:
            if not self.approved_by_id or not self.approved_at or not self.review_note.strip():
                raise ValidationError("Approved plans require an independent reviewer, time, and basis.")
            if self.approved_by_id in {self.created_by_id, self.submitted_by_id}:
                raise ValidationError("The plan preparer or submitter cannot approve the same local plan.")
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "cycle_id", "cadence", "first_due_at", "grace_minutes", "minimum_reviewed_runs",
                "enabled_transaction_types", "local_authority_reference", "local_acceptance_note",
                "critical_resolution_hours", "critical_escalation_route", "high_resolution_hours",
                "high_escalation_route", "medium_resolution_hours", "medium_escalation_route",
                "low_resolution_hours", "low_escalation_route", "created_by_id",
            )
            if prior.status in {self.SUBMITTED, self.APPROVED} and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted plan controls are immutable. Return the plan before correction.")
            if prior.status == self.APPROVED:
                locked = governed + (
                    "status", "evidence_checksum", "submitted_by_id", "submitted_at",
                    "approved_by_id", "approved_at", "review_note",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in locked):
                    raise ValidationError("An approved reconciliation plan is immutable for this cycle.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.DRAFT:
            raise ValidationError("A submitted reconciliation plan cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceShadowReconciliationRun(models.Model):
    OPEN = "open"
    SUBMITTED = "submitted"
    RECONCILED = "reconciled"
    REVIEWED_WITH_EXCEPTIONS = "reviewed_exceptions"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (OPEN, "Open comparison run"),
        (SUBMITTED, "Awaiting independent review"),
        (RECONCILED, "Independently reconciled"),
        (REVIEWED_WITH_EXCEPTIONS, "Reviewed with open exceptions"),
        (RETURNED, "Returned for correction"),
    )

    cycle = models.ForeignKey(
        FinanceShadowCycle, on_delete=models.PROTECT, related_name="reconciliation_runs",
    )
    plan = models.ForeignKey(
        FinanceShadowReconciliationPlan, on_delete=models.PROTECT, related_name="runs",
    )
    sequence = models.PositiveIntegerField()
    scheduled_for = models.DateTimeField()
    due_at = models.DateTimeField()
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=OPEN)
    comparison_snapshot = models.JSONField(default=list, blank=True)
    defect_snapshot = models.JSONField(default=list, blank=True)
    comparison_count = models.PositiveIntegerField(default=0)
    matched_count = models.PositiveIntegerField(default=0)
    explained_count = models.PositiveIntegerField(default=0)
    open_defect_count = models.PositiveIntegerField(default=0)
    evidence_checksum = models.CharField(max_length=64, blank=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="prepared_finance_shadow_reconciliation_runs",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_shadow_reconciliation_runs",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_shadow_reconciliation_runs",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sequence", "pk")
        constraints = (
            models.UniqueConstraint(fields=("cycle", "sequence"), name="unique_shadow_reconciliation_sequence"),
            models.UniqueConstraint(fields=("cycle", "scheduled_for"), name="unique_shadow_reconciliation_schedule"),
        )

    def __str__(self):
        return f"{self.cycle.code} reconciliation #{self.sequence}"

    @property
    def is_overdue(self):
        return self.status in {self.OPEN, self.RETURNED} and timezone.now() > self.due_at

    def clean(self):
        if self.cycle_id and self.plan_id and self.plan.cycle_id != self.cycle_id:
            raise ValidationError({"plan": "Use the reconciliation plan approved for this cycle."})
        if self.due_at and self.scheduled_for and self.due_at < self.scheduled_for:
            raise ValidationError({"due_at": "The due time cannot precede the scheduled run time."})
        if not isinstance(self.comparison_snapshot, list) or not isinstance(self.defect_snapshot, list):
            raise ValidationError("Reconciliation evidence snapshots must be lists.")
        if self.status in {self.SUBMITTED, self.RECONCILED, self.REVIEWED_WITH_EXCEPTIONS}:
            if not self.evidence_checksum or not self.submitted_by_id or not self.submitted_at:
                raise ValidationError("Submitted runs require checksum-backed evidence and an attributed submitter.")
        if self.status in {self.RECONCILED, self.REVIEWED_WITH_EXCEPTIONS}:
            if not self.reviewed_by_id or not self.reviewed_at or not self.review_note.strip():
                raise ValidationError("Reviewed runs require an independent reviewer and basis.")
            if self.reviewed_by_id == self.submitted_by_id:
                raise ValidationError("The run submitter cannot independently review the same evidence.")
        if self.status == self.RECONCILED and self.open_defect_count:
            raise ValidationError("A run with open defects must be recorded as reviewed with exceptions.")
        if self.status == self.REVIEWED_WITH_EXCEPTIONS and not self.open_defect_count:
            raise ValidationError("Use independently reconciled when the run has no open defects.")
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            evidence_fields = (
                "cycle_id", "plan_id", "sequence", "scheduled_for", "due_at",
                "comparison_snapshot", "defect_snapshot", "comparison_count", "matched_count",
                "explained_count", "open_defect_count", "evidence_checksum", "prepared_by_id",
            )
            if prior.status in {self.SUBMITTED, self.RECONCILED, self.REVIEWED_WITH_EXCEPTIONS} and any(
                getattr(prior, field) != getattr(self, field) for field in evidence_fields
            ):
                raise ValidationError("Submitted run evidence is immutable. Return before correction or open the next scheduled run.")
            if prior.status in {self.RECONCILED, self.REVIEWED_WITH_EXCEPTIONS}:
                locked = evidence_fields + (
                    "status", "submitted_by_id", "submitted_at", "reviewed_by_id",
                    "reviewed_at", "review_note",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in locked):
                    raise ValidationError("An independently reviewed run is immutable. Open the next scheduled run.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Scheduled reconciliation history cannot be deleted.")


class FinanceShadowDefect(models.Model):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SEVERITY_CHOICES = (
        (CRITICAL, "Critical"), (HIGH, "High"), (MEDIUM, "Medium"), (LOW, "Low"),
    )
    OPEN = "open"
    RESOLUTION_REVIEW = "resolution_review"
    RESOLVED = "resolved"
    STATUS_CHOICES = (
        (OPEN, "Open / being corrected"),
        (RESOLUTION_REVIEW, "Resolution awaiting independent review"),
        (RESOLVED, "Resolution independently accepted"),
    )

    cycle = models.ForeignKey(FinanceShadowCycle, on_delete=models.PROTECT, related_name="defects")
    first_seen_run = models.ForeignKey(
        FinanceShadowReconciliationRun, on_delete=models.PROTECT, null=True, blank=True,
        related_name="first_seen_defects",
    )
    comparison = models.ForeignKey(
        FinanceShadowComparison, on_delete=models.PROTECT, related_name="defects",
    )
    code = models.SlugField(max_length=80)
    severity = models.CharField(max_length=12, choices=SEVERITY_CHOICES)
    summary = models.CharField(max_length=200)
    impact = models.TextField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_finance_shadow_defects",
    )
    correction_due_at = models.DateTimeField()
    escalation_route_snapshot = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    resolution_note = models.TextField(blank=True)
    resolution_evidence_reference = models.TextField(blank=True)
    resolution_submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_shadow_defect_resolutions",
    )
    resolution_submitted_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="resolved_finance_shadow_defects",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    last_escalation_note = models.TextField(blank=True)
    last_escalation_at = models.DateTimeField(null=True, blank=True)
    last_escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="escalated_finance_shadow_defects",
    )
    escalation_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_shadow_defects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("status", "correction_due_at", "-severity", "code")
        constraints = (
            models.UniqueConstraint(fields=("cycle", "code"), name="unique_shadow_defect_code"),
        )

    def __str__(self):
        return f"{self.code} — {self.summary}"

    @property
    def is_overdue(self):
        return self.status != self.RESOLVED and timezone.now() > self.correction_due_at

    def clean(self):
        if self.comparison_id and self.cycle_id and self.comparison.cycle_id != self.cycle_id:
            raise ValidationError({"comparison": "The defect comparison must belong to this cycle."})
        if self.first_seen_run_id and self.first_seen_run.cycle_id != self.cycle_id:
            raise ValidationError({"first_seen_run": "The first-seen run must belong to this cycle."})
        if self.owner_id and self.comparison_id and self.comparison.defect_owner_id not in {None, self.owner_id}:
            raise ValidationError({"owner": "Use the owner already assigned on the open comparison, or correct the comparison first."})
        if self.status in {self.RESOLUTION_REVIEW, self.RESOLVED}:
            if not self.resolution_note.strip() or not self.resolution_evidence_reference.strip():
                raise ValidationError("A proposed resolution requires both a plain-language correction note and retained evidence reference.")
            if not self.resolution_submitted_by_id or not self.resolution_submitted_at:
                raise ValidationError("A proposed resolution requires an attributed submitter and time.")
        if self.status == self.RESOLVED:
            if not self.resolved_by_id or not self.resolved_at:
                raise ValidationError("A resolved defect requires an independent reviewer and time.")
            if self.resolved_by_id == self.resolution_submitted_by_id:
                raise ValidationError("The resolution submitter cannot independently accept the same correction.")
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            immutable = (
                "cycle_id", "first_seen_run_id", "comparison_id", "code", "severity", "summary",
                "impact", "owner_id", "correction_due_at", "escalation_route_snapshot", "created_by_id",
            )
            if any(getattr(prior, field) != getattr(self, field) for field in immutable):
                raise ValidationError("Defect intake evidence is immutable. Use resolution and escalation actions.")
            if prior.status == self.RESOLVED:
                locked = immutable + (
                    "status", "resolution_note", "resolution_evidence_reference",
                    "resolution_submitted_by_id", "resolution_submitted_at", "resolved_by_id",
                    "resolved_at", "last_escalation_note", "last_escalation_at",
                    "last_escalated_by_id", "escalation_count",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in locked):
                    raise ValidationError("An independently resolved defect is immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Defect history cannot be deleted.")


class FinanceCutoverReadinessPlan(models.Model):
    LEARNING_PRIVACY_NOTICE = (
        "Floating Internal How-To progress is private, optional learning-state data. "
        "It is not training acceptance, performance evidence, or an employee evaluation."
    )
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (DRAFT, "Draft readiness plan"),
        (SUBMITTED, "Awaiting independent approval"),
        (APPROVED, "Approved for this cycle"),
        (RETURNED, "Returned for correction"),
    )

    cycle = models.OneToOneField(
        FinanceShadowCycle, on_delete=models.PROTECT, related_name="cutover_readiness_plan",
    )
    curriculum_register_reference = models.TextField()
    quick_guides_reference = models.TextField()
    supervisor_runbook_reference = models.TextField()
    support_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="owned_finance_cutover_readiness_plans",
    )
    support_channels_and_hours = models.TextField()
    support_escalation_procedure = models.TextField()
    local_acceptance_note = models.TextField()
    learning_privacy_notice = models.TextField(
        default=LEARNING_PRIVACY_NOTICE, editable=False,
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    evidence_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_cutover_readiness_plans",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_cutover_readiness_plans",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="approved_finance_cutover_readiness_plans",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.cycle.code} cutover readiness plan"

    def clean(self):
        if self.learning_privacy_notice != self.LEARNING_PRIVACY_NOTICE:
            raise ValidationError("The private, non-evaluative Internal How-To progress boundary cannot be changed.")
        if self.cycle_id:
            try:
                cutover_status = self.cycle.cutover_decision.status
            except FinanceCutoverDecision.DoesNotExist:
                cutover_status = ""
            if cutover_status and cutover_status != FinanceCutoverDecision.DRAFT and not self.pk:
                raise ValidationError("The readiness plan cannot be added after the cutover record is submitted.")
        if self.status in {self.SUBMITTED, self.APPROVED} and not self.evidence_checksum:
            raise ValidationError("Submitted readiness plans require a checksum-backed snapshot.")
        if self.status == self.APPROVED:
            if not self.approved_by_id or not self.approved_at or not self.review_note.strip():
                raise ValidationError("Approved readiness plans require an independent reviewer, time, and basis.")
            if self.approved_by_id in {self.created_by_id, self.submitted_by_id}:
                raise ValidationError("The readiness-plan preparer or submitter cannot approve the same plan.")
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "cycle_id", "curriculum_register_reference", "quick_guides_reference",
                "supervisor_runbook_reference", "support_owner_id", "support_channels_and_hours",
                "support_escalation_procedure", "local_acceptance_note", "learning_privacy_notice",
                "created_by_id",
            )
            if prior.status in {self.SUBMITTED, self.APPROVED} and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted readiness controls are immutable. Return the plan before correction.")
            if prior.status == self.APPROVED:
                locked = governed + (
                    "status", "evidence_checksum", "submitted_by_id", "submitted_at",
                    "approved_by_id", "approved_at", "review_note",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in locked):
                    raise ValidationError("An approved cutover readiness plan is immutable for this cycle.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.DRAFT:
            raise ValidationError("A submitted cutover readiness plan cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceCutoverReadinessExercise(models.Model):
    ROLE_TRAINING = "role_training"
    SECURITY_ACCESS = "security_access"
    PRIVACY = "privacy"
    ACCESSIBILITY = "accessibility"
    PERFORMANCE = "performance"
    PRINTING = "printing"
    BACKUP_RESTORE = "backup_restore"
    BUSINESS_CONTINUITY = "business_continuity"
    INCIDENT_RESPONSE = "incident_response"
    KIND_CHOICES = (
        (ROLE_TRAINING, "Role curriculum and synthetic job exercise"),
        (SECURITY_ACCESS, "Security and access-control exercise"),
        (PRIVACY, "Privacy and redaction exercise"),
        (ACCESSIBILITY, "Accessibility and assisted-use exercise"),
        (PERFORMANCE, "Performance and operating-volume exercise"),
        (PRINTING, "Printing, paper, and physical-custody exercise"),
        (BACKUP_RESTORE, "Backup and restore exercise"),
        (BUSINESS_CONTINUITY, "Business-continuity exercise"),
        (INCIDENT_RESPONSE, "Incident and support-escalation exercise"),
    )
    PLANNED = "planned"
    SUBMITTED = "submitted"
    PASSED = "passed"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (PLANNED, "Planned / evidence in progress"),
        (SUBMITTED, "Awaiting assigned witness"),
        (PASSED, "Independently witnessed as passed"),
        (RETURNED, "Returned for correction or rerun"),
    )

    cycle = models.ForeignKey(
        FinanceShadowCycle, on_delete=models.PROTECT, related_name="cutover_readiness_exercises",
    )
    plan = models.ForeignKey(
        FinanceCutoverReadinessPlan, on_delete=models.PROTECT, related_name="exercises",
    )
    stakeholder_acceptance = models.ForeignKey(
        "FinanceStakeholderAcceptance", on_delete=models.PROTECT, null=True, blank=True,
        related_name="training_exercises",
    )
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    code = models.SlugField(max_length=80)
    title = models.CharField(max_length=200)
    enabled_scope = models.TextField()
    procedure = models.TextField()
    expected_result = models.TextField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="owned_finance_cutover_readiness_exercises",
    )
    witness = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="witnessed_finance_cutover_readiness_exercises",
    )
    support_route_snapshot = models.TextField()
    scheduled_for = models.DateTimeField()
    due_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PLANNED)
    actual_result = models.TextField(blank=True)
    evidence_reference = models.TextField(blank=True)
    evidence_checksum = models.CharField(max_length=64, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_cutover_readiness_exercises",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_cutover_readiness_exercises",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="created_finance_cutover_readiness_exercises",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("kind", "scheduled_for", "code")
        constraints = (
            models.UniqueConstraint(fields=("cycle", "code"), name="unique_cutover_readiness_exercise_code"),
        )

    def __str__(self):
        return f"{self.code} — {self.title}"

    @property
    def is_overdue(self):
        return self.status != self.PASSED and timezone.now() > self.due_at

    def clean(self):
        if self.cycle_id:
            try:
                cutover_status = self.cycle.cutover_decision.status
            except FinanceCutoverDecision.DoesNotExist:
                cutover_status = ""
            if cutover_status and cutover_status != FinanceCutoverDecision.DRAFT and not self.pk:
                raise ValidationError("Readiness exercises cannot be added after the cutover record is submitted.")
        if self.plan_id and self.cycle_id and self.plan.cycle_id != self.cycle_id:
            raise ValidationError({"plan": "Use the cutover readiness plan approved for this cycle."})
        if self.plan_id and self.plan.status != FinanceCutoverReadinessPlan.APPROVED:
            raise ValidationError({"plan": "Approve the cutover readiness plan before scheduling exercises."})
        if self.cycle_id and self.enabled_scope.strip() != self.cycle.enabled_scope.strip():
            raise ValidationError({"enabled_scope": "The exercise scope must exactly match the shadow cycle."})
        if self.due_at and self.scheduled_for and self.due_at < self.scheduled_for:
            raise ValidationError({"due_at": "The evidence due time cannot precede the scheduled exercise time."})
        if self.owner_id and self.witness_id and self.owner_id == self.witness_id:
            raise ValidationError({"witness": "The exercise owner cannot independently witness the same result."})
        if self.kind == self.ROLE_TRAINING:
            if not self.stakeholder_acceptance_id:
                raise ValidationError({"stakeholder_acceptance": "Choose the stakeholder acceptance covered by this role exercise."})
            if self.stakeholder_acceptance_id:
                acceptance = self.stakeholder_acceptance
                if acceptance.cycle_id != self.cycle_id:
                    raise ValidationError({"stakeholder_acceptance": "The stakeholder acceptance must belong to this cycle."})
                if self.owner_id != acceptance.assigned_reviewer_id:
                    raise ValidationError({"owner": "The role-exercise owner must be the named stakeholder reviewer."})
        elif self.stakeholder_acceptance_id:
            raise ValidationError({"stakeholder_acceptance": "Only role curriculum exercises attach to a stakeholder acceptance."})
        if self.status in {self.SUBMITTED, self.PASSED}:
            if not self.actual_result.strip() or not self.evidence_reference.strip():
                raise ValidationError("Submitted exercises require an actual result and retained evidence reference.")
            if not self.evidence_checksum or not self.submitted_by_id or not self.submitted_at:
                raise ValidationError("Submitted exercises require checksum-backed evidence and an attributed owner.")
        if self.status == self.PASSED:
            if not self.reviewed_by_id or not self.reviewed_at or not self.review_note.strip():
                raise ValidationError("Passed exercises require an assigned witness, time, and review basis.")
            if self.reviewed_by_id != self.witness_id:
                raise ValidationError("Only the assigned witness can independently pass this exercise.")
            if self.reviewed_by_id == self.submitted_by_id:
                raise ValidationError("The evidence submitter cannot independently witness the same exercise.")
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            planned_fields = (
                "cycle_id", "plan_id", "stakeholder_acceptance_id", "kind", "code", "title",
                "enabled_scope", "procedure", "expected_result", "owner_id", "witness_id",
                "support_route_snapshot", "scheduled_for", "due_at", "created_by_id",
            )
            evidence_fields = planned_fields + (
                "actual_result", "evidence_reference", "evidence_checksum", "submitted_by_id", "submitted_at",
            )
            if prior.status == self.SUBMITTED and any(
                getattr(prior, field) != getattr(self, field) for field in evidence_fields
            ):
                raise ValidationError("Submitted exercise evidence is immutable. The witness must return it before a rerun.")
            if prior.status == self.PASSED:
                locked = evidence_fields + ("status", "reviewed_by_id", "reviewed_at", "review_note")
                if any(getattr(prior, field) != getattr(self, field) for field in locked):
                    raise ValidationError("An independently passed readiness exercise is immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.PLANNED:
            raise ValidationError("Submitted readiness exercise history cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceCutoverQualificationPlan(models.Model):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (DRAFT, "Draft qualification plan"),
        (SUBMITTED, "Awaiting independent review"),
        (APPROVED, "Approved for field qualification"),
        (RETURNED, "Returned for correction"),
    )

    cycle = models.OneToOneField(
        FinanceShadowCycle, on_delete=models.PROTECT, related_name="cutover_qualification_plan",
    )
    minimum_consecutive_cycles = models.PositiveSmallIntegerField(
        default=2,
        help_text="Editable local threshold. Count the candidate cycle and its explicit predecessors; use at least two.",
    )
    require_parallel_cycle = models.BooleanField(
        default=True,
        help_text="Keep selected when local acceptance requires at least one controlled parallel run in the qualifying chain.",
    )
    local_authority_reference = models.TextField(
        help_text="Reference the locally approved pilot/parallel-run direction. Do not treat the starter threshold as a COA or DBM rule.",
    )
    accepted_rules_forms_reference = models.TextField(
        help_text="Reference the locally accepted rules, forms, print layouts, and instructions used across the qualifying cycles.",
    )
    field_evidence_basis = models.TextField(
        help_text="State what counts as actual field execution and which retained records prove it.",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    evidence_checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_cutover_qualification_plans",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_cutover_qualification_plans",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="approved_finance_cutover_qualification_plans",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-cycle__fiscal_year", "cycle__code")

    def __str__(self):
        return f"{self.cycle.code} field-cycle qualification plan"

    def clean(self):
        if self.minimum_consecutive_cycles < 2:
            raise ValidationError({"minimum_consecutive_cycles": "Use at least two consecutive cycles; record the actual local threshold in the authority reference."})
        if self.evidence_checksum and (
            len(self.evidence_checksum) != 64
            or any(character not in "0123456789abcdef" for character in self.evidence_checksum.lower())
        ):
            raise ValidationError({"evidence_checksum": "The qualification-plan checksum must be a 64-character SHA-256 value."})
        if self.cycle_id:
            try:
                cutover_status = self.cycle.cutover_decision.status
            except FinanceCutoverDecision.DoesNotExist:
                cutover_status = ""
            if cutover_status and cutover_status != FinanceCutoverDecision.DRAFT and not self.pk:
                raise ValidationError("Field qualification cannot be added after the cutover record is submitted.")
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status == self.APPROVED:
                governed = (
                    "cycle_id", "minimum_consecutive_cycles", "require_parallel_cycle",
                    "local_authority_reference", "accepted_rules_forms_reference", "field_evidence_basis",
                    "evidence_checksum", "approved_by_id", "approved_at",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("An approved field-qualification plan is immutable. Use a successor cycle for changed requirements.")

    def delete(self, *args, **kwargs):
        if self.status in {self.SUBMITTED, self.APPROVED}:
            raise ValidationError("A submitted field-qualification plan cannot be deleted.")
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class FinanceCutoverQualificationEvidence(models.Model):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (DRAFT, "Draft field evidence"),
        (SUBMITTED, "Awaiting independent review"),
        (ACCEPTED, "Accepted qualifying cycle"),
        (RETURNED, "Returned for correction / rerun"),
    )

    plan = models.ForeignKey(
        FinanceCutoverQualificationPlan, on_delete=models.PROTECT, related_name="cycle_evidence",
    )
    cycle = models.ForeignKey(
        FinanceShadowCycle, on_delete=models.PROTECT, related_name="cutover_qualification_evidence",
    )
    sequence = models.PositiveSmallIntegerField(
        help_text="Oldest qualifying cycle is 1; the candidate cutover cycle is the final number.",
    )
    field_execution_reference = models.TextField(
        help_text="Reference retained records proving this was an actual limited shadow or controlled parallel field cycle.",
    )
    rules_forms_reference = models.TextField(
        help_text="Reference the accepted local rules, forms, reports, and print layouts actually used in this cycle.",
    )
    evidence_checksum = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_finance_cutover_qualification_evidence",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="submitted_finance_cutover_qualification_evidence",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_finance_cutover_qualification_evidence",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sequence", "pk")
        constraints = (
            models.UniqueConstraint(fields=("plan", "cycle"), name="unique_cutover_qualification_cycle"),
            models.UniqueConstraint(fields=("plan", "sequence"), name="unique_cutover_qualification_sequence"),
        )

    def __str__(self):
        return f"{self.plan.cycle.code} qualification {self.sequence}: {self.cycle.code}"

    def clean(self):
        if self.sequence < 1:
            raise ValidationError({"sequence": "Sequence starts at 1 for the oldest qualifying cycle."})
        if self.plan_id and self.plan.status != FinanceCutoverQualificationPlan.APPROVED:
            raise ValidationError({"plan": "Approve the local field-qualification plan before recording cycle evidence."})
        if self.cycle_id and self.cycle.status != FinanceShadowCycle.RECONCILED:
            raise ValidationError({"cycle": "Only an independently reconciled cycle can be field-qualified."})
        if self.plan_id and self.cycle_id:
            candidate = self.plan.cycle
            if self.cycle.department_id != candidate.department_id:
                raise ValidationError({"cycle": "Choose a cycle owned by the same Finance office."})
            if self.cycle.fiscal_year != candidate.fiscal_year:
                raise ValidationError({"cycle": "Choose a qualifying cycle from the same fiscal year."})
            if self.cycle.enabled_scope.strip() != candidate.enabled_scope.strip():
                raise ValidationError({"cycle": "The qualifying cycle must have the exact candidate scope."})
            try:
                cutover_status = candidate.cutover_decision.status
            except FinanceCutoverDecision.DoesNotExist:
                cutover_status = ""
            if cutover_status and cutover_status != FinanceCutoverDecision.DRAFT and not self.pk:
                raise ValidationError("Qualification evidence cannot be added after the cutover record is submitted.")
        if self.evidence_checksum and (
            len(self.evidence_checksum) != 64
            or any(character not in "0123456789abcdef" for character in self.evidence_checksum.lower())
        ):
            raise ValidationError({"evidence_checksum": "The evidence checksum must be a 64-character SHA-256 value."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status == self.ACCEPTED:
                governed = (
                    "plan_id", "cycle_id", "sequence", "field_execution_reference",
                    "rules_forms_reference", "evidence_checksum", "reviewed_by_id", "reviewed_at",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Accepted field evidence is immutable. Correct or rerun it through a successor cycle.")

    def delete(self, *args, **kwargs):
        if self.status in {self.SUBMITTED, self.ACCEPTED}:
            raise ValidationError("Submitted field evidence cannot be deleted.")
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class FinanceStakeholderAcceptance(models.Model):
    REQUESTING_OFFICE = "requesting_office"
    BUDGET = "budget"
    ACCOUNTING = "accounting"
    TREASURY = "treasury"
    IT = "it"
    MANAGEMENT = "management"
    AUDIT = "audit"
    STAKEHOLDER_CHOICES = (
        (REQUESTING_OFFICE, "Requesting office"),
        (BUDGET, "Budget"),
        (ACCOUNTING, "Accounting"),
        (TREASURY, "Treasury"),
        (IT, "IT / system administration"),
        (MANAGEMENT, "Management / cutover authority"),
        (AUDIT, "Audit stakeholder"),
    )
    PENDING = "pending"
    ACCEPTED = "accepted"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"
    DECISION_CHOICES = (
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted for stated scope"),
        (CONDITIONAL, "Accepted with conditions"),
        (REJECTED, "Not accepted"),
    )

    cycle = models.ForeignKey(FinanceShadowCycle, on_delete=models.PROTECT, related_name="stakeholder_acceptances")
    stakeholder_kind = models.CharField(max_length=24, choices=STAKEHOLDER_CHOICES)
    office = models.ForeignKey(Department, on_delete=models.PROTECT, null=True, blank=True, related_name="finance_shadow_acceptances")
    assigned_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_finance_shadow_acceptances")
    enabled_scope = models.TextField()
    training_evidence_reference = models.TextField(blank=True)
    uat_evidence_reference = models.TextField(blank=True)
    signed_decision_reference = models.TextField(
        blank=True,
        help_text="Reference the retained wet-signed or otherwise locally accepted attributable decision record; do not upload signature images here.",
    )
    signed_decision_checksum = models.CharField(
        max_length=64, blank=True,
        help_text="SHA-256 of the retained signed/attributed decision copy.",
    )
    decision = models.CharField(max_length=16, choices=DECISION_CHOICES, default=PENDING)
    conditions_or_reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="decided_finance_shadow_acceptances")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_finance_shadow_acceptances")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("stakeholder_kind", "office__name", "pk")

    def __str__(self):
        return f"{self.get_stakeholder_kind_display()} — {self.assigned_reviewer}"

    def clean(self):
        if self.cycle_id and self.enabled_scope.strip() != self.cycle.enabled_scope.strip():
            raise ValidationError({"enabled_scope": "The stakeholder scope must exactly match the shadow cycle being accepted."})
        if self.cycle_id:
            try:
                cutover_status = self.cycle.cutover_decision.status
            except FinanceCutoverDecision.DoesNotExist:
                cutover_status = ""
            if cutover_status and cutover_status != FinanceCutoverDecision.DRAFT:
                raise ValidationError("Stakeholder assignments and decisions are locked after the cutover record is submitted.")
        if self.stakeholder_kind == self.REQUESTING_OFFICE and not self.office_id:
            raise ValidationError({"office": "Choose the requesting office whose enabled scope is being accepted."})
        if self.stakeholder_kind == self.REQUESTING_OFFICE and self.office_id and self.assigned_reviewer_id:
            assigned_department_id = getattr(
                getattr(self.assigned_reviewer, "employeeprofile", None), "assigned_department_id", None,
            )
            if assigned_department_id != self.office_id:
                raise ValidationError({"assigned_reviewer": "The requesting-office reviewer must currently belong to the named office."})
        if self.decision != self.PENDING:
            if not self.signed_decision_reference.strip():
                raise ValidationError({"signed_decision_reference": "Reference the retained signed or attributable stakeholder decision record."})
            checksum = self.signed_decision_checksum.lower()
            if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
                raise ValidationError({"signed_decision_checksum": "Enter the 64-character SHA-256 of the retained stakeholder decision copy."})
        duplicate = type(self).objects.filter(
            cycle_id=self.cycle_id, stakeholder_kind=self.stakeholder_kind, office_id=self.office_id,
        ).exclude(pk=self.pk)
        if self.cycle_id and duplicate.exists():
            raise ValidationError("This stakeholder/office already has an acceptance row for the cycle.")
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.decision != self.PENDING:
                governed = (
                    "cycle_id", "stakeholder_kind", "office_id", "assigned_reviewer_id", "enabled_scope",
                    "training_evidence_reference", "uat_evidence_reference", "signed_decision_reference",
                    "signed_decision_checksum", "decision",
                    "conditions_or_reason", "decided_by_id", "decided_at",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("A recorded stakeholder decision is immutable. Add a successor shadow cycle for changed scope.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.decision != self.PENDING:
            raise ValidationError("A recorded stakeholder decision cannot be deleted.")
        return super().delete(*args, **kwargs)


class FinanceCutoverDecision(models.Model):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    AUTHORIZED = "authorized"
    DECLINED = "declined"
    ROLLED_BACK = "rolled_back"
    STATUS_CHOICES = (
        (DRAFT, "Draft decision record"),
        (SUBMITTED, "Awaiting cutover authority"),
        (AUTHORIZED, "Cutover authorized for stated scope/date"),
        (DECLINED, "Cutover not authorized"),
        (ROLLED_BACK, "Recorded rollback invoked"),
    )

    cycle = models.OneToOneField(FinanceShadowCycle, on_delete=models.PROTECT, related_name="cutover_decision")
    authority_matrix_reference = models.TextField()
    enabled_scope = models.TextField()
    cutover_at = models.DateTimeField()
    opening_reconciliation_reference = models.TextField()
    rollback_criteria = models.TextField()
    legacy_read_only_retention_plan = models.TextField()
    backup_recovery_evidence = models.TextField()
    signed_authority_reference = models.TextField(
        blank=True, default="",
        help_text="Reference the retained signed authority record for this exact scope and planned cutover date.",
    )
    signed_authority_checksum = models.CharField(
        max_length=64, blank=True, default="", help_text="SHA-256 of the retained signed authority record copy.",
    )
    signature_custody_reference = models.TextField(
        blank=True, default="",
        help_text="State the TracePoint, records folder, custodian, or other local location of the signed original/copy.",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prepared_finance_cutover_decisions")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="submitted_finance_cutover_decisions")
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="authorized_finance_cutover_decisions")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-cutover_at", "-pk")

    def __str__(self):
        return f"Cutover decision — {self.cycle.code}"

    def clean(self):
        if self.cycle_id and self.cycle.status != FinanceShadowCycle.RECONCILED:
            raise ValidationError({"cycle": "Prepare a cutover decision only after independent shadow-cycle reconciliation."})
        if self.cycle_id and self.enabled_scope.strip() != self.cycle.enabled_scope.strip():
            raise ValidationError({"enabled_scope": "The cutover scope must exactly match the independently reconciled shadow-cycle scope."})
        if not self.pk or self.signed_authority_reference or self.signed_authority_checksum or self.signature_custody_reference:
            if not self.signed_authority_reference.strip():
                raise ValidationError({"signed_authority_reference": "Reference the retained signed authority record."})
            if not self.signature_custody_reference.strip():
                raise ValidationError({"signature_custody_reference": "State the local custodian or records location."})
            checksum = self.signed_authority_checksum.lower()
            if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
                raise ValidationError({"signed_authority_checksum": "Enter the 64-character SHA-256 of the retained signed authority record."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status != self.DRAFT:
                governed = (
                    "cycle_id", "authority_matrix_reference", "enabled_scope", "cutover_at",
                    "opening_reconciliation_reference", "rollback_criteria",
                    "legacy_read_only_retention_plan", "backup_recovery_evidence",
                    "signed_authority_reference", "signed_authority_checksum", "signature_custody_reference",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("A submitted cutover record is immutable. Record a decline or rollback; do not rewrite its scope or evidence.")

    @property
    def makes_grand_authoritative(self):
        return self.status == self.AUTHORIZED

    def delete(self, *args, **kwargs):
        if self.status != self.DRAFT:
            raise ValidationError("A submitted cutover record cannot be deleted.")
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
