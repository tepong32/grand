# assistance/models.py

from django.db import models
from django_ckeditor_5.fields import CKEditor5Field
from django.utils import timezone
from django.utils.crypto import get_random_string


def sample_upload_path(instance, filename):
    return f"assistance_samples/{instance.id}/{filename}"

class AssistanceType(models.Model):
    name = models.CharField(max_length=255)
    description = CKEditor5Field('Description', config_name='default')
    requirements = CKEditor5Field('Requirements', config_name='default')
    sample_image = models.ImageField(upload_to=sample_upload_path, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class AssistanceRequest(models.Model):
    reference_code = models.CharField(max_length=20, unique=True)
    assistance_type = models.ForeignKey('AssistanceType', on_delete=models.CASCADE)
    period = models.CharField(max_length=9, help_text="e.g., 2024–2025", null=True, blank=True)

    SEMESTER_CHOICES = [
        ('1st', '1st Semester'),
        ('2nd', '2nd Semester'),
        ('summer', 'Midyear / Summer'),
    ]
    semester = models.CharField(max_length=10, choices=SEMESTER_CHOICES, blank=True, null=True, help_text="Optional: for educational assistance")

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, help_text="#s only: 09123456789", blank=False)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    edit_code = models.CharField(max_length=6, blank=True, editable=False)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True, null=True)

    approved_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.reference_code} - {self.full_name}"

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = self.generate_reference_code()
        if not self.edit_code:
            self.edit_code = get_random_string(length=6, allowed_chars='0123456789')
        if self.status == 'approved' and not self.approved_at:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)

    def generate_reference_code(self):
        now = timezone.now()
        month = now.strftime('%m')
        year = now.strftime('%Y')
        count = AssistanceRequest.objects.filter(
            submitted_at__year=year,
            submitted_at__month=month
        ).count() + 1
        return f"MSWD-{month}-{year}-{count:04d}"


class RequestDocument(models.Model):
    REQUEST_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('clearer_copy', 'Needs a Clearer Copy'),
        ('wrong_file', 'Wrong File Attached'),
        ('incomplete', 'Incomplete Document'),
        ('missing_stamp', 'Requires Official Stamp/Signature'),
        ('expired', 'Obsolete/Expired Document'),
    ]

    request = models.ForeignKey(AssistanceRequest, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField(upload_to='assistance_docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=REQUEST_STATUS_CHOICES,
        default='pending'
    )
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.file.name} ({self.get_status_display()})"
    
    
from users.models import User 
class RequestLog(models.Model):
    request = models.ForeignKey('AssistanceRequest', on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status_before = models.CharField(max_length=20)
    status_after = models.CharField(max_length=20)
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.request.reference_code} update on {self.timestamp:%Y-%m-%d %H:%M}"
