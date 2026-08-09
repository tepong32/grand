from .services.request_service import calculate_yearly_leave_usage as _calculate_yearly_leave_usage

def calculate_yearly_leave_usage(leave_requests):
    return _calculate_yearly_leave_usage(leave_requests)
