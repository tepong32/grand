from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages     # for flash messages regarding valid data in the form

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


class HomeView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = 'home/authed/home.html'
    context_object_name = 'announcements'
    # ordering    =   ['-created_at'] # not working since may filter ng types ng announcements

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = User
        profile = Profile
        pinned = Announcement.objects.filter(announcement_type=Announcement.PINNED)[::-1]
        public = Announcement.objects.filter(announcement_type=Announcement.PUBLIC)[::-1]
        internal = Announcement.objects.filter(announcement_type=Announcement.INTERNAL)[::-1]

        published = Announcement.objects.filter(published=True)
        draft = Announcement.objects.filter(published=False)
        context.update({
            'profiles': profile.objects.all(), # pwede na tong alisin pag tapos na ang testing

            'pinned': pinned,
            'public': public,
            'internal': internal,

            'published': published,
            'draft': draft
        })
        return context
        
class AnnouncementList(ListView):
    model = Announcement
    template_name = 'home/authed/announcements_list.html'
    context_object_name = 'announcements'
    ordering    =   ['-created_at']


class CreateAnnouncement(LoginRequiredMixin, CreateView):       
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'home/authed/create_announcement.html'
    success_message = "Announcement successfully posted"
    success_url = '/'

    def form_valid(self, form):
        form.instance.user = self.request.user    # to automatically get the id of the current logged-in user
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class AnnouncementDetail(DetailView):
    model = Announcement
    template_name = 'home/authed/announcement_detail.html'
    context_object_name = 'announcement'

    def get_object(self, queryset=None):
        # Get the announcement by slug
        announcement = get_object_or_404(Announcement, slug=self.kwargs['slug'])
        # Optionally, check if the announcement is published
        if not announcement.published and not self.request.user.is_staff:
            # If the announcement is unpublished and the user is not staff, raise a 404
            raise Http404("You do not have permission to view this announcement.")
        return announcement


class UpdateAnnouncement(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Announcement 
    form_class = AnnouncementForm
    template_name = 'home/authed/update_announcement.html'
    success_message = "Announcement updated"
    # success_url = '/'

    def form_valid(self, form):         
        form.instance.user = self.request.user
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def test_func(self):
        announcement = self.get_object()
        if self.request.user == announcement.user:
            return True
        return False


class DeleteAnnouncement(LoginRequiredMixin, UserPassesTestMixin, DeleteView):      
    model = Announcement
    template_name = 'home/authed/delete_announcement.html'
    success_message = "Announcement deleted"
    success_url = '/'

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def test_func(self):
        announcement = self.get_object()

        if self.request.user == announcement.user:
            return True
        return False      



