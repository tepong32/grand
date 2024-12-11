from django.core.management.base import BaseCommand
from leave_mgt.models import LeaveCredit
from django.db import transaction

import logging
# Logger setup
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Triggers the monthly accrual for LeaveCredit instances.'

    def handle(self, *args, **kwargs):
        self.update_leave_credits()
        self.accrue_leave_credits()
        self.carry_over_credits()

    @transaction.atomic
    def accrue_leave_credits(self):
        # Call the method to update leave credits
        LeaveCredit.accrue_leave_credits()
        logger.info(f"Completed monthly leave credits accruals.")

    @transaction.atomic
    def carry_over_credits(self):
        # Call the method to update leave credits
        LeaveCredit.carry_over_credits()
        logger.info(f"Completed Carry-over of remaining credits from previous year.")

'''
This file is used to manually trigger the LeaveCredit.update_leave_credits() using manage.py
Just in case the cron job is not triggering, manual use of this command is our fallback.
'''