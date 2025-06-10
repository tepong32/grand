# decorators/check_department.py
from functools import wraps
from django.shortcuts import redirect

def department_required(*allowed_departments):
    """
    Restrict access to users of specific departments by name.
    Example:
        @department_required("Accounting Office", "HR")
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            try:
                department = request.user.employeeprofile.assigned_department
                if department and department.name in allowed_departments:
                    return view_func(request, *args, **kwargs)
            except Exception:
                pass
            return redirect('unauthorized_access')
        return _wrapped_view
    return decorator
