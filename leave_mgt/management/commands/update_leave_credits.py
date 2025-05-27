from django.core.management.base import BaseCommand
from leave_mgt.models import LeaveCredit
from django.db import transaction
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Triggers the monthly accrual for LeaveCredit instances'

    def handle(self, *args, **options):
        today = datetime.today()

        # Only run on the 1st of the month
        if today.day != 1:
            logger.info("Skipped leave accrual – today is not the 1st of the month.")
            return

        with transaction.atomic():
            LeaveCredit.update_leave_credits()
            logger.info("Completed monthly leave credits accrual.")
            self.stdout.write(self.style.SUCCESS('Leave credits updated successfully.'))


'''
This file is used to manually trigger the LeaveCredit.update_leave_credits() using "python manage.py update_leave_credits"
Just in case the cron job is not triggering, manual use of this command is our fallback.
'''