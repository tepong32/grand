### grand
working on yet another "to-be-continued/discarded" project

# user profiling *(okay...almost)*
	- **automatic profile creation (with defaults on user registration)**
	- still needs to check on password-related stuffs (user-initiated change pw, reset pw, etc.)

# leave (remodelling) - ***(...in progress)***
	- **cron jobs for automated leave credits accruals and carry-overs**
	- **logic of separating templates to be displayed are handled by a custom mixin in the views are applied.**
		will also apply it on other apps' views as well, if needed.
	- create leave accumulation policies (if needed)
 		atm, we just need to set it on settings.py (MONTHLY_SL_ACCRUAL and MONTHLY_VL_ACCRUAL)
	- might need to convert leave credits to a per-15min basis so lates can be automatically be covered by leave credits (for private companies, perhaps)
	

# salary (remodelling) - *not yet started*
	- will need a solid backend logic for this one since it will affect all the other models from other apps

# working days - *not yet started*
	- this needs to be configured as to make sure that non-working holidays will automatically integrated to salary computations
	- might also affect leave credits for users if they are to request paid absences or lates

