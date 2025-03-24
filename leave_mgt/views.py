from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Sum
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required

from users.models import User, EmployeeProfile
from .forms import LeaveApplicationForm
from .models import LeaveRequest, LeaveCredit, LeaveCreditLog

from django.views.generic import (
    TemplateView,
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
    )
# from .forms import LeaveForm

from django.http import HttpResponse
from datetime import datetime
from django.utils import timezone


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
    model = LeaveRequest
    template_name = 'leave_mgt/leave_summary.html'  # Displaying the default template for normal users
    ordering    =   ['-date_filed']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
        leave_type = form.cleaned_data['leave_type']
        # number_of_days = form.cleaned_data['number_of_days']
        employee = self.request.user.employeeprofile.leavecredit

        # Calculate number of days here since it's hidden from the form
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        number_of_days = (end_date - start_date).days + 1

        # Check leave credits based on leave type
        if leave_type == 'SL':
            if employee.current_year_sl_credits <= 0 or (employee.current_year_sl_credits - number_of_days < 0):
                form.add_error(None, "Insufficient Sick Leave credits.")
                return self.form_invalid(form)

        elif leave_type == 'VL':
            if employee.current_year_vl_credits <= 0 or (employee.current_year_vl_credits - number_of_days < 0):
                form.add_error(None, "Insufficient Vacation Leave credits.")
                return self.form_invalid(form)

        # Set the calculated number of days to the form instance
        form.instance.number_of_days = number_of_days

        # If checks pass, create the leave record
        form.instance.employee = employee  # Set the employee field
        response = super().form_valid(form)

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
        # number_of_days = form.cleaned_data['number_of_days']
        employee = self.request.user.employeeprofile.leavecredit

        # Calculate number of days here since it's hidden from the form
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        number_of_days = (end_date - start_date).days + 1

        # Check leave credits based on leave type
        if leave_type == 'SL':
            if employee.current_year_sl_credits <= 0 or (employee.current_year_sl_credits - number_of_days < 0):
                messages.error(self.request, "Insufficient Sick Leave credits.")
                return self.form_invalid(form)

        elif leave_type == 'VL':
            if employee.current_year_vl_credits <= 0 or (employee.current_year_vl_credits - number_of_days < 0):
                messages.error(self.request, "Insufficient Vacation Leave credits.")
                return self.form_invalid(form)

        # If checks pass, update the leave record
        response = super().form_valid(form)

        # Update leave credits only if the leave is approved
        if form.instance.status == 'APPROVED':
            if leave_type == 'SL':
                employee.current_year_sl_credits -= number_of_days
            elif leave_type == 'VL':
                employee.current_year_vl_credits -= number_of_days
            employee.save()  # Save the updated leave credits

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
        employee = request.user.employeeprofile.leavecredit

        # If the leave is approved, add back the number of days to the corresponding credits
        # MAKE SURE THAT ONLY ADMINS CAN DELETE ALREADY-APPROVED LEAVES
        if leave.status == 'APPROVED':
            if leave.leave_type == 'SL':
                employee.current_year_sl_credits += leave.number_of_days
            elif leave.leave_type == 'VL':
                employee.current_year_vl_credits += leave.number_of_days
            employee.save()  # Save the updated leave credits

        # Call the superclass delete method
        response = super().delete(request, *args, **kwargs)
        # Add a success message
        messages.success(self.request, "Leave application deleted.")

        return response