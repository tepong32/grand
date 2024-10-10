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



class MyLeaveView(LoginRequiredMixin, TemplateView):
    template_name = 'leave_mgt/leave_summary.html'

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