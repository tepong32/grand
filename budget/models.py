from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from accounting.models import FiscalYear, Fund, FundingSource, LedgerAccount, ProgramActivityProject, ResponsibilityCenter


class BudgetOwnedModel(models.Model):
    department_id = models.PositiveBigIntegerField(db_index=True)
    department_label = models.CharField(max_length=160)

    class Meta:
        abstract = True


class BudgetCall(BudgetOwnedModel):
    DRAFT, FOR_REVIEW, PUBLISHED, RETURNED, CLOSED = "draft", "for_review", "published", "returned", "closed"
    STATUS_CHOICES = ((DRAFT, "Draft"), (FOR_REVIEW, "For review"), (PUBLISHED, "Published"), (RETURNED, "Returned"), (CLOSED, "Closed"))

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="budget_calls")
    title = models.CharField(max_length=180)
    authority_reference = models.CharField(max_length=180)
    instructions = models.TextField()
    proposal_opens_on = models.DateField()
    proposal_due_on = models.DateField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    approved_by_label = models.CharField(max_length=160, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fiscal_year__year", "-created_at")
        permissions = (
            ("view_budget_workspace", "Can view the annual Budget workspace"),
            ("prepare_budget_calls", "Can prepare annual budget calls and ceilings"),
            ("approve_budget_calls", "Can independently approve annual budget calls"),
            ("prepare_budget_proposals", "Can prepare annual budget proposals"),
            ("review_budget_proposals", "Can review and consolidate annual budget proposals"),
            ("authorize_appropriations", "Can authorize final operational appropriations"),
            ("view_budget_audit", "Can view annual Budget audit evidence"),
        )

    def __str__(self):
        return f"FY {self.fiscal_year.year} — {self.title}"

    def clean(self):
        if self.proposal_due_on < self.proposal_opens_on:
            raise ValidationError({"proposal_due_on": "The proposal deadline cannot precede the opening date."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = ("department_id", "fiscal_year_id", "title", "authority_reference", "instructions", "proposal_opens_on", "proposal_due_on")
            if prior and prior.status in (self.PUBLISHED, self.CLOSED) and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("A published budget call is immutable. Issue a governed successor call.")


class BudgetCeiling(BudgetOwnedModel):
    budget_call = models.ForeignKey(BudgetCall, on_delete=models.PROTECT, related_name="ceilings")
    requesting_department_id = models.PositiveBigIntegerField()
    requesting_department_label = models.CharField(max_length=160)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="budget_ceilings")
    expense_class = models.CharField(max_length=40)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    basis = models.TextField()

    class Meta:
        ordering = ("requesting_department_label", "fund__code", "expense_class")
        constraints = (models.UniqueConstraint(fields=("budget_call", "requesting_department_id", "fund", "expense_class"), name="unique_budget_call_ceiling"),)

    def clean(self):
        if self.amount < Decimal("0"):
            raise ValidationError({"amount": "A ceiling cannot be negative."})
        if self.department_id != self.budget_call.department_id:
            raise ValidationError("The ceiling and budget call must belong to the same Budget office.")
        if self.budget_call.status not in (BudgetCall.DRAFT, BudgetCall.RETURNED):
            raise ValidationError("Ceilings are editable only while the call is draft or returned.")


class BudgetVersion(BudgetOwnedModel):
    DEPARTMENT, EXECUTIVE, SANGGUNIAN, FINAL, SUPPLEMENTAL, REENACTED = "department", "executive", "sanggunian", "final", "supplemental", "reenacted"
    KIND_CHOICES = ((DEPARTMENT, "Department proposal"), (EXECUTIVE, "Executive proposal"), (SANGGUNIAN, "Sanggunian version"), (FINAL, "Final approved budget"), (SUPPLEMENTAL, "Supplemental budget"), (REENACTED, "Reenacted budget"))
    DRAFT, FOR_REVIEW, RETURNED, APPROVED, AUTHORIZED = "draft", "for_review", "returned", "approved", "authorized"
    STATUS_CHOICES = ((DRAFT, "Draft"), (FOR_REVIEW, "For review"), (RETURNED, "Returned"), (APPROVED, "Approved proposal"), (AUTHORIZED, "Authorized appropriation version"))

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    budget_call = models.ForeignKey(BudgetCall, on_delete=models.PROTECT, related_name="versions")
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="budget_versions")
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=DEPARTMENT)
    version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=180)
    requesting_department_id = models.PositiveBigIntegerField(null=True, blank=True)
    requesting_department_label = models.CharField(max_length=160, blank=True)
    change_explanation = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    supersedes = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="successors")
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    decided_by_label = models.CharField(max_length=160, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fiscal_year__year", "kind", "-version")
        constraints = (models.UniqueConstraint(fields=("budget_call", "kind", "requesting_department_id", "version"), name="unique_budget_version_scope"),)

    @property
    def is_spendable_authority(self):
        authorization = getattr(self, "appropriation_authorization", None)
        return bool(self.status == self.AUTHORIZED and authorization and authorization.status == AppropriationAuthorization.AUTHORIZED)

    @property
    def total_amount(self):
        return self.lines.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    def clean(self):
        if self.fiscal_year_id != self.budget_call.fiscal_year_id or self.department_id != self.budget_call.department_id:
            raise ValidationError("The budget version must use its call's fiscal year and Budget office.")
        if self.kind == self.DEPARTMENT and not self.requesting_department_id:
            raise ValidationError({"requesting_department_id": "A department proposal requires a requesting department."})
        if self.supersedes_id and (self.supersedes_id == self.pk or self.supersedes.fiscal_year_id != self.fiscal_year_id):
            raise ValidationError({"supersedes": "A version may supersede only an earlier version in the same fiscal year."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            governed = ("budget_call_id", "fiscal_year_id", "kind", "version", "title", "requesting_department_id", "requesting_department_label", "change_explanation", "supersedes_id")
            if prior and prior.status in (self.APPROVED, self.AUTHORIZED) and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("Approved budget versions are immutable. Create a successor version.")


class BudgetProposalLine(BudgetOwnedModel):
    APPROPRIATION_CHOICES = (("new", "New"), ("continuing", "Continuing"), ("statutory", "Statutory / mandatory"), ("supplemental", "Supplemental"))
    version = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT, related_name="lines")
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="budget_lines")
    responsibility_center = models.ForeignKey(ResponsibilityCenter, on_delete=models.PROTECT, related_name="budget_lines")
    program = models.ForeignKey(ProgramActivityProject, on_delete=models.PROTECT, null=True, blank=True, related_name="budget_lines")
    funding_source = models.ForeignKey(FundingSource, on_delete=models.PROTECT, null=True, blank=True, related_name="budget_lines")
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="budget_lines")
    expense_class = models.CharField(max_length=40)
    appropriation_type = models.CharField(max_length=16, choices=APPROPRIATION_CHOICES, default="new")
    particulars = models.CharField(max_length=240)
    performance_target = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    change_explanation = models.TextField(blank=True)

    class Meta:
        ordering = ("responsibility_center__code", "program__code", "account__code", "pk")

    def clean(self):
        if self.amount <= Decimal("0"):
            raise ValidationError({"amount": "A proposed amount must be greater than zero."})
        if self.department_id != self.version.department_id:
            raise ValidationError("The line and version must belong to the same Budget office.")
        if self.version.status not in (BudgetVersion.DRAFT, BudgetVersion.RETURNED):
            raise ValidationError("Proposal lines are editable only while the version is draft or returned.")
        ledger_department = self.version.fiscal_year.department_id
        dimensions = (self.fund, self.responsibility_center, self.account, self.program, self.funding_source)
        if any(item and item.department_id != ledger_department for item in dimensions):
            raise ValidationError("All classification dimensions must belong to the selected Finance ledger.")


class BudgetResourceEstimate(BudgetOwnedModel):
    version = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT, related_name="resource_estimates")
    funding_source = models.ForeignKey(FundingSource, on_delete=models.PROTECT, related_name="budget_resource_estimates")
    description = models.CharField(max_length=220)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    basis = models.TextField()

    def clean(self):
        if self.amount < Decimal("0"):
            raise ValidationError({"amount": "A resource estimate cannot be negative."})
        if self.version.status not in (BudgetVersion.DRAFT, BudgetVersion.RETURNED):
            raise ValidationError("Resource estimates are editable only while the version is draft or returned.")


class BudgetVersionSource(BudgetOwnedModel):
    target_version = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT, related_name="source_links")
    source_version = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT, related_name="consolidation_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("source_version__requesting_department_label", "source_version__version")
        constraints = (models.UniqueConstraint(fields=("target_version", "source_version"), name="unique_budget_consolidation_source"),)

    def clean(self):
        if self.target_version_id == self.source_version_id:
            raise ValidationError("A budget version cannot consolidate itself.")
        if self.target_version.budget_call_id != self.source_version.budget_call_id:
            raise ValidationError("Consolidation sources must belong to the same annual budget call.")
        if self.target_version.status != BudgetVersion.DRAFT:
            raise ValidationError("Consolidation lineage is fixed after the target leaves draft.")
        if self.source_version.status != BudgetVersion.APPROVED:
            raise ValidationError("Only independently approved proposal versions may be consolidated.")


class AppropriationAuthorization(BudgetOwnedModel):
    ORDINANCE, SUPPLEMENTAL, REENACTED = "ordinance", "supplemental", "reenacted"
    AUTHORITY_CHOICES = ((ORDINANCE, "Annual appropriation ordinance"), (SUPPLEMENTAL, "Supplemental appropriation"), (REENACTED, "Reenacted budget authority"))
    PENDING, FAVORABLE, CONDITIONAL, ADVERSE = "pending", "favorable", "conditional", "adverse"
    REVIEW_CHOICES = ((PENDING, "Pending review"), (FAVORABLE, "Favorable review"), (CONDITIONAL, "Favorable with conditions"), (ADVERSE, "Adverse / not executable"))
    DRAFT, FOR_REVIEW, RETURNED, AUTHORIZED = "draft", "for_review", "returned", "authorized"
    STATUS_CHOICES = ((DRAFT, "Draft evidence"), (FOR_REVIEW, "For independent authorization"), (RETURNED, "Returned"), (AUTHORIZED, "Operational appropriation authority"))

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    version = models.OneToOneField(BudgetVersion, on_delete=models.PROTECT, related_name="appropriation_authorization")
    authority_type = models.CharField(max_length=16, choices=AUTHORITY_CHOICES)
    ordinance_number = models.CharField(max_length=100)
    ordinance_date = models.DateField()
    effectivity_date = models.DateField()
    review_status = models.CharField(max_length=16, choices=REVIEW_CHOICES, default=PENDING)
    review_reference = models.CharField(max_length=180)
    review_date = models.DateField(null=True, blank=True)
    conditions = models.TextField(blank=True)
    evidence_reference = models.TextField(help_text="Reference the accepted ordinance, review, and signed schedule evidence; do not upload unredacted production evidence during synthetic UAT.")
    signed_control_total = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    authorized_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    authorized_by_label = models.CharField(max_length=160, blank=True)
    authorized_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-version__fiscal_year__year", "-created_at")

    @property
    def computed_total(self):
        return self.version.total_amount

    @property
    def control_difference(self):
        return self.signed_control_total - self.computed_total

    def clean(self):
        if self.department_id != self.version.department_id:
            raise ValidationError("Authorization evidence and budget version must belong to the same Budget office.")
        if self.version.kind not in (BudgetVersion.FINAL, BudgetVersion.SUPPLEMENTAL, BudgetVersion.REENACTED):
            raise ValidationError({"version": "Authorize only a final, supplemental, or reenacted budget version."})
        if self.version.status not in (BudgetVersion.APPROVED, BudgetVersion.AUTHORIZED):
            raise ValidationError({"version": "The exact budget version must be independently approved first."})
        if self.effectivity_date < self.ordinance_date:
            raise ValidationError({"effectivity_date": "Effectivity cannot precede the ordinance/authority date."})
        if self.review_status == self.CONDITIONAL and not self.conditions.strip():
            raise ValidationError({"conditions": "Record every condition attached to the favorable review."})
        if self.status == self.AUTHORIZED:
            if self.review_status not in (self.FAVORABLE, self.CONDITIONAL) or not self.review_date:
                raise ValidationError("Operational authority requires a dated favorable review result.")
            if self.control_difference != Decimal("0"):
                raise ValidationError("The signed appropriation control total must equal the exact approved version total.")
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status == self.AUTHORIZED:
                governed = ("version_id", "authority_type", "ordinance_number", "ordinance_date", "effectivity_date", "review_status", "review_reference", "review_date", "conditions", "evidence_reference", "signed_control_total", "snapshot_checksum")
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Authorized appropriation evidence is immutable. Create the applicable successor budget version.")


class AuthorizedAppropriationLine(BudgetOwnedModel):
    authorization = models.ForeignKey(AppropriationAuthorization, on_delete=models.PROTECT, related_name="schedule_lines")
    source_line_id = models.PositiveBigIntegerField()
    fund_code = models.CharField(max_length=40)
    responsibility_center_code = models.CharField(max_length=40)
    program_code = models.CharField(max_length=60, blank=True)
    funding_source_code = models.CharField(max_length=40, blank=True)
    account_code = models.CharField(max_length=40)
    expense_class = models.CharField(max_length=40)
    appropriation_type = models.CharField(max_length=16)
    particulars = models.CharField(max_length=240)
    performance_target = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ("fund_code", "responsibility_center_code", "program_code", "account_code", "pk")
        constraints = (models.UniqueConstraint(fields=("authorization", "source_line_id"), name="unique_authorized_appropriation_source_line"),)

    def save(self, *args, **kwargs):
        if self.authorization.status == AppropriationAuthorization.AUTHORIZED:
            raise ValidationError("Authorized appropriation schedule snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Authorized appropriation schedule history cannot be deleted.")


class BudgetReviewComment(BudgetOwnedModel):
    version = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT, related_name="review_comments")
    author_id = models.PositiveBigIntegerField()
    author_label = models.CharField(max_length=160)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Budget review comments are append-only.")
        return super().save(*args, **kwargs)


class BudgetAuditEvent(BudgetOwnedModel):
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
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
            raise ValidationError("Budget audit events are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Budget audit events cannot be deleted.")
