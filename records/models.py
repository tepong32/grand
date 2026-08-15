from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from departments.models import Department


def record_file_path(instance, filename):
    return f"records/{instance.record.department.slug}/{instance.record.public_id}/{filename}"


class DepartmentRecord(models.Model):
    CLASS_GENERAL = "general"
    CLASS_ASSISTANCE = "assistance"
    CLASS_PROGRAM = "program"
    CLASS_ACTIVITY = "activity"
    CLASS_CITIZEN = "citizen"
    CLASS_REPORT = "report"
    CLASS_CHOICES = (
        (CLASS_GENERAL, "General office record"),
        (CLASS_ASSISTANCE, "Assistance case record"),
        (CLASS_PROGRAM, "Program record"),
        (CLASS_ACTIVITY, "Activity record"),
        (CLASS_CITIZEN, "Citizen service record"),
        (CLASS_REPORT, "Official report"),
    )

    CONFIDENTIALITY_INTERNAL = "internal"
    CONFIDENTIALITY_RESTRICTED = "restricted"
    CONFIDENTIALITY_CONFIDENTIAL = "confidential"
    CONFIDENTIALITY_CHOICES = (
        (CONFIDENTIALITY_INTERNAL, "Department internal"),
        (CONFIDENTIALITY_RESTRICTED, "Restricted"),
        (CONFIDENTIALITY_CONFIDENTIAL, "Confidential / contains sensitive information"),
    )

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    DISPOSED = "disposed"
    STATUS_CHOICES = (
        (DRAFT, "Draft"), (UNDER_REVIEW, "Under review"), (APPROVED, "Approved"),
        (SUPERSEDED, "Superseded"), (ARCHIVED, "Archived"), (DISPOSED, "Disposed"),
    )

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="official_records")
    record_number = models.CharField(max_length=80)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    classification = models.CharField(max_length=24, choices=CLASS_CHOICES, default=CLASS_GENERAL)
    confidentiality = models.CharField(max_length=20, choices=CONFIDENTIALITY_CHOICES, default=CONFIDENTIALITY_INTERNAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT, db_index=True)
    custodian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="custodied_department_records")
    retention_years = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)])
    retention_notes = models.TextField(blank=True)
    retention_start_date = models.DateField(null=True, blank=True)
    disposition_due_date = models.DateField(null=True, blank=True, db_index=True)
    legal_hold = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_department_records")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_department_records")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_department_records")
    superseded_by = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="supersedes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    disposed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-updated_at", "-pk")
        constraints = (
            models.UniqueConstraint(fields=("department", "record_number"), name="unique_record_number_per_department"),
        )
        permissions = (
            ("view_records_workspace", "Can access the department records workspace"),
            ("manage_department_records", "Can create and update department records"),
            ("review_department_records", "Can review department records"),
            ("approve_department_records", "Can approve and supersede department records"),
            ("download_department_records", "Can download department record files"),
            ("manage_record_retention", "Can manage retention, archival, and disposal"),
            ("view_restricted_records", "Can view restricted and confidential department records"),
        )

    def __str__(self):
        return f"{self.record_number} - {self.title}"

    def get_absolute_url(self):
        return reverse("records:record_detail", kwargs={"public_id": self.public_id})

    @property
    def is_retention_due(self):
        return bool(self.disposition_due_date and self.disposition_due_date <= timezone.localdate())

    @property
    def can_be_disposed(self):
        return self.status == self.ARCHIVED and self.is_retention_due and not self.legal_hold

    def clean(self):
        if self.disposition_due_date and not self.retention_start_date:
            raise ValidationError({"retention_start_date": "A retention start date is required when a disposition date is set."})
        if self.disposition_due_date and self.retention_start_date and self.disposition_due_date < self.retention_start_date:
            raise ValidationError({"disposition_due_date": "Disposition cannot be earlier than the retention start date."})
        if self.superseded_by_id:
            if self.superseded_by_id == self.pk:
                raise ValidationError({"superseded_by": "A record cannot supersede itself."})
            if self.superseded_by.department_id != self.department_id:
                raise ValidationError({"superseded_by": "The replacement record must belong to the same department."})
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            if previous and previous.status == self.DISPOSED:
                raise ValidationError("Disposed record metadata is immutable.")
            if previous and previous.status in (self.APPROVED, self.ARCHIVED, self.SUPERSEDED):
                protected_fields = ("department_id", "record_number", "title", "description", "classification", "confidentiality")
                if any(getattr(previous, field) != getattr(self, field) for field in protected_fields):
                    raise ValidationError("Approved record identity and descriptive metadata are immutable. Create a new version instead.")


class RecordAssociation(models.Model):
    ALLOWED_MODELS = {
        "assistance.assistancerequest", "assistance.requestdocument", "assistance.citizenprofile",
        "social_welfare.socialwelfareprogram", "social_welfare.programactivity", "reporting.reportrun",
    }

    record = models.ForeignKey(DepartmentRecord, on_delete=models.CASCADE, related_name="associations")
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    role = models.CharField(max_length=40, default="context")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_record_associations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = (
            models.UniqueConstraint(fields=("record", "content_type", "object_id", "role"), name="unique_record_association"),
        )

    def __str__(self):
        return f"{self.record.record_number}: {self.content_type.app_label}.{self.content_type.model}#{self.object_id}"

    @property
    def model_label(self):
        return f"{self.content_type.app_label}.{self.content_type.model}"

    def clean(self):
        if self.content_type_id and self.model_label not in self.ALLOWED_MODELS:
            raise ValidationError({"content_type": "Only approved GRAND operational records may be linked."})
        if self.content_type_id and not self.content_object:
            raise ValidationError({"object_id": "The linked operational record no longer exists."})

    def save(self, *args, **kwargs):
        if self.record_id and self.record.status not in (DepartmentRecord.DRAFT, DepartmentRecord.UNDER_REVIEW):
            raise ValidationError("Operational sources cannot be attached after approval. Create a new record version instead.")
        return super().save(*args, **kwargs)


class RecordFile(models.Model):
    record = models.ForeignKey(DepartmentRecord, on_delete=models.PROTECT, related_name="files")
    file = models.FileField(upload_to=record_file_path, max_length=500)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=64)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_record_files")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    superseded_by = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="supersedes")

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.record.record_number}: {self.display_name}"


class RecordEvent(models.Model):
    record = models.ForeignKey(DepartmentRecord, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="department_record_events")
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.record.record_number}: {self.action}"

    @property
    def display_action(self):
        return self.action.replace("_", " ").title()

    @property
    def display_from_status(self):
        return self.from_status.replace("_", " ").title()

    @property
    def display_to_status(self):
        return self.to_status.replace("_", " ").title()
