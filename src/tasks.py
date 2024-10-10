from celery import shared_task
from django.utils import timezone
from leave_mgt.models import LeaveCredits

@shared_task
def update_leave_credits():
    """
    Handles both monthly leave credit updates and annual carry-over 
    on the 1st day of each month.
    """
    now = timezone.now()

    leave_credits = LeaveCredits.objects.all()
    for leave_credit in leave_credits:
        # Monthly Update 
        if now.day == 1:  
            leave_credit.current_year_sl_credits += 1.2
            leave_credit.current_year_vl_credits += 1.2

        # Annual Carry-over (January 1st)
        if now.month == 1 and now.day == 1:
            leave_credit.carry_over_credits()

        leave_credit.save()