# this file is so that newly-registered users can have the "defaults" saved in their profiles.
from django.db.models.signals import post_save	# a signal that gets fired whenever an object is saved
from .models import User, Profile
from django.dispatch import receiver 	# receiver




@receiver(post_save, sender=User)	# (arguments == the_signal, sender)
def create_profile(sender, instance, created, **kwargs):
	'''
		a function to automatically create a profile for every time a new user registers/ is created
	'''
	if created:
		Profile.objects.create(user=instance)

@receiver(post_save, sender=User)	# (arguments == the_signal, sender)
def save_profile(sender, instance, **kwargs):
	'''
		a function to save the profile
	'''
	instance.profile.save()

'''
	after creation of this file, we must save the signals to the app's app.py (users/apps.py)
'''
