# Employee custody and clearance design

Published at236c5e1: migration0017, custody services and signed employee
search/review screens are implemented and validated. Clearance is not implemented.
This continues roadmap item4, rather than replacing
GRAND HR with an inventory-owned employee register.

## Verified source

Fetched GSO master60d12af and GRAND32ab046 on2026-10-17. GSO was clean and0/0 before
branch creation. Parallel GRAND has ongoing unpublished Form1 changes; its profile,
user and profile-access files have no local differences from the clean validation
checkout. No parallel source files were edited.

`profiles.EmployeeProfile.user` is a one-to-one relationship to `users.User`.
`assigned_department` is the current department; both identities are numeric local
keys without public UUIDs. The profile contains sensitive personal, salary and tax
fields that custody does not need. `ProfileEditLog` records actor/time/section/note,
not a structured previous/new department or employment-separation event.

Source inspection and a repository-wide Python search found no HR separation,
offboarding or employee-clearance model. The cheque-clearance model is unrelated.
`User.is_active` controls account availability; it does not establish employment
termination. Do not infer an exit from login deactivation, a changed department,
appointment text, names or an unrelated Finance record.

The new read-only `inventory.employee_sources.resolve_employee_custodian` adapter
requires actual GRAND profiles/departments/vouchers, explicit `transfer_asset`
authority, GSO scope and non-UAT access. It applies GRAND's profile-view authority,
accepts only active employee accounts with a department for new custody selection,
and reads only identity/name/department columns. Its fingerprinted snapshot contains
local user/profile/department IDs, username/display name, department label and
explicitly named account_active. No address, tax identifiers, salary, contact,
birthdate or claimed employment status. It neither searches by name nor writes HR,
custody or Finance data. A later write must re-resolve inside its transaction and
compare the reviewed fingerprint.

## Implemented relationships

Migration0017 adds nullable protected custodian relationships to the existing Asset/AssetTransfer
models using `settings.AUTH_USER_MODEL`. GRAND's existing one-to-one employee
profile validates that selected account; retain the observed profile ID and office
in the source snapshot. This reuses the established portable auth dependency and
avoids a separate employee table or a conditional migration dependency on profiles.
Existing asset UUIDs remain inventory identities; new transfer UUIDs use nullable
expansion, per-row backfill and then a unique/non-null constraint. User/profile local IDs
must be explicitly mapped on import into another installation, never assumed equal.

Do not backfill a person from `assigned_office` or destination_custodian text.
Preserve those labels as legacy evidence. Begin named custody only through an
explicit selection with a documented reference and acknowledged transfer. Pin the
selected identity/department snapshot; if the profile changes before acknowledgment,
require review rather than silently changing the intended recipient. A named
recipient must acknowledge their own custody and cannot be the initiating officer;
existing office-level delegation does
not prove that individual accepted it. Preserve the existing legacy office-only
handoff route without inventing a personal signature.

Once an asset has an explicit employee relationship, ordinary register edits cannot
alter its custody label/department or clear the relation. The service also rejects
downgrading it to an office-only free-text handoff. All changes go through
the custody workflow. Existing asset snapshots and transfer source checks now retain
the identity/source so
concurrent handoffs, maintenance and disposal cannot detach identity from history.
HR department changes must flag a review need, not move the asset automatically.

## Clearance sequence — remaining work

The [custody review workbench](custody-review.md) now implements the read-only
retained-assignment prerequisite, published atfb2eae2. [Witnessed returns](custody-returns.md)
are published at2a7bb5f. HR-reference clearance decisions remain unimplemented.

List retained assets by explicit employee identity, including unresolved legacy
records separately instead of claiming a complete employee inventory. Preserve
historical custody even when an account is disabled or a profile disappears. A
new-custody selection failure must never erase an old assignment or imply clearance.

Use a documented HR request/reference for a manually initiated GSO movement/exit
review until GRAND provides an authoritative separation event. Label it as a GSO
review of the supplied request, not an HR employment decision. Record return,
acknowledged handoff or unresolved item with evidence and actors. A return by an
inactive employee needs an authorized witnessed GSO return path; never impersonate
the employee or forge their acknowledgment. Define independent review for that path
before implementation. Outstanding items remain visible and must not be labelled
cleared or silently block unrelated HR actions.

No payment deduction, salary hold, liability valuation or accounting posting follows
automatically from custody or clearance. Finance can refer to explicit asset/custody
identities later, subject to its own authority and source checks.

## Employee search pages — 2026-10-19

The handoff and HR-reference review selectors previously stopped after25 active
matches (and25 linked inactive matches for reviews). A repeated/common-name
search could not reach later eligible accounts. The handoff's POST choices also
used only that first page. This was a lookup limitation, not a new eligibility rule.

Both workflows now show25 accounts per employee page with complete authorized
match counts and Previous/Next employees links. Active results retain the same
minimal directory columns and `can_view_profile` predicate before counting or
paging; hidden candidates cannot consume visible slots or leak through totals.
The helper iterates the minimal matching rows to retain that per-profile policy;
it does not claim production-scale performance. Empty search remains empty.

The handoff carries its employee page through form validation and restricts a
submitted ID to that page's current choices. Invalid details retain the selected
employee and entered facts. A changed selection asks the clerk to search again.
Page metadata is not custody authority: the existing signed actor/asset preview,
native employee snapshot, expiry, source revalidation, idempotent request and
independent recipient acknowledgment remain unchanged. No assignment changes on
search, preview or request creation; acknowledgment owns the existing custody write.

HR-reference employee pages retain the existing active-profile visibility and
inactive-with-explicit-owning-office-custody-history policy. No unlinked inactive
account is added. Inactivity is still an account fact, not termination or clearance.
Employee paging is separate from retained-review paging; both preserve the query
and the other page. The create view rechecks the selected native identity as before.
Read-only UAT users do not gain record/selection authority. No new permission,
model, migration, Finance rule, source identity or automatic grant.

Ten cases in the two existing HTTP/review classes cover all53 active matches,
later-page signed handoff/acknowledgment and retry, invalid form retention,
off-page IDs, source changes, eligibility, profile visibility before totals,
all28 linked inactive accounts and UAT/empty-search boundaries. Unchanged205:
10 tests,9 expected assertion failures/zero errors,3.604s. Corrected frozen proof:
10/10 pass,4.023s,zero skips. One positive fixture initially got the correct403
because it lacked asset-view authority; only its test grants were corrected.
No authorization check or assertion was weakened.

Actual browser proof selects an employee on page2 of3, creates one pending request
without changing custody, then independently acknowledges it as the synthetic
recipient. Exactly one transfer, one audit event and the expected asset custody
fields result. Prior transfers/audits, all other assets, HR cases/events and exact
Finance bytes remain unchanged. A page2 inactive custodian also reaches the HR
request form without a new case. Three screenshots inspected; mobile390 viewport
has375px document width. Original paired fixture/files are untouched and the
browser/owned loopback server are stopped. Synthetic branding/favicon404s and a
private-server idle socket timeout remain fixture limits.

Fresh broad GSO SQLite:439 discovered,408 passed/31 existing native-only skips,
87.788s,exit0; both aliases destroyed, all old identities/classes/shard owners and
seven frozen source hashes verified. No new search case is skipped. Framework and
migration-drift checks pass. A new native run is out of scope for selector/form
paging over unchanged domain writers, models, source identities, locks and routing;
the skipped scenarios are not claimed as passes. Exact commands and local206
checkpoint are in [CONTINUE.md](../../CONTINUE.md). This is not an HR event, official clearance,
financial liability finding, production migration or LGU acceptance. No deployment;
Finance remains **NO-GO** and operational/formal acceptance gates remain open.

## Validation checkpoint

Standalone SQLite: 69 discovered, 60 executed, nine native-only skips; PASS9.882s.
Native MySQL: 69/69 PASS28.912s, including populated0016-to0017 replay and historical
actor deletion guards. The replay preserves original asset/transfer values, assigns
distinct transfer UUIDs and leaves employee links null; no inferred backfill.

Actual GRAND: 44/44 native tests PASS12.481s, including service, HTTP and two new
races (duplicate request IDs; acknowledgment versus cancellation). Existing23 GRAND
W036 warnings remain, none in the GSO apps. Final run after tightened actor/asset
binding assertions and wording changes passed44/44 in11.095s. Disposable schemas
were removed and the owned MySQL server stopped normally. Model/drift
checks for both apps and both environments' dependency checks pass.

Real-browser login, search, signed review/submission and separate recipient
acknowledgment passed. Desktop1440x1000/mobile390x844 inspected; no page horizontal
overflow or duplicate IDs. Handoff tables scroll within their panel. Synthetic GRAND
logo/avatar files are absent (404s). Browser sessions and preview8020 are stopped.

Stopped paired SQLite recovery reconciled196 default/83 finance tables, retained
employee snapshot/accepted actor/audit history, detected injected custody/audit loss,
and restored it without changing the source. Evidence is under
`C:/Users/Administrator/.codex/backups/gsov2-custody-recovery-20261017-nj9xiahl`.
This is not private-upload, online MySQL or operator recovery. No operator migration,
permission grant or installation in GRAND occurred. BranchCI38945305792 passed before master fast-forward/push; remote master/tag
match236c5e1. See the handoff for primary CI status.

## Staff handoff review

Authorized GSO staff search up to25 active employee matches using only name, account
and department fields, then review a signed30-minute preview. The preview binds
actor, asset, current custody, employee fingerprint, reference/date/reason and a
request UUID. Confirmation revalidates source and custody inside the write transaction.
Exact retries return the original handoff even after acceptance or cancellation;
they never recreate it. Named recipients in another GSO office can see their incoming
handoffs without gaining write authority over the owning office. Transfer initiator,
recipient and cancellation actors remain protected from deletion.
