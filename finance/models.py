from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

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
        ("responsibility_center", "Office / responsibility center"),
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


class FinanceSignatory(models.Model):
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="finance_signatories")
    release = models.ForeignKey(FinanceConfigurationRelease, on_delete=models.PROTECT, related_name="signatories")
    role_code = models.SlugField(max_length=80)
    display_name = models.CharField(max_length=180)
    position_title = models.CharField(max_length=180)
    acting = models.BooleanField(default=False)
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
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status in LOCKED_STATES:
                fields = ("department_id", "release_id", "document_type", "version", "title", "mapping", "workbook_checksum", "mapping_checksum", "preflight_result", "effective_from", "effective_to")
                changed = any(getattr(prior, field) != getattr(self, field) for field in fields) or prior.workbook.name != self.workbook.name
                if changed:
                    raise ValidationError("Approved finance template versions are immutable. Upload a new version.")


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
