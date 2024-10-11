from apscheduler.schedulers.background import BackgroundScheduler
from django.db import transaction
from .models import LeaveCredits  # Import the class, not the method since we made it a '@classmethod'

logger = logging.getLogger(__LeaveUpdateLogger__)

def start_scheduler():
    scheduler = BackgroundScheduler()

    # Schedule for the 1st of the month
    scheduler.add_job(LeaveCredits.update_leave_credits, 'cron', day=1, hour=0, minute=0)

    # Schedule for the 2nd of the month
    scheduler.add_job(LeaveCredits.update_leave_credits, 'cron', day=2, hour=0, minute=0) 

    scheduler.start()


@transaction.atomic  # Optional: Wrap in a transaction
def update_leave_credits():
    now = timezone.now()
    try:
        # 1. Reset Flag on the 2nd
        if now.day == 2:
            LeaveCredits.objects.all().update(credits_accrued_this_month=False)

        # 2. Accrue Credits on the 1st
        leave_credits = LeaveCredits.objects.filter(credits_accrued_this_month=False)
        for leave_credit in leave_credits:
            if now.day == 1:
                # ... (accrual logic) 

            if now.month == 1 and now.day == 1:
                leave_credit.carry_over_credits() 

    except Exception as e:
        # Log the error
        logger.error(f"An error occurred during leave credit update: {e}", exc_info=True)

        # Additional error handling (optional):
        # - Send email notifications to admins
        # - Retry the task later
        # - ... other actions based on your requirements