# Finance operations entry

Status: F1.2 implemented navigation control. This page makes the existing complete-cycle workspaces easier to find; it does not create a new transaction, approval, balance, or authority layer.

## What staff receive

`/finance/` is the stable Finance starting page. Its cards are assembled from the same existing access checks used by Budget, Voucher Workbench, Accounting, Reporting, Finance Setup, Decisions and evidence, and Shadow/cutover workspaces.

- A normal Finance user sees only workspaces already available to the account's department and permissions.
- Reporting access alone does not classify a general employee as a Finance user.
- A named cross-office field reviewer may reach Field acceptance without receiving Finance setup or transaction authority.
- Existing direct workspace links remain in the account drawer for familiar, low-friction access.
- Each destination continues to enforce its own permission and object/department checks after navigation.

The page deliberately shows no synthetic totals, copied case lists, inferred notifications, or second set of workflow states. The existing domain workspaces remain the source of their filters, next actions, histories, and exports.

## Internal How-To

The seeded `Find and continue your Finance work` guide matches the operations entry page and is published separately for each department. It explains the shared-case handoff, governed modification boundary, role-shaped next actions, TraceSync-ready export handling, and the private tutorial-progress boundary.

Run `python manage.py seed_internal_howtos` after deployment to publish the starter where no equal or newer local version exists. Existing newer local instructions are preserved.

## Boundaries

- A card proves only that the current account may open that workspace; it does not grant every action within it.
- Before voucher/check issuance, only the applicable reason-required modification route may be used. Issued checks, posted JEVs, locked evidence, and recorded decisions use cancellation, replacement, reversal, successor, or another governed correction route.
- Tutorial checkmarks are optional personal resume state, not attendance, competence, approval, UAT, or employee-evaluation evidence.
- A portable export is evidence/interchange, not automatically an official form, statutory filing, database backup, or authority decision.
- F1 still requires named-user role walkthroughs, supported-device/accessibility observation, local security/privacy review, recovery evidence, and acceptance before its parent exit gate can be claimed.

## Regression contract

Automated coverage verifies full and selective Finance-card composition, denial for ordinary/reporting-only employees, anonymous redirection, preservation of established Finance URL paths, and field-only navigation for an assigned cross-office reviewer.
