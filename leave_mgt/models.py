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
            # Example: Add a portion (e.g., 50%) of unused current year SL       ##### modify this logic: vl=max+10, sl=nolimit
            self.total_sl_credits += self.current_year_sl_credits  

            # Reset current year credits 
            self.current_year_sl_credits = 0
            self.current_year_vl_credits = 0

            self.save()
