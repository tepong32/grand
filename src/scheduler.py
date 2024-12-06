from apscheduler.schedulers.background import BackgroundScheduler
from django.db import transaction
import logging


# Set the logging level to INFO, DEBUG, WARNING or ERROR
logging.basicConfig(level=logging.INFO)

# name/indicator for the logs in app.log?
logger = logging.getLogger('LeaveUpdateLogger')

def start_scheduler():
    from leave_mgt.models import LeaveCredit  # Import the class, not the method since we made it a '@classmethod'
    scheduler = BackgroundScheduler()

    # Schedule for the 1st of the month
    scheduler.add_job(LeaveCredit.update_leave_credits, 'cron', day=1, hour=0, minute=0)

    # Schedule for the 2nd of the month
    scheduler.add_job(reset_credits_accrued_flag, 'cron', day=2, hour=0, minute=0)

    scheduler.start()


@transaction.atomic
def reset_credits_accrued_flag():
    '''
        Setting this attr back to False after on the 2nd day.
        Fallback setting to make sure accrual only triggers once on every 1st of the month.
    '''
    LeaveCredit.objects.update(credits_accrued_this_month=False)