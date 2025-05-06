from django.db.models.signals import post_save
from django.dispatch import receiver
from allauth.socialaccount.models import SocialAccount
# from django.contrib.auth.models import User 	# the auth.models.User version (default)
from .models import User, EmployeeProfile, Department, CitizenProfile
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User )
def create_profile(sender, instance, created, **kwargs):
    '''
    Automatically create a profile for every time a new user registers/ is created
    '''
    if created:
        # Check if the user has a SocialAccount (indicating they registered via allauth Links)
        if SocialAccount.objects.filter(user=instance).exists():
            # Create a CitizenProfile for outsiders
            CitizenProfile.objects.create(user=instance)
            logger.info(f"CitizenProfile created for user: {instance.username}")
            return  # Skip further processing for outsiders

        # Logic for organization users
        default_department = Department.objects.get_or_create(
            name='Default Department',
        )[0]
        EmployeeProfile.objects.create(
            user=instance,
            department=default_department,
        )
        logger.info(f"EmployeeProfile created for user: {instance.username}")

@receiver(post_save, sender=User )
def save_profile(sender, instance, **kwargs):
    '''
    A function to save the profile
    '''
    logger.info(f"Saving profile for user: {instance.username}")
    if hasattr(instance, 'employeeprofile'):
        instance.employeeprofile.save()
    elif hasattr(instance, 'citizenprofile'):
        instance.citizenprofile.save()

@receiver(post_save, sender=EmployeeProfile) 
def create_leave_credits(sender, instance, created, **kwargs):
    """Creates LeaveCredits for a Profile when the Profile is created."""
    if created:
        LeaveCredit.objects.create(employee=instance)