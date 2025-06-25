from django.shortcuts import redirect
from functools import wraps

def mswd_required(view_func):
    # Checks if the logged-in user is an MSWD staff by department slug.
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect('login')  # or your public login page

        employee = getattr(user, 'employeeprofile', None)
        if employee and employee.assigned_department and employee.assigned_department.slug == 'mswd':
            return view_func(request, *args, **kwargs)
        
        return redirect('home')  # fallback if not MSWD
    return wrapper

