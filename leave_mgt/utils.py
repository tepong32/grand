from collections import defaultdict
from django.utils import timezone

def calculate_yearly_leave_usage(leave_requests):
    """
    Calculate the total leave taken, average leave per month, and SL vs VL usage for the current year.
    :param leave_requests: QuerySet of leave requests
    :return: Dictionary with total leave taken, average leave per month, and SL vs VL usage
    """
    current_year = timezone.now().year
    total_days = 0
    leave_per_month = defaultdict(int)
    sl_vs_vl = {'SL': 0, 'VL': 0}

    for req in leave_requests.filter(status='APPROVED', start_date__year=current_year):
        total_days += req.number_of_days
        month = req.start_date.month
        leave_per_month[month] += req.number_of_days

        if req.leave_type in sl_vs_vl:
            sl_vs_vl[req.leave_type] += req.number_of_days

    # Compute average across months with at least one leave
    months_used = len(leave_per_month)
    average_per_month = round(total_days / months_used, 2) if months_used else 0

    return {
        'total_leave_taken': total_days,
        'average_leave_per_month': average_per_month,
        'sl_vs_vl_usage': sl_vs_vl
    }
