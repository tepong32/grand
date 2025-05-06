from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from users.models import User, EmployeeProfile
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

    # def get_total_special_leaves_taken(self):
    #     return SpecialLeaves.objects.filter(leave_credits=self).count()

    # def get_total_special_leaves_days(self):
    #     return SpecialLeaves.objects.filter(leave_credits=self).aggregate(total_days=models.Sum('number_of_days'))['total_days'] or 0

    def carry_over_credits(self):
        """
        Carries over un-used Leave credits from the current year to credits_from_prev_yr, 
        Afterwards, the current_year_xx_credits will reset to 0 and this can be basis for monetization of leave credits.
        Add logic to handle carry-over limits if necessary.
        Trigger on every Jan 1st ---date-checking logic removed
        """
        # Define logic:
        # Example: Add all of / a portion of (e.g., 50%) un-used current_year credits
        self.sl_credits_from_prev_yr += self.current_year_sl_credits  

        # Add unused current year VL with a max carry-over of 20
        self.vl_credits_from_prev_yr += min(self.current_year_vl_credits, 20)

        # Reset current year credits after transferring
        self.current_year_sl_credits = 0
        self.current_year_vl_credits = 0
        self.save()
        # Log the carry-over event so users can check if there are missed carry-over events
        LeaveCreditLog.objects.create(action_type='Yearly Carry Over', leave_credits=self)

    def accrue_leave_credits(self):
        """
        Accrues leave credits based on the defined accrual models or a default value.
        """
        # Default accrual value
        default_sl_accrual = Decimal(1.2)
        default_vl_accrual = Decimal(1.2)  # Assuming the same defaults

        # Check for SL_Accrual
        try:
            sl_accrual = SL_Accrual.objects.first()  # Get the first instance or None
            if sl_accrual:
                sl_accrual_value = sl_accrual.accrual_value  # Assuming this field exists
            else:
                sl_accrual_value = default_sl_accrual
        except Exception as e:
            sl_accrual_value = default_sl_accrual  # Fallback to default on error

        # Check for VL_Accrual
        try:
            vl_accrual = VL_Accrual.objects.first()  # Get the first instance or None
            if vl_accrual:
                vl_accrual_value = vl_accrual.accrual_value  # Assuming this field exists
            else:
                vl_accrual_value = default_vl_accrual
        except Exception as e:
            vl_accrual_value = default_vl_accrual  # Fallback to default on error

        # Now you can use sl_accrual_value and vl_accrual_value for accruing credits
        self.current_year_sl_credits += sl_accrual_value
        self.current_year_vl_credits += vl_accrual_value
        self.credits_accrued_this_month = True
        self.save()  # Save the updated leave credits
        LeaveCreditLog.objects.create(action_type='Monthly credit accruals', leave_credits=self)

        # Log the accrual
        logger.info(f"Accrued {sl_accrual_value:.1f} sick leave and {vl_accrual_value:.1f} vacation leave credits.") #':.1f' format specifier ensures that the output is formatted as a floating-point number with one decimal place.

    @classmethod
    def update_leave_credits(cls):
        """
        Handles both monthly leave credit updates and annual carry-over.
        Ensures all changes are persisted to the database.
        """
        try:
            logger.info("Updating leave credits...")
    
            # Reset Flag on the 2nd
            if timezone.now().day == 2:
                logger.info("credits_accrued_this_month flags are set to True. \nResetting flags to False.")
                cls.objects.all().update(credits_accrued_this_month=False)
                logger.info("Reset monthly accrual flag to False.")
    
            # Accrue Credits on the 1st
            if timezone.now().day == 1:
                logger.info("credits_accrued_this_month flags are set to False. \nWorking on adding leave credits.")
                leave_credits = cls.objects.filter(credits_accrued_this_month=False)
                if leave_credits.exists():
                    for leave_credit in leave_credits:
                        leave_credit.accrue_leave_credits()
                        leave_credit.save()  # Save changes to the database
                    logger.info("Accrued monthly leave credits succesfully. \nSetting credits_accrued_this_month to True in preparation for Reset.")
                else:
                    logger.warning("credits_accrued_this_month flags are set to True. Leave credits have already been accrued for today. No action taken.")
    
            # Annual Carry-over
            if timezone.now().month == 1 and timezone.now().day == 1:
                for leave_credit in cls.objects.all():
                    leave_credit.carry_over_credits()
                    leave_credit.save()  # Save changes to the database
                logger.info("Carried over unused leave credits.")
    
        except Exception as e:
            logger.error(f"An error occurred during leave credit update: {e}", exc_info=True)
                # Additional error handling (optional):
                # - Send email notifications to admins
                # - Retry the task later
                # - ... other actions based on your requirements

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
        return f"{self.action_type} completed."