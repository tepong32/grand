from .models import LeaveCounter

def increase_max_instances(year_additional_instances, quarter_additional_instances):
    """
    A function that is used to adjust max_instances_per_year/quarter for all employees.
    (e.g.: Special Non-Working Holidays announcements)
    """
    leave_counters = LeaveCounter.objects.all()
    for leave_counter in leave_counters:
        leave_counter.max_instances_per_year += year_additional_instances
        leave_counter.max_instances_per_quarter += quarter_additional_instances
        leave_counter.save()
