from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from leave_mgt.models import LeaveCredits, Leave
from users.models import User, Profile

from django.views.generic import (
    TemplateView,
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
    )
from .forms import LeaveForm

from django.http import HttpResponse
from datetime import datetime
from django.utils import timezone


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'home/authed/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = User
        profile = Profile
        loggedin_user = self.request.user.profile
        leave_credits = LeaveCredits.objects.get(employee=loggedin_user)
        pending_leaves = Leave.objects.filter(employee=leave_credits, status='PENDING')
        pending_leaves_count = sum(leave.number_of_days for leave in pending_leaves)
        user_leaves = Leave.objects.filter(employee=leave_credits)[::-1]  # Filter the leaves of the current user, latest first


        context.update({
            'leave_credits': leave_credits,
            'pending_leaves': pending_leaves,
            'pending_leaves_count': pending_leaves_count,
            'profiles': profile.objects.all(),
            'user_leaves': user_leaves,
        })

        return context
        


class ApplyLeaveView(LoginRequiredMixin, CreateView):       
    model = Leave
    form_class = LeaveForm
    template_name = 'home/authed/apply_leave_form.html'
    success_message = "Leave request submitted."
    success_url = '/'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'employee': self.request.user})
        return kwargs

    def get_context_data(self, **kwargs):
        '''
            The get_context_data method is used to add additional context variables to the template.
            If you’re using the leave_counter variable in your template, then you should keep this method.
            This method ensures that a LeaveCounter object is created for every user when they access the view.
        '''
        data = super().get_context_data(**kwargs)
        leave_counter, _ = LeaveCounter.objects.get_or_create(employee=self.request.user.profile)
        data['leave_counter'] = leave_counter
        server_time = datetime.now()
        data['server_time'] = server_time
        instances_used_this_year = leave_counter.instances_used_this_year
        data['instances_used_this_year'] = instances_used_this_year
        instances_used_this_quarter = leave_counter.instances_used_this_quarter
        data['instances_used_this_quarter'] = instances_used_this_quarter
        return data

    def form_valid(self, form):
        form.instance.employee = self.request.user    # to automatically get the id of the current logged-in user
        return super().form_valid(form)


class LeaveUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Leave 
    form_class = LeaveForm
    template_name = 'home/authed/update_leave_form.html'
    success_message = "Leave application updated."
    success_url = '/'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'employee': self.request.user})
        return kwargs

    def get_context_data(self, **kwargs):
        '''
            The get_context_data method is used to add additional context variables to the template.
            If you’re using the leave_counter variable in your template, then you should keep this method.
            This method ensures that a LeaveCounter object is created for every user when they access the view.
        '''
        data = super().get_context_data(**kwargs)
        leave_counter, _ = LeaveCounter.objects.get_or_create(employee=self.request.user)
        data['leave_counter'] = leave_counter
        server_time = datetime.now()
        data['server_time'] = server_time
        instances_used_this_year = leave_counter.instances_used_this_year
        data['instances_used_this_year'] = instances_used_this_year
        instances_used_this_quarter = leave_counter.instances_used_this_quarter
        data['instances_used_this_quarter'] = instances_used_this_quarter
        return data

    def form_valid(self, form):         
        form.instance.employee = self.request.user
        return super().form_valid(form)

    def test_func(self):
        leave = self.get_object()

        if self.request.user == leave.employee:
            return True
        return False


class LeaveDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):      
    model = Leave
    template_name = 'home/authed/delete_leave_form.html'
    success_url = '/'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'employee': self.request.user})
        return kwargs

    def get_context_data(self, **kwargs):
        '''
            The get_context_data method is used to add additional context variables to the template.
            If you’re using the leave_counter variable in your template, then you should keep this method.
            This method ensures that a LeaveCounter object is created for every user when they access the view.
        '''
        data = super().get_context_data(**kwargs)
        leave_counter, _ = LeaveCounter.objects.get_or_create(employee=self.request.user)
        data['leave_counter'] = leave_counter
        server_time = datetime.now()
        data['server_time'] = server_time
        instances_used_this_year = leave_counter.instances_used_this_year
        data['instances_used_this_year'] = instances_used_this_year
        instances_used_this_quarter = leave_counter.instances_used_this_quarter
        data['instances_used_this_quarter'] = instances_used_this_quarter
        return data

    def form_valid(self, form):
        form.instance.employee = self.request.user
        return super().form_valid(form)

    def test_func(self):
        leave = self.get_object()

        if self.request.user == leave.employee:
            return True
        return False      


# views.py
from django.views.generic.edit import FormView
from .forms import IncreaseMaxInstancesForm
from .utils import increase_max_instances
from django.contrib import messages


class IncreaseMaxInstancesView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'home/authed/increase_max_instances.html'
    form_class = IncreaseMaxInstancesForm
    success_url = '/'  # replace with your success url

    # def test_func(self):
    #     return self.request.user.is_staff or self.request.user.profile.emp_type == "Team Leader" or self.request.user.profile.emp_type == "Operations Mgr"

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_team_leader or self.request.user.is_operations_manager

    def get_context_data(self, **kwargs):
        '''
            The get_context_data method is used to add additional context variables to the template.
            If you’re using the leave_counter variable in your template, then you should keep this method.
            This method ensures that a LeaveCounter object is created for every user when they access the view.
        '''
        data = super().get_context_data(**kwargs)
        leave_counter, _ = LeaveCounter.objects.get_or_create(employee=self.request.user)
        data['leave_counter'] = leave_counter
        server_time = datetime.now()
        data['server_time'] = server_time
        instances_used_this_year = leave_counter.instances_used_this_year
        data['instances_used_this_year'] = instances_used_this_year
        instances_used_this_quarter = leave_counter.instances_used_this_quarter
        data['instances_used_this_quarter'] = instances_used_this_quarter
        return data

    def form_valid(self, form):
        year_additional_instances = form.cleaned_data.get('year_additional_instances')
        quarter_additional_instances = form.cleaned_data.get('quarter_additional_instances')
        increase_max_instances(year_additional_instances, quarter_additional_instances)
        messages.success(self.request, f'Successfully adjusted max instances for all users by: \nYearly: {year_additional_instances} \nQuarterly: {quarter_additional_instances}')
        return super().form_valid(form)


from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

@csrf_exempt
@login_required
def check_reset_date(request):
    if request.method == 'POST':
        leave_counter = LeaveCounter.objects.get(employee=request.user)
        leave_counter.reset_counters()
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    else:  # GET request
        return render(request, 'home/authed/reset_counters.html')
