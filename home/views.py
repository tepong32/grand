from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .models import Announcement
from leave_mgt.models import LeaveRequest
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
from .forms import AnnouncementForm

from django.http import HttpResponse
from datetime import datetime
from django.utils import timezone


class HomeView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = 'home/authed/home.html'
    context_object_name = 'announcements'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = User
        profile = Profile

        context.update({
            'profiles': profile.objects.all(),
        })

        return context
        


class CreateAnnouncement(LoginRequiredMixin, CreateView):       
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'home/authed/create_announcement.html'
    success_message = "Announcement successfully posted."
    success_url = '/'

    def form_valid(self, form):
        form.instance.user = self.request.user    # to automatically get the id of the current logged-in user
        return super().form_valid(form)

class AnnouncementDetail(DetailView):
    model = Announcement
    template_name = 'home/authed/announcement_detail.html'
    context_object_name = 'announcement'

    def get_queryset(self):
        # Override to filter by slug
        return Announcement.objects.filter(slug=self.kwargs['slug'], published=True)


class UpdateAnnouncement(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Announcement 
    form_class = AnnouncementForm
    template_name = 'home/authed/update_announcement.html'
    success_message = "Announcement updated."
    # success_url = '/'

    def form_valid(self, form):         
        form.instance.user = self.request.user
        return super().form_valid(form)

    def test_func(self):
        announcement = self.get_object()
        if self.request.user == announcement.user:
            return True
        return False


class DeleteAnnouncement(LoginRequiredMixin, UserPassesTestMixin, DeleteView):      
    model = Announcement
    template_name = 'home/authed/delete_announcement.html'
    success_url = '/'

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def test_func(self):
        announcement = self.get_object()

        if self.request.user == announcement.user:
            return True
        return False      



