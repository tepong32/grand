from __future__ import annotations

from django.contrib.auth import get_user_model

from profiles.models import ProfileEditLog

User = get_user_model()


def get_viewed_user(username):
    return User.objects.get(username=username)


def can_view_profile(actor_user, target_user):
    return bool(actor_user.is_authenticated)


def can_edit_profile(actor_user, target_user):
    if not actor_user.is_authenticated:
        return False
    is_owner = actor_user == target_user
    is_admin = actor_user.is_staff or actor_user.is_superuser
    return is_owner or is_admin


def profile_view_context(viewed_user, actor_user, leave_credit):
    if not can_view_profile(actor_user, viewed_user):
        return {
            'viewed_user': viewed_user,
            'leave_credits': None,
            'edit_logs': [],
            'can_view_sensitive_profile': False,
        }

    can_view_sensitive_profile = bool(actor_user == viewed_user or actor_user.is_staff or actor_user.is_superuser)
    if actor_user.is_staff:
        edit_logs = ProfileEditLog.objects.filter(user=viewed_user).order_by('-timestamp')
    elif actor_user == viewed_user:
        edit_logs = ProfileEditLog.objects.filter(user=viewed_user).order_by('-timestamp')[:5]
    else:
        edit_logs = []

    return {
        'viewed_user': viewed_user,
        'leave_credits': leave_credit,
        'edit_logs': edit_logs,
        'can_view_sensitive_profile': can_view_sensitive_profile,
    }


def profile_edit_context(viewed_user, actor_user):
    if not can_edit_profile(actor_user, viewed_user):
        return None

    return {
        'viewed_user': viewed_user,
        'is_employee': hasattr(viewed_user, 'employeeprofile'),
        'is_citizen': hasattr(viewed_user, 'citizenprofile'),
        'is_owner': actor_user == viewed_user,
        'is_admin': actor_user.is_staff or actor_user.is_superuser,
    }


def log_edit(target_user, actor_user, profile_type, section, note):
    ProfileEditLog.objects.create(
        user=target_user,
        edited_by=actor_user,
        profile_type=profile_type,
        section=section,
        note=note,
    )
