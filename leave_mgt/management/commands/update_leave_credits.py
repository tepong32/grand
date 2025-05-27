from django.core.management.base import BaseCommand
from leave_mgt.models import LeaveCredit
from django.db import transaction
from datetime import datetime
import logging
### this is important for django-crontab to properly read django settings and avoid SECRET_KEY not set error ###
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.settings')


logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Triggers the monthly accrual for LeaveCredit instances'

    def handle(self, *args, **options):
        today = datetime.today()

        with transaction.atomic():
            LeaveCredit.update_leave_credits()
            logger.info("Completed monthly leave credits accrual. - mgt commannd")
            self.stdout.write(self.style.SUCCESS('Leave credits updated successfully.'))
