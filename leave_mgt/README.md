# Leave credit policy

Grand stores leave rules in the active `LeavePolicy` row. The seeded policy preserves the previous monthly default of 1.20 sick-leave and 1.20 vacation-leave credits, grants 10 special-leave credits at the annual rollover, accepts half-day requests, leaves sick carry-over uncapped, and caps vacation carry-over at 20 days.

## Predictable automation

The production cron entry runs daily at midnight. Monthly accrual and yearly carry-over transactions have database uniqueness constraints keyed by employee, leave type, and period. Running the cron or management command repeatedly in the same period therefore does not grant credits twice.

```powershell
.\env\Scripts\python.exe manage.py update_leave_credits
```

Approved requests deduct carried credits first, then current-year credits. Cancelling or changing an approved request creates an exact reversal from the original transaction split.

## Who may manage credits

The leave management screen is available to:

- superusers;
- the user assigned as head/OIC of the department whose slug is `hr`;
- users granted the `leave_mgt.manage_leave_credits` permission.

Policy changes create a new version and retain inactive history. Manual adjustments require a reason, must follow the policy increment, record the actor, and cannot make a total balance negative.

## Half-day requests

Employees can choose a morning or afternoon half-day when the request starts and ends on the same working day. Multi-day requests remain whole working days. If a policy changes the minimum increment to one day, the half-day choices are removed and service validation rejects half-day submissions.
