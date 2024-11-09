# grand
working on yet another "to-be-continued/discarded" project

## user profiling *(okay...almost)*
	**automatic profile creation (with defaults on user registration)**
	- still needs to check on password-related stuffs (user-initiated change pw, reset pw, etc.)

## leave (remodelling) - ***(...in progress)***
	**cron jobs for automated leave credits accruals and carry-overs**
	**separating views based on user roles applied on template instead of thru mixins**
	**automated deduction of number_of_days from current_yr_XX_credits upon saving an "Approved" request.**
	**automated leave calculation with regard to excluding weekends on date ranges.**
		might need to have a way to adjust days as "non-working holiday", as well. will figure that out later on "working days" branch.
	**validation for making sure start_date < end_date.**
	**added global context thru an additional context_processor so variable usage are consistent.**

	- create leave accumulation policies (if needed)
 		atm, we just need to change its default in the admin UI: SL_Accrual and VL_Accrual
	- might need to convert leave credits to a per-15min basis so lates can be automatically be covered by leave credits (for private companies, perhaps)
	

## salary (remodelling) - *not yet started*
	- will need a solid backend logic for this one since it will affect all the other models from other apps

## working days - *not yet started*
	- this needs to be configured as to make sure that non-working holidays will automatically integrated to salary computations
	- might also affect leave credits for users if they are to request paid absences or lates

