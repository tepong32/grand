from django.core.management.base import BaseCommand
from leave_mgt.models import LeaveCredit
from django.db import transaction
import logging

# Logger setup
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Triggers the monthly accrual for LeaveCredit instances.'

    def handle(self, *args, **kwargs):
        try:
            logger.info("Starting leave credits update process...")
            
            # Ensure operations are atomic
            with transaction.atomic():
                LeaveCredit.update_leave_credits()
            
            logger.info("Leave credits update completed successfully.")
        except Exception as e:
            logger.error(f"Error while updating leave credits: {e}", exc_info=True)


'''
This file is used to manually trigger the LeaveCredit.update_leave_credits() using "python manage.py update_leave_credits"
Just in case the cron job is not triggering, manual use of this command is our fallback.
'''