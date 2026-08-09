from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from leave_mgt.cron import update_leave_credits_from_cronPy
from leave_mgt.models import LeaveCredit, LeaveRequest
from leave_mgt.services.request_service import calculate_request_days, has_request_conflict
from profiles.models import EmployeeProfile


class LeaveManagementServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='testpass123'
        )
        self.profile = EmployeeProfile.objects.get(user=self.user)
        self.profile.contact_number = '09123456789'
        self.profile.save()
        self.credits = LeaveCredit.objects.get(employee=self.profile)
        self.credits.current_year_sl_credits = 10
        self.credits.current_year_vl_credits = 10
        self.credits.save()

    def test_calculate_request_days_excludes_weekends(self):
        start = date(2026, 8, 2)  # Monday
        end = date(2026, 8, 8)    # Sunday
        self.assertEqual(calculate_request_days(start, end), 5)

    def test_request_credit_transition_reverts_and_reapplies_on_update(self):
        request = LeaveRequest.objects.create(
            employee=self.credits,
            leave_type='SL',
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 4),
            status='PENDING'
        )
        request.status = 'APPROVED'
        request.save()
        self.credits.refresh_from_db()
        self.assertEqual(self.credits.current_year_sl_credits, 8)

        request.end_date = date(2026, 8, 6)
        request.save()
        self.credits.refresh_from_db()
        self.assertEqual(self.credits.current_year_sl_credits, 6)

        request.status = 'CANCELLED'
        request.save()
        self.credits.refresh_from_db()
        self.assertEqual(self.credits.current_year_sl_credits, 10)

    def test_overlapping_requests_are_detected(self):
        LeaveRequest.objects.create(
            employee=self.credits,
            leave_type='SL',
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 11),
            status='APPROVED'
        )
        self.assertTrue(has_request_conflict(self.credits, date(2026, 8, 11), date(2026, 8, 12)))
        self.assertFalse(has_request_conflict(self.credits, date(2026, 8, 12), date(2026, 8, 12)))


class LeaveManagementRegressionTests(TestCase):
    def test_leave_credit_alias_still_exists(self):
        from leave_mgt.models import LeaveCredits

        self.assertIs(LeaveCredits, LeaveCredit)

    def test_update_leave_credits_cron_path_still_runs(self):
        update_leave_credits_from_cronPy()

    def test_management_command_runs(self):
        output = StringIO()
        call_command("update_leave_credits", stdout=output)
        self.assertIn("Leave credits updated successfully.", output.getvalue())
