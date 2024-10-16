from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib.auth.decorators import login_required

from users.models import User, Profile
from .forms import LeaveApplicationForm
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

'''
    Since I am using a "dashboard stats on all pages" approach, I am defining a global_context dictionary here and
will just have specific views update the context variable (thru context.update(global_context) in get_context_data())
depending on their specific needs.
    Adjust the imports 'per-app' to properly locate the model sources.
'''
# Define a function to fetch dynamic data since we need the 'request' object
def get_dynamic_context(request):
    leave_credits = LeaveCredits.objects.get(employee=request.user.profile)
    pending_leaves = Leave.objects.filter(employee=leave_credits, status='PENDING')
    global_context = {
        'leave_credits': leave_credits,
        'remaining_sl_credits': leave_credits.current_year_sl_credits,
        'remaining_vl_credits': leave_credits.current_year_vl_credits,
        # 'total_acquired_sl_credits': leave_credits.total_acquired_sl_credits,
        # 'total_acquired_vl_credits': leave_credits.total_acquired_vl_credits,
        # 'total_used_sl_credits': leave_credits.total_used_sl_credits,
        # 'total_used_vl_credits': leave_credits.total_used_vl_credits,
        'pending_leaves': pending_leaves
    }
    return global_context

# Define a global context{} for static information that needs to be displayed on every view, if there's any
global_static_context = {
    # 'static_key': 'static_value',
}


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

        # Update context with global context
        context.update(global_static_context)
        # Fetch dynamic data and update context
        context.update(get_dynamic_context(self.request))
        # assign and add VIEW-SPECIFIC value to context{'<key>': <value>}
        leave_credits = LeaveCredits.objects.get(employee=self.request.user.profile) 
        context['leave_credits'] = leave_credits
        return context

class LeaveApplicationCreateView(CreateView, LoginRequiredMixin):
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application.html'
    success_url = "/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(global_static_context)
        context.update(get_dynamic_context(self.request))
        leave_credits = LeaveCredits.objects.get(employee=self.request.user.profile) 
        context['leave_credits'] = leave_credits
        return context

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
        return redirect('/')  # Redirect to a success page

class LeaveApplicationUpdateView(UpdateView):
    model = Leave
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application.html'
    success_url = "/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(global_static_context)
        context.update(get_dynamic_context(self.request))
        leave_credits = LeaveCredits.objects.get(employee=self.request.user.profile) 
        context['leave_credits'] = leave_credits
        return context

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
        return redirect('/')  # Redirect to a success page


class LeaveApplicationDetailView(DetailView):
    model = Leave
    form_class = LeaveApplicationForm
    template_name = 'leave_mgt/leave_application_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(global_static_context)
        context.update(get_dynamic_context(self.request))
        leave_credits = LeaveCredits.objects.get(employee=self.request.user.profile) 
        context['leave_credits'] = leave_credits
        return context


class LeaveApplicationDeleteView(DeleteView):
    model = Leave
    template_name = 'leave_mgt/leave_application_delete.html'
    success_url = reverse_lazy('leave_list')  # Redirect to leave_mgt/ (MyLeaveView) view after deletion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(global_static_context)
        context.update(get_dynamic_context(self.request))
        leave_credits = LeaveCredits.objects.get(employee=self.request.user.profile) 
        context['leave_credits'] = leave_credits
        return context

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