from django.db import models
from django.utils import timezone

from users.models import User, Profile

class LeaveCredits(models.Model):
    employee = models.OneToOneField(Profile, on_delete=models.CASCADE)

    # Current Year Credits
    current_year_sl_credits = models.FloatField(default=0)
    current_year_vl_credits = models.FloatField(default=0)
    speacial_leaves_taken = models.FloatField(default=0)

    # Total Accumulated Credits (including carry-over)
    total_sl_credits = models.FloatField(default=0)
    total_vl_credits = models.FloatField(default=0)

    # Boolean flag to check if user already accrued leave credits this month
    credits_accrued_this_month = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.employee.user.get_full_name()}'s Leave Credits" 

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

        # 1. Reset Flag on the 2nd
        if now.day == 2:
            cls.objects.all().update(credits_accrued_this_month=False)

        # 2. Accrue Credits on the 1st (only if not already accrued)
        leave_credits = cls.objects.filter(credits_accrued_this_month=False)
        for leave_credit in leave_credits:
            with transaction.atomic():
                # Monthly Leave Accrual
                # why not make the value dynamic so it can be adjusted on the admin interface?
                if now.day == 1:
                    # Get accrual values from settings (or provide defaults: 1.2 in this case)
                    sl_accrual = getattr(settings, 'MONTHLY_SL_ACCRUAL', 1.2) 
                    vl_accrual = getattr(settings, 'MONTHLY_VL_ACCRUAL', 1.2)

                    leave_credit.current_year_sl_credits += sl_accrual
                    leave_credit.current_year_vl_credits += vl_accrual

                    leave_credit.credits_accrued_this_month = True
                    leave_credit.save()

                # Annual Carry-over 
                if now.month == 1 and now.day == 1:
                    leave_credit.carry_over_credits()



