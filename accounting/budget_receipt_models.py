import uuid
from django.core.exceptions import ValidationError
from django.db import models
from .models import DepartmentOwnedModel, Fund, JournalEntry


class BudgetReceiptAttributionBatch(DepartmentOwnedModel):
    SUBMITTED, APPROVED, RETURNED = 'submitted', 'approved', 'returned'
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT)
    period_start = models.DateField()
    period_end = models.DateField()
    prepared_by_id = models.PositiveBigIntegerField()
    prepared_by_label = models.CharField(max_length=160)
    prepared_at = models.DateTimeField()
    payload = models.JSONField()
    payload_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=12, default=SUBMITTED)
    reviewed_by_id = models.PositiveBigIntegerField(null=True, blank=True)
    reviewed_by_label = models.CharField(max_length=160, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    decision_checksum = models.CharField(max_length=64, blank=True)

    class Meta:
        permissions = [(action + '_budget_receipt_attributions', label) for action, label in (
            ('view', 'Can read Budget receipt attributions'), ('prepare', 'Can propose Budget receipt attributions'),
            ('review', 'Can independently review Budget receipt attributions'), ('export', 'Can export Budget receipt attributions'))]

    def save(self, *args, **kwargs):
        if self.pk:
            prior = type(self).objects.get(pk=self.pk)
            allowed = {'status', 'reviewed_by_id', 'reviewed_by_label', 'reviewed_at', 'review_note', 'decision_checksum'}
            if (not getattr(self, '_decision_write', False) or prior.status != self.SUBMITTED
                or self.status not in (self.APPROVED, self.RETURNED)
                or not self.reviewed_by_id or self.reviewed_by_id == self.prepared_by_id
                or not self.reviewed_at or not self.review_note.strip() or not self.decision_checksum
                or any(getattr(self, f.attname) != getattr(prior, f.attname)
                    for f in self._meta.concrete_fields if f.attname not in allowed)):
                raise ValidationError('Retain original receipt proposals and independent decisions; prepare a successor.')
        elif self.status != self.SUBMITTED or self.reviewed_by_id or self.decision_checksum:
            raise ValidationError('A new receipt attribution batch starts pending independent review.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain receipt attribution batches and decisions.')


class BudgetReceiptAttribution(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    batch = models.ForeignKey(BudgetReceiptAttributionBatch, on_delete=models.PROTECT, related_name='members')
    entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name='budget_receipt_attributions')
    version = models.PositiveIntegerField()
    base_version = models.PositiveIntegerField(default=0)
    partition = models.JSONField()
    dependencies = models.JSONField(default=list)

    class Meta:
        ordering = ('entry_id', '-version')
        constraints = (
            models.UniqueConstraint(fields=('entry', 'version'), name='unique_budget_receipt_version'),
            models.UniqueConstraint(fields=('batch', 'entry'), name='unique_budget_receipt_member'),
        )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Receipt attribution members are immutable; prepare a successor.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Retain receipt attribution members.')


class BudgetReceiptAttributionHead(models.Model):
    entry = models.OneToOneField(JournalEntry, on_delete=models.PROTECT, related_name='budget_receipt_attribution_head')
    attribution = models.OneToOneField(BudgetReceiptAttribution, on_delete=models.PROTECT, related_name='receipt_current_head')

    def clean(self):
        if self.attribution_id and (self.attribution.entry_id != self.entry_id
            or self.attribution.batch.status != BudgetReceiptAttributionBatch.APPROVED):
            raise ValidationError('Select an independently approved receipt attribution for this exact journal.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
