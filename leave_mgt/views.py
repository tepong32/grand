from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError

from django.shortcuts import render, redirect
from django.urls import reverse_lazy

from .forms import LeaveApplicationForm
from .models import LeaveRequest, LeaveCredit, LeaveCreditLog
from .services.request_service import (
    build_leave_dashboard_context,
    validate_request_payload,
    revert_leave_credit_for_deleted_request,
)
from .utils import calculate_yearly_leave_usage

from django.views.generic import (
    TemplateView,
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
    )

from django.utils import timezone

from profiles.models import EmployeeProfile


class RoleBasedTemplateMixin(UserPassesTestMixin):
    '''
        This mixin is used to determine what template to display to the user depending on roles:
        Normal user vs Superuser/Admin.
        Add more logic to test_func() as needed.
        Create separate html pages as needed.
    '''
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

    def get_template_names(self):
        if self.test_func():
            return ['leave_mgt/leave_summary_admin.html']  # template for admins
        return ['leave_mgt/leave_summary.html']            # template for normal users #########################not used atm


class MyLeaveView(LoginRequiredMixin, ListView):
    """
    View for displaying the logged-in user's leave requests and related stats.
    """
    model = LeaveRequest
    template_name = 'leave_mgt/leave_summary.html'
    ordering = ['-date_filed']
    context_object_name = 'leave_requests'  # optional: so you can just use {{ leave_requests }}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            leave_credit = self.request.user.employeeprofile.leavecredit
            status_filter = self.request.GET.get('status') or None
            context.update(build_leave_dashboard_context(leave_credit, status_filter=status_filter))

        except (EmployeeProfile.DoesNotExist, LeaveCredit.DoesNotExist):
            # Fallback context in case of missing data
            context.update({
                'leave_credits': None,
                'cy_sl': 0,
                'cy_vl': 0,
                'approved_leaves': [],
                'approved_leave_count': 0,
                'current_year': timezone.now().year,
                'current_yr_leave_usage': 0,
                'total_leave_taken': 0,
                'average_leave_per_month': 0,
                'sl_vs_vl_usage': {},
                'accrual_logs': [],
                'leave_requests': [],
            })

        return context



class HRLeaveDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'leave_mgt/hr_dashboard.html'

    def test_func(self):
        return self.request.user.employeeprofile.department.name == "HR" # or "Human Resource Management Office", check your department name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_requests = LeaveRequest.objects.select_related('employee').all()

        # Example: usage stats across employees
        context['all_leave_usage'] = calculate_yearly_leave_usage(all_requests)

        return context


class LeaveApplicationCreateView(CreateView, LoginRequiredMixin):
    model = LeaveRequest
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application.html'
    success_url = "leave_list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        employee = self.request.user.employeeprofile.leavecredit
        leave_type = form.cleaned_data['leave_type']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']

        try:
            number_of_days = validate_request_payload(
                leave_credit=employee,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
            )
            form.instance.number_of_days = number_of_days
        except ValidationError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        # If checks pass, create the leave record
        form.instance.employee = employee  # Set the employee field
        super().form_valid(form)

        messages.success(self.request, "Leave application submitted successfully.")
        return redirect('leave_list')  # Redirect to a success page

class LeaveApplicationUpdateView(UpdateView, LoginRequiredMixin):
    model = LeaveRequest
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application.html'
    success_url = "leave_list"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        leave_type = form.cleaned_data['leave_type']
        employee = self.request.user.employeeprofile.leavecredit
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']

        try:
            number_of_days = validate_request_payload(
                leave_credit=employee,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                exclude_pk=form.instance.pk,
                current_status=form.instance.status,
                current_request=form.instance,
            )
            form.instance.number_of_days = number_of_days
        except ValidationError as exc:
            messages.error(self.request, str(exc))
            return self.form_invalid(form)

        super().form_valid(form)
        messages.success(self.request, "Leave application updated successfully.")
        return redirect('leave_list')  # Redirect to a success page


class LeaveApplicationDetailView(DetailView, LoginRequiredMixin):
    model = LeaveRequest
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class LeaveApplicationDeleteView(DeleteView, LoginRequiredMixin):
    model = LeaveRequest
    template_name = 'leave_mgt/leave_application_delete.html'
    success_url = reverse_lazy('leave_list')  # Redirect to leave_mgt/ (MyLeaveView) view after deletion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def delete(self, request, *args, **kwargs):
        leave = self.get_object()
        revert_leave_credit_for_deleted_request(leave)

        # Call the superclass delete method
        response = super().delete(request, *args, **kwargs)
        # Add a success message
        messages.success(self.request, "Leave application deleted.")

        return response
