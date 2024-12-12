from users.models import User, Profile
from .models import LeaveCredit, LeaveRequest, LeaveCreditLog
from django.core.paginator import Paginator
from django.utils import timezone


def dashboard_context(request):
    """
    Universal context for Dashboard Widget
    """
    if request.user.is_authenticated:
        user = request.user
        # Fetch the user-specific data you need
        leave_credits = LeaveCredit.objects.get(employee=user.profile)
        cy_remaining_sl = leave_credits.current_year_sl_credits
        cy_remaining_vl = leave_credits.current_year_vl_credits
        pending_leaves = LeaveRequest.objects.filter(employee=leave_credits, status='PENDING') # assigning variable to all instances of pending leaves for us
        pending_leaves_count = sum(leave.number_of_days for leave in pending_leaves)	# to get their number_of_days total count
        approved_leaves = LeaveRequest.objects.filter(employee=leave_credits, status='APPROVED') # assigning variable to all instances of approved leaves for us
        approved_leave_count = sum(leave.number_of_days for leave in approved_leaves)	# to get their number_of_days total count

        # Get the current year
        current_year = timezone.now().year
        # Get the count of approved leave requests for the current year
        current_yr_leave_usage = get_leave_usage(leave_credits, current_year)
        accrual_logs = LeaveCreditLog.objects.filter(leave_credits=leave_credits).order_by('-action_date')

        # For filtering the LeaveRequests per status:
        # Get the status filter from the GET request
        status_filter = request.GET.get('status', None)
        leave_requests = LeaveRequest.objects.filter(employee=leave_credits)
        # Apply the filter if a status is specified
        if status_filter:
            leave_requests = leave_requests.filter(status=status_filter)

        # Paginate the data
        page_size = 10  # Number of items per page
        page_number = request.GET.get('page', 1)  # Get the current page number

        paginator_accrual_logs = Paginator(accrual_logs, page_size)
        paginator_approved_leaves = Paginator(approved_leaves, page_size)
        paginator_leave_requests = Paginator(leave_requests, page_size)
        paginator_pending_leaves = Paginator(pending_leaves, page_size)

        page_accrual_logs = paginator_accrual_logs.get_page(page_number)
        page_approved_leaves = paginator_approved_leaves.get_page(page_number)
        page_leave_requests = paginator_leave_requests.get_page(page_number)
        page_pending_leaves = paginator_pending_leaves.get_page(page_number)

        # Misc Global Context
        server_time = timezone.now()

        return {
            'accrual_logs': page_accrual_logs,
            'approved_leaves': page_approved_leaves,
            'approved_leave_count': approved_leave_count,

            'current_year': current_year,
            'current_yr_leave_usage': current_yr_leave_usage,
            'cy_sl': cy_remaining_sl,
            'cy_vl': cy_remaining_vl,
            'leave_credits': leave_credits,
            'leave_requests': page_leave_requests,

            'pending_leaves': page_pending_leaves,
            'pending_leaves_count': pending_leaves_count,

            'server_time': server_time,
        }
    return {}


def get_leave_usage(leave_credits, year):
    return LeaveRequest.objects.filter(
        employee=leave_credits,
        status='APPROVED',
        start_date__year=year
    ).count()