# Authentication, account provisioning and dashboard access

Security review requested 2026-10-14. This record covers the primary-branch
implementation; it does not import the outstanding Finance feature branches or
establish production/LGU acceptance.

## Account concept

- Public signup at `/register/` redirects to allauth's `/accounts/signup/`.
  Public password signup creates only `CitizenProfile`, requires email
  verification, and ignores supplied employee/staff/superuser fields. Google
  signup uses the same citizen identity before the first user save. Connecting
  a provider to an existing employee is not public employee provisioning.
- Employees do not self-register. `/users/employee-register/` requires HR
  directory authority plus `users.add_user` (or superuser authority). Its form
  requires an actual department; module permissions remain separate. Internally
  created users without an explicit assignment remain unassigned, rather than
  receiving Mayor's Office authority. Staff flags alone do not confer HR powers.
- Editing another employee's HR fields requires HR directory authority and
  `profiles.change_employeeprofile`. Owners can edit their basic/contact fields;
  client-supplied department, permissions and staff flags are ignored.
- `/dashboard/` derives the office from the authenticated employee profile,
  never request parameters. Employees without an assignment see the pending
  assignment page. Citizens go to `/citizen/dashboard/`, with public services
  and their own profile. `/home/` retains the same safe account routing.
- Employees may see colleagues' masked profiles. Citizens cannot enumerate
  other users' profiles. Internal announcements require employee identity;
  publication requires the model permission. Draft access and author changes
  require the corresponding permission. Public department pages contain only
  office contact information.

## Password guessing and URL probing

`AuthAttemptMiddleware` follows CSRF and authentication middleware. Every POST
attempt shares the default-store counter for its route family, including
`/login/`, `/accounts/login/` and `/admin/login/`. Login permits 30 network
attempts and 10 normalized identity attempts per five-minute window; signup and
password-reset families permit 10 network/5 identity attempts. Root and allauth
password-reset confirmation POSTs are included. Counts include successful and
invalid requests and do not clear when the requester changes cookies or route.

Counters use HMAC digests and ordinary primary-key uniqueness with conditional
SQL increments/reset. They retain neither plaintext identities/IPs nor
passwords. They work across workers without a process-local cache. Exceeding a
limit returns 429 with `Retry-After: 300`; unavailable counter storage returns
503 and prevents authentication. Expiration restores capacity. Run
`python manage.py prune_auth_attempts` daily to remove expired counters older
than one day. The new `users/0002` migration belongs only in the default store;
normal two-store migration routing remains mandatory.

`REMOTE_ADDR` is trusted; user-supplied forwarded IP headers are ignored. IPv6
addresses share a /64 counter. Behind a proxy the network counter can therefore
be shared by all clients using that proxy. The deployment must establish its
trusted edge/client-IP contract and capacity before opening to real municipal
traffic. Edge request limits remain necessary for broad scanning/DoS. A URL is
not a secret: permission checks must deny guessed paths and object/export IDs.
Rate limits bound attempts; they cannot promise that attackers cannot send them.

Django's safe `next` validation, session rotation, POST-only logout, CSRF,
password hashing/validation and password-reset tokens remain in use. The public
password login also checks the verified citizen email, closing the alternate
Django-login verification bypass. Reset responses stay generic even during
email-delivery failure. Sensitive account identities are not written to reset
delivery logs.

## Existing-account reconciliation

The former social signup could create both profiles; user-save signals could
also recreate a cached deleted profile. New signup marks the unsaved user before
profile creation, and saving a user no longer implicitly saves a related
profile. Existing conflicting identities are quarantined with 403 on requests
except logout. Nothing silently deletes HR, leave, service or financial history.

Before rollout, an authorized operator must run
`python manage.py audit_account_identities` against the intended default store
and review the reported IDs against actual HR authority. This command is
read-only. Password signups historically misclassified only as employees cannot
be safely inferred from dates or email domains; reconcile them against the
actual employee roster. No live operator database or grants were changed in
this review. Deploy the migration before serving the middleware.

## Dependency and implementation evidence

The baseline focused suite passed 113 tests. The first new boundary suite
reproduced 12 failed denials/behavior checks and one broken citizen profile URL
across 19 tests, before fixes. A later fixture omitted a unique email and failed
on both stores; the fixture was corrected without relaxing the identity rules.

The initial dependency audit found 25 advisories in PyJWT 2.13.0, pypdf 6.16.1
and urllib3 2.7.0. Updated pins are PyJWT 2.15.1, pypdf 6.19.0 and urllib3 2.8.0.
Django 5.2.18 and allauth 65.19.7 also include current security patches. The
updated audit reports no known vulnerabilities and dependency consistency passes.
References: [Django 5.2.18](https://docs.djangoproject.com/en/5.2/releases/5.2.18/),
[allauth release notes](https://docs.allauth.org/en/latest/release-notes/recent.html),
[allauth rate-limit boundaries](https://docs.allauth.org/en/latest/account/rate_limits.html),
[Django authentication](https://docs.djangoproject.com/en/5.2/topics/auth/default/).

Final validation and publishing evidence is recorded in `CONTINUE.md` and the
pull request. Tests use disposable stores and runtime files. The local native
runner uses separate `test_grand_auth_ci_default` and
`test_grand_auth_ci_finance` schemas on the already-running owned MySQL fixture,
so other Finance test schemas and the existing server lifecycle are preserved.
Google's external OAuth callback, live email delivery, production edge behavior
and real operator acceptance require the configured deployment environment.

The first full regression found 51 calendar-sensitive Finance fixture failures;
all 51 reproduce on untouched primary with its original dependencies. The
shared voucher fixture now anchors its business clock to September 15, 2026
while retaining explicit historical scenario dates and all production date
guards. This repairs the release test harness rather than weakening capacity,
correction or stale-cash checks.

See [platform roadmap](ROADMAP.md), [repository guide](../AGENTS.md) and
[continuation](../CONTINUE.md).

## Reproduction and validation scope

Use Python 3.11 with the pinned requirements. Start with:

```powershell
python manage.py test users profiles departments home leave_mgt
python manage.py test
python scripts/run_mysql_tests.py users profiles departments home leave_mgt
python -m pip check
python -m pip_audit -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
```

The actual local invocations used isolated `.tmp/sqlite_run.py` and
`.tmp/native_auth.py` wrappers around these same Django/native runners, disabling
operator dotenv loading and placing media/exports/backups in disposable paths.
The native wrapper changes only the dedicated test-schema prefix and supplies
private fixture credentials without printing them. The original two-store
runner's fresh migration lifecycle and native race checks remain in use.

Broad regression is required here because auth, profiles, permissions,
middleware, dependency pins and shared navigation affect multiple modules.
The native auth scope covers the new persistent counter and two simultaneous
first-use/expiry races. The full CI MySQL job provides broader native regression.
Google adapter provisioning is exercised offline; configured OAuth, email and
proxy acceptance are separate environmental checks and are not counted as passes.
