# Finance operations entry

Status: F1.2–F1.5 foundation and source adapters implemented: navigation, shared-case finder, private saved-view controls, and a permission-filtered work-attention overview with exact setup, discovery, field-operation, bank-advice, returned-payment, period-close/reopen, cash-policy, and cash-position handoffs. These pages make existing complete-cycle workspaces and authorized case timelines easier to find and resume; they do not create a new transaction, approval, balance, search index, assignment, notification, or authority layer.

## What staff receive

`/finance/` is the stable Finance starting page. Its cards are assembled from the same existing access checks used by Budget, Voucher Workbench, Accounting, Reporting, Finance Setup, Decisions and evidence, and Shadow/cutover workspaces.

- A normal Finance user sees only workspaces already available to the account's department and permissions.
- Reporting access alone does not classify a general employee as a Finance user.
- A named cross-office field reviewer may reach Field acceptance without receiving Finance setup or transaction authority.
- Existing direct workspace links remain in the account drawer for familiar, low-friction access.
- Each destination continues to enforce its own permission and object/department checks after navigation.

The entry page deliberately shows no synthetic transaction totals, copied case lists, inferred notifications, or second set of workflow states. Its Work needing attention link opens the separately documented F1.5 read model; existing domain workspaces remain the source of every filter, next action, history, and export.

## Shared-case finder

Users who may open Voucher Workbench receive a case finder on `/finance/`. It hands the normalized query to the existing role-shaped workbench rather than querying through a second index. The workbench applies department/role visibility first and then matches up to eight safe tokens or an exact controlled identifier.

Supported search evidence includes the case reference, safe payee/purpose, transaction type, requesting/current office, OBR/obligation, claim, DV, JEV, check, receipt, advice, and exact case/payment/advice/posting UUID. Exact 64-character locks may match the authorized case's obligation, posting payload/rule, or controlled-output checksum.

The same filter service drives the on-screen queue and authorized case-register/custody exports. A hidden case contributes no result, option, or count; the page makes no existence suggestion. A search result opens the existing shared case, whose detail page already carries Budget authority, claim/DV, Accounting handoffs, payment/advice/release, custody/output, and permitted append-only history.

## Private saved case views

An authorized workbench user can give the current case filters a short name and reopen them later. Saving the same name, without regard to capitalization, updates that user's shortcut. Removing it deliberately deletes only the preference; it is not financial or acceptance evidence and therefore does not enter the immutable transaction timeline.

Each user may retain up to 25 views. Names and filter choices are editable by the owner, and ordinary users cannot retain the UAT-only office-preview field. Every open runs the stored choices through current authentication, workbench role, department visibility, and fail-closed filter validation. A former office, role, or permission therefore cannot remain accessible through an old shortcut.

These views are private conveniences. They do not assign work, create a notification, affect counts outside the authorized result, approve a case, authorize an export, or become governed shared filters. F1 governed shared views and notifications remain separate future work that requires named ownership and local acceptance rules.

## Internal How-To

The seeded `Find and continue your Finance work` guide matches the operations entry page and is published separately for each department. Version 3 explains the permission-filtered case finder, private saved-view controls, shared-case handoff, governed modification boundary, role-shaped next actions, TraceSync-ready export handling, and the private tutorial-progress boundary.

Run `python manage.py seed_internal_howtos` after deployment to publish the starter where no equal or newer local version exists. Existing newer local instructions are preserved.

The F1.5 page also receives a separate department-kind guide for requesting offices, Budget, Accounting, or Treasury. See [Finance work-attention foundation](FINANCE_MY_WORK.md) for its exact adapter and deferral boundaries.

## Boundaries

- A card proves only that the current account may open that workspace; it does not grant every action within it.
- Before voucher/check issuance, only the applicable reason-required modification route may be used. Issued checks, posted JEVs, locked evidence, and recorded decisions use cancellation, replacement, reversal, successor, or another governed correction route.
- Tutorial checkmarks are optional personal resume state, not attendance, competence, approval, UAT, or employee-evaluation evidence.
- A portable export is evidence/interchange, not automatically an official form, statutory filing, database backup, or authority decision.
- F1 still requires named-user role walkthroughs, supported-device/accessibility observation, local security/privacy review, recovery evidence, and acceptance before its parent exit gate can be claimed.

## Regression contract

Automated coverage verifies full and selective Finance-card composition, denial for ordinary/reporting-only employees, anonymous redirection, preservation of established Finance URL paths, field-only navigation for an assigned cross-office reviewer, safe multi-token/controlled-ID matching, zero-result isolation for another requesting office's known case reference, private save/open/update/remove behavior, owner isolation, current-scope rechecks, exact shared-case attention parity, UAT preview exclusion, and page-relevant floating guidance.
