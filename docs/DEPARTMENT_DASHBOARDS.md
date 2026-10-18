# Department starting pages

The October 14, 2026 user-requested auth/dashboard pass supplies one responsive
GRAND presentation for employee, citizen and assignment-pending dashboards.
It uses the existing configured institution, primary color and accent color.
Cards show real configured workspaces and live aggregates, with explicit
nonclickable Planned or Permission required states for unfinished/restricted work.

Twenty presets cover MSWD, HR, GSO, Accounting, Budget, Treasury, Planning,
Engineering, Health, Agriculture, Civil Registry, Assessor, Business Permits,
Disaster Risk Reduction, Environment, Mayor, Sangguniang Bayan, PESO, Tourism
and ICT. Common slug aliases select descriptions only; they do not grant roles
or change department identities. Unknown offices use the generic starting page.
No offices, permissions or operator data are seeded automatically.

Finance card aggregates use the workbench's existing case visibility, including
completed history: requesting-office clerks' counts exclude other offices' cases,
while existing UAT broader read access is preserved. See the [clerk handoff evidence](FINANCE_CLERK_HANDOFFS_2026-10-14.md)
for the red reproduction, repair, real-route comparison and acceptance boundary.

The local Asset-cost worksheets entry reuses its workbench permission and exact
current GSO-owner/explicitly shared Accounting scope. Its review-status counts include
retained history and are not financial values or approval authority. UAT may read
without acquiring mutation rights. Actors without the separate module grant retain
their other authorized workspaces. See [the worksheet contract](gso/asset-cost-allocations.md)
and CONTINUE.md for current validation and publication state.

Accounting, Budget, collection, reporting, record, custody, Finance setup and
voucher links reuse their existing access helpers. HR leave administration links
to the actual management screen only when authorized. Everyday employee links
cover their own profile/leave and announcements. Employee account creation is
visible only to authorized HR account managers. Citizen navigation offers public
services, their profile and public announcements; HR provisioning explains the
separate employee path. Public office detail/directory pages contain contact
information rather than an internal dashboard.

Public signup/sign-in templates retain allauth verification, forms, CSRF and
safe return URLs. Employee sign-in uses Django's validated form, surfaces errors
and links to the correct named password-reset URL. Google remains a citizen
option through allauth's confirmation flow. The layout supports mobile cards,
visible keyboard focus, labeled navigation and browser zoom.

Run `python manage.py test departments users profiles home leave_mgt assistance
social_welfare reporting records tracepoint finance.test_operations` for affected
integration coverage. Full SQLite/security and fresh MySQL CI regression remain
release gates. See [auth boundaries](AUTH_SECURITY.md), [roadmap](ROADMAP.md)
and [actual validation/publishing status](../CONTINUE.md). Desktop/mobile browser
checks use synthetic users and disposable stores; they are not LGU acceptance.
