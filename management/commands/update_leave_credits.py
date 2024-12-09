from django.core.management.base import BaseCommand
from leave_mgt.models import LeaveCredit
from django.db import transaction

class Command(BaseCommand):
    help = 'Update leave credits and reset accrued flag'

    def handle(self, *args, **kwargs):
        self.update_leave_credits()
        self.reset_credits_accrued_flag()

    @transaction.atomic
    def update_leave_credits(self):
        # Call the method to update leave credits
        LeaveCredit.update_leave_credits()

    @transaction.atomic
    def reset_credits_accrued_flag(self):
        # Reset the flag
        LeaveCredit.objects.update(credits_accrued_this_month=False)