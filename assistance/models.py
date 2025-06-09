# assistance/models.py

from django.db import models
from django_ckeditor_5.fields import CKEditor5Field
import uuid

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
    assistance_type = models.ForeignKey(AssistanceType, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True) # to mark if the request is still active or not

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.reference_code} - {self.full_name}"

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = self.generate_reference_code()
        super().save(*args, **kwargs)

    def generate_reference_code(self):
        now = timezone.now()
        month = now.strftime('%m')
        year = now.strftime('%Y')
        
        # Count requests made this month
        count = AssistanceRequest.objects.filter(
            submitted_at__year=year,
            submitted_at__month=month
        ).count() + 1

        return f"MSWD-{month}-{year}-{count:04d}"
