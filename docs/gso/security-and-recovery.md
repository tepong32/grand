# Security and recovery boundary

This shell is for controlled development. A release is not permission to expose it
to the internet or an assertion that LGU operational acceptance has passed.

## Implemented checkpoint

- Django 5.2.18, Pillow 12.3.0 and python-dotenv 1.2.2 match the inspected GRAND
  application requirements. Django's [5.2.18 security release](https://docs.djangoproject.com/en/5.2/releases/5.2.18/)
  is the verified framework target. Continue dependency audits; a clean audit is
  only a known-vulnerability check, not a penetration test.
- `DEBUG=0` refuses a missing/weak secret, missing/wildcard host list, or missing/
  publicly located private-evidence root. HTTPS redirect, secure session/CSRF
  cookies, HSTS and frame denial are enabled. Development still defaults to DEBUG=1;
  explicitly select production settings. Subdomain HSTS/preload remain off until
  the deployment's complete domain is validated.
- `GSO_DATABASE_PATH` allows disposable test/rehearsal databases without moving the
  operator database. No operator migration is performed by a code release.
- Stock ownership is enforced in list/detail/export and write services. The
  original GSO-wide stock query was broader than its owning department. Service
  inputs now reject replacing identity, ownership and actor fields.
- Runtime SQLite, private evidence and new user uploads are excluded from Git.
  Untracking current data does not remove historical Git objects or revoke any
  credentials previously published. No history rewrite or credential rotation
  is claimed. Before production use, inspect historical exposure privately and
  replace any real credentials/accounts that were distributed in a prototype DB.

## Verified historical database exposure — 2026-10-17

Read-only inspection at master89890e1 found nine distinct `db.sqlite3` blobs
reachable through origin/master history. Each contains two account rows, one
superuser row, at least one usable password-hash record and session rows. All nine
passed SQLite integrity_check. Inspection used in-memory, query-only SQLite and
exported aggregate metadata only; no account identifiers, password hashes or
session contents were printed or copied into documentation. Current tracked files
contain neither `.env` nor SQLite databases. This confirms historical exposure;
it does not establish real credential reuse, current session validity or compromise.
The bounded check is not a comprehensive historical secret/media scan.

Integration decision: never import prototype users' authentication credentials,
sessions, tokens or privileges into GRAND. Use native GRAND accounts with explicit
reviewed identity mappings for business history. Do not substitute invented users
or silently rewrite historical actor snapshots/checksums. No data importer exists
yet, so this is a required import acceptance condition, not an implemented filter.

Operator confirmation2026-10-17: prototype credentials were isolated and were not
reused in GRAND or any live system. Record that disposition; do not continue treating
credential reuse as an unanswered blocker or request live rotation on this evidence.
Historical copies still contain prototype authentication/private data, so the import
exclusion and controlled handling remain. Signing-secret reuse was not separately
verified by the bounded source check. No live credential rotation,
session revocation, history rewrite or removal from existing clones is claimed.
Historical release evidence and operator databases remain untouched.

## Recovery approach aligned with GRAND

Clerical receipt quantity corrections add private packets under
`inventory/receipt-quantity-corrections/`. Preserve these with the original delivery
packets, correction/predecessor/events, result stock movements and exact source-lot
allocations or erroneous-asset audit event. Run
`python manage.py check_receipt_quantity_correction_evidence` against stopped-write
or restored storage. It reports file integrity/orphans without repairing anything;
application verification also checks retained event/result snapshots and chains.
Reject/cancel may release a pending hold when a file is missing, but cannot approve
a physical adjustment. A filesystem write surviving database rollback is retained
for investigation, never automatically deleted. See the
[workflow and release gates](receipt-quantity-corrections.md).

Use GRAND's `docs/DATABASE_BACKUP.md` at integration. It captures default and
finance as separate native dumps under one verified same-server MySQL read lock;
two independently timed snapshots are not an accepted equivalent. GSO tables join
default, not a third authority database. Uploaded evidence and exports need their
own coordinated protected backup; GRAND's database backup alone does not contain
those files. Do not build a separate GSO cloud-sync service.

For this standalone shell, before migrations or imports:

1. Pause application writes/jobs in a controlled maintenance window. Preserve an
   exact operator copy and create a SQLite backup using its backup API; do not copy
   only the main database while ignoring a live WAL.
2. Capture `DISPOSAL_PRIVATE_ROOT`, required media and retained exports to a
   restricted location outside Git/web roots. Record file sizes and SHA-256 hashes.
   Keep configuration/secrets separately protected, with limited restore access.
3. Restore to an isolated database/storage directory. Check SQLite integrity,
   migration state, asset and stock counts/balances, and every referenced evidence
   file. Run the affected workflows there. Do not overwrite operator data for a test.
4. Retain the pre-change set and import mapping until review accepts the migration.
   Once portable UUIDs are exchanged externally, removing/recreating the identity
   migration would change external identities; restore the coordinated backup or
   make a forward repair instead.

The session's operator SQLite snapshot passed integrity_check and its raw copy
matched the original hash. This is **not** a complete backup/restore acceptance:
private evidence, restore drills, encryption, offsite retention, RPO/RTO and
production operating procedures remain to be established and verified.

### Receiving evidence under development

The receiving feature retains files before committing their database metadata.
An injected audit-write failure verifies that metadata/version changes roll back,
but the file survives. Database transactions cannot roll back filesystem writes.
Include these unreferenced files in protected backup and investigate them during
maintenance reconciliation; do not automatically delete them or attach them to a
receipt based on filenames. Compare stored file paths, hashes and sizes to committed
evidence records. Missing or changed referenced files block submission/acceptance.
Run `python manage.py check_receiving_evidence` with the intended database and private
storage configuration during a maintenance window with writes paused, or against an
isolated restored copy. It prints a JSON report and exits nonzero for missing/changed,
unsafe-path or unreferenced files. It never repairs, deletes or attaches files.
Restrict the report like other operational records. Only receiving evidence is
covered; Accounting import snapshots still require separate checks. Disposal checks
are described below.
Do not run against a changing live store and interpret transient results as a verified
backup. Symlink/junction redirection and paths outside receiving storage are rejected.

A synthetic SQLite receipt/evidence restore and deliberate-corruption drill passed
on 2026-10-17; see the validation record. This is not proof of source-document
authenticity, malware scanning, complete operator recovery, or GRAND two-store recovery.

A separate stopped synthetic GRAND preview was backed up/restored as a paired
default/finance SQLite set on 2026-10-17: all 193 default and 83 finance table contents
matched, both integrity/foreign-key checks passed, and loss of an approval event in
the restored copy was detected then recovered. Original source hashes were unchanged.
This database-only rehearsal covers attribution relationships/history; its fixture
had no private attachment set. It does not establish online MySQL backup consistency,
offsite retention, operational RPO/RTO or complete GRAND private-file recovery.

## Supply-count evidence

Include `inventory/stock_counts/` in coordinated private storage backups. Run
`python manage.py check_stock_count_evidence` against the paused/restored intended
store; it reports missing, changed, unsafe and orphan files without repairing them.
Review and downloads check retained hashes and sizes. Filesystem writes cannot roll
back with a failed database transaction; investigate unreferenced files rather than
silently deleting them. A stopped synthetic paired restore preserved201 default and
83 finance tables plus one count file, detected/restored corruption/loss and left
source hashes unchanged. See [validation](validation-2026-10-16.md); this does not
establish online/operator recovery or document authenticity.

## Gates still open

Witnessed returns add private files under `inventory/custody_returns/`; include them
in the coordinated backup alongside both GRAND databases. Run the read-only
`check_custody_return_evidence` on the restored copy. The stopped synthetic rehearsal
preserved198 default/83 finance tables plus one return file, detected/restored file
corruption and loss, and preserved source hashes. See [returns](custody-returns.md)
and [validation](validation-2026-10-16.md); online/operator recovery remains open.

- Use GRAND's authentication, permissions and source-visibility checks during merge,
  including its UAT-viewer mutation denials. This shell is not a replacement IdP.
- Internet deployment needs tested login/reset rate limiting, secret/email setup,
  HTTPS proxy trust configuration, request limits, protected storage, monitoring,
  least-privilege database accounts and a restore rehearsal. No proxy header is
  trusted by default; only configure it for an actual proxy that strips forged headers.
- Native MySQL integration must address existing conditional unique constraints
  and validate write races; SQLite alone is insufficient. Model save hooks are
  application controls and do not make data immune to direct administrator SQL.
- Official-form acceptance, audit retention policy, lost-item accountability and
  safe historical correction workflows remain in the roadmap.

## GRAND legacy inventory authority

Asset register, legacy handoff, disposal and physical-verification actions use
GRAND explicit user/group grants. A superuser flag alone does not grant an action.
Finance UAT membership denies all mutation checks even when action grants exist.
Scoped reads retain explicit grants: history pages may use the existing workflow
action permission in read-only mode, while forms/services use the mutation check.
This preserves review access without granting edit, acknowledgment, disposal or
count authority. No grants are installed automatically. Standalone permissions
remain compatible. Navigation resolves real scoped read helpers. Maintenance and
stock audit reads also require explicit grants in GRAND.

The internal read_only argument is only for read routes/navigation; it must never
be derived from request input or passed by mutation services. Department/owner,
independent review and lifecycle checks still apply separately. No data migration,
public service, authentication backend or Finance posting path is introduced.

Receipt amendment evidence is private under `inventory/receipt-amendments` and must
be included with the database pair in recovery. Use the read-only
`check_receipt_amendment_evidence` command alongside existing evidence checks.
Amendment review checks retained bytes and content/predecessor basis; unknown/zero
cost never creates positive claim-support capacity. No amendment or recovery
fixture authorizes an operator migration, grant or deployment.

HR-reference custody cases add `inventory/custody-reviews` private request files.
Include them in the same coordinated backup as default/finance stores. Run
`check_custody_review_evidence` on restored copies; preserve the immutable case
header and event chain. Missing sources or changed custody block independent review;
an as-of review is not a permanent employee-clearance authorization. See
[the case design](hr-custody-review.md) and validation for current release status.

Supplied requisition documents use `inventory/requisitions` private storage.
Include this namespace with both databases and run `check_requisition_evidence`
on restored copies. Retain request/line/fulfillment UUIDs, linked stock movements,
FIFO allocations and review/event history together. See [request design](stock-request-design.md)
for permissions, lock order, retry and evidence-integrity boundaries.

Supply return evidence adds `inventory/supply-returns`; run
`check_supply_return_evidence` on coordinated restored copies. Preserve original
issue/allocation, return case/event, new stock movement and optional FIFO lot as
one trail. Accepted returns never remove the original requisition fulfillment.
See [return boundaries](supply-returns.md), including unknown costs and legacy gaps.

Supplied property determination packets use `inventory/property-determinations`.
Preserve record/event/predecessor relations and files with both databases; run
`check_property_evidence` on restored copies. Verification checks fresh source
bytes and retained asset/receipt basis. Missing files, history drift and stale
versions fail closed. Useful-life expiry does not erase physical accountability.
The same packet namespace now covers supplied acquisition facts. Restore item
numbers, source references/dates and old NULL/blank facts exactly; do not rebuild
historical snapshots by injecting new blank fields. A verified successor may make
an older Finance link stale; preserve that link's approval history during recovery.

Property Finance associations reuse the existing determination packet. Include
adapter link/events/predecessors in the same coordinated backup, along with native
Finance dimensions and any supporting receipt-journal mapping. Finance access to
one shared packet is scoped through an explicit request and action grants; it
does not widen the original GSO property routes. Verify retained link history and
live dimension/mapping availability after restore. Missing/changed dimensions
invalidate current-use assertions without deleting the historical association.


Disposal evidence remains in `inventory/disposal`. Migration0026 adds retained
SHA-256 for new uploads; old blanks remain unknown, without rewriting history or
reading/backfilling historical files. Include the namespace and database records
in coordinated backups. Run `python manage.py check_disposal_evidence` on restored
copies. A nonzero result reports unknown baselines, missing/changed/unsafe paths
or unreferenced files; investigate the report without deleting or silently
rehashing evidence. The command never changes data or files.

Downloads validate known hashes and all recorded sizes before streaming the same
opened file; legacy downloads explicitly indicate unknown integrity. Authorization
and completion reject missing or detectably changed retained evidence. Legacy
unknowns remain operationally usable, but strict source verification rejects them.
This distinction must survive restore and later property-card integration.
New upload hashes establish byte consistency, not document authenticity or malware
safety. File writes are not transactional with the database; interrupted operations
can leave unreferenced files, which require investigation rather than automatic deletion.


Property movements add `inventory/property-movements` private packets. Restore
records/events, predecessor links, pinned property/source snapshots and disposal
UUIDs with the same coordinated stores/files. Run `check_property_movement_evidence`
on restored copies. Missing or changed packets invalidate the current working
balance; preserve historical records for investigation. Never reconstruct openings,
chronology or source UUIDs from today's custody. The stopped synthetic rehearsal
preserved both stores and verified corrections; it does not replace operational
online MySQL backup/restore acceptance.


## Receiving follow-up lineage

Follow-up inspection reuses the receiving private namespace. Preserve the original
receipt/line and packet, child source relation/basis, child packet/materialization
and both event histories together. The stopped synthetic paired restore retained
219 default/83 Finance tables and16 files, stock7.5 and unresolved remainder0.5;
missing/changed original or child packets were detected. See validation for the
backup receipt and limits. Adapter0006 only declares the inventory0028 dependency.
No operator migration or online recovery acceptance is established by that drill.
