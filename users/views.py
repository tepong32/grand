from django.shortcuts import render, redirect
from .models import User, EmployeeProfile, Department
from django.contrib import messages     # for flash messages regarding valid data in the form
from leave_mgt.models import LeaveCredit


# for needing user to be logged-in first before accessing the page requested
from django.contrib.auth.decorators import login_required
from .forms import *

def usersIndexView(request):
    user = User
    departments = Department.objects.all() #listing all the Departments
    department_users = {} #empty dict for users filtered by "department" attr

    for department in departments:
        profiles = EmployeeProfile.objects.filter(department=department) #separating users per department
        department_users[department.name] = profiles #adding the department_users to the dict using the department name as key

    if request.user.is_staff:
        messages.info(request, f"You are seeing this page because you are a Staff/Admin.")
        
    context_data = {
        # all users sorted by last_name attr, paginating by 50 per page
        'users': user.objects.all().order_by('last_name', 'first_name')[:50],
        'userCount': user.objects.count(),
        'department_users': department_users,
    }

    return render(request, 'users/users_index.html', context_data)


def register(request):
    '''
        if the page gets a POST request, the POST's data gets instantiated to the UserCreationForm,
        otherwise, it instantiates a blank form.
    '''
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()     # to make sure that the registering user gets saved to the database
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    # arguments == "request", the_template, the_context(dictionary))
    return render(request, 'auth/register.html', {'form': form})


def employeeRegister(request):
    '''
        if the page gets a POST request, the POST's data gets instantiated to the UserCreationForm,
        otherwise, it instantiates a blank form.
    '''
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()     # to make sure that the registering user gets saved to the database
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    # arguments == "request", the_template, the_context(dictionary))
    return render(request, 'auth/employee_register.html', {'form': form})


@login_required ###previously-used decorator dj2.1.5
def profileView(request, username=None):
    if User.objects.get(username=username):
        user = User.objects.get(username=username)
        context = {
            "user": user,
        }
        leave_credits = None
        if request.user.is_authenticated:
            try:
                leave_credits = LeaveCredit.objects.get(employee=request.user.employeeprofile) #since LeaveCredit is related to Profile; not User
            except LeaveCredit.DoesNotExist:
                pass # Or handle the case where it's not found: like messages.danger('no leave credits accumulated yet')?

        context['leave_credits'] = leave_credits
        return render(request, 'users/profile.html', context)
    else:
        return render ("User not found.")


@login_required
def profileEditView(request, username=None):
    if User.objects.get(username=username):
        user = User.objects.get(username=username)
        if user == request.user:  # Check if the user is trying to edit their own profile
            if request.method == 'POST':
                # the forms from forms.py
                u_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)        # instance is for the fields to auto-populate with user info
                p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.employeeprofile)

                if u_form.is_valid() and p_form.is_valid():
                    u_form.save()
                    p_form.save()
                    messages.success(request, f"Account info has been updated.")
                    return render(request, "users/profile.html", {"user":request.user})

            else:
                # Pass the instance of the user to the forms when the request method is GET
                u_form = UserUpdateForm(instance=request.user)
                p_form = ProfileUpdateForm(instance=request.user.employeeprofile)

            context = {
                'u_form': u_form,
                'p_form': p_form
            }
            return render(request, 'users/profile_edit.html', context)
        else:
            # If the user is trying to edit someone else's profile, return an error message
            return render(request, "users/error.html", {"error": "You do not have permission to edit this profile."})

    else:
        return render ("User not found.")


### accounts/users searching view
### not used ATM

from django.db.models import Q  # This is needed for the search query to work properly
                                # allowing the search to use matches on usersnames OR email addresses
                                # as opposed to the original username AND email:
                                # "search_results = User.objects.filter(username__icontains=search_query).filter(email__icontains=search_query).distinct()"

def user_search_view(request, *args, **kwargs):
    context = {}
    if request.method == "GET":
        print("Request GET:", request.GET)  # Add this line
        search_query = request.GET.get("q")
        print("Search query:", search_query)  # Add this line
        try:
            if len(search_query) > 0:
                search_results = User.objects.filter(Q(username__icontains=search_query) | Q(email__icontains=search_query) | Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query)).distinct() # match EITHER-OR any of the queries
                user = request.user
                accounts = [] # [(account1, True), (account2, False), ...]
                for account in search_results:
                    accounts.append((account, False)) # I do not need this False part yet since I have no intention to use a Friend system on an LGU app but I'll keep it here for future reference.
                context['accounts'] = accounts
                context['search_query'] = search_query
        except Exception as e:
            print("Error:", e)
            print("Request GET:", request.GET)
            print("Search query:", search_query)
                
    return render(request, "users/user_search_results.html", context)


##################### PW Resets
from django.contrib.auth.views import PasswordResetView
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _
import logging

# Set up logging
logger = logging.getLogger(__name__)

class CustomPasswordResetView(PasswordResetView):
    def form_valid(self, form):
        try:
            # Call the original form_valid method to send the email
            response = super().form_valid(form)
            logger.debug("Context for password reset email: %s", self.get_context_data())
            logger.info("Password reset email sent to: %s", form.cleaned_data['email'])
            return response

        except Exception as e:
            # Log the error if sending the email fails
            logger.error("Failed to send password reset email to %s: %s", form.cleaned_data['email'], str(e))
            # You may also want to return an error message to the user
            form.add_error(None, _("There was an error sending the password reset email. Please try again later."))
            return self.form_invalid(form)