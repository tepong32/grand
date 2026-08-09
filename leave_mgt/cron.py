from django.db import transaction
from leave_mgt.models import LeaveCredit, SL_Accrual, VL_Accrual
from .services.cron_service import run_leave_credit_cron_update
import logging

# Logger setup
logger = logging.getLogger(__name__)

def update_leave_credits_from_cronPy():
    with transaction.atomic():
        run_leave_credit_cron_update(LeaveCredit, SL_Accrual, VL_Accrual)
        logger.info("leave_mgt CronJob: update_leave_credits_from_cronPy tiggered.")

'''
This file is for the crontab.CRONJOBS[] in settings.py file
This works using "python manage.py crontab add"
Just facing issues with SECRET_KEY env var so I set it to hard-coded value for now

'''
