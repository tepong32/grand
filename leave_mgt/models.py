from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
import logging

from profiles.models import EmployeeProfile


# Logger setup
logger = logging.getLogger(__name__)


class AccrualModel(models.Model):
    accrual_value = models.DecimalField(max_digits=4, decimal_places=2, default=1.2, help_text="This defaults to 1.2 per month.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SL_Accrual(AccrualModel):
    '''
    Assign values here if the default (1.2) does not fit your needs.
    Useful if the changes will be made in the admin UI instead of the codebase.
    '''

    class Meta:
        verbose_name = "SL Accrual"
        verbose_name_plural = "SL Accruals"
        constraints = [
            models.UniqueConstraint(fields=['id'], name='unique_sl_accrual')
        ]


class VL_Accrual(AccrualModel):
    '''
    Assign values here if the default (1.2) does not fit your needs.
    Useful if the changes will be made in the admin UI instead of the codebase.
    '''

    class Meta:
        verbose_name = "VL Accrual"
        verbose_name_plural = "VL Accruals"
        constraints = [
            models.UniqueConstraint(fields=['id'], name='unique_vl_accrual')
        ]


class LeaveCredit(models.Model):
    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE)

    # Current Year Credits
    current_year_sl_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_year_vl_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_year_special_credits = models.DecimalField(max_digits=5, decimal_places=2, default=10) # not being handled yet

    # Total Accumulated Credits (including carry-over)
    sl_credits_from_prev_yr = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    vl_credits_from_prev_yr = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Boolean flag to check if user already accrued leave credits this month
    credits_accrued_this_month = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.employee.user.get_full_name()}'s Leave Credits" 

    @classmethod
    def reset_accrual_flags(cls):
        """
        Resets the credits_accrued_this_month flags for all leave credits.
        """
        from .services.credit_service import reset_accrual_flags

        logger.info("Resetting credits_accrued_this_month flags to False.")
        reset_count = reset_accrual_flags(cls)
        logger.info("Reset monthly accrual flag to False for %s rows.", reset_count)
        return reset_count

    def carry_over_credits(self):
        """
        Carries over un-used Leave credits from the current year to credits_from_prev_yr.
        """
        self.sl_credits_from_prev_yr += self.current_year_sl_credits
        # Add unused current year VL with a max carry-over of 20.
        self.vl_credits_from_prev_yr += min(self.current_year_vl_credits, 20)

        # Reset current year credits after transferring
        self.current_year_sl_credits = 0
        self.current_year_vl_credits = 0
        self.save()

        # Log the carry-over event so users can check if there are missed carry-over events
        LeaveCreditLog.objects.create(action_type='Yearly Carry Over', leave_credits=self)

    @classmethod
    def carry_over_unused_credits(cls):
        """
        Carries over unused leave credits for all employees.
        """
        from .services.credit_service import carry_over_unused_credits

        count = carry_over_unused_credits(cls)
        logger.info("carry_over_unused_credits() triggered. Carried over unused credits for %s employees.", count)
        return count

    @classmethod
    def get_accrual_value(cls, accrual_model, default_value):
        """
        Fetches the accrual value from the model or returns a default value if not found.
        """
        from .services.credit_service import get_accrual_value

        return get_accrual_value(accrual_model, default_value)

    @classmethod
    def accrue_all_leave_credits(cls):
        """
        Accrues leave credits based on the defined accrual models or a default value.
        """
        from .services.credit_service import accrue_all_leave_credits

        logger.info("Starting monthly leave credit accrual...")
        return accrue_all_leave_credits(cls, SL_Accrual, VL_Accrual)

    @classmethod
    def update_leave_credits(cls):
        """
        Scheduled/manual refresh that handles monthly accruals and annual carry-over.
        """
        from .services.credit_service import update_leave_credits

        logger.info("update_leave_credits(cls): Updating leave credits...")
        # Keep behavior aligned with previous implementation: carry over only on Jan 1st.
        return update_leave_credits(cls, SL_Accrual, VL_Accrual, from_cron=False)


def leave_form_directory_path(instance, filename):
    # Leave > LeaveCredits > Profile > User > username
    username = instance.employee.employee.user.username
    return 'users/{}/leaveForms/{}'.format(username, filename)


class LeaveRequest(models.Model):
    LEAVE_TYPES = [
        ('SL', 'Sick Leave'),
        ('VL', 'Vacation Leave'),
        ('SP', 'Special Leave'),
    ]

    STATUS_OPTIONS = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]

    employee = models.ForeignKey(LeaveCredit, on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=2, choices=LEAVE_TYPES)
    date_filed = models.DateField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=False)
    end_date = models.DateField(null=True, blank=False)
    number_of_days = models.IntegerField(null=True, blank=True) # prevent manual editing
    status = models.CharField(max_length=10, choices=STATUS_OPTIONS, default='PENDING')
    notes = models.TextField(null=True, blank=True)
    form_photo = models.ImageField(null=True, blank=True, upload_to=leave_form_directory_path, verbose_name="Form Photo (w/ Signatures): ")

    class Meta:
        ordering = ['-date_filed']

    def __str__(self):
        return f"{self.employee.employee.user.get_full_name()} - {self.leave_type} - {self.date_filed}"

    def get_absolute_url(self):
        return reverse('leave_detail', kwargs={'pk': self.pk})

    def clean(self):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("Start date cannot be greater than end date.")
        else:
            raise ValidationError("Both start date and end date are required.")

        if self.employee:
            from .services.request_service import has_request_conflict
            if self.status != 'CANCELLED' and has_request_conflict(
                self.employee,
                self.start_date,
                self.end_date,
                exclude_pk=self.pk,
            ):
                raise ValidationError("A leave request already exists for this date range.")

    def save(self, *args, **kwargs):
        self.number_of_days = self.calculate_number_of_days()

        old_status = None
        old_leave_type = None
        old_number_of_days = None

        if self.pk:
            old_instance = LeaveRequest.objects.get(pk=self.pk)
            old_status = old_instance.status
            old_leave_type = old_instance.leave_type
            old_number_of_days = old_instance.number_of_days

        with transaction.atomic():
            super().save(*args, **kwargs)

            from .services.request_service import sync_leave_credit_for_status_change
            sync_leave_credit_for_status_change(
                self,
                old_status=old_status,
                old_leave_type=old_leave_type,
                old_number_of_days=old_number_of_days,
            )

    def calculate_number_of_days(self):
        from .services.request_service import calculate_request_days
        return calculate_request_days(self.start_date, self.end_date)

    def get_remaining_leave_credits(self):
        """
        Calculates the remaining leave credits for the employee based on the leave request's status and type.
        """
        if self.status == 'APPROVED':
            if self.leave_type == 'SL':
                return self.employee.current_year_sl_credits - self.number_of_days
            elif self.leave_type == 'VL':
                return self.employee.current_year_vl_credits - self.number_of_days
        # Handle special leave credits if applicable
        else:
            pending_days = LeaveRequest.objects.filter(
                employee=self.employee,
                status='PENDING',
                leave_type=self.leave_type
            ).aggregate(total=models.Sum('number_of_days'))['total'] or 0
            if self.leave_type == 'SL':
                return f"{self.employee.current_year_sl_credits} - {pending_days} (pending)"
            elif self.leave_type == 'VL':
                return f"{self.employee.current_year_vl_credits} - {pending_days} (pending)"
            # Handle special leave credits if applicable
            elif self.leave_type == 'SP':
                return None


class LeaveCreditLog(models.Model):
    action_date = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=50)  # e.g., 'Monthly Accrual', 'Yearly Carry Over'
    leave_credits = models.ForeignKey(LeaveCredit, on_delete=models.CASCADE, related_name='logs')

    def __str__(self):
        return f"{self.action_type} completed."


# Backward-compatible alias retained for existing imports/tests.
LeaveCredits = LeaveCredit
