from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum


class DepartmentOwnedModel(models.Model):
    """Finance-domain ownership without a cross-database foreign key."""

    department_id = models.PositiveBigIntegerField(db_index=True)
    department_label = models.CharField(max_length=160)

    class Meta:
        abstract = True


class FiscalYear(DepartmentOwnedModel):
    DRAFT = "draft"
    FOR_REVIEW = "for_review"
    APPROVED = "approved"
    ACTIVE = "active"
    CLOSED = "closed"
    STATUS_CHOICES = (
        (DRAFT, "Draft"),
        (FOR_REVIEW, "For review"),
        (APPROVED, "Approved"),
        (ACTIVE, "Active"),
        (CLOSED, "Closed"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    year = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=80)
    starts_on = models.DateField()
    ends_on = models.DateField()
    business_date = models.DateField(help_text="The controlled operational date used by Finance workflows.")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    source_release_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_release_code = models.CharField(max_length=80, blank=True)
    source_release_version = models.PositiveIntegerField(null=True, blank=True)
    source_checksum = models.CharField(max_length=64, blank=True)
    created_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_by_label = models.CharField(max_length=160, blank=True)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    approved_by_label = models.CharField(max_length=160, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-year", "department_id")
        constraints = (
            models.UniqueConstraint(fields=("department_id", "year"), name="unique_typed_fiscal_year"),
        )
        permissions = (
            ("approve_fiscal_readiness", "Can approve fiscal-year setup and readiness layers"),
        )

    def __str__(self):
        return self.label

    def clean(self):
        if self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "The fiscal-year end cannot precede its start."})
        if not self.starts_on <= self.business_date <= self.ends_on:
            raise ValidationError({"business_date": "The business date must fall inside the fiscal year."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = (
                "department_id", "year", "label", "starts_on", "ends_on",
                "source_release_id", "source_release_code", "source_release_version", "source_checksum",
            )
            if prior and prior.status in (self.APPROVED, self.ACTIVE, self.CLOSED):
                if any(getattr(prior, field) != getattr(self, field) for field in governed) and not getattr(self, "_governed_amendment", False):
                    raise ValidationError("An approved fiscal year cannot be redefined. Adopt a successor setup release instead.")


class AccountingPeriod(DepartmentOwnedModel):
    OPEN = "open"
    CLOSED = "closed"
    STATUS_CHOICES = ((OPEN, "Open"), (CLOSED, "Closed"))

    fiscal_year = models.PositiveSmallIntegerField(help_text="Compatibility snapshot of the typed fiscal year.")
    fiscal_year_record = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, null=True, blank=True, related_name="periods",
    )
    period_number = models.PositiveSmallIntegerField(help_text="Usually 1–12; period 13 may be used for year-end adjustments.")
    is_adjustment_period = models.BooleanField(default=False)
    label = models.CharField(max_length=80)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=OPEN)
    closed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    closed_by_label = models.CharField(max_length=160, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-fiscal_year", "period_number")
        constraints = (
            models.UniqueConstraint(fields=("department_id", "fiscal_year", "period_number"), name="unique_accounting_period"),
            models.CheckConstraint(condition=models.Q(period_number__gte=1, period_number__lte=13), name="valid_accounting_period_number"),
        )

    def __str__(self):
        return f"FY {self.fiscal_year} · {self.label}"

    def clean(self):
        if self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "The period end cannot be before its start."})
        if self.fiscal_year_record_id:
            if self.fiscal_year_record.department_id != self.department_id:
                raise ValidationError({"fiscal_year_record": "The fiscal year must belong to this department ledger."})
            if self.fiscal_year_record.year != self.fiscal_year:
                raise ValidationError({"fiscal_year_record": "The typed fiscal year must match the period year."})
            if not (
                self.fiscal_year_record.starts_on <= self.starts_on <= self.ends_on <= self.fiscal_year_record.ends_on
            ):
                raise ValidationError({"ends_on": "The accounting period must fall inside its fiscal year."})
            if self.fiscal_year_record.status in (FiscalYear.ACTIVE, FiscalYear.CLOSED) and self.pk:
                prior = type(self).objects.filter(pk=self.pk).first()
                governed = ("fiscal_year", "fiscal_year_record_id", "period_number", "label", "starts_on", "ends_on", "is_adjustment_period")
                if prior and any(getattr(prior, field) != getattr(self, field) for field in governed) and not getattr(self, "_governed_amendment", False):
                    raise ValidationError("The calendar of an active fiscal year cannot be redefined.")
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and self.journal_entries.exists():
                governed = ("fiscal_year", "period_number", "label", "starts_on", "ends_on", "department_id")
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("A period already used by journals cannot be redefined.")


class Fund(DepartmentOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        constraints = (models.UniqueConstraint(fields=("department_id", "code"), name="unique_accounting_fund"),)

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the effective date."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = ("code", "name", "category", "effective_from", "effective_to")
            if prior and self.journal_entries.exists() and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("A fund already used by journals cannot be redefined. Archive it and create its successor.")


class ResponsibilityCenter(DepartmentOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    office_id = models.PositiveBigIntegerField(null=True, blank=True, help_text="Stable snapshot of the core office identity, not a cross-database relation.")
    office_code = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        constraints = (models.UniqueConstraint(fields=("department_id", "code"), name="unique_responsibility_center"),)

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the effective date."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = ("code", "name", "office_id", "office_code", "effective_from", "effective_to")
            if prior and self.journal_lines.exists() and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("A responsibility center already used by journals cannot be redefined. Archive it and create its successor.")


class LedgerAccount(DepartmentOwnedModel):
    TYPE_CHOICES = (
        ("asset", "Asset"), ("liability", "Liability"), ("equity", "Equity"),
        ("revenue", "Revenue"), ("expense", "Expense"),
    )
    NORMAL_CHOICES = (("debit", "Debit"), ("credit", "Credit"))

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    government_account_code = models.CharField(max_length=40, blank=True)
    subsidiary_reference_type = models.CharField(max_length=80, blank=True)
    account_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    normal_balance = models.CharField(max_length=8, choices=NORMAL_CHOICES)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    allow_posting = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        constraints = (models.UniqueConstraint(fields=("department_id", "code"), name="unique_ledger_account"),)

    def __str__(self):
        return f"{self.code} — {self.title}"

    def clean(self):
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the effective date."})
        if self.parent_id and self.parent.department_id != self.department_id:
            raise ValidationError({"parent": "The parent account must belong to the same department ledger."})
        if self.parent_id == self.pk:
            raise ValidationError({"parent": "An account cannot be its own parent."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = (
                "code", "title", "government_account_code", "account_type", "normal_balance", "parent_id",
                "subsidiary_reference_type", "effective_from", "effective_to",
            )
            if prior and self.journal_lines.exists() and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("An account already used by journals cannot be redefined. Archive it and create its successor.")


class FundingSource(DepartmentOwnedModel):
    KIND_CHOICES = (
        ("local", "Local source"),
        ("national", "National government transfer"),
        ("grant", "Grant"),
        ("loan", "Loan proceeds"),
        ("trust", "Trust / special purpose"),
        ("other", "Other approved source"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="funding_sources")
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, null=True, blank=True, related_name="funding_sources")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="local")
    authority_reference = models.CharField(max_length=160, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("fiscal_year__year", "code")
        constraints = (
            models.UniqueConstraint(fields=("department_id", "fiscal_year", "code"), name="unique_funding_source"),
        )

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        if self.fiscal_year_id and self.fiscal_year.department_id != self.department_id:
            raise ValidationError({"fiscal_year": "The fiscal year must belong to this department ledger."})
        if self.fund_id and self.fund.department_id != self.department_id:
            raise ValidationError({"fund": "The fund must belong to this department ledger."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the effective date."})
        if self.fiscal_year_id and self.fiscal_year.status in (FiscalYear.ACTIVE, FiscalYear.CLOSED):
            if not self.pk:
                raise ValidationError("Funding sources cannot be added to an active fiscal year.")
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = ("code", "name", "kind", "fund_id", "authority_reference", "effective_from", "effective_to", "is_active")
            if prior and any(getattr(prior, field) != getattr(self, field) for field in governed) and not getattr(self, "_governed_amendment", False):
                raise ValidationError("Funding sources in an active fiscal year are immutable.")


class ProgramActivityProject(DepartmentOwnedModel):
    KIND_CHOICES = (
        ("mfo", "Major final output"),
        ("program", "Program"),
        ("ppa", "Program / project / activity group"),
        ("project", "Project"),
        ("activity", "Activity"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="program_classifications")
    code = models.CharField(max_length=60)
    name = models.CharField(max_length=220)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    responsibility_center = models.ForeignKey(
        ResponsibilityCenter, on_delete=models.PROTECT, null=True, blank=True, related_name="program_classifications",
    )
    funding_source = models.ForeignKey(
        FundingSource, on_delete=models.PROTECT, null=True, blank=True, related_name="program_classifications",
    )
    authority_reference = models.CharField(max_length=160, blank=True)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("fiscal_year__year", "code")
        constraints = (
            models.UniqueConstraint(fields=("department_id", "fiscal_year", "code"), name="unique_program_classification"),
        )

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        if self.fiscal_year_id and self.fiscal_year.department_id != self.department_id:
            raise ValidationError({"fiscal_year": "The fiscal year must belong to this department ledger."})
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "A classification cannot be its own parent."})
            if self.parent.department_id != self.department_id or self.parent.fiscal_year_id != self.fiscal_year_id:
                raise ValidationError({"parent": "The parent must belong to the same department and fiscal year."})
            ancestor = self.parent
            visited = set()
            while ancestor:
                if ancestor.pk == self.pk or ancestor.pk in visited:
                    raise ValidationError({"parent": "The classification hierarchy cannot contain a cycle."})
                visited.add(ancestor.pk)
                ancestor = ancestor.parent
        if self.responsibility_center_id and self.responsibility_center.department_id != self.department_id:
            raise ValidationError({"responsibility_center": "The office must belong to this department ledger."})
        if self.funding_source_id and (
            self.funding_source.department_id != self.department_id
            or self.funding_source.fiscal_year_id != self.fiscal_year_id
        ):
            raise ValidationError({"funding_source": "The funding source must belong to the same department and fiscal year."})
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot precede the effective date."})
        if self.fiscal_year_id and self.fiscal_year.status in (FiscalYear.ACTIVE, FiscalYear.CLOSED):
            if not self.pk:
                raise ValidationError("Program classifications cannot be added to an active fiscal year.")
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = (
                "code", "name", "kind", "parent_id", "responsibility_center_id", "funding_source_id",
                "authority_reference", "effective_from", "effective_to", "is_active",
            )
            if prior and any(getattr(prior, field) != getattr(self, field) for field in governed) and not getattr(self, "_governed_amendment", False):
                raise ValidationError("Program classifications in an active fiscal year are immutable.")


class FiscalYearReadinessApproval(DepartmentOwnedModel):
    TECHNICAL = "technical"
    BUDGET = "budget"
    ACCOUNTING = "accounting"
    TREASURY = "treasury"
    FORMS = "forms"
    LAYER_CHOICES = (
        (TECHNICAL, "Technical setup"),
        (BUDGET, "Budget approval"),
        (ACCOUNTING, "Accounting approval"),
        (TREASURY, "Treasury readiness"),
        (FORMS, "Form readiness"),
    )
    PENDING = "pending"
    APPROVED = "approved"
    RETURNED = "returned"
    STATUS_CHOICES = ((PENDING, "Pending"), (APPROVED, "Approved"), (RETURNED, "Returned"))

    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="readiness_layers")
    layer = models.CharField(max_length=16, choices=LAYER_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    evidence_note = models.TextField(blank=True)
    decided_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    decided_by_label = models.CharField(max_length=160, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    state_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("fiscal_year__year", "layer")
        constraints = (
            models.UniqueConstraint(fields=("fiscal_year", "layer"), name="unique_fiscal_readiness_layer"),
        )

    def __str__(self):
        return f"{self.fiscal_year}: {self.get_layer_display()}"

    def clean(self):
        if self.fiscal_year_id and self.fiscal_year.department_id != self.department_id:
            raise ValidationError({"fiscal_year": "The readiness layer must belong to this department ledger."})
        if self.status in (self.APPROVED, self.RETURNED) and not self.evidence_note.strip():
            raise ValidationError({"evidence_note": "Record the decision basis or evidence."})
        if self.pk and self.fiscal_year_id and self.fiscal_year.status in (FiscalYear.ACTIVE, FiscalYear.CLOSED):
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = ("status", "evidence_note", "decided_by_id", "decided_by_label", "decided_at")
            if prior and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("Readiness evidence for an active fiscal year is immutable.")


class OpeningBalanceBatch(DepartmentOwnedModel):
    DRAFT = "draft"
    VALIDATED = "validated"
    FOR_REVIEW = "for_review"
    APPROVED = "approved"
    POSTED = "posted"
    RECONCILED = "reconciled"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (DRAFT, "Draft staging"),
        (VALIDATED, "Validated"),
        (FOR_REVIEW, "For review"),
        (APPROVED, "Approved for posting"),
        (POSTED, "Posted; reconciliation pending"),
        (RECONCILED, "Reconciled"),
        (RETURNED, "Returned for correction"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="opening_balance_batches")
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="opening_balance_batches")
    title = models.CharField(max_length=180)
    source_reference = models.CharField(max_length=120)
    source_filename = models.CharField(max_length=255, blank=True)
    source_checksum = models.CharField(max_length=64, blank=True)
    import_schema_version = models.PositiveSmallIntegerField(default=1)
    expected_row_count = models.PositiveIntegerField(default=0)
    expected_debit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    expected_credit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    is_zero_balance_declaration = models.BooleanField(default=False)
    validation_summary = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    approved_by_label = models.CharField(max_length=160, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    posted_by_label = models.CharField(max_length=160, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    reconciled_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reconciled_by_label = models.CharField(max_length=160, blank=True)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fiscal_year__year", "-created_at", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("department_id", "fiscal_year", "source_reference"),
                name="unique_opening_source_reference",
            ),
        )
        permissions = (
            ("prepare_opening_balances", "Can stage and correct opening balances"),
            ("approve_opening_balances", "Can independently approve opening balances"),
            ("post_opening_balances", "Can post and reconcile opening balances"),
        )

    def __str__(self):
        return f"{self.fiscal_year} · {self.source_reference}"

    def clean(self):
        if self.fiscal_year_id and self.fiscal_year.department_id != self.department_id:
            raise ValidationError({"fiscal_year": "The fiscal year must belong to this department ledger."})
        if self.period_id:
            if self.period.department_id != self.department_id:
                raise ValidationError({"period": "The opening period must belong to this department ledger."})
            if self.fiscal_year_id and self.period.fiscal_year_record_id != self.fiscal_year_id:
                raise ValidationError({"period": "The opening period must be linked to the selected fiscal year."})
        if self.expected_debit < 0 or self.expected_credit < 0:
            raise ValidationError("Declared control totals cannot be negative.")
        if self.is_zero_balance_declaration:
            if self.expected_row_count or self.expected_debit or self.expected_credit:
                raise ValidationError("A zero-balance declaration must have zero rows and zero debit/credit totals.")
        elif not self.expected_row_count:
            raise ValidationError({"expected_row_count": "Declare the source schedule row count."})
        elif self.expected_debit <= 0 or self.expected_debit != self.expected_credit:
            raise ValidationError("Declared opening debit and credit control totals must be equal and positive.")
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = (
                "department_id", "fiscal_year_id", "period_id", "title", "source_reference",
                "source_filename", "source_checksum", "import_schema_version", "expected_row_count",
                "expected_debit", "expected_credit", "is_zero_balance_declaration", "created_by_id",
            )
            if prior and prior.status in (self.APPROVED, self.POSTED, self.RECONCILED):
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Approved opening evidence is immutable. Return it before posting or use an adjusting entry after posting.")


class OpeningBalanceRow(models.Model):
    PENDING = "pending"
    VALID = "valid"
    ERROR = "error"
    VALIDATION_CHOICES = ((PENDING, "Pending validation"), (VALID, "Valid"), (ERROR, "Needs correction"))

    batch = models.ForeignKey(OpeningBalanceBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    raw_fund_code = models.CharField(max_length=80)
    raw_account_code = models.CharField(max_length=80)
    raw_responsibility_center_code = models.CharField(max_length=80, blank=True)
    raw_debit = models.CharField(max_length=80, blank=True)
    raw_credit = models.CharField(max_length=80, blank=True)
    subsidiary_reference = models.CharField(max_length=160, blank=True)
    memo = models.CharField(max_length=255, blank=True)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, null=True, blank=True, related_name="opening_balance_rows")
    account = models.ForeignKey(
        LedgerAccount, on_delete=models.PROTECT, null=True, blank=True, related_name="opening_balance_rows",
    )
    responsibility_center = models.ForeignKey(
        ResponsibilityCenter, on_delete=models.PROTECT, null=True, blank=True,
        related_name="opening_balance_rows",
    )
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    validation_status = models.CharField(max_length=12, choices=VALIDATION_CHOICES, default=PENDING)
    validation_errors = models.JSONField(default=list, blank=True)
    correction_version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("row_number", "pk")
        constraints = (
            models.UniqueConstraint(fields=("batch", "row_number"), name="unique_opening_batch_row"),
            models.CheckConstraint(condition=models.Q(debit__gte=0, credit__gte=0), name="nonnegative_opening_amounts"),
        )

    def __str__(self):
        return f"{self.batch.source_reference} row {self.row_number}"

    def clean(self):
        debit = self.debit or Decimal("0.00")
        credit = self.credit or Decimal("0.00")
        if self.validation_status == self.VALID and (debit > 0) == (credit > 0):
            raise ValidationError("A valid opening row must carry a positive debit or credit, not both.")
        if self.fund_id and self.fund.department_id != self.batch.department_id:
            raise ValidationError({"fund": "The fund must belong to this department ledger."})
        if self.account_id and self.account.department_id != self.batch.department_id:
            raise ValidationError({"account": "The account must belong to this department ledger."})
        if self.responsibility_center_id and self.responsibility_center.department_id != self.batch.department_id:
            raise ValidationError({"responsibility_center": "The responsibility center must belong to this department ledger."})

    def save(self, *args, **kwargs):
        if self.batch_id:
            current_status = OpeningBalanceBatch.objects.filter(pk=self.batch_id).values_list("status", flat=True).first()
            if current_status not in (OpeningBalanceBatch.DRAFT, OpeningBalanceBatch.RETURNED) and not getattr(
                self, "_validation_update", False,
            ):
                raise ValidationError("Opening rows can be changed only in draft or returned staging.")
        return super().save(*args, **kwargs)


class OpeningBalancePosting(models.Model):
    batch = models.ForeignKey(OpeningBalanceBatch, on_delete=models.PROTECT, related_name="postings")
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="opening_balance_postings")
    entry = models.OneToOneField("JournalEntry", on_delete=models.PROTECT, related_name="opening_balance_posting")
    debit = models.DecimalField(max_digits=20, decimal_places=2)
    credit = models.DecimalField(max_digits=20, decimal_places=2)
    row_count = models.PositiveIntegerField()

    class Meta:
        ordering = ("fund__code", "pk")
        constraints = (
            models.UniqueConstraint(fields=("batch", "fund"), name="unique_opening_posting_per_fund"),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Opening posting lineage is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Opening posting lineage cannot be deleted.")


class OpeningBalanceEvent(DepartmentOwnedModel):
    batch = models.ForeignKey(OpeningBalanceBatch, on_delete=models.PROTECT, related_name="events")
    action = models.CharField(max_length=40)
    actor_id = models.PositiveBigIntegerField()
    actor_label = models.CharField(max_length=160)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Opening-balance evidence is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Opening-balance evidence cannot be deleted.")


class PostingMapping(DepartmentOwnedModel):
    PAYABLE = "payable"
    DEDUCTION = "deduction"
    BANK = "bank"
    CATEGORY_CHOICES = (
        (PAYABLE, "Voucher net payable"),
        (DEDUCTION, "Deduction / withholding"),
        (BANK, "Bank account"),
    )

    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES)
    source_code = models.CharField(max_length=80, help_text="The controlled code used by Finance Setup or the Voucher Workbench.")
    label = models.CharField(max_length=160)
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="posting_mappings")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("category", "source_code")
        constraints = (
            models.UniqueConstraint(fields=("department_id", "category", "source_code"), name="unique_accounting_posting_mapping"),
        )

    def __str__(self):
        return f"{self.get_category_display()}: {self.source_code} → {self.account.code}"

    def clean(self):
        if self.account_id and self.account.department_id != self.department_id:
            raise ValidationError({"account": "The posting account must belong to this department ledger."})
        if self.account_id and (not self.account.is_active or not self.account.allow_posting):
            raise ValidationError({"account": "Choose an active posting account."})


class JournalEntry(DepartmentOwnedModel):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    POSTED = "posted"
    VOIDED = "voided"
    STATUS_CHOICES = ((DRAFT, "Draft"), (SUBMITTED, "For posting"), (POSTED, "Posted"), (VOIDED, "Voided"))
    SOURCE_CHOICES = (
        ("manual", "Manual journal"), ("voucher", "Voucher"),
        ("remittance", "Deduction / withholding remittance"),
        ("adjustment", "Adjusting entry"), ("reversal", "Reversing entry"),
        ("opening", "Opening balance"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference = models.CharField(max_length=60)
    entry_date = models.DateField()
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="journal_entries")
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="journal_entries")
    source_type = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="manual")
    description = models.TextField()
    source_reference = models.CharField(max_length=80, null=True, blank=True)
    source_snapshot = models.JSONField(default=dict, blank=True)
    reversal_of = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="reversal_entries",
    )
    reversal_reason = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    posted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    posted_by_label = models.CharField(max_length=160, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-entry_date", "-pk")
        constraints = (
            models.UniqueConstraint(fields=("department_id", "reference"), name="unique_journal_reference"),
            models.UniqueConstraint(fields=("department_id", "source_type", "source_reference"), name="unique_accounting_source_reference"),
        )
        permissions = (
            ("view_accounting_workspace", "Can view the accounting workspace"),
            ("manage_accounting_setup", "Can manage accounting setup"),
            ("prepare_journal_entries", "Can prepare journal entries"),
            ("post_journal_entries", "Can independently post journal entries"),
            ("view_general_ledger", "Can view the general ledger and trial balance"),
        )

    def __str__(self):
        return self.reference

    def clean(self):
        if self.period_id and self.period.department_id != self.department_id:
            raise ValidationError({"period": "The accounting period must belong to this department ledger."})
        if self.fund_id and self.fund.department_id != self.department_id:
            raise ValidationError({"fund": "The fund must belong to this department ledger."})
        if self.period_id and not (self.period.starts_on <= self.entry_date <= self.period.ends_on):
            raise ValidationError({"entry_date": "The entry date must fall inside the selected accounting period."})
        if self.reversal_of_id:
            if self.reversal_of.department_id != self.department_id:
                raise ValidationError({"reversal_of": "The original journal must belong to the same department ledger."})
            if self.reversal_of.status != self.POSTED:
                raise ValidationError({"reversal_of": "Only a posted journal can be reversed."})
            if not self.reversal_reason.strip():
                raise ValidationError({"reversal_reason": "Explain why this reversal is required."})

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.source_reference:
                source_governed = (
                    "reference", "entry_date", "period_id", "fund_id", "source_type", "description",
                    "source_reference", "source_snapshot", "reversal_of_id", "reversal_reason",
                    "department_id", "department_label", "created_by_id", "created_by_label",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in source_governed):
                    raise ValidationError("Source-generated journal headers are immutable. Discard and recreate the draft from its source instead.")
            if prior and prior.status in (self.POSTED, self.VOIDED):
                governed = (
                    "reference", "entry_date", "period_id", "fund_id", "source_type", "description", "source_reference", "source_snapshot",
                    "reversal_of_id", "reversal_reason",
                    "status", "department_id", "department_label", "created_by_id", "created_by_label",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Posted and discarded journals are immutable. Create an adjusting entry instead.")
        return super().save(*args, **kwargs)

    @property
    def totals(self):
        values = self.lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
        return values["debit"] or Decimal("0.00"), values["credit"] or Decimal("0.00")


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    sequence = models.PositiveSmallIntegerField()
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="journal_lines")
    responsibility_center = models.ForeignKey(ResponsibilityCenter, on_delete=models.PROTECT, null=True, blank=True, related_name="journal_lines")
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    memo = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("sequence", "pk")
        constraints = (
            models.UniqueConstraint(fields=("entry", "sequence"), name="unique_journal_line_sequence"),
            models.CheckConstraint(condition=models.Q(debit__gte=0, credit__gte=0), name="nonnegative_journal_amounts"),
        )

    def __str__(self):
        return f"{self.entry.reference} line {self.sequence}"

    def clean(self):
        debit = self.debit or Decimal("0.00")
        credit = self.credit or Decimal("0.00")
        if (debit > 0) == (credit > 0):
            raise ValidationError("Enter a positive amount in either debit or credit, not both.")
        if self.account_id:
            if self.account.department_id != self.entry.department_id:
                raise ValidationError({"account": "The account must belong to this department ledger."})
            if not self.account.is_active or not self.account.allow_posting:
                raise ValidationError({"account": "Choose an active posting account."})
        if self.responsibility_center_id and self.responsibility_center.department_id != self.entry.department_id:
            raise ValidationError({"responsibility_center": "The responsibility center must belong to this department ledger."})

    def save(self, *args, **kwargs):
        current_status = JournalEntry.objects.filter(pk=self.entry_id).values_list("status", flat=True).first() if self.entry_id else None
        if current_status and current_status != JournalEntry.DRAFT:
            raise ValidationError("Journal lines can be changed only while the entry is a draft.")
        if self.pk and JournalEntry.objects.filter(pk=self.entry_id, source_reference__isnull=False).exists():
            raise ValidationError("Generated journal lines cannot be edited. Discard and recreate the source draft instead.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        current_status = JournalEntry.objects.filter(pk=self.entry_id).values_list("status", flat=True).first()
        if current_status != JournalEntry.DRAFT:
            raise ValidationError("Journal lines can be removed only while the entry is a draft.")
        if JournalEntry.objects.filter(pk=self.entry_id, source_reference__isnull=False).exists():
            raise ValidationError("Generated journal lines cannot be removed. Discard and recreate the source draft instead.")
        return super().delete(*args, **kwargs)


class JournalSubsidiaryLine(models.Model):
    PAYABLE = "payable"
    WITHHOLDING = "withholding"
    CATEGORY_CHOICES = (
        (PAYABLE, "Payable by claimant / payee"),
        (WITHHOLDING, "Deduction / withholding payable"),
    )

    entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name="subsidiary_lines")
    journal_line = models.OneToOneField(
        JournalLine, on_delete=models.PROTECT, related_name="subsidiary_posting",
    )
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES)
    reference_key = models.CharField(
        max_length=100,
        help_text="Stable payee key, deduction code, or other governed subsidiary identity.",
    )
    reference_label = models.CharField(max_length=220)
    source_code = models.CharField(max_length=80)
    source_reference = models.CharField(max_length=120)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    source_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("entry__entry_date", "entry_id", "journal_line__sequence")
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(debit__gt=0, credit=0)
                    | models.Q(credit__gt=0, debit=0)
                ),
                name="one_sided_positive_subsidiary_amount",
            ),
        )

    def __str__(self):
        return f"{self.get_category_display()} · {self.reference_label} · {self.entry.reference}"

    def clean(self):
        if self.journal_line_id:
            if self.journal_line.entry_id != self.entry_id:
                raise ValidationError("The subsidiary detail must belong to its journal line's entry.")
            if self.debit != self.journal_line.debit or self.credit != self.journal_line.credit:
                raise ValidationError("The subsidiary amount must exactly mirror its journal control-account line.")
        if not self.reference_key.strip() or not self.reference_label.strip():
            raise ValidationError("Subsidiary details require a stable reference and readable label.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Journal subsidiary details are immutable. Reverse the posted entry instead.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Journal subsidiary details cannot be deleted. Reverse the journal entry instead.")


class ControlAccountReconciliation(DepartmentOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    as_of_date = models.DateField()
    is_balanced = models.BooleanField(default=False)
    absolute_difference_total = models.DecimalField(
        max_digits=20, decimal_places=2, default=Decimal("0.00"),
    )
    result_snapshot = models.JSONField(default=dict)
    result_checksum = models.CharField(max_length=64)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_by_label = models.CharField(max_length=160)
    prepared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-as_of_date", "-prepared_at", "-pk")
        permissions = (
            ("reconcile_control_accounts", "Can record payable and withholding control reconciliations"),
        )

    def __str__(self):
        return f"Control reconciliation through {self.as_of_date}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Control-account reconciliation evidence is immutable. Run a new reconciliation.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Control-account reconciliation evidence cannot be deleted.")


class PeriodClosePolicy(DepartmentOwnedModel):
    OBSERVE = "observe"
    ENFORCE = "enforce"
    MODE_CHOICES = (
        (OBSERVE, "Observe and explain exceptions"),
        (ENFORCE, "Enforce accepted close gates"),
    )
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    STARTER = "starter"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = (
        (DRAFT, "Editable draft"), (SUBMITTED, "For independent review"),
        (RETURNED, "Returned for correction"), (STARTER, "Controlled starter"),
        (ACTIVE, "Locally accepted active policy"), (SUPERSEDED, "Superseded"),
    )
    LOCKED_STATUSES = {STARTER, ACTIVE, SUPERSEDED}

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    version = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    mode = models.CharField(max_length=12, choices=MODE_CHOICES, default=OBSERVE)
    require_control_reconciliation = models.BooleanField(default=True)
    require_bank_reconciliation = models.BooleanField(default=True)
    require_statement_reports = models.BooleanField(default=True)
    require_handoff_clearance = models.BooleanField(default=True)
    require_year_end_closing_entries = models.BooleanField(default=True)
    authority_reference = models.TextField(blank=True)
    local_acceptance_note = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors",
    )
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reviewed_by_label = models.CharField(max_length=160, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-version", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("department_id", "version"), name="unique_period_close_policy_version",
            ),
            models.UniqueConstraint(
                fields=("department_id",), condition=models.Q(status="active"),
                name="one_active_period_close_policy",
            ),
        )
        permissions = (
            ("manage_period_close_policies", "Can prepare period-close policies"),
            ("approve_period_close_policies", "Can independently approve period-close policies"),
        )

    def __str__(self):
        return f"{self.title} · v{self.version}"

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        if self.supersedes_id and (
            self.supersedes.department_id != self.department_id
            or self.version <= self.supersedes.version
        ):
            raise ValidationError({"supersedes": "Choose an earlier policy for this Accounting office."})
        if self.status == self.ACTIVE:
            if not self.authority_reference.strip() or not self.local_acceptance_note.strip():
                raise ValidationError("An active close policy requires reviewed authority and local acceptance evidence.")
            if not self.snapshot_checksum or not self.reviewed_at or not self.reviewed_by_id:
                raise ValidationError("An active close policy requires immutable independent-review evidence.")
            if self.created_by_id == self.reviewed_by_id:
                raise ValidationError("The close-policy preparer cannot approve the same version.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "department_id", "department_label", "version", "title", "description", "mode",
                "require_control_reconciliation", "require_bank_reconciliation",
                "require_statement_reports", "require_handoff_clearance", "authority_reference",
                "require_year_end_closing_entries", "local_acceptance_note", "supersedes_id",
                "created_by_id", "created_by_label",
            )
            if prior.status in self.LOCKED_STATUSES and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Locked close policies are immutable. Create a successor version.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in self.LOCKED_STATUSES or self.close_runs.exists():
            raise ValidationError("Period-close policy history cannot be deleted.")
        return super().delete(*args, **kwargs)


class PeriodCloseRun(DepartmentOwnedModel):
    DRAFT = "draft"
    RETURNED = "returned"
    SUBMITTED = "submitted"
    CLOSED = "closed"
    REOPEN_REQUESTED = "reopen_requested"
    REOPENED = "reopened"
    STATUS_CHOICES = (
        (DRAFT, "Draft checklist"), (RETURNED, "Returned for correction"),
        (SUBMITTED, "For independent close review"), (CLOSED, "Period closed"),
        (REOPEN_REQUESTED, "Reopen requested"), (REOPENED, "Period reopened"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="close_runs")
    version = models.PositiveSmallIntegerField()
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors",
    )
    policy = models.ForeignKey(PeriodClosePolicy, on_delete=models.PROTECT, related_name="close_runs")
    policy_snapshot = models.JSONField(default=dict)
    policy_checksum = models.CharField(max_length=64)
    checklist_snapshot = models.JSONField(default=dict)
    checklist_checksum = models.CharField(max_length=64)
    adjustment_review_note = models.TextField()
    evidence_reference = models.TextField()
    preparer_note = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=DRAFT)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_by_label = models.CharField(max_length=160)
    prepared_at = models.DateTimeField(auto_now_add=True)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    decided_by_label = models.CharField(max_length=160, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    reopen_requested_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reopen_requested_by_label = models.CharField(max_length=160, blank=True)
    reopen_requested_at = models.DateTimeField(null=True, blank=True)
    reopen_reason = models.TextField(blank=True)
    reopen_authority_reference = models.TextField(blank=True)
    reopened_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reopened_by_label = models.CharField(max_length=160, blank=True)
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopen_review_note = models.TextField(blank=True)
    state_version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period__fiscal_year", "-period__period_number", "-version")
        constraints = (
            models.UniqueConstraint(
                fields=("period", "version"), name="unique_period_close_run_version",
            ),
        )
        permissions = (
            ("prepare_period_close", "Can prepare and submit period close checklists"),
            ("approve_period_close", "Can independently approve period close"),
            ("reopen_period", "Can independently decide period reopen requests"),
            ("export_period_close", "Can export period close evidence"),
        )

    def __str__(self):
        return f"{self.period} · close v{self.version}"

    @property
    def is_editable(self):
        return self.status in (self.DRAFT, self.RETURNED)

    def clean(self):
        if self.period_id and self.period.department_id != self.department_id:
            raise ValidationError({"period": "The close run must belong to the same Accounting office."})
        if self.policy_id and self.policy.department_id != self.department_id:
            raise ValidationError({"policy": "The close policy must belong to the same Accounting office."})
        if self.supersedes_id and (
            self.supersedes.period_id != self.period_id or self.version <= self.supersedes.version
        ):
            raise ValidationError({"supersedes": "Choose an earlier close run for this same period."})
        if self.status in (self.SUBMITTED, self.CLOSED, self.REOPEN_REQUESTED, self.REOPENED):
            if not self.adjustment_review_note.strip() or not self.evidence_reference.strip():
                raise ValidationError("Submitted close evidence requires the adjustment review and retained evidence reference.")
            if not self.checklist_checksum or not self.policy_checksum:
                raise ValidationError("Submitted close evidence requires checksummed policy and checklist snapshots.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            governed = (
                "department_id", "department_label", "period_id", "version", "supersedes_id",
                "policy_id", "policy_snapshot", "policy_checksum", "checklist_snapshot",
                "checklist_checksum", "adjustment_review_note", "evidence_reference", "preparer_note",
                "prepared_by_id", "prepared_by_label", "prepared_at",
            )
            if prior.status not in (self.DRAFT, self.RETURNED) and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted period-close evidence is immutable. Return it or create a successor close run.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.events.exists() or self.status not in (self.DRAFT, self.RETURNED):
            raise ValidationError("Period-close history cannot be deleted.")
        return super().delete(*args, **kwargs)


class PeriodCloseEvent(DepartmentOwnedModel):
    run = models.ForeignKey(PeriodCloseRun, on_delete=models.PROTECT, related_name="events")
    action = models.CharField(max_length=60)
    actor_id = models.PositiveBigIntegerField()
    actor_label = models.CharField(max_length=160)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Period-close events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Period-close events cannot be deleted.")


class BankStatementBatch(DepartmentOwnedModel):
    DRAFT = "draft"
    VALIDATED = "validated"
    FOR_REVIEW = "for_review"
    RECONCILED = "reconciled"
    RETURNED = "returned"
    STATUS_CHOICES = (
        (DRAFT, "Draft / staging"),
        (VALIDATED, "Statement controls validated"),
        (FOR_REVIEW, "For independent review"),
        (RECONCILED, "Reconciled"),
        (RETURNED, "Returned for correction"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    statement_reference = models.CharField(max_length=100)
    bank_account_code = models.CharField(max_length=80)
    bank_name = models.CharField(max_length=160)
    account_number_masked = models.CharField(max_length=40, blank=True)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="bank_statement_batches")
    period_start = models.DateField()
    period_end = models.DateField()
    received_on = models.DateField()
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2)
    expected_row_count = models.PositiveIntegerField()
    expected_deposits = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    expected_withdrawals = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    source_version = models.PositiveIntegerField(default=0)
    source_filename = models.CharField(max_length=255, blank=True)
    source_checksum = models.CharField(max_length=64, blank=True)
    validation_summary = models.JSONField(default=dict, blank=True)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reconciled_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reconciled_by_label = models.CharField(max_length=160, blank=True)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciliation_checksum = models.CharField(max_length=64, blank=True)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-period_end", "bank_account_code", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("department_id", "bank_account_code", "statement_reference"),
                name="unique_bank_statement_reference",
            ),
        )
        permissions = (
            ("view_bank_reconciliation", "Can view bank reconciliation workspaces"),
            ("prepare_bank_reconciliation", "Can stage and match bank statements"),
            ("approve_bank_reconciliation", "Can independently approve bank reconciliations"),
            ("export_bank_reconciliation", "Can export bank reconciliation evidence"),
        )

    def __str__(self):
        return f"{self.bank_account_code} · {self.statement_reference}"

    def clean(self):
        if self.period_end < self.period_start:
            raise ValidationError({"period_end": "The statement end cannot precede its start."})
        if self.received_on and self.period_end and self.received_on < self.period_end:
            raise ValidationError({"received_on": "The statement cannot be received before its covered period ends."})
        if self.fund_id and self.fund.department_id != self.department_id:
            raise ValidationError({"fund": "The fund must belong to this department ledger."})
        if self.expected_deposits < 0 or self.expected_withdrawals < 0:
            raise ValidationError("Statement control totals cannot be negative.")
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = (
                "department_id", "statement_reference", "bank_account_code", "bank_name",
                "account_number_masked", "fund_id", "period_start", "period_end", "received_on",
                "opening_balance", "closing_balance", "expected_row_count", "expected_deposits",
                "expected_withdrawals",
            )
            if prior and prior.status in (self.FOR_REVIEW, self.RECONCILED) and any(
                getattr(prior, field) != getattr(self, field) for field in governed
            ):
                raise ValidationError("Submitted bank-reconciliation controls are immutable. Return the batch before correction.")

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status == self.RECONCILED:
                raise ValidationError("Reconciled bank evidence is immutable. Use a later adjustment and successor reconciliation.")
            if prior and prior.status == self.FOR_REVIEW:
                changed = {
                    field.name for field in self._meta.concrete_fields
                    if field.name not in ("id", "updated_at") and getattr(prior, field.name) != getattr(self, field.name)
                }
                if changed and self.status not in (self.RETURNED, self.RECONCILED):
                    raise ValidationError("A bank reconciliation under review can only be returned or reconciled.")
                allowed = {"status", "state_version"}
                if self.status == self.RECONCILED:
                    allowed.update((
                        "reconciled_by_id", "reconciled_by_label", "reconciled_at", "reconciliation_checksum",
                    ))
                if changed - allowed:
                    raise ValidationError("A bank reconciliation under review is read-only until it is returned.")
        return super().save(*args, **kwargs)


class BankStatementRow(models.Model):
    batch = models.ForeignKey(BankStatementBatch, on_delete=models.PROTECT, related_name="rows")
    source_version = models.PositiveIntegerField()
    row_number = models.PositiveIntegerField()
    transaction_date = models.DateField()
    bank_reference = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=255)
    withdrawal = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    deposit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    running_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    row_checksum = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("source_version", "row_number", "pk")
        constraints = (
            models.UniqueConstraint(
                fields=("batch", "source_version", "row_number"), name="unique_statement_version_row",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(withdrawal__gt=0, deposit=0)
                    | models.Q(deposit__gt=0, withdrawal=0)
                ),
                name="one_sided_bank_statement_amount",
            ),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Staged bank rows are immutable. Restage a corrected statement version.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Staged bank rows are retained as source evidence.")


class BankStatementMatch(models.Model):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    STATUS_CHOICES = ((ACTIVE, "Active"), (SUPERSEDED, "Superseded"))
    AUTO = "auto"
    MANUAL = "manual"
    METHOD_CHOICES = ((AUTO, "Unique exact suggestion"), (MANUAL, "Guided manual match"))

    batch = models.ForeignKey(BankStatementBatch, on_delete=models.PROTECT, related_name="matches")
    statement_row = models.ForeignKey(BankStatementRow, on_delete=models.PROTECT, related_name="matches")
    journal_line = models.ForeignKey(JournalLine, on_delete=models.PROTECT, related_name="bank_statement_matches")
    method = models.CharField(max_length=12, choices=METHOD_CHOICES)
    reason = models.TextField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=ACTIVE)
    source_snapshot = models.JSONField(default=dict)
    source_checksum = models.CharField(max_length=64)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("statement_row__row_number", "-created_at", "-pk")
        constraints = (
            models.UniqueConstraint(
                fields=("statement_row",), condition=models.Q(status="active"),
                name="unique_active_statement_row_match",
            ),
            models.UniqueConstraint(
                fields=("journal_line",), condition=models.Q(status="active"),
                name="unique_active_bank_journal_match",
            ),
        )

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_lineage_transition", False):
            raise ValidationError("Bank match evidence is immutable. Supersede it through the guided correction action.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Bank match evidence cannot be deleted.")


class BankOutstandingItem(models.Model):
    OUTSTANDING_DEPOSIT = "outstanding_deposit"
    OUTSTANDING_CHECK = "outstanding_check"
    KIND_CHOICES = (
        (OUTSTANDING_DEPOSIT, "Deposit in transit"),
        (OUTSTANDING_CHECK, "Outstanding check / withdrawal"),
    )
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CLEARED = "cleared"
    STATUS_CHOICES = (
        (ACTIVE, "Outstanding"),
        (SUPERSEDED, "Superseded"),
        (CLEARED, "Cleared by later bank statement"),
    )

    batch = models.ForeignKey(BankStatementBatch, on_delete=models.PROTECT, related_name="outstanding_items")
    journal_line = models.ForeignKey(JournalLine, on_delete=models.PROTECT, related_name="bank_outstanding_items")
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    explanation = models.TextField()
    evidence_reference = models.CharField(max_length=160)
    expected_clearance_date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=ACTIVE)
    source_snapshot = models.JSONField(default=dict)
    source_checksum = models.CharField(max_length=64)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)
    superseded_at = models.DateTimeField(null=True, blank=True)
    carried_from = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="carry_forward_versions",
    )
    carried_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    carried_by_label = models.CharField(max_length=160, blank=True)
    carried_at = models.DateTimeField(null=True, blank=True)
    cleared_by_match = models.ForeignKey(
        BankStatementMatch, on_delete=models.PROTECT, null=True, blank=True,
        related_name="cleared_outstanding_items",
    )
    cleared_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    cleared_by_label = models.CharField(max_length=160, blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("journal_line__entry__entry_date", "journal_line_id", "-created_at")
        constraints = (
            models.UniqueConstraint(
                fields=("batch", "journal_line"), condition=models.Q(status="active"),
                name="unique_active_bank_outstanding_item",
            ),
        )

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, "_lineage_transition", False):
            raise ValidationError("Outstanding-item evidence is immutable. Supersede it through guided correction.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Outstanding-item evidence cannot be deleted.")

    @property
    def age_days(self):
        if not self.batch_id or not self.journal_line_id:
            return 0
        return max((self.batch.period_end - self.journal_line.entry.entry_date).days, 0)


class BankReconciliationEvent(DepartmentOwnedModel):
    batch = models.ForeignKey(BankStatementBatch, on_delete=models.PROTECT, related_name="events")
    action = models.CharField(max_length=40)
    actor_id = models.PositiveBigIntegerField()
    actor_label = models.CharField(max_length=160)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Bank-reconciliation events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Bank-reconciliation events cannot be deleted.")


class AccountingAuditEvent(DepartmentOwnedModel):
    entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, null=True, blank=True, related_name="audit_events")
    action = models.CharField(max_length=40)
    actor_id = models.PositiveBigIntegerField()
    actor_label = models.CharField(max_length=160)
    reason = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Accounting audit events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Accounting audit events cannot be deleted.")
