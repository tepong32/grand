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
    user = get_object_or_404(User, username=username)

    if user != request.user:
        return render(request, "profiles/error.html", {"error": "You do not have permission to edit this profile."})

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.employeeprofile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f"Account info has been updated.")
            return render(request, "profiles/profile.html", {"user": request.user})
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.employeeprofile)

    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'profiles/profile_edit.html', context)
