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
            ("view_allotment_control", "Can view appropriation and allotment control"),
            ("prepare_allotment_releases", "Can prepare allotment release orders"),
            ("approve_allotment_releases", "Can independently post allotment release orders"),
            ("view_obligation_registry", "Can view the obligation registry and accountability balances"),
            ("initiate_obligation_requests", "Can initiate requesting-office obligation requests"),
            ("certify_obligations", "Can independently certify obligations"),
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
    planning_context_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    actuals_source_selection = models.JSONField(default=dict, blank=True, editable=False)
    actuals_source_origins = models.JSONField(default=dict, blank=True, editable=False)
    historical_forecasts = models.JSONField(default=dict, blank=True, editable=False)
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
    combined_version_number = models.GeneratedField(
        expression=models.Case(
            models.When(requesting_department_id__isnull=True, then=models.F('version')),
            default=models.Value(None),
        ), output_field=models.PositiveIntegerField(), db_persist=True, null=True,
    )
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
        constraints = (
            models.UniqueConstraint(fields=("budget_call", "kind", "requesting_department_id", "version"), name="unique_budget_version_scope"),
            models.UniqueConstraint(fields=('budget_call', 'kind', 'combined_version_number'), name='unique_combined_budget_version'),
        )

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
            if prior and prior.actuals_source_origins != self.actuals_source_origins:
                raise ValidationError('Consolidated actual-source origins are immutable.')
            governed = ("budget_call_id", "fiscal_year_id", "kind", "version", "title", "requesting_department_id", "requesting_department_label", "change_explanation", "supersedes_id", "planning_context_snapshot", "actuals_source_selection", "historical_forecasts")
            if prior and prior.status in (self.APPROVED, self.AUTHORIZED) and any(getattr(prior, field) != getattr(self, field) for field in governed):
                raise ValidationError("Approved budget versions are immutable. Create a successor version.")


class BudgetSummaryReconciliation(BudgetOwnedModel):
    """Immutable two-period cohort preparation; separate from Form 1 issuance."""
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    proposal = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT, related_name='summary_reconciliations')
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    entity_key = models.CharField(max_length=80)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, default='prepared')
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_at = models.DateTimeField()
    reviewed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    review_authority = models.CharField(max_length=2000, blank=True)
    decision_checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('proposal', 'fund', 'entity_key', 'version'), name='unique_budget_summary_reconciliation')]
        ordering = ('-prepared_at', '-pk')

    def save(self, *args, **kwargs):
        try:
            if self.pk:
                prior = type(self).objects.get(pk=self.pk)
                allowed = {'status', 'reviewed_by_id', 'reviewed_at', 'review_note', 'review_authority', 'decision_checksum'}
                if any(getattr(self, f.attname) != getattr(prior, f.attname) and not
                    (f.attname in allowed and getattr(self, '_decision_write', False)) for f in self._meta.concrete_fields):
                    raise ValidationError('Retain reconciliation evidence; prepare a successor.')
            return super().save(*args, **kwargs)
        finally:
            self._decision_write = False

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain reconciliation preparations and decisions.')


class BudgetReceiptForecast(BudgetOwnedModel):
    """Whole Fund/entity forecast review package; never joint actuals or issuance."""
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    proposal = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT, related_name='receipt_forecasts')
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, default='prepared',
        choices=(('prepared', 'For Budget Officer review'), ('approved', 'Reviewed estimates'), ('returned', 'Returned')))
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_at = models.DateTimeField()
    reviewed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    review_authority = models.CharField(max_length=2000, blank=True)
    decision_checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ('-prepared_at', '-pk')
        constraints = [models.UniqueConstraint(fields=('proposal', 'fund', 'version'), name='unique_budget_receipt_forecast')]
        permissions = (
            ('view_budget_receipt_forecasts', 'Can view retained Budget receipt forecasts'),
            ('export_budget_receipt_forecasts', 'Can export retained Budget receipt forecasts'),
            ('prepare_budget_receipt_forecasts', 'Can prepare complete Budget receipt forecast packages'),
            ('review_budget_receipt_forecasts', 'Can independently review receipt forecasts as designated Budget Officer'),
        )

    def save(self, *args, **kwargs):
        try:
            if self.pk:
                prior = type(self).objects.get(pk=self.pk)
                allowed = {'status', 'reviewed_by_id', 'reviewed_at', 'review_note', 'review_authority', 'decision_checksum'}
                if any(getattr(self, f.attname) != getattr(prior, f.attname) and not
                    (f.attname in allowed and getattr(self, '_decision_write', False)) for f in self._meta.concrete_fields):
                    raise ValidationError('Retain receipt forecast evidence; prepare a successor.')
            return super().save(*args, **kwargs)
        finally:
            self._decision_write = False

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain forecast packages and independent decisions.')


class Form1AccountReview(BudgetOwnedModel):
    """Reporting-account review, independent of fiscal/form issuance authority."""
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    proposal = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    forecast = models.ForeignKey(BudgetReceiptForecast, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, default='prepared',
        choices=(('prepared', 'For Accounting review'), ('approved', 'Reviewed selections'), ('returned', 'Returned')))
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    evidence = models.BinaryField(editable=False)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_at = models.DateTimeField()
    reviewed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    review_authority = models.CharField(max_length=2000, blank=True)
    decision_checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ('-prepared_at', '-pk')
        constraints = [models.UniqueConstraint(fields=('proposal', 'fund', 'version'), name='unique_form1_account_review')]
        permissions = (
            ('view_form1_account_reviews', 'Can view reporting-account review packages'),
            ('export_form1_account_reviews', 'Can export reporting-account review packages'),
            ('prepare_form1_account_reviews', 'Can prepare reporting-account review packages in Budget'),
            ('review_form1_account_reviews', 'Can independently review reporting accounts in Accounting'),
        )

    def save(self, *args, **kwargs):
        try:
            if self.pk:
                prior = type(self).objects.get(pk=self.pk)
                allowed = {'status', 'reviewed_by_id', 'reviewed_at', 'review_note', 'review_authority', 'decision_checksum'}
                if any(getattr(self, f.attname) != getattr(prior, f.attname) and not
                    (f.attname in allowed and getattr(self, '_decision_write', False)) for f in self._meta.concrete_fields):
                    raise ValidationError('Retain original reporting-account evidence; prepare a successor.')
            return super().save(*args, **kwargs)
        finally:
            self._decision_write = False

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain reporting-account preparations and decisions.')


class Form1SPAReview(BudgetOwnedModel):
    """Retained SPA treatment; not appropriation authorization or form issuance."""
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    proposal = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    account_review = models.ForeignKey(Form1AccountReview, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=20, default='prepared')
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    evidence = models.BinaryField(editable=False)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_at = models.DateTimeField()

    class Meta:
        ordering = ('-prepared_at', '-pk')
        constraints = [models.UniqueConstraint(fields=('proposal','fund','version'), name='unique_form1_spa_review')]
        permissions = (
            ('view_form1_spa_reviews', 'Can view original SPA subdivision reviews'),
            ('export_form1_spa_reviews', 'Can export original SPA subdivision reviews'),
            ('prepare_form1_spa_reviews', 'Can prepare SPA source subdivisions in Budget'),
            ('review_form1_spa_budget', 'Can independently review Budget SPA subdivision treatment'),
            ('review_form1_spa_accounting', 'Can independently review SPA actual-source treatment in Accounting'),
        )

    def save(self,*args,**kwargs):
        try:
            if self.pk:
                prior=type(self).objects.get(pk=self.pk)
                if any(getattr(self,f.attname)!=getattr(prior,f.attname)
                    and not (f.attname=='status' and getattr(self,'_decision_write',False))
                    for f in self._meta.concrete_fields):
                    raise ValidationError('Retain original SPA preparations; prepare a successor.')
            return super().save(*args,**kwargs)
        finally: self._decision_write=False

    def delete(self,*args,**kwargs):
        raise ValidationError('Retain SPA preparation and independent decision history.')


class Form1SPADecision(models.Model):
    review = models.ForeignKey(Form1SPAReview,on_delete=models.PROTECT,related_name='decisions')
    role = models.CharField(max_length=12)
    approve = models.BooleanField()
    actor_id = models.PositiveBigIntegerField()
    actor_department_id = models.PositiveBigIntegerField()
    treatment_verified = models.BooleanField(default=False)
    decided_at = models.DateTimeField()
    authority = models.CharField(max_length=2000)
    note = models.CharField(max_length=2000)
    decision_checksum = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('review','role'),name='unique_form1_spa_role_decision')]
        ordering = ('role',)

    def save(self,*args,**kwargs):
        if self.pk: raise ValidationError('Retain each original SPA role decision unchanged.')
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Retain original SPA role decisions.')


class Form1Package(BudgetOwnedModel):
    """Immutable whole-form preparation; independent review and issuance are separate."""
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    proposal = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    spa_review = models.ForeignKey(Form1SPAReview, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_at = models.DateTimeField()

    class Meta:
        ordering = ('-prepared_at', '-pk')
        constraints = [models.UniqueConstraint(fields=('proposal','fund','version'), name='unique_form1_package_version')]
        permissions = (
            ('prepare_form1_packages', 'Can retain complete Form 1 preparations in Budget'),
            ('view_form1_packages', 'Can view original complete Form 1 packages'),
            ('export_form1_packages', 'Can export original complete Form 1 packages'),
        )

    def save(self,*args,**kwargs):
        if self.pk:
            prior=type(self).objects.get(pk=self.pk)
            if any(getattr(self,f.attname)!=getattr(prior,f.attname) for f in self._meta.concrete_fields):
                raise ValidationError('Retain the whole Form 1 preparation; create a successor.')
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Retain original whole Form 1 preparations.')


class Form1PackageOffice(models.Model):
    """Candidate retrieval index only; original source checks still authorize access."""
    package = models.ForeignKey(Form1Package, on_delete=models.PROTECT, related_name='office_index')
    department_id = models.PositiveBigIntegerField(db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('package','department_id'), name='unique_form1_package_office')]

    def save(self,*args,**kwargs):
        if self.pk: raise ValidationError('Retain the original package office index.')
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Retain the original package office index.')


class Form1PackageAttachment(models.Model):
    package = models.ForeignKey(Form1Package, on_delete=models.PROTECT, related_name='attachments')
    key = models.CharField(max_length=100)
    data = models.BinaryField(editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('package','key'), name='unique_form1_package_attachment')]
        ordering = ('key',)

    def save(self,*args,**kwargs):
        if self.pk: raise ValidationError('Retain original whole Form 1 attachment bytes.')
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Retain original whole Form 1 attachments.')


class Form1PackageDecision(models.Model):
    """Independent internal review; statutory signatures and issuance are separate."""
    package = models.ForeignKey(Form1Package, on_delete=models.PROTECT, related_name='decisions')
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    role = models.CharField(max_length=16)
    actor_id = models.PositiveBigIntegerField()
    actor_department_id = models.PositiveBigIntegerField()
    approve = models.BooleanField()
    decided_at = models.DateTimeField()
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)

    class Meta:
        ordering = ('decided_at','pk')
        constraints = [
            models.UniqueConstraint(fields=('package','role','actor_department_id'), name='unique_form1_package_office_review'),
            models.UniqueConstraint(fields=('package','actor_id'), name='unique_form1_package_review_actor'),
        ]
        permissions = tuple((f'review_form1_package_{role}',f'Can independently review whole Form 1 in {role}')
            for role in ('budget','accounting','treasury'))

    def save(self,*args,**kwargs):
        if self.pk: raise ValidationError('Retain each independent whole Form 1 decision unchanged.')
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Retain independent whole Form 1 decisions.')


class BudgetOfficeForm(BudgetOwnedModel):
    """Retained Form 2 preparation and independently issued unsigned bytes."""
    PREPARED, ISSUED, RETURNED = 'prepared', 'issued', 'returned'
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    proposal = models.ForeignKey(BudgetVersion, on_delete=models.PROTECT, related_name='office_forms')
    office_id = models.PositiveBigIntegerField()
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, default=PREPARED,
        choices=((PREPARED, 'For independent review'), (ISSUED, 'Issued unsigned copy'), (RETURNED, 'Returned')))
    payload = models.JSONField(default=dict)
    payload_checksum = models.CharField(max_length=64)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_by_label = models.CharField(max_length=160)
    prepared_at = models.DateTimeField(auto_now_add=True)
    decided_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    decided_by_label = models.CharField(max_length=160, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    decision_checksum = models.CharField(max_length=64, blank=True)
    document = models.BinaryField(default=bytes, editable=False)
    document_checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ('-prepared_at', '-pk')
        constraints = (models.UniqueConstraint(fields=('proposal', 'office_id', 'fund', 'version'),
            name='unique_budget_office_form_version'),)

    def save(self, *args, **kwargs):
        if self.pk and not getattr(self, '_decision_write', False):
            raise ValidationError('Retained office forms are immutable; use an independent decision or a successor.')
        try:
            super().save(*args, **kwargs)
        finally:
            self._decision_write = False

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain office-form preparations, decisions and issued copies.')


class BudgetProposalLine(BudgetOwnedModel):
    second_half_estimate = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    estimate_as_of = models.DateField(null=True, blank=True)
    estimate_basis = models.TextField(blank=True)
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
        if self.second_half_estimate is not None:
            if self.second_half_estimate < 0 or not self.estimate_as_of or not self.estimate_basis.strip():
                raise ValidationError("A second-half estimate requires a nonnegative amount, dated basis and evidence reference.")
            from django.utils import timezone
            if self.estimate_as_of.year != self.version.fiscal_year.year - 1 or self.estimate_as_of > timezone.localdate():
                raise ValidationError("Date the estimate within the current planning year, not in the future.")
        elif self.estimate_as_of or self.estimate_basis:
            raise ValidationError("Supply the estimate amount, including an explicit zero, or clear all estimate fields.")
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
        if (self.department_id != self.version.department_id
                or self.funding_source.department_id != self.version.fiscal_year.department_id
                or self.funding_source.fiscal_year_id != self.version.fiscal_year_id
                or (self.funding_source.fund_id and self.funding_source.fund.department_id != self.funding_source.department_id)):
            raise ValidationError('Resource estimates must match the proposal owner, Finance ledger and fiscal year.')

    def save(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic(using='finance'):
            if self.pk and type(self).objects.get(pk=self.pk).version_id != self.version_id:
                raise ValidationError('Resource estimate ownership cannot be moved between proposals.')
            self.version = BudgetVersion.objects.select_for_update().get(pk=self.version_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain resource-estimate history; revise a draft with an audited reason.')


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
    current_quarterly_plan = models.ForeignKey("QuarterlyFinancialPlan", null=True, blank=True,
        on_delete=models.PROTECT, related_name="+", editable=False)
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

    def __str__(self):
        ppa = f" / {self.program_code}" if self.program_code else ""
        return f"{self.fund_code} / {self.responsibility_center_code}{ppa} / {self.account_code} — {self.particulars}"

    def save(self, *args, **kwargs):
        if self.authorization.status == AppropriationAuthorization.AUTHORIZED:
            raise ValidationError("Authorized appropriation schedule snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Authorized appropriation schedule history cannot be deleted.")


class AllotmentReleaseOrder(BudgetOwnedModel):
    planning_context_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    planning_deviation_basis = models.TextField(blank=True)
    INITIAL, LATER, RESERVE, DEFERRAL, ADJUSTMENT, RETURN, CANCELLATION = (
        "initial", "later", "reserve", "deferral", "adjustment", "return", "cancellation"
    )
    KIND_CHOICES = (
        (INITIAL, "Initial allotment release"), (LATER, "Later allotment release"),
        (RESERVE, "Reserve / withholding"), (DEFERRAL, "Deferral"),
        (ADJUSTMENT, "Allotment adjustment"), (RETURN, "Allotment return"),
        (CANCELLATION, "Allotment cancellation"),
    )
    DRAFT, FOR_REVIEW, RETURNED, POSTED = "draft", "for_review", "returned", "posted"
    STATUS_CHOICES = (
        (DRAFT, "Draft"), (FOR_REVIEW, "For independent review"),
        (RETURNED, "Returned for correction"), (POSTED, "Posted to allotment ledger"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    authorization = models.ForeignKey(AppropriationAuthorization, on_delete=models.PROTECT, related_name="allotment_orders")
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="allotment_release_orders")
    order_number = models.CharField(max_length=100)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    release_date = models.DateField()
    effective_date = models.DateField()
    authority_reference = models.CharField(max_length=180)
    evidence_reference = models.TextField(help_text="Reference the accepted ARO/equivalent and signed schedule; keep synthetic UAT evidence non-sensitive.")
    purpose = models.TextField()
    signed_control_total = models.DecimalField(max_digits=18, decimal_places=2)
    corrects = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="correction_orders")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    posted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    posted_by_label = models.CharField(max_length=160, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fiscal_year__year", "-effective_date", "-created_at")
        constraints = (
            models.UniqueConstraint(fields=("department_id", "fiscal_year", "order_number"), name="unique_allotment_order_number"),
        )

    def __str__(self):
        return f"FY {self.fiscal_year.year} · {self.order_number}"

    @property
    def computed_total(self):
        return self.lines.aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

    @property
    def control_difference(self):
        return self.signed_control_total - self.computed_total

    def clean(self):
        if self.department_id != self.authorization.department_id:
            raise ValidationError("The allotment order must belong to the appropriation's Budget office.")
        if self.authorization.status != AppropriationAuthorization.AUTHORIZED:
            raise ValidationError({"authorization": "Only an operationally authorized appropriation may release allotment."})
        if self.fiscal_year_id != self.authorization.version.fiscal_year_id:
            raise ValidationError({"fiscal_year": "The order must use the authorized appropriation fiscal year."})
        if not (self.fiscal_year.starts_on <= self.effective_date <= self.fiscal_year.ends_on):
            raise ValidationError({"effective_date": "The effective date must fall inside the selected fiscal year."})
        if self.effective_date < self.authorization.effectivity_date:
            raise ValidationError({"effective_date": "Allotment cannot take effect before its appropriation authority."})
        if self.corrects_id:
            if self.corrects_id == self.pk or self.corrects.department_id != self.department_id or self.corrects.status != self.POSTED:
                raise ValidationError({"corrects": "A correction may reference only a posted order in the same Budget office."})
            if self.corrects.authorization_id != self.authorization_id or self.corrects.fiscal_year_id != self.fiscal_year_id:
                raise ValidationError({"corrects": "A correcting order must use the same appropriation authority and fiscal year."})
            if self.kind not in (self.ADJUSTMENT, self.RETURN, self.CANCELLATION):
                raise ValidationError({"corrects": "Only adjustment, return, or cancellation orders may correct a posted order."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status == self.POSTED:
                governed = (
                    "authorization_id", "fiscal_year_id", "order_number", "kind", "release_date", "effective_date",
                    "authority_reference", "evidence_reference", "purpose", "signed_control_total", "corrects_id", "snapshot_checksum",
                    "planning_context_snapshot", "planning_deviation_basis",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Posted allotment orders are immutable. Record a linked correcting order.")


class AllotmentOrderLine(BudgetOwnedModel):
    RELEASE, RELEASE_REDUCTION, RESERVE, RESERVE_RELEASE, DEFERRAL, DEFERRAL_RELEASE, RETURN, CANCELLATION = (
        "release", "release_reduction", "reserve", "reserve_release", "deferral", "deferral_release", "return", "cancellation"
    )
    MOVEMENT_CHOICES = (
        (RELEASE, "Release allotment"), (RELEASE_REDUCTION, "Reduce released allotment"),
        (RESERVE, "Place reserve / withholding"), (RESERVE_RELEASE, "Release reserve / withholding"),
        (DEFERRAL, "Defer available allotment"), (DEFERRAL_RELEASE, "Lift deferral"),
        (RETURN, "Return allotment"), (CANCELLATION, "Cancel allotment"),
    )
    ALLOWED_BY_ORDER = {
        AllotmentReleaseOrder.INITIAL: (RELEASE,), AllotmentReleaseOrder.LATER: (RELEASE,),
        AllotmentReleaseOrder.RESERVE: (RESERVE, RESERVE_RELEASE),
        AllotmentReleaseOrder.DEFERRAL: (DEFERRAL, DEFERRAL_RELEASE),
        AllotmentReleaseOrder.ADJUSTMENT: (RELEASE, RELEASE_REDUCTION, RESERVE, RESERVE_RELEASE, DEFERRAL, DEFERRAL_RELEASE),
        AllotmentReleaseOrder.RETURN: (RETURN,), AllotmentReleaseOrder.CANCELLATION: (CANCELLATION,),
    }

    order = models.ForeignKey(AllotmentReleaseOrder, on_delete=models.PROTECT, related_name="lines")
    appropriation_line = models.ForeignKey(AuthorizedAppropriationLine, on_delete=models.PROTECT, related_name="allotment_order_lines")
    movement_type = models.CharField(max_length=24, choices=MOVEMENT_CHOICES)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("appropriation_line__fund_code", "appropriation_line__responsibility_center_code", "appropriation_line__account_code", "pk")

    def clean(self):
        if self.amount <= Decimal("0"):
            raise ValidationError({"amount": "A movement amount must be greater than zero."})
        if self.appropriation_line.authorization_id != self.order.authorization_id:
            raise ValidationError({"appropriation_line": "Choose a line from this order's exact authorized appropriation."})
        if self.department_id != self.order.department_id:
            raise ValidationError("The order line and order must belong to the same Budget office.")
        if self.movement_type not in self.ALLOWED_BY_ORDER.get(self.order.kind, ()):
            raise ValidationError({"movement_type": "That movement is not valid for this order type."})
    def save(self, *args, **kwargs):
        if self.order.status not in (AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED):
            raise ValidationError("Allotment lines are editable only while the order is draft or returned.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.order.status not in (AllotmentReleaseOrder.DRAFT, AllotmentReleaseOrder.RETURNED):
            raise ValidationError("Posted or submitted allotment schedule lines cannot be deleted.")
        return super().delete(*args, **kwargs)


class AllotmentMovement(BudgetOwnedModel):
    order = models.ForeignKey(AllotmentReleaseOrder, on_delete=models.PROTECT, related_name="movements")
    source_line_id = models.PositiveBigIntegerField()
    appropriation_line = models.ForeignKey(AuthorizedAppropriationLine, on_delete=models.PROTECT, related_name="allotment_movements")
    movement_type = models.CharField(max_length=24, choices=AllotmentOrderLine.MOVEMENT_CHOICES)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    release_effect = models.DecimalField(max_digits=18, decimal_places=2)
    hold_effect = models.DecimalField(max_digits=18, decimal_places=2)
    effective_date = models.DateField()
    order_number_snapshot = models.CharField(max_length=100)
    authority_reference_snapshot = models.CharField(max_length=180)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("effective_date", "pk")
        constraints = (models.UniqueConstraint(fields=("order", "source_line_id"), name="unique_allotment_movement_source"),)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Posted allotment movements are append-only and immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted allotment movements cannot be deleted.")


class ObligationRequest(BudgetOwnedModel):
    ORIGINAL, ADJUSTMENT, RETURN, CANCELLATION = "original", "adjustment", "return", "cancellation"
    KIND_CHOICES = (
        (ORIGINAL, "Original obligation"), (ADJUSTMENT, "Obligation adjustment"),
        (RETURN, "Obligation return"), (CANCELLATION, "Obligation cancellation"),
    )
    ALOBS, ORS, OBR = "alobs", "ors", "obr"
    FORM_CHOICES = ((ALOBS, "ALOBS"), (ORS, "ORS"), (OBR, "OBR"))
    DRAFT, FOR_CERTIFICATION, RETURNED, CERTIFIED = "draft", "for_certification", "returned", "certified"
    STATUS_CHOICES = (
        (DRAFT, "Draft request"), (FOR_CERTIFICATION, "For Budget certification"),
        (RETURNED, "Returned for correction"), (CERTIFIED, "Certified and posted"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    authorization = models.ForeignKey(AppropriationAuthorization, on_delete=models.PROTECT, related_name="obligation_requests")
    fiscal_year = models.ForeignKey(FiscalYear, on_delete=models.PROTECT, related_name="obligation_requests")
    requesting_department_id = models.PositiveBigIntegerField(db_index=True)
    requesting_department_label = models.CharField(max_length=160)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=ORIGINAL)
    form_type = models.CharField(max_length=12, choices=FORM_CHOICES, default=OBR)
    request_reference = models.CharField(max_length=100)
    obligation_number = models.CharField(max_length=100, blank=True)
    # Nullable generated keys retain conditional uniqueness on MySQL as well as
    # SQLite. The database derives these values even for bulk/queryset writes.
    unique_obligation_number = models.GeneratedField(
        expression=models.Case(
            models.When(obligation_number="", then=models.Value(None)),
            default=models.F("obligation_number"),
        ),
        output_field=models.CharField(max_length=100), db_persist=True, null=True,
    )
    original_request_reference = models.GeneratedField(
        expression=models.Case(
            models.When(kind="original", then=models.F("request_reference")),
            default=models.Value(None),
        ),
        output_field=models.CharField(max_length=100), db_persist=True, null=True,
    )
    obligation_date = models.DateField()
    claimant_payee = models.CharField(max_length=220)
    particulars = models.TextField()
    evidence_reference = models.TextField(help_text="Reference the locally accepted request and support; keep synthetic UAT evidence non-sensitive.")
    signed_control_total = models.DecimalField(max_digits=18, decimal_places=2)
    corrects = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="correction_requests")
    linked_voucher_case_public_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=DRAFT)
    snapshot_checksum = models.CharField(max_length=64, blank=True)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=160)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    submitted_by_label = models.CharField(max_length=160, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    certified_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    certified_by_label = models.CharField(max_length=160, blank=True)
    certified_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True)
    state_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fiscal_year__year", "-obligation_date", "-created_at")
        constraints = (
            models.UniqueConstraint(
                fields=("department_id", "fiscal_year", "unique_obligation_number"),
                name="unique_certified_obligation_number",
            ),
            models.UniqueConstraint(
                fields=("requesting_department_id", "fiscal_year", "original_request_reference"),
                name="unique_original_obligation_request_reference",
            ),
        )

    def __str__(self):
        return self.obligation_number or self.request_reference

    @property
    def computed_effect_total(self):
        total = Decimal("0")
        for line in self.lines.all():
            total += line.effect
        return total

    @property
    def control_difference(self):
        return self.signed_control_total - self.computed_effect_total

    def clean(self):
        if self.department_id != self.authorization.department_id:
            raise ValidationError("The obligation must belong to the appropriation's Budget office.")
        if self.authorization.status != AppropriationAuthorization.AUTHORIZED:
            raise ValidationError({"authorization": "Choose an operationally authorized appropriation."})
        if self.fiscal_year_id != self.authorization.version.fiscal_year_id:
            raise ValidationError({"fiscal_year": "The obligation must use the authorized appropriation fiscal year."})
        if not (self.fiscal_year.starts_on <= self.obligation_date <= self.fiscal_year.ends_on):
            raise ValidationError({"obligation_date": "The obligation date must fall inside the selected fiscal year."})
        if self.fiscal_year.status == FiscalYear.CLOSED:
            raise ValidationError("The fiscal year is closed to new obligation activity.")
        if self.kind == self.ORIGINAL and self.corrects_id:
            raise ValidationError({"corrects": "An original obligation cannot correct another obligation."})
        if self.kind != self.ORIGINAL:
            if not self.corrects_id or self.corrects.status != self.CERTIFIED:
                raise ValidationError({"corrects": "An adjustment, return, or cancellation must reference a certified obligation."})
            if self.corrects.department_id != self.department_id or self.corrects.fiscal_year_id != self.fiscal_year_id:
                raise ValidationError({"corrects": "A correction must stay in the same Budget office and fiscal year."})
            if self.corrects.requesting_department_id != self.requesting_department_id:
                raise ValidationError({"corrects": "A correction must stay with the original requesting office."})
        if self.status == self.CERTIFIED and not self.obligation_number.strip():
            raise ValidationError({"obligation_number": "Budget certification must assign the controlled obligation number."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior and prior.status == self.CERTIFIED:
                governed = (
                    "authorization_id", "fiscal_year_id", "requesting_department_id", "kind", "form_type",
                    "request_reference", "obligation_number", "obligation_date", "claimant_payee", "particulars",
                    "evidence_reference", "signed_control_total", "corrects_id", "linked_voucher_case_public_id",
                    "snapshot_checksum",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Certified obligations are immutable. Use a linked governed correction.")


class PayableObligationAllocation(BudgetOwnedModel):
    """Versioned claim-capacity reservations against one authoritative obligation lineage."""

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
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (ACTIVE, "Active allocation"),
        (SUPERSEDED, "Superseded by guided revision"),
        (CANCELLED, "Removed before DV issuance"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    obligation = models.ForeignKey(
        ObligationRequest, on_delete=models.PROTECT, related_name="payable_allocations",
        help_text="The certified original at the root of the corrected obligation lineage.",
    )
    voucher_case_public_id = models.UUIDField(db_index=True)
    voucher_reference_snapshot = models.CharField(max_length=40)
    relationship_type = models.CharField(max_length=16, choices=RELATIONSHIP_CHOICES)
    allocated_amount = models.DecimalField(max_digits=18, decimal_places=2)
    obligation_amount_snapshot = models.DecimalField(max_digits=18, decimal_places=2)
    obligation_checksum_snapshot = models.CharField(max_length=64)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    active_identity_marker = models.GeneratedField(
        expression=models.Case(
            models.When(status="active", then=models.Value(1)),
            default=models.Value(None),
        ),
        output_field=models.PositiveSmallIntegerField(), db_persist=True, null=True,
    )
    supersedes = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="successor_allocations",
    )
    change_reason = models.TextField()
    recorded_by_id = models.PositiveBigIntegerField()
    recorded_by_label = models.CharField(max_length=160)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("voucher_reference_snapshot", "obligation__obligation_number", "version")
        constraints = (
            models.UniqueConstraint(
                fields=("obligation", "voucher_case_public_id", "version"),
                name="unique_payable_allocation_version",
            ),
            models.UniqueConstraint(
                fields=("obligation", "voucher_case_public_id", "active_identity_marker"),
                name="unique_active_payable_allocation",
            ),
            models.CheckConstraint(
                condition=models.Q(allocated_amount__gte=Decimal("0.00")),
                name="payable_allocation_nonnegative",
            ),
        )

    def __str__(self):
        return f"{self.obligation} → {self.voucher_reference_snapshot} v{self.version}"

    def clean(self):
        if self.obligation_id and self.obligation.kind != ObligationRequest.ORIGINAL:
            raise ValidationError({"obligation": "Allocate against the certified original at the lineage root."})
        if self.obligation_id and self.obligation.status != ObligationRequest.CERTIFIED:
            raise ValidationError({"obligation": "Allocate only against a certified obligation."})
        if self.status == self.ACTIVE and self.allocated_amount <= Decimal("0.00"):
            raise ValidationError({"allocated_amount": "An active allocation must be greater than zero."})
        if self.status == self.CANCELLED and self.allocated_amount != Decimal("0.00"):
            raise ValidationError({"allocated_amount": "A cancelled allocation must have a zero current amount."})
        if not self.change_reason.strip():
            raise ValidationError({"change_reason": "Record the reviewed reason for this allocation version."})
        if self.supersedes_id:
            if (
                self.supersedes.obligation_id != self.obligation_id
                or self.supersedes.voucher_case_public_id != self.voucher_case_public_id
                or self.version != self.supersedes.version + 1
            ):
                raise ValidationError({"supersedes": "A successor must continue the same obligation/case lineage in sequence."})
        elif self.version != 1:
            raise ValidationError({"version": "An initial allocation starts at version 1."})
        if self.pk:
            prior = type(self).objects.filter(pk=self.pk).first()
            if prior:
                governed = (
                    "public_id", "department_id", "department_label", "obligation_id",
                    "voucher_case_public_id", "voucher_reference_snapshot", "relationship_type",
                    "allocated_amount", "obligation_amount_snapshot", "obligation_checksum_snapshot",
                    "version", "supersedes_id", "change_reason", "recorded_by_id", "recorded_by_label",
                )
                if any(getattr(prior, field) != getattr(self, field) for field in governed):
                    raise ValidationError("Payable allocation evidence is immutable; create a successor version.")
                if prior.status != self.status and not (
                    prior.status == self.ACTIVE and self.status == self.SUPERSEDED
                ):
                    raise ValidationError("Only an active allocation may transition to superseded.")

    def delete(self, *args, **kwargs):
        raise ValidationError("Payable allocation history cannot be deleted; create a cancelled successor.")


class ObligationRequestLine(BudgetOwnedModel):
    OBLIGATE, REDUCE = "obligate", "reduce"
    MOVEMENT_CHOICES = ((OBLIGATE, "Obligate allotment"), (REDUCE, "Reduce / return obligation"))
    request = models.ForeignKey(ObligationRequest, on_delete=models.PROTECT, related_name="lines")
    appropriation_line = models.ForeignKey(AuthorizedAppropriationLine, on_delete=models.PROTECT, related_name="obligation_request_lines")
    movement_type = models.CharField(max_length=12, choices=MOVEMENT_CHOICES, default=OBLIGATE)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("appropriation_line__fund_code", "appropriation_line__responsibility_center_code", "appropriation_line__account_code", "pk")

    @property
    def effect(self):
        return self.amount if self.movement_type == self.OBLIGATE else -self.amount

    def clean(self):
        if self.amount <= Decimal("0"):
            raise ValidationError({"amount": "An obligation line amount must be greater than zero."})
        if self.appropriation_line.authorization_id != self.request.authorization_id:
            raise ValidationError({"appropriation_line": "Choose a line from the request's exact authorized appropriation."})
        if self.department_id != self.request.department_id:
            raise ValidationError("The obligation line and request must belong to the same Budget office.")
        if self.request.kind == ObligationRequest.ORIGINAL and self.movement_type != self.OBLIGATE:
            raise ValidationError({"movement_type": "An original request may only create an obligation."})
        if self.request.kind in (ObligationRequest.RETURN, ObligationRequest.CANCELLATION) and self.movement_type != self.REDUCE:
            raise ValidationError({"movement_type": "A return or cancellation may only reduce an obligation."})

    def save(self, *args, **kwargs):
        if self.request.status not in (ObligationRequest.DRAFT, ObligationRequest.RETURNED):
            raise ValidationError("Obligation lines are editable only while the request is draft or returned.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.request.status not in (ObligationRequest.DRAFT, ObligationRequest.RETURNED):
            raise ValidationError("Submitted or certified obligation lines cannot be deleted.")
        return super().delete(*args, **kwargs)


class ObligationMovement(BudgetOwnedModel):
    request = models.ForeignKey(ObligationRequest, on_delete=models.PROTECT, related_name="movements")
    source_line_id = models.PositiveBigIntegerField()
    appropriation_line = models.ForeignKey(AuthorizedAppropriationLine, on_delete=models.PROTECT, related_name="obligation_movements")
    movement_type = models.CharField(max_length=12, choices=ObligationRequestLine.MOVEMENT_CHOICES)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    obligation_effect = models.DecimalField(max_digits=18, decimal_places=2)
    effective_date = models.DateField()
    obligation_number_snapshot = models.CharField(max_length=100)
    requesting_department_snapshot = models.CharField(max_length=160)
    claimant_payee_snapshot = models.CharField(max_length=220)
    particulars_snapshot = models.TextField()
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("effective_date", "pk")
        constraints = (models.UniqueConstraint(fields=("request", "source_line_id"), name="unique_obligation_movement_source"),)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Certified obligation movements are append-only and immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Certified obligation movements cannot be deleted.")


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

class QuarterlyFinancialPlan(BudgetOwnedModel):
    DRAFT, FOR_REVIEW, RETURNED, APPROVED = "draft", "for_review", "returned", "approved"
    STATUS_CHOICES = ((DRAFT, "Draft"), (FOR_REVIEW, "For review"), (RETURNED, "Returned"), (APPROVED, "Approved plan"))
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    authorization = models.ForeignKey(AppropriationAuthorization, on_delete=models.PROTECT, related_name="quarterly_plans")
    version = models.PositiveIntegerField()
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="successors")
    reference = models.CharField(max_length=120)
    prepared_on = models.DateField()
    evidence_reference = models.TextField()
    change_basis = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=DRAFT)
    submitted_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    snapshot_checksum = models.CharField(max_length=64, blank=True, editable=False)
    created_by_id = models.PositiveBigIntegerField()
    created_by_label = models.CharField(max_length=180)
    submitted_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    approved_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    approved_by_label = models.CharField(max_length=180, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_basis = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-version", "-pk")
        constraints = (models.UniqueConstraint(fields=("authorization", "version"), name="unique_quarterly_plan_version"),)

    def clean(self):
        from django.utils import timezone
        if self.authorization.department_id != self.department_id or self.authorization.status != AppropriationAuthorization.AUTHORIZED:
            raise ValidationError("Select an authorized appropriation in this Budget office.")
        if self.prepared_on > timezone.localdate():
            raise ValidationError("The plan preparation date cannot be in the future.")
        if self.supersedes_id and (self.supersedes.authorization_id != self.authorization_id or self.supersedes.status != self.APPROVED):
            raise ValidationError("A successor must retain an approved plan for the same authority.")

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk, status=self.APPROVED).exists():
            raise ValidationError("Approved planning history is immutable. Create a successor.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain planning versions and their review history.")


class QuarterlyPlanLine(BudgetOwnedModel):
    plan = models.ForeignKey(QuarterlyFinancialPlan, on_delete=models.PROTECT, related_name="lines")
    appropriation_line = models.ForeignKey(AuthorizedAppropriationLine, on_delete=models.PROTECT, related_name="quarterly_plan_lines")
    q1 = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    q2 = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    q3 = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    q4 = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    basis = models.TextField(blank=True)
    indicator = models.CharField(max_length=240, blank=True)
    target_unit = models.CharField(max_length=80, blank=True)
    target_q1 = models.CharField(max_length=120, blank=True)
    target_q2 = models.CharField(max_length=120, blank=True)
    target_q3 = models.CharField(max_length=120, blank=True)
    target_q4 = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ("appropriation_line_id",)
        constraints = (models.UniqueConstraint(fields=("plan", "appropriation_line"), name="unique_quarterly_plan_source"),)

    def clean(self):
        if self.department_id != self.plan.department_id or self.appropriation_line.authorization_id != self.plan.authorization_id:
            raise ValidationError("Planning rows must use the plan's exact authorized schedule.")
        amounts = [getattr(self, f"q{i}") for i in range(1, 5)]
        if any(value is not None and value < 0 for value in amounts):
            raise ValidationError("Quarter allocations cannot be negative.")
        if sum((value or Decimal("0") for value in amounts), Decimal("0")) > self.appropriation_line.amount:
            raise ValidationError("Quarter allocations exceed this line's authorized appropriation.")
        targets = [getattr(self, f"target_q{i}") for i in range(1, 5)]
        if any(targets) and (not self.indicator.strip() or not self.target_unit.strip()):
            raise ValidationError("Physical targets need their indicator and unit; they are not financial amounts.")

    def save(self, *args, **kwargs):
        if self.plan.status not in (QuarterlyFinancialPlan.DRAFT, QuarterlyFinancialPlan.RETURNED):
            raise ValidationError("Return the plan before editing its rows.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Retain the complete authorized schedule; use explicit zero allocations.")
