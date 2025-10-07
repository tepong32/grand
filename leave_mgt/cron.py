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
        logger.info("leave_mgt CronJob: update_leave_credits_from_cronPy tiggered.")

'''
This file is for the crontab.CRONJOBS[] in settings.py file
This works using "python manage.py crontab add"
Just facing issues with SECRET_KEY env var so I set it to hard-coded value for now

'''