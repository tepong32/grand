# Asset maintenance

## Closed-record correction notices — local development, 2026-10-18

`codex/gso-maintenance-notices` starts at local VM v0.7.177 / `04f6200`; it is
unpublished and does not change GRAND's remote v0.7.176 baseline. The new notice
workflow addresses a concrete closed-record limitation without rewriting its
original outcome. [GRAND's handoff](../../CONTINUE.md) owns actual verification.

A manager with the existing explicit maintenance grant may retain an attributable
statement against a completed or cancelled case, with its basis/reference and an
optional private PDF/image. A viewer, including a separately authorized UAT viewer,
can read history and retained files but cannot record notices. No new grants or
approval authority are introduced. Source metadata is observed and pinned; this
does not certify the original supporting bytes or establish an approved correction.

The original closure, cost, dates, status, asset history and events remain unchanged.
The notice is immutable, actor/time-stamped and checksum-backed. A mistaken notice
requires another statement, not deletion or replacement; none automatically becomes
the effective truth. The work-record page warns before displaying original values
and pages all notices. Current consumers of documented cost are confined to that
page/history; no Finance integration or quantity/valuation calculation is added.
Applying corrected values remains [DECISION-GSO-003](../IMPLEMENTATION_DECISIONS.md#consolidated-owner-decisions--2026-10-18).

Asset-before-case locks serialize creation and the shared 20-document/100 MB case
budget; reference-only notices remain possible when no additional file can be
retained. Every file is at most 15 MB. A signed actor/case/source-bound request and
unique UUID provide exact retries without duplicate notices/files. Record/body
tampering is detected; valid file downloads verify hash/size and stream the same
handle through the shared private-evidence helper.

Migration0030 adds one default-store table, its foreign keys and an unconditional
file-metadata check. It rewrites no old case, event, asset or Finance row and creates
no model permissions. `inventory/maintenance_notices/<case UUID>/` is a separate
private namespace; interrupted writes may leave an orphan, which is investigated
rather than automatically removed. Coordinated recovery must retain it alongside
the existing maintenance namespace and database. Run both
`check_maintenance_evidence` and `check_maintenance_notices`; the latter verifies
notice/source metadata, file hashes/sizes and orphan paths without changing data.
No production migration, official approval or operational acceptance is implied.

The original `codex/asset-maintenance` workflow below was carried into GRAND at
v0.7.174. [GRAND's handoff](../../CONTINUE.md) records current code/release status;
code integration does not establish installation or operational acceptance.

The operational record follows an existing asset through a reported concern, work
updates, retained supporting documents and completion or cancellation. It is not a
procurement approval, payment certification, capitalization decision or official COA
form. See [COA scope](coa-requirements.md), [integration design](grand-integration-design.md)
and [roadmap](inventory-roadmap.md).

## Record and authority

`AssetMaintenanceCase` has a public UUID and protected asset/actor relationships in
`default`. Reported date, problem, provider label, work, optional documented cost,
cost reference and closure outcome are retained. Unknown cost is distinct from zero.
Cost uses GRAND's 18-digit, two-decimal shape; it never changes acquisition cost.
Provider text is descriptive evidence, not a `FinanceParty` identity or implicit
voucher match. No Finance, Accounting or Budget writes occur.

The explicit `manage_assetmaintenancecase` permission permits GSO staff to open,
update, attach evidence and close cases in their asset owner's office. The separate
`view_assetmaintenancecase` permission permits reading. No grants are automatic.
When GRAND's vouchers app is installed, management also requires its explicit grant
check and excludes Finance UAT viewers. Custodian office alone does not authorize
maintenance writes or private-document access.

Migration0016 adds three tables and two constraints; it does not rewrite existing
assets or financial records. The nullable virtual generated marker plus ordinary
unique constraint allows one open case per asset on SQLite and MySQL, while keeping
all completed/cancelled history. The existing user and asset are protected rather
than copied into new identity tables.

## Workflow

Open from the asset detail. Starting a case sets the asset under maintenance and
retains its prior status. A retired asset or an asset with an open transfer/disposal
case cannot start maintenance. All service operations lock the asset before the
case; ordinary register edits, transfer starts and disposal starts check that same
lock before rejecting an open maintenance case. Custody remains unchanged.

Save work details before completing. Completion requires recorded work, a finish
date between report date and today, an explanation, and a choice of returned to
service or still unserviceable. A positive documented cost additionally needs a
reference and supporting file. Completion closes the case even if further work is
needed; another case can record the later repair. Cancellation requires a reason
and restores the pre-case asset status, including a legacy maintenance status.

Version checks reject stale writes. Duplicate starts and duplicate closure cannot
create a second outcome. Each change appends an actor-stamped snapshot; status
changes also append the existing asset audit trail. Closed cases are read-only.
Authoritative replacements for closed values are not implemented; the local notice
workflow above records statements without replacing values. Do not erase history or
reopen closed rows directly. Model save/delete guards protect event/evidence use
through the application, not arbitrary privileged SQL access.

## Evidence and recovery

Files use the existing private storage root under `inventory/maintenance/<uuid>/`.
The existing PDF/JPEG/PNG/WebP validator applies, with 15 MB per file, 20 documents
per case and 100 MB total. SHA-256, byte count, original name, explanation, actor and
time are retained. Downloads require scoped access, force attachment delivery and
send no-store/nosniff headers. Closure checks every retained file for presence and
integrity, including cancellation. Restore or investigate damaged evidence first.

Database transactions do not roll filesystem writes back. An interrupted upload can
leave an unreferenced private file, which must be investigated rather than deleted
automatically. A database-only restore is insufficient; preserve the private
maintenance namespace alongside the operational database under GRAND's coordinated
recovery plan. Run `python manage.py check_maintenance_evidence` against the restored
database and private root. It reports missing, changed, unsafe and unreferenced paths
as JSON and fails if investigation is needed; it does not delete or repair anything.
The existing receiving checker shares the same local-storage inspection logic.

## Validation checkpoint

The expanded standalone suite passes65/65 on MySQL8.4.11 (15.703s); SQLite runs56
with nine native-only skips (7.048s). Coverage includes lifecycle conflicts,
permissions, stale versions, retained history, evidence corruption/loss/orphans,
rollback, document scope, CSRF, staff HTTP flow, three maintenance races and a
populated0015-to0016 upgrade preserving all pre-existing inventory tables.

Actual-GRAND SQLite integration passes29 discovered/24 executed/five native-only
skips. Maintenance tests use real profiles, explicit grants including superuser/UAT
denial, and prove no Finance-store queries. Browser login/open/work/upload/complete
was exercised at1440x1000 and390x844; completed mobile has no horizontal overflow or
duplicate IDs. Screenshots: `output/playwright/maintenance-*.png`.
Final actual-GRAND MySQL integration passes29/29 in8.430s. Its23 pre-existing W036
conditional-uniqueness warnings remain; none belong to inventory/inventory_finance.

Stopped synthetic SQLite plus private-file recovery reconciled all37 tables and the
one retained document, recovered deliberately corrupted/missing restored-copy
evidence, and left source hashes unchanged. Manifest and copies:
`C:/Users/Administrator/.codex/backups/gsov2-maintenance-recovery-20261017-nzu80ff7`.
This is not an online MySQL or operator-data restoration claim. The handoff and
[validation record](validation-2026-10-16.md) own final native GRAND/release results;
no production acceptance or full COA compliance is asserted.
