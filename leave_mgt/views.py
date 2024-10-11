from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from users.models import User, Profile
from .models import LeaveCredits

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


class AdminTemplateMixin(UserPassesTestMixin):
    '''
        This mixin is used to determine what template to display to the user depending on roles:
        normal user vs superuser/admins
    '''
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

    def get_template_names(self):
        if self.test_func():
            return ['leave_mgt/admin_leaves_summary.html']
        return ['leave_mgt/leave_summary.html']


class MyLeaveView(LoginRequiredMixin, AdminTemplateMixin, TemplateView):
    template_name = 'leave_mgt/leaves_summary.html' # default template for normal users

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = User
        profile = Profile
        
        leave_credits = None
        if self.request.user.is_authenticated:
            try:
                leave_credits = LeaveCredits.objects.get(employee=self.request.user.profile) #since LeaveCredits is related to Profile; not User
            except LeaveCredits.DoesNotExist:
                pass # Or handle the case where it's not found: like messages.danger('no leave credits accumulated yet')?

        context['leave_credits'] = leave_credits

        return context