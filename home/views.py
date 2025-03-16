from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages     # for flash messages regarding valid data in the form
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse




from .models import Announcement, OrgPersonnel, DepartmentContact, DownloadableForm
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


class UnauthedHomeView(ListView):
    model = Announcement
    template_name = 'home/unauthed/home.html'
    context_object_name = 'announcements'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch public announcements and order them by created_at
        public = Announcement.objects.filter(announcement_type=Announcement.PUBLIC).order_by('-created_at')
        internal = Announcement.objects.filter(announcement_type=Announcement.INTERNAL).order_by('-created_at')

        # Get the latest 5 public announcements for the carousel
        latest_public = public[:5]  # Slicing to get the latest 5
        # Filter out the latest announcements from the public list
        remaining_public = public[5:]  # Get all public announcements except the latest 5

        # Set up pagination for remaining public announcements
        page_number = self.request.GET.get('page')  # Get the page number from the query parameters
        paginator = Paginator(remaining_public, 5)  # Show 5 announcements per page
        page_obj = paginator.get_page(page_number)  # Get the page object

        # Optionally, if you need published and draft announcements for admin posting purposes
        published = Announcement.objects.filter(published=True)
        draft = Announcement.objects.filter(published=False)

        # Manually iterated latest announcements for chaotic positioning on the bulletin board
        latest_positions = [
            {'announcement': latest_public[0], 'top': '23%', 'left': '30%'},
            {'announcement': latest_public[1], 'top': '33%', 'left': '10%'},
            {'announcement': latest_public[2], 'top': '40%', 'left': '63%'},
            {'announcement': latest_public[3], 'top': '55%', 'left': '45%'},
            {'announcement': latest_public[4], 'top': '68%', 'left': '25%'},
        ]

        context.update({
            'public': public,
            'latest_public': latest_public,
            'latest_positions': latest_positions,
            'remaining_public': page_obj,  # Use the paginated announcements
            'internal': internal,
            'published': published,
            'draft': draft,

            'departments': DepartmentContact.objects.all(),
            'downloadableforms': DownloadableForm.objects.all(),
        })
        return context


class OrgChartView(ListView):
    model = OrgPersonnel
    template_name = 'home/unauthed/orgchart.html'
    context_object_name = 'orgpersonnel'
    ordering = ['display_order']



####################### VIEWS THAT NEED AUTHENTICATION (INTERNAL VIEWS)
class AuthedHomeView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = 'home/authed/home.html'
    context_object_name = 'announcements'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # user = User # not being used atm

        internal = Announcement.objects.filter(announcement_type=Announcement.INTERNAL).order_by('-created_at')

        # Optionally, if you need published and draft announcements for admin posting purposes
        published = Announcement.objects.filter(published=True)
        draft = Announcement.objects.filter(published=False)
        context.update({
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
        announcement = form.save()  # Save the form and get the instance
        messages.success(self.request, self.success_message)
        return redirect('announcement-detail', slug=announcement.slug)  # Redirect to the detail view using the slug


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


def announcement_search_view(request, *args, **kwargs):
    context = {}
    if request.method == "GET":
        print("Request GET:", request.GET)  # Debugging line
        search_query = request.GET.get("q", "")  # Default to empty string if not found
        print("Search query:", search_query)  # Debugging line
        try:
            if search_query:  # This checks if search_query is not empty
                search_results = Announcement.objects.filter(
                    Q(title__icontains=search_query) | Q(content__icontains=search_query)
                ).distinct()
                
                announcements = []  # Initialize the list for announcements
                for announcement in search_results:
                    announcements.append((announcement, False))  # Append the announcement

                context['announcements'] = announcements  # Corrected variable name
                context['search_query'] = search_query
        except Exception as e:
            print("Error:", e)
            print("Request GET:", request.GET)
            print("Search query:", search_query)
                
    return render(request, "home/unauthed/announcement_search_results.html", context)