from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from .models import User
from .forms import UserRegisterForm
from django.db.models import Q
import logging
from departments.models import Department
from profiles.models import EmployeeProfile


logger = logging.getLogger(__name__)

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    return render(request, 'auth/register.html', {'form': form})


def employeeRegister(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    return render(request, 'auth/employee_register.html', {'form': form})


def user_search_view(request):
    context = {}
    if request.method == "GET":
        search_query = request.GET.get("q")
        try:
            if search_query and len(search_query) > 0:
                search_results = User.objects.filter(
                    Q(username__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query)
                ).distinct()
                accounts = [(account, False) for account in search_results]
                context['accounts'] = accounts
                context['search_query'] = search_query
        except Exception as e:
            logger.error(f"Search error: {e}")
    return render(request, "users/user_search_results.html", context)


@login_required
def usersIndexView(request):
    departments = Department.objects.order_by("name")
    department_users = {
        dept.name: EmployeeProfile.objects.filter(assigned_department=dept)
        for dept in departments
    }

    if request.user.is_staff:
        messages.info(request, "You are seeing this page because you are a Staff/Admin.")
        
    context_data = {
        'users': User.objects.all().order_by('last_name', 'first_name')[:50],
        'userCount': User.objects.count(),
        'department_users': department_users,
    }
    return render(request, 'users/users_index.html', context_data)


class CustomPasswordResetView(PasswordResetView):
    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            logger.info("Password reset email sent to: %s", form.cleaned_data['email'])
            return response
        except Exception as e:
            logger.error("Failed to send password reset email to %s: %s", form.cleaned_data['email'], str(e))
            form.add_error(None, _("There was an error sending the password reset email. Please try again later."))
            return self.form_invalid(form)
