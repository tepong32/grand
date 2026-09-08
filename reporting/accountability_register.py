"""Shared current-office selectors for accountability source records and actions."""
from .access import (
    can_view_reporting, department_for_user, can_manage_accountability_profiles,
    can_approve_accountability_profiles, can_prepare_accountability_packages,
    can_review_accountability_packages,
)
from .models import FinanceAccountabilityPackage, FinanceAccountabilityPackageProfile


ACTION_SPECS = {
    "profile_prepare": ("profile", "Prepare or correct accountability profile", can_manage_accountability_profiles, False),
    "profile_review": ("profile", "Review or return accountability profile", can_approve_accountability_profiles, True),
    "package_prepare": ("package", "Select or correct accountability evidence", can_prepare_accountability_packages, False),
    "package_review": ("package", "Review or return accountability package", can_review_accountability_packages, True),
}


def visible_accountability_records(user, kind):
    model = {"profile": FinanceAccountabilityPackageProfile, "package": FinanceAccountabilityPackage}[kind]
    if not can_view_reporting(user):
        return model.objects.none()
    return model.objects.filter(department=department_for_user(user))


def accountability_action_queryset(user, action):
    kind, _label, allowed, review = ACTION_SPECS[action]
    records = visible_accountability_records(user, kind)
    if not allowed(user):
        return records.none()
    model = records.model
    if review:
        return records.filter(status=model.SUBMITTED).exclude(created_by=user).exclude(submitted_by=user)
    return records.filter(status__in=(model.DRAFT, model.RETURNED))
