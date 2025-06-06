from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.socialaccount.models import SocialAccount
from django.core.exceptions import ObjectDoesNotExist
from .models import User
from profiles.models import EmployeeProfile, CitizenProfile
from departments.models import Department
from leave_mgt.models import LeaveCredit
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically creates a CitizenProfile (for social auth) or EmployeeProfile (for regular users)
    when a new User is created.
    """
    if not created:
        return

    try:
        # Case 1: Signed up via SocialAccount (e.g., Google, Facebook) -> CitizenProfile
        if SocialAccount.objects.filter(user=instance).exists():
            CitizenProfile.objects.create(user=instance)
            logger.info(f"✅ CitizenProfile created for user: {instance.username}")
            return

        # Case 2: Internal Employee -> assign default department
        default_department, _ = Department.objects.get_or_create(name="Mayor's Office")
        EmployeeProfile.objects.create(
            user=instance,
            assigned_department=default_department,
        )
        logger.info(f"✅ EmployeeProfile created for user: {instance.username}")

    except Exception as e:
        logger.error(f"❌ Error creating profile for user {instance.username}: {e}")


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save the related profile (Employee or Citizen) whenever the User is saved.
    """
    try:
        if hasattr(instance, 'employeeprofile'):
            instance.employeeprofile.save()
        elif hasattr(instance, 'citizenprofile'):
            instance.citizenprofile.save()
        logger.info(f"💾 Profile saved for user: {instance.username}")
    except Exception as e:
        logger.error(f"❌ Error saving profile for user {instance.username}: {e}")


@receiver(post_save, sender=EmployeeProfile)
def create_leave_credit_for_employee(sender, instance, created, **kwargs):
    """
    Automatically create LeaveCredit when an EmployeeProfile is created.
    """
    if created:
        try:
            LeaveCredit.objects.create(employee=instance)
            logger.info(f"✅ LeaveCredit created for employee: {instance.user.username}")
        except Exception as e:
            logger.error(f"❌ Error creating LeaveCredit for {instance.user.username}: {e}")
