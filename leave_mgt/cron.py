from leave_mgt.models import LeaveCredit
from django.db import transaction

import logging
# Logger setup
logger = logging.getLogger(__name__)

def update_leave_credits_from_cronPy():
    help = 'Triggers the monthly accrual for LeaveCredit instances.'

    @transaction.atomic
    # Call the method to update leave credits
    LeaveCredit.accrue_leave_credits()
    logger.info(f"Completed monthly leave credits accruals from update_leave_credits_from_cronPy().")

    @transaction.atomic
    # Call the method to update leave credits
    LeaveCredit.carry_over_credits()
    logger.info(f"Completed Carry-over of remaining credits from previous year from update_leave_credits_from_cronPy().")


'''
This file is for the crontab.CRONJOBS[] in settings.py file
This works using crontab add.
Just facing issues with SECRET_KEY env var so I set it to hard-coded value for now.
REMEMBER to change python executable path in NC cronjobs UI. It automatically changes python3 to python3.11_bin which causes the task to not trigger.

'''