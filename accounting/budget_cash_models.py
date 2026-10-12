import uuid
from django.core.exceptions import ValidationError
from django.db import models
from .models import DepartmentOwnedModel, Fund


class BudgetCashEvidence(DepartmentOwnedModel):
    """Dated cash certificate, separate from available-capacity authorization."""
    public_id = models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    fund = models.ForeignKey(Fund,on_delete=models.PROTECT)
    budget_department_id = models.PositiveBigIntegerField()
    treasury_department_id = models.PositiveBigIntegerField()
    entity_key = models.CharField(max_length=80)
    balance_date = models.DateField()
    boundary = models.CharField(max_length=16)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12,default='submitted')
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    certificate = models.BinaryField(editable=False)
    reconciliation = models.BinaryField(editable=False)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_by_label = models.CharField(max_length=160)
    prepared_at = models.DateTimeField()
    reviewed_by_id = models.PositiveBigIntegerField(null=True,blank=True)
    reviewed_by_label = models.CharField(max_length=160,blank=True)
    reviewed_at = models.DateTimeField(null=True,blank=True)
    review_note = models.TextField(blank=True)
    review_authority = models.CharField(max_length=2000,blank=True)
    decision_checksum = models.CharField(max_length=64,blank=True)

    class Meta:
        ordering = ('-prepared_at','-pk')
        constraints = [models.UniqueConstraint(fields=('department_id','fund','entity_key','balance_date','boundary','version'),name='unique_budget_cash_evidence_version')]
        permissions = [(f'{action}_budget_cash_evidence',f'Can {action} historical Budget cash evidence') for action in ('view','prepare','review','export')]

    def save(self,*args,**kwargs):
        try:
            if self.pk:
                prior=type(self).objects.get(pk=self.pk)
                allowed={'status','reviewed_by_id','reviewed_by_label','reviewed_at','review_note','review_authority','decision_checksum'}
                if any(getattr(self,f.attname)!=getattr(prior,f.attname) and not
                    (f.attname in allowed and getattr(self,'_decision_write',False)) for f in self._meta.concrete_fields):
                    raise ValidationError('Retain original cash evidence; prepare a successor.')
            return super().save(*args,**kwargs)
        finally:
            self._decision_write=False

    def delete(self,*args,**kwargs):
        raise ValidationError('Retain dated cash evidence and decisions.')


class NativeBudgetCashPreparation(DepartmentOwnedModel):
    """Immutable source preparation, never an approval or cash-capacity grant."""
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    budget_department_id = models.PositiveBigIntegerField()
    treasury_department_id = models.PositiveBigIntegerField()
    entity_key = models.CharField(max_length=80)
    balance_date = models.DateField()
    boundary = models.CharField(max_length=16)
    version = models.PositiveIntegerField()
    restriction_source = models.ForeignKey(BudgetCashEvidence, null=True, blank=True,
        on_delete=models.PROTECT, related_name='native_preparations')
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    certificate = models.BinaryField(editable=False, default=bytes)
    reconciliation = models.BinaryField(editable=False, default=bytes)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_by_label = models.CharField(max_length=160)
    prepared_at = models.DateTimeField()

    class Meta:
        ordering = ('-prepared_at', '-pk')
        constraints = [models.UniqueConstraint(
            fields=('department_id', 'fund', 'entity_key', 'balance_date', 'boundary', 'version'),
            name='unique_native_budget_cash_version')]
        permissions = [(f'{action}_native_budget_cash', f'Can {action} native Budget cash preparations')
            for action in ('view', 'prepare', 'export')]

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            if any(getattr(self, field.attname) != getattr(prior, field.attname)
                   for field in self._meta.concrete_fields):
                raise ValidationError('Retain native cash preparation; create a successor version.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain native cash preparation history.')


class NativeBudgetCashDecision(DepartmentOwnedModel):
    """One immutable role decision on an unchanged observed cash preparation."""
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    preparation = models.ForeignKey(NativeBudgetCashPreparation, on_delete=models.PROTECT,
        related_name='joint_decisions')
    role = models.CharField(max_length=12, choices=(('accountant', 'Accountant'), ('treasurer', 'Treasurer')))
    outcome = models.CharField(max_length=12, choices=(('certified', 'Certified'), ('returned', 'Returned')))
    actor_id = models.PositiveBigIntegerField()
    actor_label = models.CharField(max_length=160)
    actor_department_id = models.PositiveBigIntegerField()
    decided_at = models.DateTimeField()
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)

    class Meta:
        ordering = ('decided_at', 'pk')
        constraints = [models.UniqueConstraint(fields=('preparation', 'role'),
            name='unique_native_cash_role_decision')]
        permissions = [(f'certify_{role}_native_budget_cash', f'Can certify native Budget cash as {role}')
            for role in ('accountant', 'treasurer')]

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            if any(getattr(self, field.attname) != getattr(prior, field.attname)
                   for field in self._meta.concrete_fields):
                raise ValidationError('Retain original native cash role decision; prepare a successor.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain original native cash joint decisions.')
