from __future__ import annotations

import uuid

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


def finance_template_path(instance, filename):
    return f"finance/templates/{instance.department.slug}/{instance.document_type}/v{instance.version}/{filename}"


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
