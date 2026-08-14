from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .access import (
    can_manage_social_welfare,
    mswd_programs_required,
    mswd_department_for_user,
    social_welfare_manager_required,
)
from .forms import ProgramActivityForm, SocialWelfareProgramForm
from .models import ProgramActivity, SocialWelfareProgram


def _programs_for_mswd():
    return SocialWelfareProgram.objects.filter(
        department__slug__iexact="mswd"
    ).select_related("department", "coordinator")


@mswd_programs_required
def program_list(request):
    programs = _programs_for_mswd().annotate(
        activity_count=Count("activities"),
        recorded_attendance=Sum(
            "activities__actual_attendance",
            filter=Q(activities__status=ProgramActivity.STATUS_COMPLETED),
        ),
    )
    upcoming_query = ProgramActivity.objects.filter(
        program__department__slug__iexact="mswd",
        starts_at__gte=timezone.now(),
        status=ProgramActivity.STATUS_PLANNED,
    ).select_related("program")
    upcoming = upcoming_query[:8]
    return render(
        request,
        "social_welfare/program_list.html",
        {
            "programs": programs,
            "upcoming_activities": upcoming,
            "can_manage_programs": can_manage_social_welfare(request.user),
            "active_program_count": programs.filter(status=SocialWelfareProgram.STATUS_ACTIVE).count(),
            "upcoming_activity_count": upcoming_query.count(),
            "completed_activity_count": ProgramActivity.objects.filter(
                program__department__slug__iexact="mswd",
                status=ProgramActivity.STATUS_COMPLETED,
            ).count(),
        },
    )


@mswd_programs_required
def program_detail(request, pk):
    program = get_object_or_404(_programs_for_mswd(), pk=pk)
    return render(
        request,
        "social_welfare/program_detail.html",
        {
            "program": program,
            "activities": program.activities.all(),
            "can_manage_programs": can_manage_social_welfare(request.user),
        },
    )


@social_welfare_manager_required
@require_http_methods(["GET", "POST"])
def program_create(request):
    department = mswd_department_for_user(request.user)
    form = SocialWelfareProgramForm(request.POST or None, department=department)
    if request.method == "POST" and form.is_valid():
        program = form.save(commit=False)
        program.department = department
        program.created_by = request.user
        program.updated_by = request.user
        program.save()
        messages.success(request, f"Program “{program.name}” was created.")
        return redirect(program)
    return render(request, "social_welfare/program_form.html", {"form": form, "mode": "Create"})


@social_welfare_manager_required
@require_http_methods(["GET", "POST"])
def program_update(request, pk):
    program = get_object_or_404(_programs_for_mswd(), pk=pk)
    form = SocialWelfareProgramForm(
        request.POST or None,
        instance=program,
        department=program.department,
    )
    if request.method == "POST" and form.is_valid():
        program = form.save(commit=False)
        program.updated_by = request.user
        program.save()
        messages.success(request, f"Program “{program.name}” was updated.")
        return redirect(program)
    return render(request, "social_welfare/program_form.html", {"form": form, "mode": "Update", "program": program})


@social_welfare_manager_required
@require_http_methods(["GET", "POST"])
def activity_create(request, program_pk):
    program = get_object_or_404(_programs_for_mswd(), pk=program_pk)
    form = ProgramActivityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        activity = form.save(commit=False)
        activity.program = program
        activity.created_by = request.user
        activity.updated_by = request.user
        activity.save()
        messages.success(request, f"Activity “{activity.title}” was scheduled.")
        return redirect(program)
    return render(
        request,
        "social_welfare/activity_form.html",
        {"form": form, "mode": "Schedule", "program": program},
    )


@social_welfare_manager_required
@require_http_methods(["GET", "POST"])
def activity_update(request, pk):
    activity = get_object_or_404(
        ProgramActivity.objects.select_related("program", "program__department"),
        pk=pk,
        program__department__slug__iexact="mswd",
    )
    form = ProgramActivityForm(request.POST or None, instance=activity)
    if request.method == "POST" and form.is_valid():
        activity = form.save(commit=False)
        activity.updated_by = request.user
        activity.save()
        messages.success(request, f"Activity “{activity.title}” was updated.")
        return redirect(activity.program)
    return render(
        request,
        "social_welfare/activity_form.html",
        {"form": form, "mode": "Update", "program": activity.program, "activity": activity},
    )
