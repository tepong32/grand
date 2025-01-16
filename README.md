# grand
working on yet another "to-be-continued/discarded" project

## user profiling *(...tbc for external users)*
	**automatic profile creation (with defaults on user registration)**
	**password changes and resets now working properly**
		used mailtrap (https://mailtrap.io) for testing pw reset emails

	- will work on separating registering users: internal vs external
	- will need to work on allauth for external users

## leave (remodelling) - ***(already-working logic, just needs adjustments for dividing days to hours or minutes)***
	
	**separating views based on user roles applied on template instead of thru mixins**
	**automated deduction of number_of_days from current_yr_XX_credits upon saving an "Approved" request.**
	**automated leave calculation with regard to excluding weekends on date ranges.**
		might need to have a way to adjust days as "non-working holiday", as well. will figure that out later on "working days" branch.
	**validation for making sure start_date < end_date.**
	**added global context thru an additional context_processor so variable usage are consistent.**
	**server-side cron jobs working as intended, just need to check variations of server time vs local time**

	- create leave accumulation policies (if needed)
 		atm, we just need to change its default in the admin UI: SL_Accrual and VL_Accrual
	- might need to convert leave credits to a per-15min basis so lates can be automatically be covered by leave credits (for private companies, perhaps)

## announcements **(almost complete)**
	**public, internal, pinned, drafts vs posted, etc**

	- just change the display for the users

## salary (remodelling) - *not yet started*
	- will need a solid backend logic for this one since it will affect all the other models from other apps

## working days - *not yet started*
	- this needs to be configured as to make sure that non-working holidays will automatically integrated to salary computations
	- might also affect leave credits for users if they are to request paid absences or lates

