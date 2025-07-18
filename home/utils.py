from profiles.models import EmployeeProfile
from leave_mgt.models import LeaveRequest
from assistance.models import AssistanceRequest
# from gso.models import MaintenanceTask
# from salaries.models import PayrollBatch

def get_department_dashboard_context(department, user):
    """
    Returns extra context specific to a department's dashboard.
    Additional context can be added as the complexity of each department's dashboard grows.
    This function is designed to be extensible for future department-specific needs.
    """
    context = {}

    match department.slug:
        case "hr":
            context.update({
                "employees": EmployeeProfile.objects.all(),
                "leave_requests": LeaveRequest.objects.all()[:10],
            })
        case "gso":
            context.update({
                # "maintenance_tasks": MaintenanceTask.objects.filter(status="Pending"),
            })
        case "acctg":
            context.update({
                # "salary_batches": PayrollBatch.objects.order_by('-created_at')[:5],
            })
        case "mswd":
            context.update({
                "recent_requests": AssistanceRequest.objects.order_by('-submitted_at')[:10],
                "request_count": AssistanceRequest.objects.count(),
                "pending_count": AssistanceRequest.objects.filter(status='pending').count(),
                "review_count": AssistanceRequest.objects.filter(status='review').count(),
                "approved_count": AssistanceRequest.objects.filter(status='approved').count(),
                "denied_count": AssistanceRequest.objects.filter(status='denied').count(),
            })

    # Add more elif blocks as new departments grow in complexity

    return context
