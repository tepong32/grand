from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages     # for flash messages regarding valid data in the form
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now

from .models import Announcement, OrgPersonnel, DepartmentContact, DownloadableForm
from leave_mgt.models import LeaveRequest
from users.models import User

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

####################### VIEWS FOR THE GENERAL PUBLIC
class UnauthedHomeView(ListView):
    model = Announcement
    template_name = 'home/unauthed/home.html'
    context_object_name = 'announcements'

    ### removed this line as i want even logged-in users to see the announcements on the home page, too
    ### with this block, they will be redirected to their respective department dashboards when trying to view the unauthed home page.
    # def dispatch(self, request, *args, **kwargs):
    #     """
    #     Redirects authenticated users to their respective department dashboards.
    #     If the user is not authenticated, it proceeds with the normal dispatch: ListView behavior.
    #     """
    #     if request.user.is_authenticated:
    #         return redirect('home_redirect')  # 👈 This sends logged-in users to their dashboards
    #     return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch announcements
        public = Announcement.objects.filter(announcement_type=Announcement.PUBLIC).order_by('-created_at')
        internal = Announcement.objects.filter(announcement_type=Announcement.INTERNAL).order_by('-created_at')

        # Split into latest (top 5) and remaining
        latest_public = public[:5]
        remaining_public = public[5:]

        # Paginate remaining public announcements
        paginator = Paginator(remaining_public, 5)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Admin use: published vs draft (if needed)
        published = Announcement.objects.filter(published=True)
        draft = Announcement.objects.filter(published=False)

        context.update({
            'public': public,
            'latest_public': latest_public,
            'remaining_public': page_obj,
            'internal': internal,
            'published': published,
            'draft': draft,
        })

        return context



class OrgChartView(ListView):
    model = OrgPersonnel
    template_name = 'home/unauthed/orgchart.html'
    context_object_name = 'orgpersonnel'
    ordering = ['display_order']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deptheads'] = OrgPersonnel.objects.exclude(title__in=["Mayor", "Vice Mayor", "Councilor"]).order_by('display_order')
        return context


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
    paginate_by = 9

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = now()
        return context

class CreateAnnouncement(LoginRequiredMixin, CreateView):       
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'home/authed/announcement_create.html'
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
    template_name = 'home/authed/announcement_update.html'
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
    template_name = 'home/authed/announcement_delete.html'
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


from django.template.loader import get_template, TemplateDoesNotExist
from home.utils import get_department_dashboard_context

@login_required
def department_dashboard_dynamic(request):
    user = getattr(request.user, 'employeeprofile', None)
    if not user:
        # If user has no employee profile, fallback to home or a suitable page
        return redirect('home')

    department = getattr(user, 'assigned_department', None)
    if not department:
        return redirect('home')

    fallback_template = 'home/authed/dashboards/generic.html'
    template_path = (department.dashboard_template or '').strip()
    print("💡 USING department_dashboard_dynamic view")
    print(f"[DEBUG] Department slug: {department.slug}")


    try:
        if template_path:
            # Check if the template actually exists
            get_template(template_path)
        else:
            raise TemplateDoesNotExist("No template path specified.")
    except TemplateDoesNotExist:
        template_path = fallback_template

    context = {
        "department": department,
    }

    # Merge department-specific dashboard context
    context.update(get_department_dashboard_context(department, user))

    return render(request, template_path, context)


def unauthorized_access_view(request):
    return render(request, 'home/authed/dashboards/403_unauthorized.html', status=403)
