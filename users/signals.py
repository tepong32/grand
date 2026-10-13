from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User
from profiles.models import CitizenProfile, EmployeeProfile
from leave_mgt.models import LeaveCredit

import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Public adapters mark the unsaved user before its first save. Internal
    provisioning retains an employee profile; assignment is a separate decision.
    """
    if not created:
        return

    try:
        if getattr(instance, '_public_signup', False):
            CitizenProfile.objects.create(user=instance, social_auth=getattr(instance, '_social_signup', False))
            logger.info("CitizenProfile created for user: %s", instance.username)
            return

        EmployeeProfile.objects.create(user=instance)
        logger.info("EmployeeProfile created for user: %s", instance.username)
    except Exception:
        logger.exception("Identity profile provisioning failed")
        raise


@receiver(post_save, sender=EmployeeProfile)
def create_leave_credit_for_employee(sender, instance, created, **kwargs):
    """Create leave credit row for new employee profiles."""
    if created:
        try:
            LeaveCredit.objects.create(employee=instance)
            logger.info("LeaveCredit created for employee: %s", instance.user.username)
        except Exception as e:
            logger.error("Error creating LeaveCredit for %s: %s", instance.user.username, e)
