from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required

from users.models import User, Profile
from .forms import LeaveForm
from .models import Leave, LeaveCredits

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
        return ['leave_mgt/leave_summary.html']            # template for normal users


class MyLeaveView(LoginRequiredMixin, RoleBasedTemplateMixin, TemplateView):
    template_name = 'leave_mgt/leave_summary.html' # displaying the default template for normal users

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leave_credits = None
        if self.request.user.is_authenticated:
            try:
                leave_credits = LeaveCredits.objects.get(employee=self.request.user.profile) #since LeaveCredits is related to Profile; not User
            except LeaveCredits.DoesNotExist:
                pass # Or handle the case where it's not found: like messages.danger('no leave credits accumulated yet')?

        context['leave_credits'] = leave_credits

        return context

class LeaveApplicationCreateView(CreateView, LoginRequiredMixin):
    form_class = LeaveForm
    template_name = 'leave_mgt/leave_application.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        leave_type = form.cleaned_data['leave_type']
        number_of_days = form.cleaned_data['number_of_days']
        employee = self.request.user.profile.leavecredits

        # Check leave credits based on leave type
        if leave_type == 'SL':
            if employee.current_year_sl_credits <= 0 or (employee.current_year_sl_credits - number_of_days < 0):
                messages.error(self.request, "Insufficient Sick Leave credits.")
                return self.form_invalid(form)

        elif leave_type == 'VL':
            if employee.current_year_vl_credits <= 0 or (employee.current_year_vl_credits - number_of_days < 0):
                messages.error(self.request, "Insufficient Vacation Leave credits.")
                return self.form_invalid(form)

        # If checks pass, create the leave record
        form.instance.employee = employee  # Set the employee field
        response = super().form_valid(form)

        # Update leave credits only if the leave is approved
        if form.instance.status == 'APPROVED':
            if leave_type == 'SL':
                employee.current_year_sl_credits -= number_of_days
            elif leave_type == 'VL':
                employee.current_year_vl_credits -= number_of_days
            employee.save()  # Save the updated leave credits

        messages.success(self.request, "Leave application submitted successfully.")
        return redirect('success_view')  # Redirect to a success page

class LeaveApplicationUpdateView(UpdateView):
    model = Leave
    form_class = LeaveForm
    template_name = 'leave_mgt/leave_application.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        leave_type = form.cleaned_data['leave_type']
        number_of_days = form.cleaned_data['number_of_days']
        employee = self.request.user.profile.leavecredits

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
        return redirect('success_view')  # Redirect to a success page


class LeaveApplicationDeleteView(DeleteView):
    model = Leave
    template_name = 'leave_mgt/leave_application_delete.html'
    success_url = reverse_lazy('leave_list')  # Redirect to a list view after deletion

    def delete(self, request, *args, **kwargs):
        leave = self.get_object()
        employee = request.user.profile.leavecredits

        # If the leave is approved, add back the number of days to the corresponding credits
        if leave.status == 'APPROVED':
            if leave.leave_type == 'SL':
                employee.current_year_sl_credits += leave.number_of_days
            elif leave.leave_type == 'VL':
                employee.current_year_vl_credits += leave.number_of_days
            employee.save()  # Save the updated leave credits

        return super().delete(request, *args, **kwargs)