from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from users.models import User
from departments.models import Department
from leave_mgt.models import LeaveCredit
from .models import EmployeeProfile, CitizenProfile
from .forms import ProfileUpdateForm, EmploymentProfileUpdateForm, CitizenProfileUpdateForm
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
    user = get_object_or_404(User, username=username)
    is_owner = request.user == user
    is_admin = request.user.is_staff or request.user.is_superuser

    # Detect profile type
    is_employee = hasattr(user, "employeeprofile")
    is_citizen = hasattr(user, "citizenprofile")

    if not (is_owner or is_admin):
        return render(request, "profiles/error.html", {"error": "You do not have permission to edit this profile."})

    u_form = UserUpdateForm(request.POST or None, request.FILES or None, instance=user, prefix='user')

    # Handle forms conditionally
    p_form = None
    hr_form = None
    c_form = None

    if is_employee:
        profile = user.employeeprofile
        p_form = ProfileUpdateForm(request.POST or None, request.FILES or None, instance=profile, prefix='basic')
        if is_admin:
            hr_form = EmploymentProfileUpdateForm(request.POST or None, request.FILES or None, instance=profile, prefix='hr')
    elif is_citizen:
        profile = user.citizenprofile
        c_form = CitizenProfileUpdateForm(request.POST or None, request.FILES or None, instance=profile, prefix='citizen')

    if request.method == 'POST':
        is_valid = u_form.is_valid()

        if is_employee:
            is_valid &= p_form.is_valid()
            if is_admin and hr_form:
                is_valid &= hr_form.is_valid()
        elif is_citizen:
            is_valid &= c_form.is_valid()

        if is_valid:
            u_form.save()
            if p_form: p_form.save()
            if hr_form: hr_form.save()
            if c_form: c_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect(profile.get_absolute_url())

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'hr_form': hr_form,
        'c_form': c_form,
        'is_employee': is_employee,
        'is_citizen': is_citizen,
        'is_admin': is_admin,
        'is_owner': is_owner,
        'viewed_user': user,
    }
    return render(request, 'profiles/profile_edit.html', context)


