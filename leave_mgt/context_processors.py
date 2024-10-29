from users.models import User, Profile
from .models import LeaveCredits, LeaveRequest

from django.utils import timezone


def dashboard_context(request):
	"""
	Universal context for Dashboard Widget
	"""
	if request.user.is_authenticated:
		user = request.user
		# Fetch the user-specific data you need
		leave_credits = LeaveCredits.objects.get(employee=request.user.profile)
		cy_sl = leave_credits.current_year_sl_credits
		cy_vl = leave_credits.current_year_vl_credits
		pending_leaves = LeaveRequest.objects.filter(employee=leave_credits, status='PENDING')
		pending_leaves_count = sum(leave.number_of_days for leave in pending_leaves)	# of days count
		approved_leaves = LeaveRequest.objects.filter(employee=leave_credits, status='APPROVED')
		approved_leave_count = sum(leave.number_of_days for leave in pending_leaves)	# of days count

		# Get the current year
		current_year = timezone.now().year
		# Get the count of approved leave requests for the current year
		current_yr_leave_usage = get_leave_usage(leave_credits, current_year)

		return {
			'approved_leaves': approved_leaves,
			'approved_leave_count': approved_leave_count,

			'current_year': current_year,
			'current_yr_leave_usage': current_yr_leave_usage,
			'cy_sl': cy_sl,
			'cy_vl': cy_vl,
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