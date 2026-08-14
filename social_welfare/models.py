from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from departments.models import Department


class SocialWelfareProgram(models.Model):
    TYPE_FEEDING = "feeding"
    TYPE_SEMINAR = "seminar"
    TYPE_ORIENTATION = "orientation"
    TYPE_OUTREACH = "outreach"
    TYPE_DISTRIBUTION = "distribution"
    TYPE_INTERVENTION = "intervention"
    TYPE_OTHER = "other"
    TYPE_CHOICES = (
        (TYPE_FEEDING, "Feeding program"),
        (TYPE_SEMINAR, "Seminar"),
        (TYPE_ORIENTATION, "Orientation"),
        (TYPE_OUTREACH, "Outreach"),
        (TYPE_DISTRIBUTION, "Distribution"),
        (TYPE_INTERVENTION, "Social intervention"),
        (TYPE_OTHER, "Other"),
    )

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_ARCHIVED, "Archived"),
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="social_welfare_programs",
    )
    name = models.CharField(max_length=180)
    code = models.CharField(max_length=40)
    program_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coordinated_social_welfare_programs",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_social_welfare_programs",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_social_welfare_programs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(
                fields=("department", "code"),
                name="unique_social_welfare_program_code_per_department",
            ),
        )
        permissions = (
            ("manage_social_welfare_programs", "Can manage social welfare programs and activities"),
        )

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be earlier than the start date."})

    def get_absolute_url(self):
        return reverse("social_welfare:program_detail", kwargs={"pk": self.pk})


class ProgramActivity(models.Model):
    TYPE_FEEDING = "feeding"
    TYPE_SEMINAR = "seminar"
    TYPE_ORIENTATION = "orientation"
    TYPE_OUTREACH = "outreach"
    TYPE_DISTRIBUTION = "distribution"
    TYPE_FIELD_OPERATION = "field_operation"
    TYPE_OTHER = "other"
    TYPE_CHOICES = (
        (TYPE_FEEDING, "Feeding session"),
        (TYPE_SEMINAR, "Seminar"),
        (TYPE_ORIENTATION, "Orientation"),
        (TYPE_OUTREACH, "Outreach activity"),
        (TYPE_DISTRIBUTION, "Distribution activity"),
        (TYPE_FIELD_OPERATION, "Field operation"),
        (TYPE_OTHER, "Other"),
    )

    STATUS_PLANNED = "planned"
    STATUS_ONGOING = "ongoing"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_PLANNED, "Planned"),
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    program = models.ForeignKey(
        SocialWelfareProgram,
        on_delete=models.PROTECT,
        related_name="activities",
    )
    title = models.CharField(max_length=180)
    activity_type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    venue = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    expected_attendance = models.PositiveIntegerField(default=0)
    actual_attendance = models.PositiveIntegerField(null=True, blank=True)
    outcome_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_program_activities",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="updated_program_activities",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("starts_at", "title")
        verbose_name_plural = "program activities"

    def __str__(self):
        return f"{self.title} ({self.program.code})"

    def clean(self):
        if self.ends_at and self.ends_at < self.starts_at:
            raise ValidationError({"ends_at": "End time cannot be earlier than the start time."})

    def get_absolute_url(self):
        return self.program.get_absolute_url()
