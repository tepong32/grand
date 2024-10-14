from django.db import models
from django.utils import timezone

from users.models import User, Profile


class AccrualModel(models.Model):
    accrual_value = models.DecimalField(max_digits=4, decimal_places=2, default=1.2)
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

class LeaveCredits(models.Model):
    employee = models.OneToOneField(Profile, on_delete=models.CASCADE)

    # Current Year Credits
    current_year_sl_credits = models.FloatField(default=0)
    current_year_vl_credits = models.FloatField(default=0)

    # Total Accumulated Credits (including carry-over)
    total_sl_credits = models.FloatField(default=0)
    total_vl_credits = models.FloatField(default=0)

    # Boolean flag to check if user already accrued leave credits this month
    credits_accrued_this_month = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.employee.user.get_full_name()}'s Leave Credits" 

    def get_total_special_leaves_taken(self):
        return SpecialLeaves.objects.filter(leave_credits=self).count()

    def get_total_special_leaves_days(self):
        return SpecialLeaves.objects.filter(leave_credits=self).aggregate(total_days=models.Sum('number_of_days'))['total_days'] or 0

    def carry_over_credits(self):
        """
        Carries over unused SL credits from the current year to total, 
        resets current year credits, and handles limits if necessary.
        """
        now = timezone.now()

        # Only carry over if it's the beginning of a new year
        if now.month == 1 and now.day == 1: 
            # Example: Add a portion (e.g., 50%) of unused current year SL
            self.total_sl_credits += self.current_year_sl_credits  

            # Add unused current year VL with a max carry-over of 10
            self.total_vl_credits += min(self.current_year_vl_credits, 10)

            # Reset current year credits 
            self.current_year_sl_credits = 0
            self.current_year_vl_credits = 0
            # Reset at the start of the year
            self.credits_accrued_this_month = False 
            self.save()

    @classmethod
    def update_leave_credits(cls):
        """
        Handles both monthly leave credit updates and annual carry-over 
        on the 1st day of each month.
        """
        now = timezone.now()
        try:
            # 1. Reset Flag on the 2nd
            if now.day == 2:
                cls.objects.all().update(credits_accrued_this_month=False)

            # 2. Accrue Credits on the 1st (only if not already accrued)
            if now.day == 1:
                leave_credits = cls.objects.filter(credits_accrued_this_month=False)
                for leave_credit in leave_credits:
                    with transaction.atomic():  # write all-or-nothing on the db
                        # Monthly Leave Accrual
                        # Retrieve accrual values from the database or use defaults
                        try:
                            sl_accrual = SL_Accrual.objects.first()  # Get the first SL_Accrual instance
                            vl_accrual = VL_Accrual.objects.first()  # Get the first VL_Accrual instance

                            # Use the accrual values if they exist, otherwise use the default value
                            DEFAULT_SL_ACCRUAL = sl_accrual.accrual_value if sl_accrual else 1.2
                            DEFAULT_VL_ACCRUAL = vl_accrual.accrual_value if vl_accrual else 1.2

                        except Exception as e:
                            # Fallback to default if an error occurs
                            DEFAULT_SL_ACCRUAL = 1.2
                            DEFAULT_VL_ACCRUAL = 1.2

                        # Update leave credits with the accrued values
                        leave_credit.current_year_sl_credits += DEFAULT_SL_ACCRUAL
                        leave_credit.current_year_vl_credits += DEFAULT_VL_ACCRUAL

                        leave_credit.credits_accrued_this_month = True
                        leave_credit.save()

            # Annual Carry-over 
            if now.month == 1 and now.day == 1:
                for leave_credit in cls.objects.all():
                    leave_credit.carry_over_credits()
                            
        except Exception as e:
            # Log the error
            logger.error(f"An error occurred during leave credit update: {e}", exc_info=True)

            # Additional error handling (optional):
            # - Send email notifications to admins
            # - Retry the task later
            # - ... other actions based on your requirements


class SpecialLeaves(models.Model):
    '''
    using related-name, you can use it (for testing) in python like this:
        leave_credits = LeaveCredits.objects.get(id=1)
        special_leaves = leave_credits.special_leaves.all()
    '''
    leave_credits = models.ForeignKey(LeaveCredits, on_delete=models.CASCADE, related_name='special_leaves')
    notes = models.TextField(blank=True)
    date_taken = models.DateField()
    number_of_days = models.IntegerField()

    # Add a file upload field
    # approval_document = models.FileField(upload_to='approvals/', blank=True, null=True)
    # Or, if you want to specifically handle images:
    def approval_directory_path(instance, filename):
        # file will be uploaded to MEDIA_ROOT/DP/<username>/<filename> ---check settings.py. MEDIA_ROOT=media for the exact folder/location
        return 'users/{}/leaveForms/{}'.format(instance.leavecredits.employee.username, filename)
    form_photo = models.ImageField(null=True, blank=True, upload_to=approval_directory_path, verbose_name="Form Photo (w/ Signature): ")

    def __str__(self):
        return f"Special Leave for {self.leave_credits.employee.user.get_full_name()} on {self.date_taken}"
