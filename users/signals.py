# this file is so that newly-registered users can have the "defaults" saved in their profiles.
from django.db.models.signals import post_save, post_migrate
# from django.contrib.auth.models import User 	# the auth.models.User version (default)
from .models import User, Profile, Designation, Department
from django.dispatch import receiver 	# receiver


@receiver(post_migrate)
def create_default_designation(sender, **kwargs):
	'''
		making sure to create the default designation before the 1st user registers to the site
	'''
	if sender.name == 'users': # the app/directory where the signal comes from; not a model
		Designation.objects.get_or_create(
			name='Default Designation',
			salary_grade=1,
			salary_grade_step=0
			)


@receiver(post_save, sender=User)	# (arguments == the_signal, sender)
def create_profile(sender, instance, created, **kwargs):
	'''
		a function to automatically create a profile for every time a new user registers/ is created
	'''
	if created:
		default_designation = Designation.objects.get_or_create(
			name='Default Designation',
			salary_grade=1,
			salary_grade_step=0
		)[0]
		default_department = Department.objects.get_or_create(
			name='Default Department',
		)[0]
		Profile.objects.create(
			user=instance,
			designation=default_designation,
			department=default_department,
		)

@receiver(post_save, sender=User)	# (arguments == the_signal, sender)
def save_profile(sender, instance, **kwargs):
	'''
		a function to save the profile
	'''
	print(f"Saving profile for user: {instance.username}")
	instance.profile.save()


from leave_mgt.models import LeaveCredits

@receiver(post_save, sender=Profile) 
def create_leave_credits(sender, instance, created, **kwargs):
    """Creates LeaveCredits for a Profile when the Profile is created."""
    if created:
        LeaveCredits.objects.create(employee=instance)
'''
	after creation of this file, we must save the signals to the app's app.py (users/apps.py)
'''
