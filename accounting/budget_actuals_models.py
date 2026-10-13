"""Retained native category/entity review, separate from statutory certification."""
import uuid
from django.core.exceptions import ValidationError
from django.db import models
from .models import DepartmentOwnedModel, Fund


class NativeBudgetActualsPreparation(DepartmentOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    budget_department_id = models.PositiveBigIntegerField()
    treasury_department_id = models.PositiveBigIntegerField()
    entity_key = models.CharField(max_length=80)
    entity_label = models.CharField(max_length=255)
    period_start = models.DateField()
    period_end = models.DateField()
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, default='submitted')
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_by_label = models.CharField(max_length=160)
    prepared_at = models.DateTimeField()
    reviewed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reviewed_by_label = models.CharField(max_length=160, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_authority = models.TextField(blank=True)
    review_note = models.TextField(blank=True)
    review_observation = models.JSONField(null=True, blank=True)
    decision_checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ('-prepared_at', '-pk')
        constraints = [models.UniqueConstraint(fields=('department_id', 'fund', 'entity_key',
            'period_start', 'period_end', 'version'), name='unique_native_actuals_version')]
        permissions = [(f'{action}_native_budget_actuals', f'Can {action} native Budget actuals preparation')
            for action in ('view', 'prepare', 'review', 'export')]

    def save(self, *args, **kwargs):
        try:
            if self.pk:
                prior = type(self).objects.get(pk=self.pk)
                allowed = {'status', 'reviewed_by_id', 'reviewed_by_label', 'reviewed_at',
                    'review_authority', 'review_note', 'review_observation', 'decision_checksum'}
                if any(getattr(self, f.attname) != getattr(prior, f.attname) and not
                    (f.attname in allowed and getattr(self, '_decision_write', False)
                     and prior.status == 'submitted') for f in self._meta.concrete_fields):
                    raise ValidationError('Retain native actuals preparation and review; create a successor.')
            elif self.status != 'submitted' or self.decision_checksum or self.reviewed_by_id or self.reviewed_at or self.review_observation:
                raise ValidationError('New native actuals preparations require a separate independent review.')
            return super().save(*args, **kwargs)
        finally:
            self._decision_write = False

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain native actuals source, category and review history.')


class NativeBudgetActualsDecision(DepartmentOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    preparation = models.ForeignKey(NativeBudgetActualsPreparation, on_delete=models.PROTECT, related_name='joint_decisions')
    role = models.CharField(max_length=12, choices=(('accountant','Accountant'),('treasurer','Treasurer')))
    outcome = models.CharField(max_length=12, choices=(('certified','Certified'),('returned','Returned')))
    actor_id = models.PositiveBigIntegerField()
    actor_label = models.CharField(max_length=160)
    actor_department_id = models.PositiveBigIntegerField()
    decided_at = models.DateTimeField()
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)

    class Meta:
        ordering = ('decided_at','pk')
        constraints = [models.UniqueConstraint(fields=('preparation','role'), name='unique_native_actuals_role')]
        permissions = [(f'certify_{role}_native_budget_actuals',f'Can certify native Budget actuals as {role}')
            for role in ('accountant','treasurer')]

    def save(self,*args,**kwargs):
        if self.pk:
            prior=type(self).objects.get(pk=self.pk)
            if any(getattr(self,f.attname)!=getattr(prior,f.attname) for f in self._meta.concrete_fields):
                raise ValidationError('Retain native actuals role decisions; prepare a successor.')
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Retain native actuals joint decision history.')
