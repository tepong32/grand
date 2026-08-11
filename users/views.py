from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from .forms import UserRegisterForm
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
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    return render(request, "auth/register.html", {"form": form})


@login_required
def employeeRegister(request):
    if not can_access_users_directory(request.user):
        messages.error(request, "Access Denied.")
        return redirect("home")
    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
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
            logger.info("Password reset email sent to: %s", form.cleaned_data["email"])
            return response
        except Exception as e:
            logger.error("Failed to send password reset email to %s: %s", form.cleaned_data["email"], str(e))
            form.add_error(
                None,
                _("There was an error sending the password reset email. Please try again later.")
            )
            return self.form_invalid(form)
