"""Retained historical joint actuals; not native certification or issued Form 1."""
import uuid

from django.core.exceptions import ValidationError
from django.db import models

from .models import DepartmentOwnedModel, Fund


class BudgetSummaryScope(DepartmentOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    budget_department_id = models.PositiveBigIntegerField()
    treasury_department_id = models.PositiveBigIntegerField()
    entity_key = models.CharField(max_length=80)
    entity_label = models.CharField(max_length=255)
    period_start = models.DateField()
    period_end = models.DateField()
    current_version = models.ForeignKey('BudgetSummaryActual', null=True, blank=True,
        on_delete=models.PROTECT, related_name='+')

    class Meta:
        constraints = [models.UniqueConstraint(fields=('department_id', 'fund', 'entity_key',
            'period_start', 'period_end'), name='unique_budget_summary_scope')]
        permissions = [(f'{action}_budget_summary_actuals', label) for action, label in (
            ('view', 'Can read historical joint Budget actuals'),
            ('prepare', 'Can prepare historical joint Budget actuals adoption'),
            ('review', 'Can independently adopt historical joint Budget actuals'),
            ('export', 'Can export historical joint Budget actuals evidence'))]

    def save(self, *args, **kwargs):
        try:
            if self.pk:
                prior = type(self).objects.get(pk=self.pk)
                for field in self._meta.concrete_fields:
                    key = field.attname
                    if getattr(self, key) != getattr(prior, key) and not (
                        key == 'current_version_id' and getattr(self, '_decision_write', False)):
                        raise ValidationError('Retain the original summary scope; do not redirect its evidence.')
            elif self.current_version_id:
                raise ValidationError('A new summary scope has no adopted version.')
            return super().save(*args, **kwargs)
        finally:
            self._decision_write = False

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain summary scopes and their history.')


class BudgetSummaryActual(DepartmentOwnedModel):
    SUBMITTED, APPROVED, RETURNED = 'submitted', 'approved', 'returned'
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    scope = models.ForeignKey(BudgetSummaryScope, on_delete=models.PROTECT, related_name='versions')
    version = models.PositiveIntegerField()
    base_version = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, default=SUBMITTED, choices=(
        (SUBMITTED, 'For independent adoption'), (APPROVED, 'Adopted historical joint actuals'), (RETURNED, 'Returned')))
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    evidence = models.BinaryField(editable=False)
    trial_balance = models.BinaryField(editable=False)
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_by_label = models.CharField(max_length=160)
    prepared_at = models.DateTimeField()
    reviewed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reviewed_by_label = models.CharField(max_length=160, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_authority = models.CharField(max_length=255, blank=True)
    review_note = models.TextField(blank=True)
    decision_checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('scope', 'version'), name='unique_budget_summary_version')]
        ordering = ('-prepared_at', '-pk')

    def save(self, *args, **kwargs):
        try:
            if self.pk:
                prior = type(self).objects.get(pk=self.pk)
                allowed = {'status', 'reviewed_by_id', 'reviewed_by_label', 'reviewed_at',
                    'review_authority', 'review_note', 'decision_checksum'}
                for field in self._meta.concrete_fields:
                    key = field.attname
                    if getattr(self, key) != getattr(prior, key) and not (
                        key in allowed and getattr(self, '_decision_write', False)):
                        raise ValidationError('Historical summary evidence is immutable; prepare a successor.')
            return super().save(*args, **kwargs)
        finally:
            self._decision_write = False

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain historical joint actuals and their decisions.')
