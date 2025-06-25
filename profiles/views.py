from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from users.models import User
from departments.models import Department
from leave_mgt.models import LeaveCredit
from .models import EmployeeProfile
from .forms import ProfileUpdateForm
from users.forms import UserUpdateForm  # still pulling from users app


@login_required
def profileView(request, username=None):
    user = get_object_or_404(User, username=username)
    leave_credits = None

    if request.user == user:
        try:
            leave_credits = LeaveCredit.objects.get(employee=request.user.employeeprofile)
        except LeaveCredit.DoesNotExist:
            messages.warning(request, "No leave credits recorded yet.")

    context = {
        "viewed_user": user,
        "leave_credits": leave_credits,
    }
    return render(request, 'profiles/profile.html', context)


@login_required
def profileEditView(request, username=None):
    '''
    Provide a form for the user to edit their profile information.
    Form that will be displayed will depend on whether the user is a Citizen or Employee.
    '''
    user = get_object_or_404(User, username=username)

    if user != request.user:
        return render(request, "profiles/error.html", {"error": "You do not have permission to edit this profile."})

    # Check if user is a Citizen or Employee
    is_employee = hasattr(user, 'employeeprofile')
    is_citizen = hasattr(user, 'citizenprofile')

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)

        if is_employee:
            p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.employeeprofile)
        elif is_citizen:
            from .forms import CitizenProfileUpdateForm
            p_form = CitizenProfileUpdateForm(request.POST, instance=request.user.citizenprofile)
        else:
            return render(request, "profiles/error.html", {"error": "Profile type not recognized."})

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, "Account info has been updated.")
            return redirect("profile", slug=request.user.citizenprofile.slug if is_citizen else request.user.employeeprofile.slug)

    else:
        u_form = UserUpdateForm(instance=request.user)
        if is_employee:
            p_form = ProfileUpdateForm(instance=request.user.employeeprofile)
        elif is_citizen:
            from .forms import CitizenProfileUpdateForm
            p_form = CitizenProfileUpdateForm(instance=request.user.citizenprofile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'is_employee': is_employee,
        'is_citizen': is_citizen
    }
    return render(request, 'profiles/profile_edit.html', context)

