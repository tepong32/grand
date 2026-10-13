from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .forms import EmployeeRegisterForm
from .access import can_manage_employee_accounts
from .services.export_service import (
    export_all_employees as export_all_employees_response,
    export_department_users as export_department_users_response,
)
from .services.query_service import (
    can_access_users_directory,
    search_users_by_query,
    users_directory_context,
)

import logging

logger = logging.getLogger(__name__)


def register(request):
    # One public signup implementation, including mandatory email verification.
    return redirect("account_signup")


@login_required
def employeeRegister(request):
    if not can_manage_employee_accounts(request.user):
        raise PermissionDenied
    if request.method == "POST":
        form = EmployeeRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("users-list")
    else:
        form = EmployeeRegisterForm()
    return render(request, "auth/employee_register.html", {"form": form})


@login_required
def user_search_view(request):
    if not can_access_users_directory(request.user):
        messages.error(request, "Access Denied.")
        return redirect("home")
    context = {}
    if request.method == "GET":
        search_query = request.GET.get("q", "")
        try:
            context["search_query"] = search_query
            context["accounts"] = search_users_by_query(search_query)
        except Exception as exc:
            logger.error("Search error: %s", exc)
    return render(request, "users/user_search_results.html", context)


@login_required
def usersIndexView(request):
    try:
        context_data = users_directory_context(request.user)
    except PermissionDenied:
        messages.error(request, "Access Denied.")
        return redirect("home")

    messages.info(request, "You are seeing this page because you are a Staff/Admin or from HR Department.")
    return render(request, "users/users_index.html", context_data)


@login_required
def export_department_users(request, department, format):
    try:
        return export_department_users_response(
            department_slug=department,
            fmt=format,
            actor_user=request.user,
        )
    except PermissionDenied:
        return HttpResponseForbidden("Insufficient privileges.")
    except ValueError:
        return HttpResponseBadRequest("Unsupported format.")


@login_required
def export_all_employees(request, format):
    try:
        return export_all_employees_response(
            fmt=format,
            actor_user=request.user,
        )
    except PermissionDenied:
        return HttpResponseForbidden("Insufficient privileges.")
    except ValueError:
        return HttpResponseBadRequest("Unsupported format.")



class CustomPasswordResetView(PasswordResetView):
    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = "/password_reset/done/"

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            return response
        except Exception as e:
            logger.error("Password reset delivery failed")
            # Delivery outages must not turn this endpoint into an account probe.
            return redirect(self.success_url)
