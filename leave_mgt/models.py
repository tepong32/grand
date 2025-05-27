from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
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

    @classmethod
    def reset_accrual_flags(cls):
        """
        Resets the credits_accrued_this_month flags for all leave credits.
        This can be called on a scheduled basis.
        """
        logger.info("Resetting credits_accrued_this_month flags to False.")
        cls.objects.all().update(credits_accrued_this_month=False)
        logger.info("Reset monthly accrual flag to False.")

    @classmethod
    def accrue_monthly_leave_credits(cls):
        """
        Accrues leave credits for all employees who haven't accrued credits this month.
        This can be called on a scheduled basis.
        """
        leave_credits = cls.objects.filter(credits_accrued_this_month=False)
        if leave_credits.exists():
            for leave_credit in leave_credits:
                leave_credit.accrue_leave_credits()  # This will call the instance method
                leave_credit.save()  # Save changes to the database
            logger.info("Accrued monthly leave credits successfully.")
        else:
            logger.warning("All leave credits have already been accrued for this month. No action taken.")

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

        # Add unused current year VL with a max carry-over of 20. CHANGE THIS IF YOU WANT TO CARRY OVER MORE THAN 20.
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
        This can be called on a scheduled basis.
        """
        for leave_credit in cls.objects.all():
            leave_credit.carry_over_credits()
            leave_credit.save()  # Save changes to the database
        logger.info("carry_over_unused_credits() triggered. \nCarried over unused leave credits.")
    
    @classmethod
    def get_accrual_value(cls, accrual_model, default_value):
        """
        Fetches the accrual value from the model or returns a default value if not found.
        """
        try:
            accrual = accrual_model.objects.first()
            return accrual.accrual_value if accrual else default_value
        except Exception as e:
            logger.error(f"Error fetching {accrual_model.__name__}: {e}")
            return default_value

    @classmethod
    def accrue_all_leave_credits(cls):
        """
        Accrues leave credits based on the defined accrual models or a default value.
        """
        # Log the start of the accrual process
        logger.info("Starting monthly leave credit accrual...")

        with transaction.atomic():
            # Default accrual value
            default_sl_accrual = Decimal(1.2)
            default_vl_accrual = Decimal(1.2)

            # Get SL and VL Accrual values
            sl_accrual_value = cls.get_accrual_value(SL_Accrual, default_sl_accrual)
            vl_accrual_value = cls.get_accrual_value(VL_Accrual, default_vl_accrual)

            # Iterate over all LeaveCredit instances
            leave_credits = cls.objects.filter(credits_accrued_this_month=False)
            for leave_credit in leave_credits:
                logger.info(f"Processing leave credits for {leave_credit.employee.user.get_full_name()}")
                # Update credits for each instance
                leave_credit.current_year_sl_credits += sl_accrual_value
                leave_credit.current_year_vl_credits += vl_accrual_value
                leave_credit.credits_accrued_this_month = True
                leave_credit.save()  # Save changes to the database
                

                # Log the accrual
                LeaveCreditLog.objects.create(action_type='Monthly credit accruals', leave_credits=leave_credit)
                logger.info(f"Accrued {sl_accrual_value:.1f} sick leave and {vl_accrual_value:.1f} vacation leave credits for {leave_credit.employee.user.get_full_name()}.") #':.1f' format specifier ensures that the output is formatted as a floating-point number with one decimal place.
    
    

    @classmethod
    def update_leave_credits(cls):
        try:
            logger.info("Updating leave credits...")

            # Reset accrual flags every month (probably 1st day, too)
            cls.reset_accrual_flags()

            # Only accrue leave credits on the 1st day of the month
            if timezone.now().day == 1:
                cls.accrue_all_leave_credits()

            # Annual Carry-over on January 1st
            if timezone.now().month == 1 and timezone.now().day == 1:
                cls.carry_over_unused_credits()
            else:
                logger.info("class method: Skipped accruals - not the 1st day of the month.")

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
                    # handle special leave credits calculation
                    pass

class LeaveCreditLog(models.Model): # might have circular dependency problem with LeaveCredits here
    action_date = models.DateTimeField(auto_now_add=True)
    action_type = models.CharField(max_length=50)  # e.g., 'Monthly Accrual', 'Yearly Carry Over'
    leave_credits = models.ForeignKey(LeaveCredit, on_delete=models.CASCADE, related_name='logs')

    def __str__(self):
        return f"{self.action_type} completed."