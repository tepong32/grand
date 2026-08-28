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


class AccountingPeriod(DepartmentOwnedModel):
    OPEN = "open"
    CLOSED = "closed"
    STATUS_CHOICES = ((OPEN, "Open"), (CLOSED, "Closed"))

    fiscal_year = models.PositiveSmallIntegerField()
    period_number = models.PositiveSmallIntegerField(help_text="Usually 1–12; period 13 may be used for year-end adjustments.")
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
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and self.journal_entries.exists():
                governed = ("fiscal_year", "period_number", "label", "starts_on", "ends_on", "department_id")
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("A period already used by journals cannot be redefined.")


class Fund(DepartmentOwnedModel):
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        constraints = (models.UniqueConstraint(fields=("department_id", "code"), name="unique_accounting_fund"),)

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and self.journal_entries.exists() and (prior.code != self.code or prior.name != self.name):
                raise ValidationError("A fund already used by journals cannot be renamed. Archive it and create its successor.")


class ResponsibilityCenter(DepartmentOwnedModel):
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        constraints = (models.UniqueConstraint(fields=("department_id", "code"), name="unique_responsibility_center"),)

    def __str__(self):
        return f"{self.code} — {self.name}"

    def clean(self):
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and self.journal_lines.exists() and (prior.code != self.code or prior.name != self.name):
                raise ValidationError("A responsibility center already used by journals cannot be renamed. Archive it and create its successor.")


class LedgerAccount(DepartmentOwnedModel):
    TYPE_CHOICES = (
        ("asset", "Asset"), ("liability", "Liability"), ("equity", "Equity"),
        ("revenue", "Revenue"), ("expense", "Expense"),
    )
    NORMAL_CHOICES = (("debit", "Debit"), ("credit", "Credit"))

    code = models.CharField(max_length=40)
    title = models.CharField(max_length=180)
    account_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    normal_balance = models.CharField(max_length=8, choices=NORMAL_CHOICES)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    allow_posting = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        constraints = (models.UniqueConstraint(fields=("department_id", "code"), name="unique_ledger_account"),)

    def __str__(self):
        return f"{self.code} — {self.title}"

    def clean(self):
        if self.parent_id and self.parent.department_id != self.department_id:
            raise ValidationError({"parent": "The parent account must belong to the same department ledger."})
        if self.parent_id == self.pk:
            raise ValidationError({"parent": "An account cannot be its own parent."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = ("code", "title", "account_type", "normal_balance", "parent_id")
            if prior and self.journal_lines.exists() and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("An account already used by journals cannot be redefined. Archive it and create its successor.")


class JournalEntry(DepartmentOwnedModel):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    POSTED = "posted"
    VOIDED = "voided"
    STATUS_CHOICES = ((DRAFT, "Draft"), (SUBMITTED, "For posting"), (POSTED, "Posted"), (VOIDED, "Voided"))
    SOURCE_CHOICES = (
        ("manual", "Manual journal"), ("voucher", "Voucher"),
        ("adjustment", "Adjusting entry"), ("opening", "Opening balance"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference = models.CharField(max_length=60)
    entry_date = models.DateField()
    period = models.ForeignKey(AccountingPeriod, on_delete=models.PROTECT, related_name="journal_entries")
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="journal_entries")
    source_type = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="manual")
    description = models.TextField()
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
        constraints = (models.UniqueConstraint(fields=("department_id", "reference"), name="unique_journal_reference"),)
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

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status in (self.POSTED, self.VOIDED):
                governed = (
                    "reference", "entry_date", "period_id", "fund_id", "source_type", "description",
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
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        current_status = JournalEntry.objects.filter(pk=self.entry_id).values_list("status", flat=True).first()
        if current_status != JournalEntry.DRAFT:
            raise ValidationError("Journal lines can be removed only while the entry is a draft.")
        return super().delete(*args, **kwargs)


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
