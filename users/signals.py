from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.socialaccount.models import SocialAccount

from .models import User
from profiles.models import CitizenProfile, EmployeeProfile
from departments.models import Department
from leave_mgt.models import LeaveCredit

import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create CitizenProfile for social-auth users, otherwise create EmployeeProfile.
    """
    if not created:
        return

    try:
        if SocialAccount.objects.filter(user=instance).exists():
            CitizenProfile.objects.create(user=instance)
            logger.info("CitizenProfile created for user: %s", instance.username)
            return

        default_department, _ = Department.objects.get_or_create(name="Mayor's Office")
        EmployeeProfile.objects.create(
            user=instance,
            assigned_department=default_department,
        )
        logger.info("EmployeeProfile created for user: %s", instance.username)
    except Exception as e:
        logger.error("Error creating profile for user %s: %s", instance.username, e)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save related profile whenever user is updated."""
    try:
        if hasattr(instance, 'employeeprofile'):
            instance.employeeprofile.save()
        elif hasattr(instance, 'citizenprofile'):
            instance.citizenprofile.save()
        logger.info("Profile saved for user: %s", instance.username)
    except Exception as e:
        logger.error("Error saving profile for user %s: %s", instance.username, e)


@receiver(post_save, sender=EmployeeProfile)
def create_leave_credit_for_employee(sender, instance, created, **kwargs):
    """Create leave credit row for new employee profiles."""
    if created:
        try:
            LeaveCredit.objects.create(employee=instance)
            logger.info("LeaveCredit created for employee: %s", instance.user.username)
        except Exception as e:
            logger.error("Error creating LeaveCredit for %s: %s", instance.user.username, e)
