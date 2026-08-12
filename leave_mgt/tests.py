from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from departments.models import Department
from leave_mgt.cron import update_leave_credits_from_cronPy
from leave_mgt.models import LeaveCredit, LeaveCreditTransaction, LeavePolicy, LeaveRequest
from leave_mgt.services.credit_service import accrue_leave_instance, update_leave_credits
from leave_mgt.services.policy_service import apply_manual_adjustment, can_manage_leave_credits
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

    def test_half_day_is_exact_and_limited_to_one_working_day(self):
        monday = date(2026, 8, 3)
        self.assertEqual(calculate_request_days(monday, monday, 'AM'), Decimal('0.5'))
        with self.assertRaises(ValidationError):
            calculate_request_days(monday, date(2026, 8, 4), 'PM')

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

    def test_approved_leave_uses_carried_credit_first_and_reverses_exactly(self):
        self.credits.current_year_sl_credits = Decimal('2.00')
        self.credits.sl_credits_from_prev_yr = Decimal('1.00')
        self.credits.save()
        request = LeaveRequest.objects.create(
            employee=self.credits,
            leave_type='SL',
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 4),
            status='PENDING',
        )
        request.status = 'APPROVED'
        request.save()
        self.credits.refresh_from_db()
        self.assertEqual(self.credits.sl_credits_from_prev_yr, Decimal('0.00'))
        self.assertEqual(self.credits.current_year_sl_credits, Decimal('1.00'))

        deduction = LeaveCreditTransaction.objects.get(transaction_type='DEDUCTION')
        self.assertEqual(deduction.carried_delta, Decimal('-1.00'))
        self.assertEqual(deduction.current_delta, Decimal('-1.00'))

        request.status = 'CANCELLED'
        request.save()
        self.credits.refresh_from_db()
        self.assertEqual(self.credits.sl_credits_from_prev_yr, Decimal('1.00'))
        self.assertEqual(self.credits.current_year_sl_credits, Decimal('2.00'))
        self.assertTrue(hasattr(deduction, 'reversal'))

    def test_half_day_approval_deducts_half_a_credit(self):
        request = LeaveRequest.objects.create(
            employee=self.credits,
            leave_type='VL',
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 3),
            day_portion='PM',
            status='PENDING',
        )
        request.status = 'APPROVED'
        request.save()
        self.credits.refresh_from_db()
        self.assertEqual(request.number_of_days, Decimal('0.5'))
        self.assertEqual(self.credits.total_vl_credits, Decimal('9.50'))

    def test_monthly_accrual_is_idempotent_for_each_period(self):
        policy = LeavePolicy.objects.get(is_active=True)
        self.credits.current_year_sl_credits = 0
        self.credits.current_year_vl_credits = 0
        self.credits.save()

        self.assertEqual(accrue_leave_instance(self.credits, policy, date(2026, 8, 1)), 2)
        self.assertEqual(accrue_leave_instance(self.credits, policy, date(2026, 8, 15)), 0)
        self.credits.refresh_from_db()
        self.assertEqual(self.credits.current_year_sl_credits, policy.monthly_sick_accrual)
        self.assertEqual(self.credits.current_year_vl_credits, policy.monthly_vacation_accrual)
        self.assertEqual(LeaveCreditTransaction.objects.filter(transaction_type='ACCRUAL').count(), 2)

        self.assertEqual(accrue_leave_instance(self.credits, policy, date(2026, 9, 1)), 2)
        self.credits.refresh_from_db()
        self.assertEqual(
            self.credits.current_year_sl_credits,
            policy.monthly_sick_accrual * 2,
        )

    def test_january_update_is_idempotent_for_carryover_and_accrual(self):
        self.credits.current_year_sl_credits = Decimal('4.00')
        self.credits.current_year_vl_credits = Decimal('3.00')
        self.credits.current_year_special_credits = Decimal('2.00')
        self.credits.save()
        january_first = date(2027, 1, 1)

        first = update_leave_credits(from_cron=True, on_date=january_first)
        second = update_leave_credits(from_cron=True, on_date=january_first)
        self.credits.refresh_from_db()

        self.assertEqual(first['carry_over_count'], 1)
        self.assertEqual(second['carry_over_count'], 0)
        self.assertEqual(second['accrued_count'], 0)
        self.assertEqual(self.credits.sl_credits_from_prev_yr, Decimal('4.00'))
        self.assertEqual(self.credits.vl_credits_from_prev_yr, Decimal('3.00'))
        self.assertEqual(self.credits.current_year_special_credits, Decimal('10.00'))
        self.assertEqual(
            LeaveCreditTransaction.objects.filter(transaction_type='CARRYOVER').count(), 3
        )

    def test_carryover_cap_applies_to_existing_and_current_credits_together(self):
        policy = LeavePolicy.objects.get(is_active=True)
        policy.vacation_carryover_cap = Decimal('20.00')
        policy.save(update_fields=['vacation_carryover_cap'])
        self.credits.vl_credits_from_prev_yr = Decimal('15.00')
        self.credits.current_year_vl_credits = Decimal('10.00')
        self.credits.save()

        update_leave_credits(from_cron=True, on_date=date(2027, 1, 1))

        self.credits.refresh_from_db()
        self.assertEqual(self.credits.current_year_vl_credits, Decimal('1.20'))
        self.assertEqual(self.credits.vl_credits_from_prev_yr, Decimal('20.00'))
        transaction = LeaveCreditTransaction.objects.get(
            transaction_type='CARRYOVER', leave_type='VL'
        )
        self.assertEqual(transaction.current_delta, Decimal('-10.00'))
        self.assertEqual(transaction.carried_delta, Decimal('5.00'))
        self.assertEqual(transaction.amount, Decimal('-5.00'))

    def test_manual_adjustments_are_permissioned_incremented_and_audited(self):
        User = get_user_model()
        manager = User.objects.create_superuser(
            username='manager', email='manager@example.com', password='testpass123'
        )
        transaction = apply_manual_adjustment(
            leave_credit=self.credits,
            leave_type='VL',
            amount=Decimal('-0.50'),
            actor=manager,
            reason='Correct an imported balance.',
        )
        self.credits.refresh_from_db()
        self.assertEqual(self.credits.current_year_vl_credits, Decimal('9.50'))
        self.assertEqual(transaction.actor, manager)

        with self.assertRaises(ValidationError):
            apply_manual_adjustment(
                leave_credit=self.credits,
                leave_type='VL',
                amount=Decimal('0.25'),
                actor=manager,
                reason='Invalid increment.',
            )
        with self.assertRaises(PermissionDenied):
            apply_manual_adjustment(
                leave_credit=self.credits,
                leave_type='VL',
                amount=Decimal('0.50'),
                actor=self.user,
                reason='Unauthorized adjustment.',
            )

    def test_hr_department_head_can_manage_but_not_other_employees(self):
        hr = Department.objects.create(name='Human Resources', slug='hr', deptHead_or_oic=self.user)
        self.assertTrue(can_manage_leave_credits(self.user))
        hr.deptHead_or_oic = None
        hr.save()
        self.assertFalse(can_manage_leave_credits(self.user))

    def test_employee_cannot_edit_another_employees_request(self):
        User = get_user_model()
        other = User.objects.create_user(
            username='bob', email='bob@example.com', password='testpass123'
        )
        other_credit = LeaveCredit.objects.get(employee=other.employeeprofile)
        request = LeaveRequest.objects.create(
            employee=other_credit,
            leave_type='SL',
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 3),
        )
        self.client.login(username='alice', password='testpass123')
        response = self.client.get(reverse('leave_update', kwargs={'pk': request.pk}))
        self.assertEqual(response.status_code, 404)

    def test_leave_management_page_rejects_regular_employee(self):
        self.client.login(username='alice', password='testpass123')
        response = self.client.get(reverse('leave_manage'))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_activate_a_versioned_policy(self):
        User = get_user_model()
        manager = User.objects.create_superuser(
            username='policy-manager',
            email='policy-manager@example.com',
            password='testpass123',
        )
        self.client.login(username='policy-manager', password='testpass123')
        response = self.client.post(reverse('leave_manage'), {
            'action': 'policy',
            'name': 'Updated policy',
            'effective_from': '2026-09-01',
            'monthly_sick_accrual': '1.50',
            'monthly_vacation_accrual': '1.25',
            'special_leave_annual_allocation': '8.00',
            'minimum_request_increment': '0.50',
            'sick_carryover_cap': '',
            'vacation_carryover_cap': '25.00',
        })
        self.assertRedirects(response, reverse('leave_manage'))
        active = LeavePolicy.objects.get(is_active=True)
        self.assertEqual(active.name, 'Updated policy')
        self.assertEqual(active.created_by, manager)
        self.assertEqual(LeavePolicy.objects.filter(is_active=True).count(), 1)


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
