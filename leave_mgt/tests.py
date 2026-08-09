from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from leave_mgt.cron import update_leave_credits_from_cronPy
from leave_mgt.models import LeaveCredit


class LeaveManagementRegressionTests(TestCase):
    def test_leave_credit_alias_still_exists(self):
        from leave_mgt.models import LeaveCredits

        self.assertIs(LeaveCredits, LeaveCredit)

    def test_update_leave_credits_cron_path_still_runs(self):
        # no leave-credit rows required; method should execute without side effects.
        update_leave_credits_from_cronPy()

    def test_management_command_runs(self):
        output = StringIO()
        call_command("update_leave_credits", stdout=output)
        self.assertIn("Leave credits updated successfully.", output.getvalue())
