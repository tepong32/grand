from django.db import models
from django.conf import settings
from django.core.validators import MinLengthValidator
from django.utils.text import slugify
from django.urls import reverse
import logging

from departments.models import Department, Plantilla
from profiles.services.file_service import (
    normalize_department_memo,
    resize_image,
    temp_memo_path,
    uploaded_images_directory_path,
)

logger = logging.getLogger(__name__)


class EmployeeProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employeeprofile"
    )

    # Personal Info
    contact_number = models.CharField(
        max_length=11,
        validators=[MinLengthValidator(10)],
        null=True,
        blank=True,
        verbose_name="Contact Number"
    )
    address = models.CharField(max_length=255, null=True, blank=True)
    note = models.CharField(max_length=255, null=True, blank=True)
    profile_image = models.ImageField(
        default='defaults/default_user_dp.png',
        upload_to=uploaded_images_directory_path,
        blank=True,
        verbose_name="Profile Image"
    )
    birthdate = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=255, null=True, blank=True)
    civil_status = models.CharField(
        max_length=20,
        choices=[
            ('Single', 'Single'),
            ('Married', 'Married'),
            ('Widowed', 'Widowed'),
            ('Divorced', 'Divorced'),
            ('Separated', 'Separated'),
        ],
        null=True,
        blank=True
    )
    gender = models.CharField(
        max_length=10,
        choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
        null=True,
        blank=True
    )
    tin = models.CharField("TIN", max_length=15, null=True, blank=True)
    gsis_id = models.CharField("GSIS ID", max_length=30, null=True, blank=True)
    pagibig_id = models.CharField("PAG-IBIG ID", max_length=30, null=True, blank=True)
    philhealth_id = models.CharField("PhilHealth ID", max_length=30, null=True, blank=True)
    sss_id = models.CharField("SSS ID", max_length=30, null=True, blank=True)

    # Employment Metadata
    jo_date_hired = models.DateField(null=True, blank=True)
    reg_date_hired = models.DateField(null=True, blank=True)
    status_of_appointment = models.CharField(max_length=100, null=True, blank=True)
    position_title = models.CharField(max_length=100, null=True, blank=True)
    salary_grade = models.CharField(max_length=10, null=True, blank=True)
    step_increment = models.PositiveIntegerField(null=True, blank=True)

    slug = models.SlugField(default='', blank=True)

    # Employment Info
    EMPLOYMENT_TYPE_CHOICES = [
        ('', "---select one---"),
        ('REG', "Regular Employee"),
        ('CT', "Co-Terminus Employee"),
        ('JO', "Job Order Employee"),
    ]
    employment_type = models.CharField(
        max_length=3,
        choices=EMPLOYMENT_TYPE_CHOICES,
        default='',
        blank=True
    )
    reg_or_ct_salary = models.ForeignKey(
        'salaries.RegOrCT_Salary',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    jo_salary = models.ForeignKey(
        'salaries.JO_Salary',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Department Assignment
    plantilla = models.ForeignKey(
        Plantilla,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    assigned_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    assigned_department_memo = models.ImageField(
        upload_to=temp_memo_path,
        blank=True,
        null=True,
        verbose_name="Memo Image"
    )

    def __str__(self):
        return f"{self.user.username}"

    def get_salary(self):
        if self.employment_type in ['REG', 'CT']:
            return self.reg_or_ct_salary.amount if self.reg_or_ct_salary else 0
        elif self.employment_type == 'JO':
            return self.jo_salary.daily_rate if self.jo_salary else 0
        return 0

    def get_absolute_url(self):
        return reverse('profile', kwargs={'username': self.user.username})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.user.username)
            slug = base_slug
            counter = 1
            while EmployeeProfile.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        super().save(*args, **kwargs)
        logger.info("EmployeeProfile saved.")

        # Resize only the profile image, not the memo
        resize_image(self.profile_image)

        # Rename memo if it exists making sure it uses the new assiged department name
        normalized_memo = normalize_department_memo(self)
        if normalized_memo:
            super().save(update_fields=['assigned_department_memo'])


class CitizenProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contact_number = models.CharField(
        max_length=11,
        validators=[MinLengthValidator(10)],
        null=True,
        blank=False,
        verbose_name="Contact Number"
    )
    address = models.CharField(max_length=255, null=True, blank=False)
    slug = models.SlugField(default='', blank=True)
    social_auth = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username}"

    def get_absolute_url(self):
        return reverse('profile', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.user.username)
            slug = base_slug
            counter = 1
            while CitizenProfile.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
        logger.info("CitizenProfile saved.")


class ProfileEditLog(models.Model):
    PROFILE_TYPE_CHOICES = [
        ('employee', 'Employee'),
        ('citizen', 'Citizen'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='edited_profile_logs',
        help_text="User whose profile was edited"
    )
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='profile_edits_made',
        help_text="Admin/HR/staff who made the change"
    )
    profile_type = models.CharField(
        max_length=10,
        choices=PROFILE_TYPE_CHOICES
    )
    section = models.CharField(
        max_length=50,
        help_text="Section of the profile edited (e.g., HR Fields, Basic Info)"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, help_text="Optional note or reason for the update")

    def __str__(self):
        return f"{self.edited_by} edited {self.user}'s {self.profile_type} profile on {self.timestamp:%Y-%m-%d %H:%M}"
