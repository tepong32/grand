from users.models import User, Profile
from .models import LeaveCredits, LeaveRequest, LeaveCreditLog

from django.utils import timezone


def dashboard_context(request):
	"""
	Universal context for Dashboard Widget
	"""
	if request.user.is_authenticated:
		user = request.user
		# Fetch the user-specific data you need
		leave_credits = LeaveCredits.objects.get(employee=request.user.profile)
		cy_remaining_sl = leave_credits.current_year_sl_credits
		cy_remaining_vl = leave_credits.current_year_vl_credits
		pending_leaves = LeaveRequest.objects.filter(employee=leave_credits, status='PENDING') # assigning variable to all instances of pending leaves for us
		pending_leaves_count = sum(leave.number_of_days for leave in pending_leaves)	# to get their number_of_days total count
		approved_leaves = LeaveRequest.objects.filter(employee=leave_credits, status='APPROVED') # assigning variable to all instances of approved leaves for us
		approved_leave_count = sum(leave.number_of_days for leave in pending_leaves)	# to get their number_of_days total count

		# Get the current year
		current_year = timezone.now().year
		# Get the count of approved leave requests for the current year
		current_yr_leave_usage = get_leave_usage(leave_credits, current_year)
		accrual_logs = LeaveCreditLog.objects.filter(leave_credits=leave_credits)

		return {
			'accrual_logs': accrual_logs,
			'approved_leaves': approved_leaves,
			'approved_leave_count': approved_leave_count,

			'current_year': current_year,
			'current_yr_leave_usage': current_yr_leave_usage,
			'cy_sl': cy_remaining_sl,
			'cy_vl': cy_remaining_vl,
			'leave_credits': leave_credits,

			'pending_leaves': pending_leaves,
			'pending_leaves_count': pending_leaves_count,
		}
	return {}


def get_leave_usage(leave_credits, year):
    return LeaveRequest.objects.filter(
        employee=leave_credits,
        status='APPROVED',
        start_date__year=year
    ).count()