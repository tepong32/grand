from leave_mgt.models import LeaveCredit
from django.db import transaction
import logging

# Logger setup
logger = logging.getLogger(__name__)

def update_leave_credits_from_cronPy():
    help = 'Triggers the monthly accrual for LeaveCredit instances from update_leave_credits_from_cronPy().'

    # Use a transaction for accruing leave credits
    with transaction.atomic():
        LeaveCredit.update_leave_credits()  # Call the method to update leave credits
        logger.info("CronJob: update_leave_credits_from_cronPy tiggered.")

'''
This file is for the crontab.CRONJOBS[] in settings.py file
This works using crontab add.
Just facing issues with SECRET_KEY env var so I set it to hard-coded value for now.
REMEMBER to change python executable path in NC cronjobs UI. It automatically changes python3 to python3.11_bin which causes the task to not trigger.

'''