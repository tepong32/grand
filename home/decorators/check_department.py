# decorators/check_department.py
from functools import wraps
from django.shortcuts import redirect

def department_required(*allowed_departments):
    """
    Restrict access to users of specific departments.
    Redirects to unauthorized page if access is denied.

    Usage:
        @department_required("HR", "Accounting Office")
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            try:
                department = request.user.employeeprofile.department
                if department and department.name in allowed_departments:
                    return view_func(request, *args, **kwargs)
            except AttributeError:
                pass
            return redirect('unauthorized_access')  # 👈 friendly fallback
        return _wrapped_view
    return decorator
