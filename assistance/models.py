from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field


def sample_upload_path(instance, filename):
    return f"assistance_samples/{instance.id}/{filename}"


class AssistanceType(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, unique=False)
    description = CKEditor5Field("Description", config_name="default")
    requirements = CKEditor5Field("Requirements", config_name="default")
    sample_image = models.ImageField(upload_to=sample_upload_path, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or "assistance-program"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class AssistanceProgram(AssistanceType):
    """
    Compatibility proxy kept for TracePoint parity while preserving existing data.
    """

    class Meta:
        proxy = True


class AssistanceRequest(models.Model):
    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("pending", "Pending"),
        ("review", "Under Review"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    ]

    SEMESTER_CHOICES = [
        ("1st", "1st Semester"),
        ("2nd", "2nd Semester"),
        ("summer", "Midyear / Summer"),
    ]

    reference_code = models.CharField(max_length=20, unique=True, db_index=True)
    assistance_type = models.ForeignKey("AssistanceType", on_delete=models.CASCADE)

    period = models.CharField(max_length=9, help_text="e.g., 2024-2025", null=True, blank=True)
    semester = models.CharField(
        max_length=10,
        choices=SEMESTER_CHOICES,
        blank=True,
        null=True,
        help_text="Optional: for educational assistance",
    )

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, help_text="#s only: 09123456789", blank=False)

    submitted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    edit_code = models.CharField(max_length=6, blank=True, editable=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="submitted")
    remarks = models.TextField(blank=True, null=True)

    approved_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)

    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    citizen = models.ForeignKey(
        "CitizenProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requests",
    )

    def __str__(self):
        return f"{self.reference_code} - {self.full_name}"

    @property
    def tracking_code(self) -> str:
        return self.reference_code

    @tracking_code.setter
    def tracking_code(self, value):
        self.reference_code = value

    @property
    def secure_edit_token(self) -> str:
        return self.edit_code

    @secure_edit_token.setter
    def secure_edit_token(self, value):
        self.edit_code = value

    @property
    def program(self):
        return self.assistance_type

    @program.setter
    def program(self, value):
        self.assistance_type = value

    @property
    def status_display(self):
        return self.get_status_display()

    @property
    def is_locked(self):
        return bool(self.claimed_at is not None or self.status == "approved")

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = self.generate_reference_code()
        if not self.edit_code:
            self.edit_code = get_random_string(length=6, allowed_chars="0123456789")
        if self.status == "approved" and not self.approved_at:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)

    def generate_reference_code(self):
        now = timezone.now()
        month = now.strftime("%m")
        year = now.strftime("%Y")
        count = (
            AssistanceRequest.objects.filter(
                submitted_at__year=year,
                submitted_at__month=month,
            ).count()
            + 1
        )
        return f"MSWD-{month}-{year}-{count:04d}"

    def get_track_url(self):
        return reverse("assistance:track_request", args=[self.reference_code])

    def get_edit_url(self):
        return reverse("assistance:edit_request", args=[self.edit_code])


class CitizenRequest(AssistanceRequest):
    """
    TracePoint-compatible façade over the legacy AssistanceRequest schema.
    """

    class Meta:
        proxy = True


class RequestDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ("birth_cert", "Birth Certificate"),
        ("indigency", "Certificate of Indigency"),
        ("school_id", "School ID"),
        ("grade_card", "Report Card / Grade Card"),
        ("cert_of_enrollment", "Certificate of Enrollment/Registration"),
        ("others", "Other Supporting Document"),
    ]
    REQUEST_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("clearer_copy", "Needs a Clearer Copy"),
        ("wrong_file", "Wrong File Attached"),
        ("incomplete", "Incomplete Document"),
        ("missing_stamp", "Requires Official Stamp/Signature"),
        ("expired", "Obsolete/Expired Document"),
    ]

    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="others")
    file = models.FileField(upload_to="assistance_docs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=REQUEST_STATUS_CHOICES, default="pending")
    remarks = models.TextField(blank=True)

    is_removed = models.BooleanField(default=False, db_index=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    replacement_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("request", "document_type")

    def __str__(self):
        return f"{self.get_document_type_display()} ({self.get_status_display()})"


class CitizenProfile(models.Model):
    RISK_LEVEL_CHOICES = [
        ("normal", "Normal"),
        ("frequent", "Frequent Requester"),
        ("priority", "Priority Assistance"),
        ("flagged", "Flagged for Review"),
    ]

    full_name = models.CharField(max_length=255)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=20, db_index=True)

    total_requests = models.PositiveIntegerField(default=0)
    last_request_at = models.DateTimeField(null=True, blank=True)
    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        default="normal",
        help_text="Future classification: normal, frequent, priority, flagged",
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.total_requests})"


class RequestTimeline(models.Model):
    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name="timeline")
    event_type = models.CharField(max_length=50)
    message = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.request.reference_code} - {self.event_type}"


class RequestLog(models.Model):
    ACTION_CHOICES = [
        ("status_change", "Status Change"),
        ("remarks_updated", "Remarks Updated"),
        ("document_review", "Document Reviewed"),
        ("manual_edit", "Manual Edit"),
    ]

    request = models.ForeignKey("AssistanceRequest", on_delete=models.CASCADE, related_name="logs")
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES, default="manual_edit")

    status_before = models.CharField(max_length=20, blank=True, null=True)
    status_after = models.CharField(max_length=20, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.request.reference_code} | {self.get_action_type_display()} @ {self.timestamp:%Y-%m-%d %H:%M}"


class DocumentLog(models.Model):
    document = models.ForeignKey("RequestDocument", on_delete=models.CASCADE, related_name="logs")
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status_before = models.CharField(max_length=20)
    status_after = models.CharField(max_length=20)
    remarks_before = models.TextField(blank=True)
    remarks_after = models.TextField(blank=True)

    def __str__(self):
        return f"DocLog for {self.document.request.reference_code} - File {self.document.id}"
