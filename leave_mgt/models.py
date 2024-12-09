from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta

from users.models import User, Profile
import logging

# Logger setup
logger = logging.getLogger(__name__)

class AccrualModel(models.Model):
    accrual_value = models.DecimalField(max_digits=4, decimal_places=2, default=1.2, help_text="This defaults to 1.2 per month.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class SL_Accrual(AccrualModel):
    class Meta:
        verbose_name = "SL Accrual"
        verbose_name_plural = "SL Accruals"
        constraints = [
            models.UniqueConstraint(fields=['id'], name='unique_sl_accrual')
        ]

class VL_Accrual(AccrualModel):
    class Meta:
        verbose_name = "VL Accrual"
        verbose_name_plural = "VL Accruals"
        constraints = [
            models.UniqueConstraint(fields=['id'], name='unique_vl_accrual')
        ]


class LeaveCredit(models.Model):
    employee = models.OneToOneField(Profile, on_delete=models.CASCADE)

    # Current Year Credits
    current_year_sl_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_year_vl_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    current_year_special_credits = models.DecimalField(max_digits=5, decimal_places=2, default=10)

    # Total Accumulated Credits (including carry-over)
    total_sl_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_vl_credits = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Boolean flag to check if user already accrued leave credits this month
    credits_accrued_this_month = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.employee.user.get_full_name()}'s Leave Credits" 

    # def get_total_special_leaves_taken(self):
    #     return SpecialLeaves.objects.filter(leave_credits=self).count()

    # def get_total_special_leaves_days(self):
    #     return SpecialLeaves.objects.filter(leave_credits=self).aggregate(total_days=models.Sum('number_of_days'))['total_days'] or 0

    def carry_over_credits(self):
        """Carries over unused SL credits from the current year to total, 
        resets current year credits, and handles limits if necessary."""
        now = timezone.now()

        # Only carry over if it's the beginning of a new year
        if now.month == 1 and now.day == 1: 
            # Example: Add a portion (e.g., 50%) of unused current year SL
            self.total_sl_credits += self.current_year_sl_credits  

            # Add unused current year VL with a max carry-over of 20
            self.total_vl_credits += min(self.current_year_vl_credits, 20)

            # Reset current year credits 
            self.current_year_sl_credits = 0
            self.current_year_vl_credits = 0
            # Reset at the start of the year
            self.credits_accrued_this_month = False 
            self.save()
            # Log the carry-over event so users can check if there are missed carry-over events
            LeaveCreditLog.objects.create(action_type='Yearly Carry Over', leave_credits=self)

    def accrue_leave_credits(self):
        """Accrues leave credits for the employee."""
        # Retrieve accrual values from the database or use defaults
        try:
            sl_accrual = SL_Accrual.objects.first()  
            vl_accrual = VL_Accrual.objects.first()  
            DEFAULT_SL_ACCRUAL = sl_accrual.accrual_value if sl_accrual else 1.2
            DEFAULT_VL_ACCRUAL = vl_accrual.accrual_value if vl_accrual else 1.2

        except Exception as e:
            DEFAULT_SL_ACCRUAL = 1.2
            DEFAULT_VL_ACCRUAL = 1.2

        # Update leave credits with the accrued values
        self.current_year_sl_credits += DEFAULT_SL_ACCRUAL
        self.current_year_vl_credits += DEFAULT_VL_ACCRUAL
        self.credits_accrued_this_month = True # set this to True so update_leave_credits on day 2 will turn it to False afterwards
        self.save()

        # Log the accrual event
        LeaveCreditLog.objects.create(action_type='Monthly Accrual', leave_credits=self)

    @classmethod
    def update_leave_credits(cls):
        """
        Handles both monthly leave credit updates and annual carry-over.
        This method can be called from the cron job.
        """
        try:
            # Reset Flag on the 2nd
            if timezone.now().day == 2:
                cls.objects.all().update(credits_accrued_this_month=False)

            # Accrue Credits on the 1st
            if timezone.now().day == 1:
                leave_credits = cls.objects.filter(credits_accrued_this_month=False)
                for leave_credit in leave_credits:
                    leave_credit.accrue_leave_credits()

            # Annual Carry-over 
            if timezone.now().month == 1 and timezone.now().day == 1:
                for leave_credit in cls.objects.all():
                    leave_credit.carry_over_credits()

        except Exception as e:
            logger.error(f"An error occurred during leave credit update: {e}", exc_info=True)
            # Additional error handling (optional):
            # - Send email notifications to admins
            # - Retry the task later
            # - ... other actions based on your requirements

    @classmethod
    def get_credit_logs(cls, employee):
        """Retrieve all leave credit logs for a specific employee."""
        return employee.logs.all()

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
        ordering = ['-date_filed'] # setting default ordering for LeaveRequest instances

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

    def save(self, *args, **kwargs):
        if not self.pk:  # Only calculate number_of_days when creating a new record
            self.number_of_days = self.calculate_number_of_days()

        old_status = None
        if self.pk:  # This check ensures we're dealing with an update
            old_instance = LeaveRequest.objects.get(pk=self.pk)
            old_status = old_instance.status

        super().save(*args, **kwargs)

        # Update leave credits only if the status changes to APPROVED
        if self.status == 'APPROVED' and old_status != 'APPROVED':
            if self.leave_type == 'SL':
                self.employee.current_year_sl_credits -= self.number_of_days
            elif self.leave_type == 'VL':
                self.employee.current_year_vl_credits -= self.number_of_days
            self.employee.save()  # Save the updated leave credits
        elif old_status == 'APPROVED' and self.status != 'APPROVED':
            # Revert leave credits if the status is changed from APPROVED to something else
            if self.leave_type == 'SL':
                self.employee.current_year_sl_credits += self.number_of_days
            elif self.leave_type == 'VL':
                self.employee.current_year_vl_credits += self.number_of_days
            self.employee.save()  # Save the reverted leave credits

    def calculate_number_of_days(self):
        total_days = (self.end_date - self.start_date).days + 1
        weekend_days = sum(1 for day in range(total_days) if (self.start_date + timedelta(days=day)).weekday() >= 5)
        return total_days - weekend_days

    def get_remaining_leave_credits(self):

        if self.status == 'APPROVED':
            # if the status is APPROVED, subtract the number_of_days from the current_yr_credits
            if self.leave_type == 'SL':
                return self.employee.current_year_sl_credits - self.number_of_days
            elif self.leave_type == 'VL':
                return self.employee.current_year_vl_credits - self.number_of_days
            elif self.leave_type == 'SP':
                # handle special leave credits calculation
                pass
        else:
            # if the leave is not approved (pending, cancelled &  rejected), return the current leave credits with pending leave days
            pending_leaves = Leave.objects.filter(employee=self.employee, status='PENDING', leave_type=self.leave_type)
            pending_days = sum(leave.number_of_days for leave in pending_leaves)
            if self.leave_type == 'SL':
                return f"{self.employee.current_year_sl_credits} - {pending_days} (pending)"
            elif self.leave_type == 'VL':
                return f"{self.employee.current_year_vl_credits} - {pending_days} (pending)"
            elif self.leave_type == 'SP':
                # handle special leave credits calculation
                pass

class LeaveCreditLog(models.Model): # might have circular dependency problem with LeaveCredits here
    action_date = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=50)  # e.g., 'Monthly Accrual', 'Yearly Carry Over'
    leave_credits = models.ForeignKey(LeaveCredit, on_delete=models.CASCADE, related_name='logs')

    def __str__(self):
        return f"{self.action_type} on {self.action_date}"