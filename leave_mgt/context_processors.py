from home.models import DownloadableForm, DepartmentContact
from .models import LeaveCredit, LeaveRequest, LeaveCreditLog
from django.core.paginator import Paginator
from django.utils import timezone


def dashboard_context(request):
    """
    Universal context for Dashboard Widget
    """
    return {
        'departments': DepartmentContact.objects.all(),
        'downloadableforms': DownloadableForm.objects.all(),
        'server_time': timezone.now(),
    }


def get_leave_usage(leave_credits, year):
    return LeaveRequest.objects.filter(
        employee=leave_credits,
        status='APPROVED',
        start_date__year=year
    ).count()