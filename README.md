### grand
working on yet another "to-be-continued/discarded" project

# user profiling *(okay...almost)*
	- automatic profile creation (with defaults on user registration)
	- still needs to check on password-related stuffs (user-initiated change pw, reset pw, etc.)

# leave (remodelling) - ***(...in progress)***
	MAKE SURE TO READ HOW-TO CELERY DOCS [like this one](https://www.geeksforgeeks.org/celery-integration-with-django/). Related files seems to be working on runserver commands but are experiencing access-denied errors.
	- here's where the logic of separating templates to be displayed are handled by a custom mixin in the views are applied.
		will also apply it on other apps' views as well, if needed.
	- celery processes already setup for background works:
		checking leave accumulation and carry-overs (need to be checked if working properly)
	- leave accumulation policies (if needed)
	- might need to convert leave credits to a per-15min basis so lates can be automatically be covered by leave credits (for private companies, perhaps)
	

# salary (remodelling) - *not yet started*
	- will need a solid backend logic for this one since it will affect all the other models from other apps

# working days - *not yet started*
	- this needs to be configured as to make sure that non-working holidays will automatically integrated to salary computations
	- might also affect leave credits for users if they are to request paid absences or lates

