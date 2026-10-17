# GSO alignment foundation validation — 2026-10-16

## 2026-10-17: PAR placeholder preparation

User authorized placeholders and focused testing at routine checkpoints; confirmed
prototype credentials were isolated. Fresh fetch clean0/0 at6b8aef4 before branch
codex/property-form-placeholders. No operator data or native Finance modifications.

PASS: isolated `.tmp/run_verification_tests.py inventory.test_property_outputs`,
4 tests0.215s: existing view grant/login/CSRF/method controls, no-store, blank
placeholders, no SQL mutation, escaped input, zero vs unknown cost, exact0.001
quantity, invalid values and bounded five-form input. Django system check PASS.
PASS: Playwright login→prepare→blank/supplied preview; desktop print-media screenshot
and390px mobile. Initial table page overflow fixed with sheet-contained scrolling;
final browser assertion verifies document width does not exceed viewport. The
reused development server cached the template; restarted once for the changed CSS.
Final screenshots output/playwright/par-placeholder-{mobile,print}-final.png.
Print screenshot inspected; signature/date blanks and all five rows retained.
Favicon404 is existing shell behavior. Both temporary preview servers and browser
closed. Test/preview data are synthetic and isolated.

NOT RUN - OUT OF SCOPE: repeated local full, native, populated-migration and restore
suites. This addition reuses the property-view policy, has no model/migration, no
asset queries or transaction/storage mutation, and does not modify Finance. Focused
HTTP tests plus visual review are the routine gate; hosted release checks remain.

## 2026-10-17: historical-data exposure audit (documentation only)

PASS: fresh GSO fetch/status and history comparison at89890e1, clean0/0. Finance
fetch unchanged a533482/master32ab046, existing coordination note only. Exact
prior release master CI38994043849 confirmed success at89890e1.

PASS: `.tmp/audit_historical_database.py` enumerated `git rev-list origin/master
-- db.sqlite3`, deduplicated existing blobs, deserialized them into query-only
in-memory SQLite, and inspected aggregate counts plus integrity_check. Nine
snapshots, all with account/usable-password/session rows; two accounts and one
superuser per snapshot. No private field values exported. Aggregate receipt:
`.tmp/historical-database-audit.json` outside tracked files. `git ls-files
'*.sqlite3' '.env'` returned none. This is a bounded exposure finding, not proof
of current credential reuse, live-session validity, compromise or remediation.

NOT RUN - OUT OF SCOPE: new application/native/browser/restore tests; only durable
prose/import-acceptance requirements changed. No production configuration or data
changed. Run diff/link review and actual VM inspect/preview before publication;
hosted exact-commit checks remain the integration gate.
Initial VM inspect found a Windows-encoded inserted dash; normalized that file
to UTF-8 and corrected newline duplication. Final diff check and preview pass.

## 2026-10-17: verification follow-up integrity (unreleased)

Sync PASS: fetched GSO master33cd899, clean0/0; Finance candidate a533482,
master32ab046 unchanged, existing coordination note only. Previous milestone
published with exact feature/master CI38992943732/38993133478 PASS.

Observed source defect: record_asset_verification replaced the physical observation
but retained resolution fields, so a newly changed missing/discrepant observation
could appear already resolved. Reset current resolution on new checks; preserve
prior event rows. Signed forms bind actor, record, latest history event and exact
observed fields; compare under the record lock. No asset or Finance state changes.

PASS: isolated `.tmp/run_verification_tests.py inventory.test_verification_followups`,
5 tests,1.668s. Covers reopened discrepancies, matched observations, retained
history, stale/duplicate decisions, missing/stale HTTP tokens and the interleaving
between reading a record and its latest event. FAIL - CAUSED BY CURRENT WORK:
intermediate timestamp-only binding did not reject same-timestamp changed facts;
replaced by exact field comparison and rerun passed. Full regression PASS202 discovered/175 run/27 native skips,76.790s, terminal44515,
`.tmp/verification-full.log`; this began before the final observed-field binding,
covered by the final focused run. Native MySQL5/5 PASS1.761s, terminal2068,
`.tmp/verification-native.log`, using `scripts/run_mysql_tests.py
inventory.test_verification_followups`. Fresh disposable schema only.

PASS: actual GRAND native authority8/8,1.053s, terminal98644 exit0 through
`.tmp/run_verification_grand.py --grand-root C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation --mysql`;
`.tmp/verification-grand-native.log`. Wrapper selects the existing authority module,
now extended with a native scoped signed review/reset/Finance-no-query case.
Owned MySQL33317 shut down normally after confirming all test schemas removed.
VM inspect/preview selects a patch and changes only VERSION/CHANGELOG.
NOT RUN - OUT OF SCOPE: new populated migration/restore drill (no schema, file or
storage change); prior evidence is retained, and regression tests explicitly check
that existing events survive new observations. Broader concurrency/deployment
acceptance is not claimed. No migration changed; operator database hash unchanged.

Research follow-up: COA's indexed relief FAQs distinguish notice/application,
but their notice-period summaries differ. Direct 2024 Citizen Charter PDF returned
403; do not infer a new deadline or adjudication workflow from these snippets.
No legal rule or loss/relief schema was added. The substantive engineering repair
above follows observed data lineage, not an unverified legal interpretation.

## 2026-10-17: reviewed clerical receipt quantities (feature validation)

GSO `codex/receipt-correction-design`, baseline ad8b348; fresh remote comparison0/0
with only the prior goal turn's intended source/design edits. That turn was progress,
not a blocked wait. Actual GRAND test checkout was fetched and remains at candidate
a533482; remote master is32ab046. The candidate is not represented as production.

Inventory0029/adapter0007 retain correction source, packet, predecessor, independent
decision and protected result; no Finance DDL/DML. Pending holds and effective
quantity consumers are wired. Signed record/review screens, original/effective
display, erroneous-asset history and private downloads are implemented. Current
publication state is in CONTINUE; these test results alone are not a release.

Commands run in the feature checkout with isolated settings/databases and the
installed Python runtimes documented below:

- PASS: standalone source/correction/receiving/follow-up45 tests,2.712s.
- PASS: `manage.py test --verbosity 1`,193 discovered/168 run/25 native skips,
  72.957s; `.tmp/correction-shell.log`. This earlier full run preceded later UI,
  result-snapshot and added migration/concurrency tests.
- PASS: `scripts/run_mysql_tests.py`, full197/197,211.086s;
  `.tmp/correction-native-shell.log`, terminal77022. This run preceded the final
  full-result snapshot comparison and asset-label/link changes; focused final
  checks cover those changes and the later follow-up case.
- PASS: native focused source/correction/race/populated-migration20/20,4.887s;
  `.tmp/correction-native-targeted-final.log`. Both simultaneous approvals and an
  issue racing a proposal serialize correctly. Populated0028-to-0029 preserves
  original supply/lot/receipt/asset rows and invents no correction.
- PASS: actual GRAND `scripts/run_grand_source_tests.py --grand-root
  C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation`,144 discovered,
  123 run/21 skips,30.468s; `.tmp/correction-grand-sqlite.log`, terminal80940.
- PASS: same actual GRAND harness with `--mysql`,144/144,61.853s;
  `.tmp/correction-grand-native.log`, terminal22305. Real native actors/permissions,
  UAT/foreign/ungranted denial, pending-support block, corrected100-to50 ceiling,
  independently approved50 support, and withdrawn support exclusion pass with zero
  Finance queries. The later Finance-versus-correction race is a separate final run.
- PASS: final local source/correction17/17,1.361s after full result snapshots and
  refreshing the current asset status during verification.
- PASS: migration drift (`manage.py makemigrations --check --dry-run`) and
  `git diff --check` at the schema checkpoint. Recheck before release.

Final affected validation:
- PASS: `scripts/run_mysql_tests.py inventory.test_receipt_quantity_corrections inventory.test_receipt_correction_sources inventory.test_receipt_quantity_concurrency inventory.test_receipt_quantity_migration`,21/21,5.594s; `.tmp/correction-native-final.log`.
- PASS: `.tmp/run_quantity_grand_targeted.py --grand-root C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation --mysql`,3/3,1.692s; `.tmp/correction-grand-native-targeted.log`, terminal98947 exit0. This wrapper selects only the correction module through the actual GRAND harness. Concurrent Finance proposal and correction produce exactly one winner under the receipt lock.
- Owned MySQL33317 shut down normally after confirming all disposable test schemas were removed. Preview processes are stopped.

Failures investigated and repaired:

- FAIL - CAUSED BY CURRENT WORK: initial service retry tests reused a consumed
  upload stream. `_packet` now rewinds before validation; exact content/identity
  checks remain. The45-test rerun passed.
- FAIL - CAUSED BY CURRENT WORK (test harness): directly calling a streaming test
  response's close triggered request-finished connection cleanup inside MySQL's
  test transaction, causing two errors. Consume its streaming iterator through
  Django's test-client wrapper instead; native20/20 rerun passed. Production
  file handling and transaction guards were not weakened.
- FAIL - CAUSED BY CURRENT WORK: a final integrity check read a cached pre-correction
  asset instance. It now queries the current asset status; final17/17 passed.
- Browser harness used unavailable global `URL` after creating the pending asset
  proposal. Resumed that same proposal at its observed URL; no duplicate entry or
  application repair was needed. Existing copied GRAND public/login media defaults
  and favicon return404; GSO screens and correction endpoints work.

Populated actual GRAND preview `.tmp/receipt-quantity-preview-rfeep089`:
all218 existing application tables' original rows retained; only2 new inventory
content types and2 custom permission definitions added, no existing role grants.
Finance bytes unchanged. System/migration-drift checks pass. Synthetic grants were
added only afterward to the copied preview actors. Desktop/mobile browser:
delivered10/accepted6 -> approved subtraction2 -> effective8/4, unresolved2;
independent review; original-lot adjustment; original acceptance retained. A second
one-unit asset case retains the asset as `entry_void`, with actions disabled and
explicit original-quantity/cost labels and authorized correction-history link.
Screenshots `output/playwright/quantity-correction-{form-mobile,approved-desktop,original-mobile,asset-mobile}.png`
were inspected. Browser receipt-quantity and both preview processes62913/91841
are stopped; no operator server was used.

Stopped paired restore PASS: `.tmp/rehearse_receipt_quantity_recovery.py`, log
`.tmp/correction-recovery.log`, backup
`C:/Users/Administrator/.codex/backups/gsov2-receipt-quantity-recovery-20261017-9xv4hpz1`.
All221 default/83 Finance tables and24 private files match retained manifests.
Older FIFO lot untouched, corrected source allocation2, combined stock10, effective
source accepted4, erroneous asset quantity0 and original history survive. Missing/
tampered correction packets and altered adjustment result fail verification; file
checkers pass after restoration. Source hashes remain unchanged. This is synthetic
stopped SQLite recovery, not operator/offsite/online MySQL RPO/RTO acceptance.

## 2026-10-17: clerical-correction source prerequisite (unreleased)

Branch `codex/receipt-correction-design`, baseline ad8b348. Fetched GSO HEAD and
origin/master0/0, clean before edits. Canonical master also clean0/0; operator DB
SHA256 remains5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
Finance fetched candidate a533482/master32ab046, only its existing untracked
coordination note. User selected clerical overstatement before use.

New internal `lock_unused_source` requires the caller's default transaction and
locks receipt then item/asset. It checks exact original acceptance/packet metadata,
file integrity, owner and materialization, prior usage/reconciliation and dependent
history. No production mutation calls it yet; no pending hold, correction write,
migration or endpoint is claimed. The design and Finance coordination are recorded.

Runtime: `C:/xxx/_INSTALLS/_HERE/_xxx/gsov2-development/Scripts/python.exe`.
Set `GSO_DATABASE_PATH` to feature `.tmp/correction-source-tests.sqlite3`; Django
created/destroyed the isolated test database, not the operator database.

- PASS: `manage.py test inventory.test_receipt_correction_sources --verbosity 1`,
  initial10 tests,0.507s. Read-only inspection, stale/missing source, scope, prior
  non-FIFO issue/return, target versus older FIFO lot, adjustments, dependent draft
  follow-up and asset audit history.
- PASS: `manage.py test inventory.test_receipt_correction_sources inventory.test_receiving inventory.test_receiving_followups --verbosity 1`,
  final40 tests,2.106s after adding malformed-history validation and original asset
  snapshot comparison. This includes11 new tests and29 dependent receiving tests.
- PASS: `git diff --check`.
- NOT RUN - OUT OF SCOPE: full/native/actual-GRAND/browser/migration/recovery gates
  for the complete correction feature, which does not exist yet. The optional
  Finance history predicate has not been tested in actual GRAND at this checkpoint.
  Native write races and hold enforcement are mandatory when those writes are added.

No runtime server was started. No VM release/integration/push for this incomplete
feature. The original receiving-followup release ad8b348 remains published; its
earlier evidence is historical and is not a test of this new source prerequisite.

## Original alignment foundation scope

Scope: UUID migration/export prerequisite, dependency update, stock-owner fix,
service input restrictions and deployment settings. Full shell suite selected
because these affect shared models, permissions, migrations and dependencies.
Working directory: `C:/Users/Administrator/.codex/worktrees/gsov2-receiving-safety`.
Runtime below: `C:/xxx/_INSTALLS/_HERE/_xxx/gsov2-development/Scripts/python.exe`
(Python 3.11; newly installed isolated environment, original venv unchanged).

| Command / check | Actual result |
| --- | --- |
| `git fetch --prune origin`, status, `git rev-list --left-right --count HEAD...origin/master` before edits | PASS: 0/0 at `64e458a`; operator DB modification identified and preserved. |
| Original `.venv/Scripts/python.exe manage.py test --verbosity 1` before changes | PASS: 7 tests, 0.657 s. This baseline has limited historical workflow coverage. |
| `python manage.py test --verbosity 1` after changes | PASS: 16 tests, 2.166 s, no skips. Includes original seven and nine foundation/migration/security cases. |
| `python manage.py makemigrations --check --dry-run` | PASS: no model/migration drift. |
| `python manage.py check` | PASS: no issues. |
| `python -m pip check` | PASS: no broken requirements. |
| `python -m pip_audit -r requirements.txt --progress-spinner off` | PASS: no known vulnerabilities reported for resolved requirements at check time. |
| `python manage.py check --deploy` with synthetic `DEBUG=0`, strong test secret, explicit host and absolute private path | PASS with W005 and W021 warnings: subdomain HSTS and preload deliberately disabled pending actual domain rollout. No production settings/secrets used. |
| `git diff --check` | PASS. |
| SQLite backup API snapshot + integrity_check; SHA-256 comparison of operator original/raw copy | PASS: integrity_check `ok`; raw copy and original bytes equal; no operator migration. |
| `GSO_DATABASE_PATH=<protected restored copy> python manage.py migrate --noinput` | PASS: actual operator snapshot copied to an isolated path, migrated through 0012; original table counts, link identities, distinct UUIDs and SQLite integrity verified. Original DB hash unchanged. |
| Feature GitHub workflow at `e642d9e`, run `38927980234` | PASS: dependency consistency/audit, system checks, migration drift and full regression on Ubuntu/Python 3.11. |
| Native MySQL and actual GRAND router/import integration | NOT RUN — ENVIRONMENTAL: not configured for this standalone shell; parallel Finance's native environment is not borrowed or disrupted. Required before GRAND merge. |
| Browser layout / official form outputs | NOT RUN — OUT OF SCOPE: no templates/UI fields or official outputs changed. Django HTTP tests exercise export, list, detail and rejected cross-office action routes. |
| Full data/evidence restore, penetration testing, LGU acceptance | NOT RUN — ENVIRONMENTAL: requires coordinated target deployment, evidence set and operational review. No production-readiness claim. |

Populated migration replay goes from 0011 to current using distinct historical
assets (including duplicate legacy tags), a supply item and receipt movements;
PKs/links/balance survive and every new UUID is populated and distinct. The migration
does not silently deduplicate, split pooled assets, map actors or infer financial data.

Stock tests cover a GSO clerk with action permissions attempting another GSO owner's
list/detail/export/receive/issue/adjust/edit routes and direct service mutations.
Cross-owner access is denied; authorized exports retain the owning UUID and distinguish
zero cost from unknown cost. Identity/owner/actor changes through service dictionaries
are rejected without extra records/audit events.

Two synthetic Git untracking trials failed safely while designing local integration:
checkout refused to overwrite an untracked test file; fast-forward refused to remove
a modified untracked test file. Operator files were never involved. This demonstrates
why canonical integration must preserve data externally rather than force checkout.
The rehearsal directory is under `.codex/worktrees/gso-untrack-rehearsal-tcs6r8bi`.

Version Manager inspect and preview preceded the actual release commit/tag. Preview
initially proposed rewriting historical baseline version mentions; these were
expressed as immutable baseline commit references before release so historical facts
were preserved. Only VERSION and CHANGELOG were then automatically updated.
Canonical/remote primary and tag were verified at `e642d9e`; operator bytes were
rechecked unchanged after integration. Primary CI and later documentation status
are linked from CONTINUE.md. Local tests do not stand in for a future GitHub run.

## Receiving HTTP and failure-path checkpoint — 2026-10-17 (unpublished)

Feature branch `codex/receiving-inspection`, based on `405f360`; fetched master
comparison 0/0 before work, with only the unfinished receiving changes present.
Commands use `C:/xxx/_INSTALLS/_HERE/_xxx/gsov2-development/Scripts/python.exe`.

- PASS: `manage.py test inventory.test_receiving --verbosity 1`, 16 tests (0.632 s),
  including complete CSRF-enforced create/line/upload/submit/return/correct/accept
  requests, invalid quantities, self-review denial and view-only permission denial.
- FAIL - CAUSED BY CURRENT WORK: first expanded full run, 32/33; new upload-failure
  test exposed that settings override did not replace the instantiated FileField
  storage. Fixed test isolation by patching the field to temporary FileSystemStorage.
- PASS: `manage.py test --verbosity 1`, 33 tests (2.561 s) after the fix. Audit failure
  rolls back receipt metadata while preserving the unreferenced uploaded file.
- PASS: `manage.py makemigrations --check --dry-run`; `git diff --check`.
- NOT RUN - OUT OF SCOPE for this checkpoint: visual desktop/mobile review, native
  MySQL races, populated 0013/0014 migration/restore, official form acceptance.
  These remain outstanding gates; the feature has not been released or deployed.

Full shell suite is appropriate here because changes touch permissions, shared
asset services, schema and stock materialization. Tests use synthetic records;
the operator database and parallel Finance code were not changed.

## Receiving migration and recovery checkpoint — 2026-10-17 (unpublished)

Fresh fetch again showed HEAD/master 0/0; unfinished feature files remained local.

- PASS: populated copy of the preserved `migration-rehearsal.sqlite3` migrated from
  inventory 0012 through 0014 via `manage.py migrate --noinput`. Compared every row
  in 37 pre-existing application tables (42 rows), excluding migration/content-type/
  permission framework metadata. SQLite integrity and foreign-key checks passed.
  Source SHA-256 remained
  `45264e6e574f76563b2e9ac591882a100688f017bae5675d452c4b17a5ace0d5`.
- PASS: separate synthetic DB seeded through receiving services, accepted six reams
  from a partial delivery, captured SQLite via backup API with writes stopped and
  copied private evidence. All 34 tables compared exactly after restore; file SHA-256
  maps matched, SQLite integrity/FK checks passed. `manage.py check_receiving_evidence`
  reported two checked files with no findings. Deliberate corruption of one restored
  file produced nonzero status and one changed-file finding; copying the source file
  back restored a clean result. Source files stayed unchanged.
- PASS: `manage.py test --verbosity 1`, 35 tests (2.768 s). Added read-only command
  tests distinguish missing/changed/unreferenced files and reject outside paths;
  failed-upload evidence remains preserved and is flagged for investigation.
- NOT RUN - OUT OF SCOPE for this checkpoint: desktop/mobile browser inspection,
  MySQL concurrency/router testing, real operator and GRAND two-store recovery.

Local drill manifests and isolated databases/files:
`C:/Users/Administrator/.codex/backups/gsov2-receiving-rehearsal-20261017-001404/`
(`migration-result.json`, `restore-result.json`). They are protected local rehearsal
artifacts, not repository fixtures or evidence of production acceptance. The original
operator database, original backup, and parallel Finance code were not modified.

## Receiving browser checkpoint — 2026-10-17 (unpublished)

Fresh fetch: branch and remote primary still 0/0; feature changes local. Playwright
CLI ran in a named `gso-receiving` session against loopback port 8017 and a disposable
`browser.sqlite3` copied from the synthetic drill. No operator login or database used.

- FAIL - CAUSED BY CURRENT WORK: receiving-only user hit the asset dashboard's 403
  after sign-in. Fixed dashboard entry to check receiving permission and redirect
  to receiving when asset view permission is absent; asset data remains inaccessible.
- FAIL - CAUSED BY CURRENT WORK: line and evidence `kind` fields shared an HTML ID,
  causing duplicate/missing accessible labels. Fixed distinct form auto-ID formats.
- PASS: browser login, delivery-draft creation and detail navigation; corrected
  Workspace route lands at receiving for the restricted user. Draft/accepted detail
  screenshots inspected at desktop 1440×1000 and phone 390×844. Phone document width
  equals viewport (390), and draft DOM has no duplicate nonempty IDs.
- PASS: `manage.py test --verbosity 1`, 36 tests (2.652 s), including regression
  checks for receiving-only landing and unique form IDs/labels.
- NOT RUN - OUT OF SCOPE: complete reviewer journey in browser; it is covered by
  enforced-CSRF HTTP tests, not claimed as browser acceptance. Native MySQL checks
  and human acceptance remain pending. Initial console errors were the diagnosed
  dashboard 403 and missing favicon; receiving screens returned HTTP 200.

Screenshots: ignored `output/playwright/receiving-desktop.png`,
`receiving-phone.png`, `receiving-accepted-phone.png`. Browser logs and screenshots
are excluded from Git to avoid accidentally publishing session evidence.

## Native MySQL receiving checkpoint — 2026-10-17 (unpublished)

Fresh fetch: 0/0 vs remote primary with unfinished local changes. Initialized a separate
owned MySQL 8.4.11 fixture under `C:/xxx/_INSTALLS/_HERE/_xxx/gsov2-mysql-validation-20261017`,
bound to 127.0.0.1:33317 with X protocol disabled and a generated local password.
The parallel Finance server was not used or modified.

- FAIL - CAUSED BY CURRENT WORK: initial 36-test MySQL run had six errors following
  the streamed-download test. It explicitly closed the response after Django's test
  streaming iterator already closed it; the second request-finished signal closed
  the transactional test connection. Removed the redundant close.
- PASS: `python scripts/run_mysql_tests.py`, all 39 tests, 7.021 s, no skips. Includes
  concurrent same-receipt stock acceptance, two receipts with duplicate tags, and
  normal asset creation competing with receiving. Each permits one result and one
  controlled validation conflict. Fresh schema migrations through 0014 completed.
- PASS: `python manage.py test --verbosity 1`, 39 discovered, 36 executed and three
  native-only skips, 3.214 s. SQLite cannot prove row locking.
- OPEN - PRE-EXISTING: W036 for conditional unique constraints on AssetTransfer and
  AssetDisposalCase, confirmed in baseline models. MySQL does not create these
  constraints. A portable replacement and transition race checks are still required;
  a green receiving suite does not establish those unrelated lifecycle invariants.

The committed native runner follows GRAND's isolated testing approach without
replacing its default/finance router or claiming two-store integration validation.

## Portable lifecycle integrity — 2026-10-17 (unpublished)

Compared GRAND's actual `accounting.BankStatementMatch.active_identity_marker` and
migration 0011. Applied the same nullable-marker/ordinary-uniqueness design to GSO
pending transfers and open disposal cases, with duplicate preflight before DDL.

- FAIL - CAUSED BY CURRENT WORK: populated SQLite rehearsal rejected addition of a
  STORED generated column, despite passing empty-schema tests. Changed the unpublished
  markers to virtual columns; this preserves the same DB-enforced uniqueness and
  permits upgrades on populated SQLite. Added an automated populated-upgrade test.
- PASS: `scripts/run_mysql_tests.py`, all 45 tests, 9.867 s, no skips or warnings.
  Direct and concurrent inserts enforce one open record; closed histories remain;
  reopening a conflicting row fails. Populated migration preserves original fields.
  Duplicate native cases cause preflight failure before marker columns are added,
  with both historical records retained.
- PASS: `manage.py test --verbosity 1`, 45 discovered, 39 executed and six native-only
  skips, 4.943 s. `manage.py makemigrations --check --dry-run`: no changes.
- PASS: isolated populated SQLite drill copy `lifecycle-0015.sqlite3` upgraded to0015
  after the virtual-marker fix; original operator data remained untouched.

This resolves the prior W036 finding for current models. The separate server is owned
by this task; normal test runs removed their random schemas. No Finance schema or
production configuration was changed.

## Receiving publication evidence - 2026-10-17

Version Manager README/inspect/preview preceded the actual minor release, commit
`7d3547fcc86e570e79db4bfc67f742335c38cf2d`. Preview touched only VERSION/CHANGELOG;
historical evidence was preserved. Explicit intended files were staged. No runtime
DB/uploads, browser artifacts or parallel Finance work were published.

PASS: optional-native/runtime dependency audit (no known vulnerabilities), pip check,
system check and diff whitespace check. Feature CI38932007629 passed before canonical
master was fast-forwarded and pushed. Remote master/tag matched the release commit;
canonical status was clean and operator DB hash matched the preservation manifest.
No operator migration or deployment occurred. Primary GSO checks CI38932087704 passed
at the release commit. This follow-up changes documentation only. The broader integration,
Finance attribution and remaining roadmap remain incomplete.


## GRAND source adapter checkpoint - 2026-10-17 (unpublished)

PASS: four standalone payload tests (0.001s); actual GRAND source tests, five tests
(0.080s), using clean published GRAND 32ab046 and isolated SQLite default/finance
schemas. Command: `grand-auth-venv/Scripts/python.exe scripts/run_grand_source_tests.py
--grand-root C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation`.
Log: `.tmp/grand-source-validation-latest.log`. That run did not install inventory.

FAIL - CAUSED BY CURRENT WORK in initial harness fixtures: duplicate profile creation
and stale reverse-profile cache from GRAND's user creation signal. Fixed by updating
the signal-created profile and refreshing the fixture user; completed run above passes.

PASS: `gsov2-development/Scripts/python.exe manage.py test inventory --verbosity 1`,
49 discovered, 43 executed, six native-only skips, 3.537s. Scope: optional source
adapter plus existing operational regression coverage. No operator database changes.
PASS: expanded runner installs inventory and applies the full migration graph with
GRAND's users and database router. Six tests in 0.090s, exit 0; log
`.tmp/grand-inventory-validation-latest.log`. New test creates receipt/audit records
using core identities, proves no Finance queries/table, and denies an outsider.
Both fresh SQLite databases were destroyed normally. Native concurrency, populated
imports and routes/UI integration remain NOT RUN - OUT OF SCOPE for this checkpoint.

PASS: first native GRAND integration run, seven tests in 0.953s, MySQL 8.4.11,
actual GRAND router and inventory migrations, exit 0. Log
`.tmp/grand-native-validation-latest.log`; both test schemas destroyed. Source
replacement used a separate connection but did not yet assert observed lock waiting.
PASS: strengthened native run, seven tests in 0.925s, exit 0; log
`.tmp/grand-native-lock-proof.log`. performance_schema confirmed the reader waited
while preparation held the case lock and then rejected the replaced line. Both test
schemas were verified absent and the owned MySQL server shut down normally.
Full standalone release suite PASS: 49 discovered, 43 executed, six native skips,
4.124s. Migration drift, pip check and diff check PASS. Operator hash unchanged.

Native integration limitation: the clean published GRAND source at `32ab046`
emitted 23 models.W036 warnings for conditional uniqueness in account, accounting,
departments, finance, leave_mgt, reporting, tracepoint and vouchers. None concern
inventory. These constraints are not created by MySQL; the seven passing tests do
not establish safety for those unrelated workflows. This is evidenced existing
GRAND schema behavior, not a new GSO migration regression. The exact model list is
retained in `.tmp/grand-native-lock-proof.log`, and the parallel Finance review note
flags the issue. Do not claim the full integrated system is production-ready.


## Reviewed attribution draft - 2026-10-17 (unpublished)

PASS: `grand-auth-venv/Scripts/python.exe scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation`, SQLite,
15 discovered, 14 executed, one native-only skip, 0.581s, exit 0. Actual GRAND
migration graph plus optional inventory_finance initial migration. Eight new tests
cover approval/withdrawal history, no Finance queries, scoped reads, retry identity,
amount precision/capacity, unaccepted receipts, UAT/self-review denial, stale versions,
replacement requiring withdrawal and stale review replay. Both schemas destroyed.
Log `.tmp/grand-attribution-validation.log`; source freeze under its recorded runtime.
Native capacity races, populated upgrades and UI are NOT RUN - pending implementation.


PASS: native attribution draft run, 19 tests in 4.128s, MySQL 8.4.11, exit 0.
Includes separate-connection competing approvals, duplicate approval and identical
request retries. Both schemas removed, owned server stopped. Log
`.tmp/grand-attribution-native.log`. Existing GRAND W036 warnings remain as recorded.
This did not test aggregate support across different claims against one receipt's
value; code review identified that missing control and it must be fixed before release.
UI HTTP run is pending; browser verification not performed yet.


FAIL - CAUSED BY CURRENT WORK: first HTTP run (23 discovered, four native skips,
2.573s) failed the expiry fixture because globally mocking signing.loads also broke
session decoding. Fixed by signing an old-timestamp proposal only. Other tested HTTP
paths passed; the corrected combined run is pending. Receipt-wide cross-claim capacity
checks and tests were added after this run and are not credited to its result.


PASS: corrected combined MySQL/HTTP run, 26 tests, 7.930s, exit0, no skips.
Receipt-wide cap across claims and unknown-cost rejection are covered, including
independent-connection approvals of different cases against the same receipt.
Log `.tmp/grand-attribution-capacity-http-native.log`. Existing GRAND W036 warnings
remain documented. Both test schemas removed; owned server stopped normally.

PASS: Playwright actual-browser clerk login, preview, submit, separate reviewer login,
approve and withdraw. Original approval and all three events remain visible. Screens
inspected at1440x1000 and390x844; proposed/approved mobile width checks show no
horizontal overflow or duplicate IDs. Screenshots output/playwright/claim-*.png.
Preview limitation: isolated media omits GRAND defaults grand-mark.svg and
 default_user_dp.png, causing image404s. No operator media was copied. Browser sessions
closed and preview port8018 stopped. Ctrl-C ended preview with exit1 before automatic
SQLite deletion; its two synthetic databases remain for recovery rehearsal.


## Claim support release checks and recovery - 2026-10-17

PASS: stopped synthetic paired SQLite recovery under
`C:/Users/Administrator/.codex/backups/gsov2-attribution-rehearsal-20261017-011803`.
All193 default and83 finance tables matched row counts/content hashes after restore;
integrity and foreign-key checks passed. Deleted a synthetic approval event from the
restored copy, detected the mismatch, restored again, and verified proposed/approved/
withdrawn history plus retained withdrawn status. Source hashes unchanged. Manifest
records per-table hashes. Database-only coverage; no private attachment fixture set.

PASS: full standalone suite49 discovered/43 executed/six native skips,3.370s.
Actual GRAND `check` and `makemigrations inventory inventory_finance --check --dry-run`
passed; no migration drift. Pip check and whitespace check passed. GitHub reports no
rulesets and no master branch protection; use branchCI before integration regardless.

## Maintenance development checks - 2026-10-17

Fresh `git fetch origin` on `codex/asset-maintenance` showed HEAD/origin/master 0/0
at28da3f1; only the prior release handoff was dirty before new feature work.
Migration0016, operational services, staff screens and private evidence are in
development. These results do not establish release or production readiness.

PASS: `python manage.py test inventory --noinput`: 60 discovered, 54 executed,
six native-only skips,4.192s before adding three native maintenance races. Eleven
maintenance service/HTTP tests exercise authorization, lifecycle exclusion, stale
writes, validation, event rollback, custody/cost preservation, evidence corruption,
download scope/headers, CSRF and open/work/close rendering. Model drift check and
`git diff --check` passed.

FAIL - CAUSED BY CURRENT WORK: first `python scripts/run_mysql_tests.py inventory`
had six errors in63 tests,12.096s. The new download test called `response.close()`
directly, emitting request_finished outside Django test client's streaming wrapper
and closing the enclosing MySQL test transaction. Later errors cascaded from that
closed connection. Corrected the test to consume `response.streaming_content`
through the wrapper and assert the actual downloaded bytes. No product workaround
or transaction-validation bypass was introduced. First log `.tmp/maintenance-native.log`.

PASS: reran the full native command on a new random schema: 63/63,12.802s, no skips
and no system-check issues. Log `.tmp/maintenance-native-corrected.log`. Added races
cover competing maintenance starts, maintenance versus asset handoff and duplicate
completion, asserting one retained result. Historical lifecycle migration tests now
restore graph leaves rather than leaving the database at0015. MySQL8.4.11 used only
owned loopback33317; verified no `gso_test_` schemas remain and normal shutdown.

NOT RUN - OUT OF SCOPE of this checkpoint: actual-GRAND maintenance authorization,
browser review, populated0016 upgrade and evidence backup/restore/reconciliation.
These remain required before release. No operator migration, grant, deployment,
Finance code edit, vm-commit, integration or push occurred for this feature yet.

## Maintenance final validation and recovery - 2026-10-17

PASS: targeted `manage.py test inventory.test_maintenance inventory.test_maintenance_migration
inventory.test_receiving --noinput`:33 tests,2.011s. New maintenance evidence checker
reuses the receiving checker's namespace-safe local inspection, detecting corruption,
missing files and orphan uploads without modifying them. Populated0015-to0016 replay
compares every pre-existing inventory table and preserves the legacy maintenance
status without inventing cases. Full native `scripts/run_mysql_tests.py inventory`
then passed65/65,15.703s, including the populated migration and three races.
Log `.tmp/maintenance-final-native.log`.

PASS: actual GRAND32ab046 SQLite integration29 discovered/24 executed/five native
skips,2.777s, log `.tmp/grand-maintenance-sqlite.log`. Real employee profiles and
GRAND explicit grants/UAT controls were used. An ungranted superuser cannot manage
maintenance; another owner cannot read the case; repair operations issue no queries
to the Finance store. The existing claim source/attribution/HTTP checks also passed.
Actual GRAND model checks and `makemigrations inventory inventory_finance --check
--dry-run` passed in isolated settings; no schema drift. No GRAND source edits.

PASS: real browser login, asset navigation, opening a case, saving work/cost/reference,
uploading a private bill and completing with a returned-to-service outcome. Screens
visually checked at1440x1000 and390x844: `output/playwright/maintenance-open-desktop.png`,
`maintenance-open-mobile.png`, `maintenance-completed-mobile.png`. Completed mobile
has viewport/scroll width390 and no duplicate IDs. Initial favicon404 is the only
observed browser console resource error. Browser closed; preview port8019 stopped.

PASS: stopped synthetic SQLite/private-file recovery at
`C:/Users/Administrator/.codex/backups/gsov2-maintenance-recovery-20261017-nzu80ff7`.
Backed up, restored and reconciled all37 tables using row counts/content SHA-256;
integrity/FKs valid. Completed case and all four events preserved. Reconciliation
checked the retained bill, detected deliberate corruption and loss in the restored
copy, then passed after copying back the backup evidence. Source database hash
unchanged. Manifest records table/file hashes. This is not an online MySQL or
operator-data restoration claim. Synthetic source retained in
`.tmp/maintenance-preview-_g03g7vp`; no live preview/browser process remains.

PASS: full shell `manage.py test --noinput`:65 discovered/56 executed/nine native
skips,7.048s; `.tmp/maintenance-release-shell.log`. Migration drift, `pip check`
and whitespace checks pass. GitHub API shows no rulesets or master protection.
External Version Manager README reviewed; inspect/preview proposed the maintenance minor release
updating only VERSION/CHANGELOG.

PASS: final actual-GRAND native command `scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation --mysql`:29/29,
8.430s, no skips. Log `.tmp/grand-maintenance-native.log`. The same23 existing GRAND
W036 warnings remain, none in inventory/inventory_finance. Both disposable schemas
removed; no `gso_test_` or `gso_grand_test_` schema remains. Owned MySQL stopped
normally. Canonical master remains28da3f1 and operator DB hash matches preservation
checkpoint before release. External vm-commit and branch/primary CI are next.

Release completed: actual external Version Manager minor commit3905a74 (tag recorded
in CONTINUE and the changelog),
feature branch `codex/asset-maintenance` pushed. BranchCI38941638939 PASS (29s),
including dependency audit, model/drift checks and full regression. Canonical clean
master fast-forwarded and pushed; remote master/tag match
`3905a74f7a0c566334145e063474cb49fe71cf53`. PrimaryCI38941747339 PASS (27s).
Operator database SHA-256 remains
`5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039`.
No deployment or operator migration. Parallel Finance note updated without changing
its source/migrations/shared handoff. Release-result documentation uses separate
`codex/maintenance-release-notes`, created after fresh fetch0/0 with clean worktree.

## Employee custody development checkpoint - 2026-10-17

Fresh fetch on clean GSO60d12af showed0/0 before `codex/employee-custody` creation.
Parallel GRAND remains32ab046 with unpublished Form1 work; inspected identity/profile
files have no local differences. Source adapter and migration0017/custody services
are under development, not released. No operator migrations or permission grants.

PASS: initial actual-GRAND source integration33 discovered/28 executed/five native
skips,3.727s; `.tmp/grand-employee-source-sqlite.log`. This preceded source refinements
and custody service changes, so does not validate the final implementation.
PASS: `manage.py test inventory.test_employee_custody_migration --noinput`, one test,
0.815s: historical transfer fields/asset data preserved, distinct per-row public UUIDs,
employee references remain null. No guessed identities from legacy labels.
PASS: `manage.py test inventory --noinput`,67 discovered/58 executed/nine native skips,
9.973s; `.tmp/employee-custody-shell-migration.log`. Migration drift and whitespace
checks passed. Later owner-check ordering adjustment covered by
`manage.py test inventory.test_employee_sources --noinput`:2/2 PASS0.012s, including
rejection of a caller object with a forged owner in favor of the locked database row.

RUNNING: expanded actual-GRAND SQLite integration, log
`.tmp/grand-employee-custody-sqlite.log`, session60414. Poll the confirmed handle;
do not infer failure/restart from a quiet schema-creation phase. Six custody tests
are added alongside the four source tests. Final native races, UI, recovery and
actor-retention review remain before release. No native server or browser is running.

FAIL - CAUSED BY CURRENT WORK: run60414 finished39 discovered with one test error
and five native skips,3.146s. New changed-department test expected ValidationError,
but the existing department-scope check correctly raised PermissionDenied first.
Corrected the test to assert that denial after a fresh user load; separately restore
the department, change the identity name and assert stale-snapshot ValidationError.
No product authority check was loosened. Prior run's disposable databases removed.
Corrected full integration run86403 is live, log
`.tmp/grand-employee-custody-sqlite-corrected.log`; poll before any restart.

Corrected run86403 PASS39 discovered/34 executed/five native skips2.927s. The
subsequent signed HTTP workflow is under validation in `.tmp/grand-custody-http.log`.
PASS: latest shell `manage.py test inventory --noinput`,69 discovered/60 executed/
nine native skips9.666s; `manage.py makemigrations --check --dry-run` clear.
PASS: `scripts/run_mysql_tests.py`, native MySQL8.4.11,69/69 in28.912s; log
`.tmp/custody-native-shell.log`. Includes populated0017 replay and protection of
requested_by/acknowledged_by/cancelled_by historical actors. No operator data used.

FAIL - CAUSED BY CURRENT WORK: new HTTP run42 tests, three errors/five native
skips3.435s. The minimal joined directory query used nested `__pk` in `.only`,
which Django does not resolve as a concrete field in its nested select mask. Fixed
the query to GRAND's concrete `id` fields and retained the minimal column boundary.
Search results also apply GRAND's existing profile-view predicate. Full native
GRAND run is in progress at `.tmp/grand-custody-native.log` (session60476).

PASS: actual GRAND native44/44 in12.481s, `.tmp/grand-custody-native.log`.
Includes duplicate-request and acknowledgment/cancellation races. Existing23 GRAND
W036 warnings remain; none from inventory/inventory_finance. Subsequent final run
covers tighter actor/asset token binding assertions and final UI wording.
PASS: final standalone SQLite69 discovered/60 executed/nine native skips9.882s,
`.tmp/custody-shell-release.log`. Both environments' pip checks clear. Actual GRAND
`check` and `makemigrations inventory inventory_finance --check --dry-run` pass via
isolated harness settings (no operator environment or databases).
PASS: browser search/review/submit then separate recipient acknowledgment. No owner
cancel action offered to incoming recipient from another GSO office. Desktop1440x1000
and mobile390x844 inspected; no page overflow or duplicate IDs; tables scroll inside
panel. Screenshots `output/playwright/custody-*.png`. Missing synthetic logo/avatar
404s only. Sessions and preview8020 stopped; no operator deployment.
PASS: stopped paired SQLite recovery196 default/83 finance tables, retained named
custody/snapshot/accepted actor/audit. Injected loss detected and restored; source
hashes unchanged. Backup `C:/Users/Administrator/.codex/backups/gsov2-custody-recovery-20261017-nj9xiahl`.
Not online MySQL/private-upload/operator recovery. Canonical operator DB hash unchanged.
Parallel Finance fresh fetch0/0; its unpublished Form1 role additions do not change
the UAT predicate used here. Only the separate GSO integration note was edited there.

PASS: final actual-GRAND native44/44 in11.095s, no skips,
`.tmp/grand-custody-native-final.log`, including tightened actor/asset token binding.
Both schemas removed; verified no GSO test schemas remain on owned33317, followed by
normal SQL SHUTDOWN and process completion. No preview/browser/test server remains.
VM inspect/preview plans the custody minor release, updates only VERSION/CHANGELOG.
Repository has no rulesets or master protection; branchCI remains the release gate.

Published custody commit236c5e1 through the actual external Version Manager.
BranchCI38945305792 PASS before canonical master fast-forward/push; remote master
and tag match236c5e1e265bc1a63b97a9d3271133e94b598f10. Final release diff changed
only intended feature/docs and generated VERSION/CHANGELOG. PrimaryCI38945433056
PASS. No operator migration/grants/deployment. Release-result documentation
uses separate `codex/custody-release-notes`, created after clean fetch0/0.

## Custody review workbench - 2026-10-17

Fresh clean55fc7bf fetch0/0 before `codex/custody-review`. GRAND fetched0/0 with
unrelated unpublished Form1 work preserved. No new schema or data mutation workflow.
PASS: `manage.py test inventory.test_employee_sources --noinput`,4/4 in0.454s.
PASS: `manage.py test inventory --noinput`,70 discovered/61 executed/nine native
skips11.670s, `.tmp/custody-review-shell.log`; model drift clear.
FAIL - CAUSED BY CURRENT WORK: actual GRAND SQLite49 discovered, one incorrect test
expectation and seven native skips5.273s, `.tmp/grand-custody-review.log`. GRAND's
explicit-permission helper requires a department; missing-department employee gets
403. Corrected expectation and checked GSO can still view the retained assignment;
no permission rule loosened. Native expanded run37525 is in progress.

PASS: `scripts/run_grand_source_tests.py --grand-root <clean32ab046> --mysql`,50/50
in14.501s, no skips; `.tmp/grand-custody-review-native.log`. Covers all six new review
cases including retained-identity JSON search on native MySQL. Existing23 GRAND W036
warnings remain; none in GSO. Both schemas removed; owned33317 SQL SHUTDOWN completed.
PASS: real GRAND browser office/legacy and moved-employee personal views at1440x1000
and390x844. Personal scope retains assignment, flags HR movement and omits owner
register link. Client/scroll width390, no overflow elements or duplicate IDs.
Screenshots `output/playwright/custody-review-*.png`; only synthetic logo/avatar404s.
Browser sessions and preview8021 stopped. Synthetic fixture retained separately at
`.tmp/custody-review-preview-6ypwa4un`, copied from the previous preserved fixture.
NOT RUN - OUT OF SCOPE: a new migration/recovery rehearsal and full standalone native
suite. This slice changes only GRAND read queries/screens and a dashboard link;
no models, services, file formats or writes changed. Existing populated/recovery
proof remains applicable. Full shell SQLite70 and actual-GRAND native50 cover the
impacted behavior; tests explicitly preserve inventory state and avoid Finance queries.

Release completed through actual Version Manager minor commitfb2eae2. Branch
CI38947590308 PASS before canonical master fast-forward/push. Remote master/tag
matchfb2eae2c59df7669cb228eb344bc3f1521f1469a. Operator hash remains
5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
No installation, operator migration or grants. PrimaryCI38947689210 PASS.
Documentation follow-up uses separate `codex/custody-review-release-notes`, created
from a clean fetch0/0 checkpoint. No source/schema changes in this follow-up.

## Witnessed custody returns — 2026-10-17

Fresh fetch and clean0/0 at efbc671 preceded `codex/witnessed-custody-returns`.
Further fetch0/0 confirmed no upstream change. Finance checkout was fetched and
unrelated Form1 changes preserved; only its authorized GSO integration note changed.
Scope includes schema, custody services, authorization, private files and HTTP, so
full standalone SQLite/native and actual GRAND native integration are appropriate.

PASS: `manage.py test inventory --noinput`,71 discovered/62 executed/nine native
skips17.436s; `.tmp/returns-shell-final.log`. PASS: `scripts/run_mysql_tests.py`,
71/71 in51.702s; `.tmp/returns-native-shell.log`. Populated0017-to0018 test preserves
existing named custody and transfer identities, defaults old movements to
handoffs and enforces the new kind constraint; isolated1/1 PASS1.048s and included
in both full suites. `makemigrations --check --dry-run` and `pip check` PASS.

PASS: initial GRAND service SQLite55 discovered/48 executed/seven native skips in
5.792s, `.tmp/grand-returns-services.log`. Initial expanded actual GRAND MySQL60/60
PASS17.049s, `.tmp/grand-returns-native.log`, including three return races. Final
expanded61-test run adds maintenance overlap and later-custodian evidence privacy.
FAIL - CAUSED BY CURRENT WORK: that run ended61 tests/one error19.332s because the
new maintenance test attempted completion without recording work. The existing guard
correctly rejected it. Corrected the fixture to record work before closing, preserving
the production guard. Corrected native run61/61 PASS16.937s,
`.tmp/grand-returns-native-corrected.log`; both schemas removed and owned MySQL33317
shut down normally. Existing23 native GRAND W036 warnings remain outside GSO.

PASS: actual GRAND browser record receipt, upload retained evidence, independently
confirm and review known GSO-held asset, desktop1440x1000/mobile390x844. Recording
officer cannot confirm. Confirmed page and returned workbench have matching375px
client/scroll widths (15px scrollbar), no duplicate IDs. Screenshots under
`output/playwright/custody-return-*.png` visually inspected. Only synthetic
logo/favicon404s; no application workflow errors. Both browser sessions and
preview8022 stopped. Fixture `.tmp/grand-source-tests-xrmc1cx7` retained.

PASS: stopped synthetic paired SQLite and private-evidence recovery reconciled198
default and83 finance tables plus one retained return file. Original identity,
independent actors, confirmed assignment and three return events survive. Checker
detected corrupted and missing evidence; restored files pass and source remains
unchanged. Backup `C:/Users/Administrator/.codex/backups/gsov2-return-recovery-20261017-tiw0kkdn`.
NOT RUN - OUT OF SCOPE: online MySQL/operator restoration, deployment, role grants
and human COA/Accounting/HR acceptance. This rehearsal is synthetic stopped recovery.

Release2a7bb5f used actual external Version Manager. BranchCI38951280608 PASS before
canonical master fast-forward/push; remote master/tag match
2a7bb5f978ee1747e869472c243312dc6a683dd1. PrimaryCI38951482546 PASS50s.
Operator DB SHA-256 remains5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
No operator migration, role grant or deployment. Release notes use separate
`codex/custody-return-release-notes` after clean fetch0/0.

## Supplies service integrity — 2026-10-17

Fresh fetch and clean0/0 at e7483a6 before `codex/stock-ledger-validation`.
Actual GRAND source/helper rechecked against fetched32ab046; parallel Form1 edits
preserved. This is a service/permission repair before physical counts, with no schema
or storage-format changes. Expanded standalone/native and actual-GRAND tests cover
the shared receiving-to-stock dependency and explicit authority.

FAIL - PRE-EXISTING reproduced: a direct receipt of0.0004 did not raise validation
despite three-place ledger fields; regression1/1 failed0.348s before the fix,
`.tmp/stock-validation-before.log`. The new service validates decimal fields before
balance/FIFO/persistence and full-cleans the pending model before saving.
FAIL - CAUSED BY CURRENT WORK: initial targeted test expected ValidationError for a
missing department, while the existing resolver correctly raises PermissionDenied.
Corrected the test expectation and removed accidentally rediscovered imported tests;
no authority rule weakened. See `.tmp/stock-validation-after.log`.

PASS: `manage.py test inventory --noinput`,76 discovered/67 executed/nine native
skips14.660s, `.tmp/stock-validation-shell.log`. PASS: `scripts/run_mysql_tests.py`,
76/76 in49.834s, `.tmp/stock-validation-native.log`. Includes five new regression
cases for precision, nonfinite/range/cost failures with no partial writes, required
adjustment reasons, exact fractional FIFO, partial catalog edits and trusted issue
department labels. `makemigrations --check --dry-run` PASS: no schema changes.
PASS: actual-GRAND native63/63 in19.761s, `.tmp/grand-stock-validation-native.log`.
The two new authority tests verify explicit grants, owner boundaries, UAT write
denials/read grants, real department labels and no Finance queries. Existing23
GRAND W036 warnings remain outside GSO. Disposable schemas removed; owned MySQL33317
shut down normally. `pip check` PASS.

NOT RUN - OUT OF SCOPE: a new browser layout or recovery rehearsal. No screen,
file format, migration or backup boundary changed. The shared service path and actual
permission helper are tested; prior paired recovery evidence remains applicable.
No operator migration, permission grant, deployment, Finance posting or official
supplies form is claimed. Physical-count workflow remains next work.

Actual VM patch releasecbece6c integrated/pushed to canonical master after
branchCI38952776429 PASS31s; remote master/tag match
cbece6c9d2875d1b255be29c03ac29ce72ae23ba. PrimaryCI38952884082 PASS41s.
Operator DB SHA-256 unchanged at5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
Documentation follow-up uses separate `codex/stock-ledger-release-notes` after
clean fetch0/0, with no code, schema or storage changes.

## Reviewed supplies counts — 2026-10-17

Fresh fetch and clean 0/0 at8809372 preceded `codex/reviewed-stock-counts`.
GRAND source pinned to fetched32ab046; parallel Form1 changes preserved. Full native
suites are appropriate for new tables, protected user/movement links, shared stock
adjustments, permissions and private files. No operator data migrated.

PASS: `python manage.py test --verbosity 1`,91 discovered/79 executed/12 native
skips in28.059s, `.tmp/stock-count-release-sqlite.log`. PASS:
`python scripts/run_mysql_tests.py`,91/91 in74.794s,
`.tmp/stock-count-release-native.log`, native MySQL8.4.11 on owned loopback33317.
Includes populated0018-to0019 ledger/lot/allocation preservation, generated pending
uniqueness, quantity constraints, duplicate record/approval and receipt-vs-review
races, stale/offsetting movement detection, audit-failure atomic rollback, exact
fractional FIFO, unknown surplus cost, zero-variance review, reviewer-only cancel,
signed-token/CSRF/actor boundaries, private download and integrity failures.
Earlier intermediate native90/90 PASS70.770s and91/91 PASS75.130s are superseded.
PASS: `manage.py makemigrations --check --dry-run`, no changes; `python -m pip check`,
no broken requirements; `git diff --check`.

FAIL - CAUSED BY CURRENT WORK: initial actual-GRAND65-test run had one test cleanup
error (`file_to_stream` is None after the test client wraps/exhausts a successful
stream). Removed the redundant manual close; the test client's exhausted streaming
wrapper closes the source. No application authority or evidence guard was changed.
PASS: final `python scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation --mysql`,
65/65 in19.277s, `.tmp/grand-stock-count-release.log`. Native GRAND permissions,
UAT denials/scoped reads, protected actors, evidence boundaries and zero Finance
queries pass. Existing23 GRAND W036 warnings remain outside GSO. Both test schemas
removed; owned MySQL33317 shut down normally. PASS: `python -m pip_audit -r
requirements.txt`, no known vulnerabilities found.

PASS: actual GRAND browser, isolated fixture`.tmp/grand-source-tests-4_1avirq` on8023:
clerk records8 against10, uploads synthetic PDF; separate reviewer approves an
adjustment-out2, retained ledger becomes8 and configured minimum8 is flagged.
Recorder has no self-approval action. Desktop1440x1000/mobile390x844 inspected;
mobile client/scroll widths both375 (scrollbar excluded), no duplicate IDs on review.
Stock table retains its existing panel scroll without page overflow. Screenshots
`output/playwright/stock-count-*.png` visually inspected. Only synthetic GRAND
logo/favicon404s; no workflow errors. Both browser sessions and preview stopped.

PASS: `.tmp/rehearse_stock_count_recovery.py` backed up/restored stopped paired
SQLite and private files outside Git. All201 default/83 finance table contents,
integrity/foreign-key checks, approved count/native actors, original UUID basis,
linked adjustment and three events survive. `check_stock_count_evidence` detects
changed/missing files, restored evidence passes and original hashes stay unchanged.
Backup `C:/Users/Administrator/.codex/backups/gsov2-stock-count-recovery-20261017-k6d90rer`.
NOT RUN - OUT OF SCOPE: online MySQL/operator recovery, role grants, deployment,
official supplies form acceptance and historical-count reconciliation. These remain
separate gates; this release does not establish financial valuation or post journals.

Actual external VM minor release3ec09d6 integrated/pushed to canonical master after
branch CI38955242812 PASS38s; remote master/tag match
3ec09d6b6e204759c8e5e33b526fc0662e33e25b. Primary CI38955372028 PASS35s.
Operator DB SHA-256 remains5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
Documentation follow-up uses separate `codex/stock-count-release-notes`, fresh clean
fetch0/0; no code/schema/storage changes in the follow-up.

## Receipt-side claim evidence — 2026-10-17

Fresh fetch and clean0/0 at217a4d3 before `codex/receipt-support-basis`. GRAND fetched
0/0 at32ab046; its unpublished Form1 sources and active test freeze preserved.
The optional adapter now pins receipt facts on preview/proposal/review/history,
with additive nullable migration0002. No accepted receipt cost is changed by the
application. This prepares for documentary amendments without inventing old evidence.

PASS: `manage.py test --verbosity 1`, standalone91 discovered/79 executed/12 native
skips in30.089s, `.tmp/receipt-basis-shell.log`. PASS: actual-GRAND
`makemigrations inventory_finance --check --dry-run` through isolated harness setup,
no changes. PASS: `python -m pip check` and `git diff --check`.

FAIL - CAUSED BY CURRENT WORK: initial actual GRAND SQLite71 tests (14.850s) and
native72 tests (35.988s) each hit one invalid fixture attempting accepted quantity2
against delivered1. Database quantity-capacity checks correctly rejected it. Changed
the test to a supply line and coherent delivered/accepted quantities; constraint
unchanged. Initial logs`.tmp/receipt-basis-{sqlite,native}.log` are not passes.
PASS: `python scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation`, final72 tests,
61 executed/11 native skips in12.432s. PASS: same command with `--mysql`,72/72 in
30.325s. Final logs`.tmp/receipt-basis-{sqlite,native}-final.log`.

Coverage includes signed receipt preview freshness, old signed payload without basis,
equal-value quantity/cost changes, header changes, historical screen provenance,
stale cross-claim approvals, NULL legacy basis/capacity/withdrawal, no Finance queries,
and populated0001→0002 preservation of all old row/event values with new NULL basis.
Native test observes the approval waiting in MySQL data_lock_waits while a synthetic
receipt amendment holds the parent lock; after commit it rejects the changed facts
and creates no approval event. It models future correction locking, not an implemented
amendment workflow. Existing23 GRAND W036 warnings are outside GSO. All disposable
schemas removed and owned MySQL33317 shut down normally; Finance33308 untouched.

PASS: actual GRAND browser preview → confirmation → independent approval, followed
by a controlled change of the isolated fixture's live cost100→200. Approved screen
retains recorded100 and warns stale, with withdrawal still available. Desktop1440
and mobile390 inspected, client/scroll widths375, no duplicate IDs. Improved warning
text contrast using GRAND/Bootstrap text-dark; restarted preview verifies dark text
rgb(33,37,41). Screenshots`output/playwright/receipt-basis-*.png`; final warning
image`receipt-basis-warning-mobile-final.png`. Only missing synthetic logo/avatar
resources; no workflow errors. All browser sessions and preview8024 stopped.
Final source hashes retained in`.tmp/receipt-basis-final-source.json`; only late
change was the browser-verified warning contrast class, not service/schema logic.

PASS: stopped synthetic paired recovery preserves201 default/83 finance table
contents, original receipt/claim snapshots, independent approval and events after
the live fixture cost changed. Deliberately deleting the restored approval event is
detected by table reconciliation, then restored from backup; source hashes unchanged.
Final backup`C:/Users/Administrator/.codex/backups/gsov2-receipt-basis-recovery-20261017-8y_nfx_8`.
No private attachments in this fixture; earlier receiving/private-evidence recovery
checks remain separate. NOT RUN - OUT OF SCOPE: operator/online MySQL recovery,
role grants, GRAND installation, legal/Accounting acceptance and cost amendment UI.
Standalone native suite not repeated: no inventory implementation/schema changed;
actual GRAND native covers the changed optional adapter and its shared dependencies.
Canonical operator DB SHA-256 remains5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.

Actual external VM minor release543fef8 integrated/pushed to canonical master after
branch CI38957280486 PASS36s; remote master/tag match
543fef8d72a30783923984c02fa4ea71157ba6bd. Primary CI38957393614 PASS42s.
Release notes use separate `codex/receipt-basis-release-notes`, fresh clean fetch0/0;
no code/schema/storage changes in that follow-up.

## Receiving authority correction — 2026-10-17

Fresh GSO fetch clean0/0 atcbdd0d1, new `codex/receiving-authority`. GRAND source
32ab046 fetched0/0; parallel dirty Form1 work preserved. Before/after probes on
copied, disposable actual-GRAND SQLite stores confirmed the gap: all five actions
were allowed for an ungranted superuser; all four writes allowed for GSO UAT.
After correction superuser actions deny without explicit grants, UAT writes deny,
and granted scoped UAT view remains. Logs`.tmp/receiving-authority-{before,after}.log`.

Initial full standalone SQLite/native: FAIL - CAUSED BY CURRENT WORK, exact cache
header assertion expected only private/no-store, but never_cache safely adds
max-age/no-cache/must-revalidate. Early assertion left the file stream open and
caused Windows cleanup error. Test now exhausts download before assertions and
checks required cache directives. Final SQLite91 discovered/79 executed/12 native
skips PASS28.340s; `manage.py makemigrations --check --dry-run` PASS no changes.

Actual GRAND browser login as GSO UAT: scoped receiving list/detail visible with
no creation/edit/upload/submit/review controls. Screenshot visually inspected:
`output/playwright/receiving-authority-uat.png`. Browser and preview8025 stopped.
Native integration tests also exercise direct POST denial, service denial, owner
isolation, authorized independent acceptance, private file read and zero Finance
queries. Their final outcomes are recorded below once available.

NOT RUN - OUT OF SCOPE: new recovery drill (no schema/storage format changes),
operator grants/migrations, deployment and human acceptance. Prior paired recovery
evidence remains applicable. Canonical operator database SHA-256 unchanged.

Final standalone native91/91 PASS72.475s, log
`.tmp/receiving-authority-shell-native-final.log`. Initial GRAND75 run:
FAIL - CAUSED BY CURRENT WORK (test assertion matched explanatory prose
"Record delivery facts" instead of the create link). Browser and response proved
no create control; changed assertion to the create URL, preserving application
behavior. Final native rerun pending; no production-policy exemption is involved.

Final actual GRAND native75/75 PASS25.703s, log
`.tmp/receiving-authority-grand-native-final.log`; both disposable schemas removed.
Existing23 GRAND W036 warnings remain outside GSO. No new GSO warning.
No extra SQLite integration rerun: native full suite covers changed integration
and shared dependencies; standalone SQLite checks shell portability. Actual VM
README/inspect/patch preview reviewed; intended changes only. Remote rulesets empty,
master unprotected. Publication gated on branch CI, then primary CI verification.

## Legacy asset authority alignment — 2026-10-17

Fresh fetch clean0/0 atb232924; separate `codex/asset-authority`. GRAND fetched0/0
at32ab046; active Form1 working tree/handoff inspected and preserved. Copied
actual-GRAND fixture before probe allowed seven mutations for each of ungranted
superuser and explicitly granted GSO UAT: create/edit, transfer/acknowledge,
disposal request/review and verification record. After correction all14 deny.
Logs`.tmp/asset-authority-{before,after}.log`. No mocked authority or operator data.

New actual-GRAND tests cover explicit-superuser denial, UAT override, unchanged
asset/custody/case/count state and zero Finance queries on denied operations;
scoped history reads/direct POST denials; authorized create/edit/legacy handoff;
and UAT acknowledgment/cancellation denial for a handoff into its own office.
The last own-office test was added after SQLite discovery and is covered by the
final native run. No database schema/storage change.

PASS: standalone SQLite91 discovered/79 executed/12 native skips,23.725s;
standalone MySQL91/91,80.414s. Actual GRAND SQLite79 discovered/68 executed/11
native skips,13.933s. Logs`.tmp/asset-authority-{shell-sqlite,shell-native,grand-sqlite}.log`.
PASS: `manage.py makemigrations --check --dry-run` no changes; `python -m pip check`
no broken requirements. Native GRAND outcome recorded below when complete.

PASS: actual GRAND browser UAT dashboard/history navigation; disposal detail shows
no review form, verification list no start form, count detail no action buttons.
Desktop disposal screenshot and mobile390 count screenshot visually inspected:
`output/playwright/asset-authority-uat-{disposal,count-mobile}.png`. Mobile client
and scroll width375, table scroll stays inside its container. Browser closed;
preview8026 stopped. NOT RUN - OUT OF SCOPE: new recovery drill (unchanged schema
and storage format), operator migration/grants, deployment, official-form acceptance.
Prior coordinated recovery evidence remains applicable.

Final actual GRAND MySQL80/80 PASS25.996s, zero skips, log
`.tmp/asset-authority-grand-native.log`. Existing23 non-GSO W036 warnings remain.
Both aliases destroyed; owned MySQL33317 stopped normally after confirming no
remaining GSO test schemas. Finance33308 untouched. Operator DB hash unchanged:
5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
VM README, inspect and patch preview checked; release contains intended changes.

## Reviewed documentary receipt cost amendments — 2026-10-17

Fresh fetch clean0/0 at83570a2, branch `codex/receipt-cost-amendments`; GRAND32ab046
fetched0/0 with active Form1 changes preserved. Implementation: inventory0020 adds
amendments/events; optional adapter0003 declares dependency, no operations. No
operator grants/migration/deployment. Original accepted receipt, asset and stock
values retained; new claim support uses reviewed documentary cost, not valuation.

PASS commands and scope:
- standalone `manage.py test inventory.test_receipt_amendments --verbosity 1`:
  5/5,0.485s, `.tmp/receipt-amendments-focused.log`.
- standalone `manage.py test --verbosity 1`:99 discovered/85 executed/14 native
  skips,28.913s, `.tmp/receipt-amendments-shell-sqlite.log`.
- `python scripts/run_mysql_tests.py`:99/99,86.671s, zero skips,
  `.tmp/receipt-amendments-shell-native.log`. Includes populated receiving migration
  and native duplicate-record/review races; all existing dependent regressions.
- actual GRAND focused SQLite adapter tests:2/2,0.441s,
  `.tmp/receipt-amendments-grand-focused.log` (fixture runner uses production harness).
- `python scripts/run_grand_source_tests.py --grand-root <pinned32ab046> --mysql`:
  83/83,27.208s, `.tmp/receipt-amendments-grand-native.log`. Includes actual amendment
  commit while claim approval demonstrably waits on receipt lock; stale approval
  rejected after commit. Existing23 non-GSO W036 warnings remain, no new GSO warning.
- copied actual-GRAND fixture targeted `migrate inventory_finance` applies prerequisite
  inventory0020 and adapter0003, preserves receipt/asset row snapshots; both-app
  `makemigrations --check --dry-run` PASS. Dependency-only0003 was added during
  native setup and separately exercised by this focused migration-graph check;
  `.tmp/receipt-amendments-migration-graph.log`. No added DDL beyond tested0020.
- standalone migration drift and `python -m pip check`: PASS.

PASS browser: actual GRAND record75.00 against accepted100.00, upload private source,
review as different explicitly granted GSO user, approved history retains both.
Desktop/mobile screenshots visually inspected at `output/playwright/receipt-amendment-approved-{desktop,mobile}.png`.
Mobile390 viewport/client375/scroll375, no duplicate IDs. Preview8027 and browser
stopped; no human/legal acceptance claimed.

PASS stopped paired recovery:203 default/83 finance tables and3 private files;
original asset/receipt100/effective75 and both events retained. Missing file, changed
file and removed approval event detected and recovered only in restored copy.
Source unchanged. Backup
`C:/Users/Administrator/.codex/backups/gsov2-receipt-amendments-recovery-20261017-g1qxchpl`;
manifest records hashes/table reconciliation. `.tmp/receipt-amendments-recovery.log`.
Both native schemas destroyed and owned33317 shut down normally; Finance33308
untouched. Canonical operator DB SHA256 remains
5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
NOT RUN - OUT OF SCOPE: online/operator recovery, deployment/grants, quantity
reversal, Accounting valuation/JEV changes, official-form or LGU acceptance.
Actual external VM README/inspect/minor preview checked before publication.

## Recognition journal preview — 2026-10-17

Started `codex/journal-source-preview` after fresh fetch, clean GSO HEAD/master0/0
atf0b20e2. GRAND active checkout fetched0/0 at32ab046, with87 parallel dirty/untracked
files preserved; only its authorized GSO coordination note was appended. Actual
published GRAND posting/source/access/model code inspected before implementation.
No schema, permission definitions, allocation reservations or ledger writes added.

- PASS — `grand-auth-venv/Scripts/python.exe .tmp/test_journal_sources_grand.py
  --grand-root C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation`:
  4/4 actual-GRAND SQLite tests,0.480s. Synthetic retained posting fixture, not a
  claim of end-to-end governed posting acceptance. Both-store captured resolver
  queries are SELECT only. Exact binding, checksum changes, draft/unbound/payment
  sources, corrupted posting audit, draft reversal, voided reversal, explicit grant
  including superuser, wrong office, HTTP405/403/404, private-payload omission and
  no-cache response covered. Log `.tmp/journal-sources-focused.log`.
- PASS — `gsov2-development/Scripts/python.exe manage.py test --verbosity 1`:
  99 discovered,85 executed,14 native-only skips;31.769s. Tests standalone optional
  app isolation and broad existing shell regressions. Log `.tmp/journal-sources-shell-sqlite.log`.
- PASS — standalone `manage.py makemigrations --check --dry-run`, `python -m pip check`,
  and `git diff --check`. No schema changes or new dependencies.
- PASS — actual GRAND synthetic reviewer login and source page on disposable8028;
  desktop/mobile screenshots inspected.390px viewport,375px page and scroll widths;
  journal table scrolls locally. Browser and preview stopped. Screens under
  `output/playwright/journal-sources-{desktop,mobile,mobile-lines}.png`.
  Copied fixture lacks GRAND logo/avatar media (404), unrelated to this page;
  no product error observed. Fixture `.tmp/receiving-authority-probe-69jwlgyv`.
- NOT RUN - OUT OF SCOPE — repeating standalone native99-case run: no standalone
  implementation/schema changed; its previous full native PASS is atf0b20e2.
  Full actual-GRAND native suite is the relevant optional-adapter release gate.
- NOT RUN - OUT OF SCOPE — new backup/restore rehearsal: this read-only feature adds
  no persisted data/files or mutations. The paired amendment recovery evidence at
  f0b20e2 remains applicable. Operator migration, grants, deployment and formal LGU
  Accounting/COA acceptance remain unperformed.

Native integration result and release identifiers follow after completion. VM
README/inspect and minor preview inspected: only VERSION and CHANGELOG generated.

PASS — final full native `grand-auth-venv/Scripts/python.exe
scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation --mysql`:
87/87 tests,30.051s, MySQL8.4.11 strict mode on owned33317; both schemas removed.
Existing23 GRAND non-GSO W036 warnings remain. Log
`.tmp/journal-sources-grand-native.log`. Normal owned MySQL shutdown requested after
schema cleanup. Operator DB SHA256 remains
`5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039`.
No additional full GRAND SQLite run: focused4-case SQLite plus full87-case native
cover this read-only adapter change. Branch CI must pass before primary integration.

## Reviewed receipt recognition mapping — 2026-10-17

Fresh GSO fetch clean0/0 atbc2fabc before branch `codex/receipt-journal-mapping`.
GRAND fetched0/0 at32ab046; its active Form1 handoff/source freeze preserved. Only
GSO coordination documentation is changed there. Actual GRAND source posting,
reversal journal lock and retained attribution patterns inspected before design.

Adapter0004 adds default-store mapping/events, no historical backfill or Finance
schema changes. Signed proposal, independent review, dual amount ceilings,
immutable proposal/event checksums, explicit owner/grant/UAT controls and ordered
withdrawal preserve original receipt cost and claim decisions. Default commit is
inside a Finance read/lock transaction; durable default rejects deferred caller
commits. This is one write store, not distributed accounting or valuation.

- PASS — initial actual-GRAND focused SQLite:5 executed/1 native skip,1.548s via
  `.tmp/test_journal_mappings_grand.py --grand-root .../gsov2-grand-source-validation`.
  `.tmp/journal-mappings-focused.log`. Before final durable/authority refinements;
  final native regression below is the release gate.
- PASS — initial full GRAND native94/94,39.534s; included actual create_reversal
  committing while mapping approval observably waited on its original journal.
  `.tmp/journal-mappings-grand-native.log`. Repeated after durable commit guard,
  post-lock authorization recheck and additional signed/UAT tests; not counted as
  final-tree coverage.
- PASS — `gsov2-development/Scripts/python.exe manage.py test --verbosity 1`:
  99 discovered/85 executed/14 native skips,24.295s; standalone remains independent
  of GRAND adapter. `.tmp/journal-mappings-shell-sqlite.log`.
- PASS — populated optional migration on copied amendment fixture: all pre-existing
  inventory/claim rows and Finance DB bytes unchanged. Both-app makemigrations
  check/dry-run passes. `.tmp/journal-mappings-preview-final.log`.
- PASS — actual GRAND browser proposal/preview/confirmation then different officer
  approval60.00 against100.00 source/support. Proposer sees withdrawal only, not
  self-approval. Desktop/mobile screenshots inspected;375px document/scroll widths
  at390px viewport, no duplicate IDs. Files `output/playwright/journal-mapping-approved-*.png`.
  Copied GRAND logo/avatar media absent (404), unrelated fixture limitation. Preview
  8029 and browser stopped. Finance file hash before/after is identical:
  `d2dd9481ea1baa61327b517f3c885b2955dad18d3dd29d824316b3d6b57b9d7c`.
- PASS — stopped paired SQLite recovery:205 default/83 finance tables, retained
  approved60.00 mapping, independent actors/events and original100.00 claim/receipt
  cost. Changed amount and lost approval event detected in restored copy, restored
  from backup; all source rows/files unchanged. No new private evidence location.
  Backup `C:/Users/Administrator/.codex/backups/gsov2-journal-mappings-recovery-20261017-38zpatp_`;
  script `.tmp/rehearse_journal_mappings_recovery.py`, log `.tmp/journal-mappings-recovery.log`.
  Initial harness failed before verification because its private-storage setting
  was missing; fixed the copied-runtime setting, rerun PASS. No product regression.
- NOT RUN - OUT OF SCOPE — standalone native repeat (no standalone implementation
  changed); final native GRAND suite covers the added adapter schema/services.
  Online MySQL operational restore, operator migrations/grants/deployment, financial
  valuation and LGU/COA acceptance remain unperformed.

Final native result and publication checks follow after completion. No test process
was restarted because it was quiet; each handle was tracked to its actual outcome.

Native96/96 PASS34.043s after durable transaction/authority refinements, log
`.tmp/journal-mappings-grand-native-final.log`. Before release review found the
mapping depended on retained receipt metadata without reopening original private
files. Added existing verify_receipt_evidence to current-basis capture and a test
for missing/changed documents with withdrawal still available. Final native97-case
run uses `.tmp/journal-mappings-grand-native-evidence.log`; result pending.

Final recovery rerun after that change:205 default/83 finance tables +2 retained
private delivery/inspection files. Approved60.00 mapping/original100.00 support and
cost preserved. Missing/changed files, changed mapping amount and removed approval
event detected and restored; source stores/files unchanged. Backup
`C:/Users/Administrator/.codex/backups/gsov2-journal-mappings-recovery-20261017-1jvg_14e`;
script `.tmp/rehearse_journal_mappings_recovery_final.py`, log
`.tmp/journal-mappings-recovery-final.log`. Fresh service fixture records and
independently approves using final evidence check; existing browser templates are
unchanged from inspected flow. No new upload location; existing receiving evidence
must be included in coordinated recovery.

PASS — supplementary final-code debit-capacity probe on a fresh copied actual-GRAND
SQLite fixture (`.tmp/probe_journal_debit_capacity.py --grand-root .../gsov2-grand-source-validation`):
two independently approved claim supports of50 each proposed40 each against one60
debit within a balanced100 journal. First approved; second denied for debit capacity,
with claim capacities independently sufficient. This separates debit-ceiling evidence
from the competing same-claim native race. Log `.tmp/journal-mappings-debit-capacity.log`.

PASS — final full actual-GRAND native97/97,34.530s, MySQL8.4.11 strict mode:
`grand-auth-venv/Scripts/python.exe scripts/run_grand_source_tests.py
--grand-root C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation --mysql`.
Log `.tmp/journal-mappings-grand-native-evidence.log`. Includes original private
file absence/corruption, UAT/ungranted-superuser denial, signed token tampering and
actor mismatch, CSRF, immutable history, source staleness, competing approvals,
actual reversal lock wait and durable-transaction nesting rejection. Both schemas
removed; owned33317 shutdown requested normally. Existing23 non-GSO GRAND W036
warnings remain. Operator DB hash unchanged at5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.

VM README/inspect/minor preview inspected; only VERSION/CHANGELOG generated.
Branch CI is required before integration; verify primary CI and remote refs afterward.

Mapping releaseba17b63 integrated/pushed after branchCI38965891940 PASS; primary
CI38966060591 PASS. Master/tag matchba17b6357f192478a2180ea89b41aa4317d1ff0a.
Follow-up documentation-only branch `codex/recognition-mapping-handoff` starts from
that completed primary milestone after fresh clean fetch0/0. Reconciles stale
historical design paragraphs that still described now-published cost amendments and
recognized-JEV links as unimplemented, retaining the genuinely unfinished quantity,
cost-component and valuation scope. Affected local Markdown links and diff check
PASS. NOT RUN - OUT OF SCOPE: repeating local application/native suites for this
prose-only correction; code is unchanged from the final97-case native PASS.
VM inspect/patch preview checked; generated changes are VERSION and CHANGELOG only.

## HR-reference custody review implementation — 2026-10-17

Branch `codex/hr-custody-review`, based on676bc29 after fresh remote fetch and clean
0/0 comparison. GRAND32ab046 freshly checked0/0;87 parallel changes retained, only
GSO_INTEGRATION_REVIEW.md appended. Default-only migration0021, explicit owner
permissions, supplied private HR request and native employee, findings/coverage,
signed submission, independent review/return/cancellation and retained snapshots.
Sorted asset → employee → case locks and changed-set retry cover new named handoffs.
No duplicate HR/Records authority, employee clearance certificate or Finance writes.

- PASS: `gsov2-development/Scripts/python.exe manage.py test inventory user --noinput`:
  99 discovered,85 executed/14 expected native skips,28.987s. Schema/services/shared
  routing justify broad shell coverage. `manage.py check`, copied actual-GRAND
  `makemigrations inventory inventory_finance --check --dry-run`, compileall and
  `git diff --check` pass.
- FAIL - CAUSED BY CURRENT WORK, corrected: first focused6 tests had one fixture
  read of a closed FieldFile; next10 test run had7 cascading errors after the HTTP
  fixture explicitly closed its response/database. The first native109 run used
  that earlier fixture and reproduced the same7 errors (38.952s). Both new native
  races completed successfully there. Tests now consume streaming downloads via
  Django's test-client wrapper. These are test bugs, not pre-existing failures.
- PASS: corrected focused actual-GRAND SQLite `.tmp/test_hr_custody_reviews_grand.py
  --grand-root .../gsov2-grand-source-validation`:12 discovered,10 executed/2 native
  skips,1.470s. Scope: owner/explicit grants/UAT, independent review, actor-bound
  tokens, CSRF, private downloads, stale custody, inactive identity, original file
  and event corruption, actual witnessed return and retained resolved asset.
- PASS: `.tmp/preview_hr_custody.py --grand-root .../gsov2-grand-source-validation`
  copies stopped populated databases, migrates only inventory/default, checks all
  pre-existing inventory/claim/mapping rows equal and Finance byte hash unchanged.
  Preview data was created only in copies. Original Finance digest:
  `d69658dc0f271c7d7202ac6b631ffee3ce9ffe25fdadf3daafdcb407b1423fe6`.
- PASS: real browser recorder saves/submits, has no independent-review control;
  separate reviewer records decision. Desktop/mobile screenshots inspected;
  390px client/scroll widths, no duplicate IDs. Preview8030 and browser stopped.
  An initial wrong preview URL404 was corrected to the actual integration route;
  copied GRAND logo/avatar/favicon404s are synthetic fixture limitations.
- FAIL - CAUSED BY CURRENT WORK, corrected: recovery first found cached FieldFile
  reopening after deletion raised ValueError. Verification now opens the checked
  private filesystem path each time; repeated missing-file test added. Final
  `.tmp/rehearse_hr_custody_recovery.py` PASS, backup
  `.codex/backups/gsov2-hr-custody-recovery-20261017-u2mmahc0`:207 default/83 finance
  tables and3 private files; altered findings, missing review event and missing/
  changed source detected/restored. Original paired sources/files unchanged. This
  stopped synthetic SQLite rehearsal is not live MySQL/operator recovery acceptance.
- PASS: native standalone `gsov2-development/Scripts/python.exe scripts/run_mysql_tests.py` on owned loopback33317:99/99,84.119s; schema removed.
- PASS: final `grand-auth-venv/Scripts/python.exe scripts/run_grand_source_tests.py
  --grand-root .../gsov2-grand-source-validation --mysql`:109/109,38.242s. Both
  schemas removed; owned33317 normal shutdown requested. Includes the final file
  correction and both native races: observed incoming-handoff employee-lock wait
  rejects a newly appearing asset set, and competing review/cancellation retains
  exactly one decision. Log `.tmp/hr-custody-grand-native-final.log`.
- NOT RUN - OUT OF SCOPE: operator migrations/grants, deployment, formal LGU/COA
  acceptance and Finance production scrutiny. No dependencies changed. Official
  clearance, financial liability and general Records association remain separate.

Operator db.sqlite3 SHA256 remains
`5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039`.
Version Manager README/inspect/preview checked: proposed minor release updates
only VERSION and CHANGELOG. All local gates now pass; release and remote CI evidence follow below.

Feature publication: VM release204df28, branchCI38969039410 PASS, then canonical
master fast-forward/push. Remote master/tag verified at
204df2842f76ef141ad5e3a83646672e1faee4cd; canonical clean0/0. PrimaryCI38969293198
PASS. The documentation follow-up records that publication. No code changes
in that follow-up. Owned33317 shutdown exited0; preview8030 stopped. All prior
migration, recovery, browser and native test evidence above applies to this code.

## Stock movement retry safety — 2026-10-17

Scope: receipt/issue/adjust HTTP retry identity, shared stock service and FIFO.
Broad standalone and actual-GRAND suites selected because stock mutation is shared.
- FAIL - PRE-EXISTING, reproduced: new replay regression against published services
  doubled receipt/issue/adjustment quantities (16/4/6 instead of13/7/8).
  Evidence `.tmp/stock-retry-before.log`; fixed by this milestone.
- PASS: `python manage.py test inventory.test_stock_retries` final focused run:
  5 discovered,4 executed,1 native skip,0.716s.
- PASS: `python manage.py test`:104 discovered,89 executed,15 native skips,24.350s.
- PASS: `python scripts/run_mysql_tests.py`:104/104,89.120s, including concurrent
  identical receipt/issue requests producing one movement and FIFO allocation.
- PASS: `python scripts/run_grand_source_tests.py --grand-root
  C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation --mysql`:
  110/110,40.463s. Actual source32ab046; signed HTTP replay, UAT denial, revoked
  permission denial and zero Finance queries covered. Both schemas removed.
- PASS: `python manage.py check`, `python manage.py makemigrations --check --dry-run`,
  `git diff --check`. No migration changes.
- PASS: browser3-unit issue from10 leaves7; desktop form inspected; mobile390px
  client/scroll widths, no duplicate IDs, hidden token not exposed as visible field.
  Screenshot `output/playwright/stock-retry-mobile.png`. Browser did not simulate
  replay; automated HTTP tests do. Synthetic logo/avatar404s remain fixture limits.
- PASS: `.tmp/rehearse_stock_retry_recovery.py`: stopped paired backup/restore of
  207 default/83 finance tables and3 private files; replay of restored identity
  returns original movement/allocation, changed quantity rejected, no added rows.
  Backup `.codex/backups/gsov2-stock-retry-recovery-20261017-ae0mofvh`.
  Original sources unchanged. This is not live MySQL/operator recovery acceptance.
- PASS: owned MySQL33317 normal shutdown exit0 after schema cleanup; browser and
  preview8030 stopped. Canonical operator DB SHA256 remains
  `5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039`.
- NOT RUN - OUT OF SCOPE: operator migration/grants, deployment, current municipal
  official-form acceptance and Finance production scrutiny. No dependencies changed.

Source research and remaining request workflow are recorded in stock-request-design.md.
Version Manager README inspected; release preview and remote CI gate integration.

## Supplied requisitions and physical fulfillment — 2026-10-17

Scope: four new operational models/migration0022, explicit grants, private evidence,
case/stock transactions and screens. Full shell and actual-GRAND native suites are
appropriate for schema, shared stock and authorization impact. Start fetch: GSO
58f7cfa clean0/0; Finance32ab046 fetched0/0 with96 parallel changes preserved.
- PASS: `python manage.py test inventory.test_requisitions`:5 discovered,4 executed,
  1 native skip,0.966s. Covers unchanged entry balance, independent review, partial
  issue, unavailable observation, closure, exact creation retry, stale issue replay,
  over-issue denial, rollback after history failure, exact decimals, scope and
  missing/changed source/history. Initial test storage override was corrected to
  patch the instantiated file storage; subsequent suites use temporary private roots.
- PASS: `python manage.py test`:109 discovered,93 executed,16 native skips,28.161s.
- PASS: `python scripts/run_mysql_tests.py`:109/109,100.492s, including two concurrent
  attempts against the same version yielding one issue and one stale rejection,
  one fulfillment/FIFO allocation and the correct remaining stock. Schema removed.
- PASS: `python scripts/run_grand_source_tests.py --grand-root
  C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation --mysql`:
  112/112,38.137s; default and finance schemas removed. Actual source32ab046,
  explicit grants, native department identity, owner/UAT/ungranted-superuser denial,
  private download scope, revocation and zero Finance queries covered.
- PASS: `python manage.py check`, `python manage.py makemigrations --check --dry-run`,
  `git diff --check`. Migration creates only the four operational default tables.
- PASS: `.tmp/preview_requisition.py` on copied paired fixtures: populated upgrade
  preserves existing inventory/claim/mapping rows and Finance bytes. Real browser
  supplies request entry, dynamic extra row, independent reviewer and3-unit partial
  issue against6 requested; stock10 becomes7. Desktop/mobile screenshots inspected;
  width/scroll390/390 and no duplicate IDs. Browser/preview8030 stopped.
  Initial incorrect integration URL404 corrected; CLI multiline quoting rejected
  before interaction, then executed from a JS file. Synthetic logo/avatar404s are
  existing fixture limitations. These are not product regressions.
- PASS: `.tmp/rehearse_requisition_recovery.py`: stopped paired recovery211 default/
  83 finance tables,4 private files; backup
  `.codex/backups/gsov2-requisition-recovery-20261017-2xmbbwth`.
  Request, original issue, FIFO and history preserved; stale issue replay denied,
  altered request and missing evidence detected; sources unchanged. Read-only
  `check_requisition_evidence` reports1 checked, zero discrepancies. Not live
  MySQL recovery or operator acceptance.
- FAIL - CAUSED BY CURRENT WORK, corrected: initial VM preview found a Windows
  encoded en dash in the edited design document. Corrected to UTF-8; Markdown
  decoding check and repeated VM preview pass, only VERSION/CHANGELOG proposed.
- PASS: owned MySQL33317 normal shutdown exit0 after all schemas removed. Canonical
  operator DB SHA256 remains
  `5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039`.
- NOT RUN - OUT OF SCOPE: operator migrations/grants/deployment, official-form
  acceptance, cross-installation data import and Finance production scrutiny.
  Returns, Accounting recognition and cost allocation remain separate roadmap work.

Version Manager README/inspect/preview reviewed; minor release gates primary
integration on successful branch CI, then verifies remote/tag and primary CI.

## Original-issue supply returns — 2026-10-17

Scope: two default operational models/migration0023, original issue/allocation
capacity, stock/FIFO transactions, explicit grants and private evidence/screens.
Full shell and actual-GRAND native suites selected for schema/auth/shared stock
impact. Start sync: GSO2ae5a9e clean0/0; Finance32ab046 fetched0/0 with96 parallel
changes preserved. Working branch codex/supply-return-lineage.

- PASS: `python manage.py test inventory.test_supply_returns`:7 discovered,
  6 executed,1 native skip,0.938s before the added prior-history/source checks.
- PASS: final `python manage.py test`:116 discovered,99 executed,17 native skips,
  32.523s. Covers exact decimals, partial/known-lot/unknown-cost/quantity-only returns,
  independent review, suitability confirmation, unchanged original issue, decline,
  cancellation, rollback, request retry, duplicate acceptance, missing/changed
  evidence, changed source/history and blocking unlinked legacy returns.
- PASS: final `python scripts/run_mysql_tests.py`:116/116,109.832s; includes two
  competing4-unit return cases against an original5-unit issue: exactly one is
  accepted, one fails capacity, one return movement/lot results. Schema removed.
- PASS: `python manage.py check`, `python manage.py makemigrations --check --dry-run`
  and `git diff --check`. Actual GRAND router restricts non-Finance models to default.
- PASS: `.tmp/preview_supply_return.py` on copied populated paired fixture:0023
  preserves existing inventory/claim/mapping/requisition rows and Finance bytes.
  Real browser follows original issue, records1-unit return with documented source
  lot, separate reviewer confirms usable stock and accepts; stock7 becomes8,
  source cost30 retained. Desktop/mobile screenshots inspected;390px page/scroll,
  no duplicate IDs. Browser and preview8030 stopped. Existing synthetic logo/avatar
  missing-file404s are fixture limitations, not a product regression.
- PASS: `.tmp/rehearse_supply_return_recovery.py`: stopped paired recovery of213
  default/83 finance tables and5 files, backup
  `.codex/backups/gsov2-supply-return-recovery-20261017-kpt5jkgy`. Original3-unit issue,
  original requisition issued quantity/status and new1-unit cost30 return lot remain
  intact. Stale acceptance rejected; altered returned lot and missing file detected;
  restored table rows/files match backup and original sources remain unchanged.
  `check_supply_return_evidence` reports1 checked, zero discrepancies. This is not
  live MySQL/operator recovery acceptance.
- NOT RUN - OUT OF SCOPE: operator migrations/grants, deployment, official-form/
  costing acceptance, legacy return repair and Finance production scrutiny.

VM README/inspect/preview reviewed; proposed minor updates only VERSION/CHANGELOG.
Native GRAND completion and release evidence follow the same primary CI gate.

Final local gate: `grand-auth-venv/Scripts/python.exe scripts/run_grand_source_tests.py
--grand-root C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation
--mysql` PASS114/114,39.941s. Native identities, explicit receive/review grants,
UAT/owner/ungranted-superuser controls, revoked permission and zero Finance queries
are covered. Both aliases removed; owned33317 normal shutdown exit0. Operator DB
SHA256 remains5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
Source research found a dated PHALGA presentation as a corroborating deferment
lead, not current return-costing authority; the feature document records that limit.

Publication verified: featuree78c404, branchCI38973327525 PASS, then canonical
master fast-forward/push. Remote master/tag match
e78c4043386c322bbaef023e46cb1d1f19046a26. PrimaryCI38973485610 PASS; canonical clean0/0.
Documentation follow-up corrects the PHALGA slide reference: deferment is on8–11,
proposed enhancements follow later. No application changes. Native suites are
NOT RUN - OUT OF SCOPE for this documentation-only follow-up; the unchanged code
retains the completed native/browser/recovery evidence above. Diff/UTF-8/VM preview
checks apply; remote CI still gates integration under the normal workflow.

## Receipt-origin asset edit protection — 2026-10-17

Fresh fetch and file status: canonical master clean/synchronized at4a81990;
feature branch codex/received-asset-source-protection. Prior goal turn completed
publication (progress). Finance fetched at32ab046 with its unpublished changes
preserved. Its latest filtered-JEV output probe is recorded in its own handoff.

Source inspection found update_asset accepted changes to original receiving cost,
quantity, supplier and PO. Added a locked service guard and disabled form fields;
no schema, Finance data, evidence storage or historical row changes. Tests cover
rejection without audit writes, same-value/description/tag updates, forged form
inputs, original NULL cost, legacy unlinked edits, and GRAND HTTP behavior with
zero Finance queries. No new Accounting classification rule is asserted.

- PASS: `python manage.py test inventory.test_receiving --verbosity 1`:21/21,
  0.891s. Initial two runs FAIL - CAUSED BY CURRENT WORK in the new test fixture:
  omitted required property tag, then two existing rollback assertions accidentally
  placed under the new test. Restored them to their original test and supplied the
  required tag; no production assertion weakened.
- PASS: `python manage.py test --verbosity 1`:117 discovered,100 executed,
  17 native skips,34.412s; `.tmp/received-asset-shell.log`, exit0.
- PASS: `python manage.py check`; `python manage.py makemigrations --check --dry-run`;
  `git diff --check`.
- PASS native commands: `python scripts/run_mysql_tests.py` (117/117,109.011s) and
  `python scripts/run_grand_source_tests.py --grand-root
  C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation --mysql`
  (114/114,38.756s). Both exit0, no skips, disposable schemas removed.
  Logs `.tmp/received-asset-shell-native.log` and `.tmp/received-asset-grand-native.log`.
  Owned33317 normal shutdown requested after checking no test schemas remain.
- NOT RUN - OUT OF SCOPE: new populated migration/recovery rehearsal, since this
  patch introduces no schema, stored-field, file or backup-path change. Earlier
  paired recovery evidence is retained; it is not presented as a new rehearsal.
- NOT RUN - OUT OF SCOPE: new visual browser pass; existing form layout is unchanged,
  with disabled fields/help text and rendered HTTP/form behavior covered by tests.

Property assessment: Asset.inventory_class is an operational reporting group, not
PPE/semi-expendable recognition; no useful-life/expiration fields exist. Existing
fund/account strings do not resolve Finance dimensions. Current receipt claim and
journal mappings allocate monetary support, not physical cost components. Follow
verified COA2024-006 annexes and Finance ownership for the next design; do not infer
classification from threshold alone or introduce a second Accounting SPLC.

## Property-record source/design checkpoint — 2026-10-17

Previous goal turn: progress, published25004cc after branchCI38974856868 and
primaryCI38975011553 PASS. Fresh fetch now GSO clean0/0; Finance32ab0460/0 with103
modified/untracked paths retained. This branch contains documentation only.

Re-inspected retained official COA2024-006 pages2,3,7,8 visually and current ONAR
metadata (issued2024-03-14, filed2024-04-15; filing is not proven publication).
Compared actual Asset/ReceivingLine/AssetTransfer and GRAND Fund/LedgerAccount/
ResponsibilityCenter definitions, plus optional claim/journal source services.
One attempted read of inventory/journal_sources.py failed because the actual file
is inventory_finance/journal_sources.py; discovered and inspected the latter.
No inferred model or nonexistent API was used in the selected design.

The design distinguishes individually retained custody, supplied property treatment/
useful-life evidence, independently authorized Finance dimension links, class/fund
SPC and Accounting SPLC. Existing money support is not physical cost allocation.
Corrected an obsolete statement that actual-GRAND native integration was unverified;
latest114/114 proof exists, while operator import/installation remains unverified.

PASS: source/model comparison and relative documentation link check; git diff check.
NOT RUN - OUT OF SCOPE: application/native/migration/recovery/browser suites for this
documentation-only change. Retain25004cc results above without presenting them as
new executions. Branch/resulting-primary CI remain the publication gates. No operator
migrations, grants, data updates or deployment.

## Supplied property determination workflow — 2026-10-17

Previous goal turn: progress (source-backed design published08b777b). Fresh GSO
fetch/status clean0/0; feature branch codex/property-determination-workflow.
Finance32ab0460/0 with104 modified/untracked paths preserved; its current handoff
is103-path release preparation. No Finance application code or operator data changed.

Inventory0024 creates two default-only tables with protected asset/native actors,
UUID/predecessor history, a unique virtual pending marker and independent decisions.
The service records supplied facts; unknown duration/expiry stay unknown. It does
not set financial treatment, mutate custody or expire accountability. Review locks
linked receipt then asset then case, matching acceptance/amendment ordering. Exact
UUID replay and version checks retain one operation. Forms, scoped/no-store views,
private downloads, asset navigation and read-only evidence checker accompany it.

Executed commands/results:
- Initial `python manage.py test inventory.test_property_determinations`: FAIL -
  CAUSED BY CURRENT WORK: four source-basis comparisons differed because a newly
  created Decimal60000 serialized differently from its reloaded60000.00 value.
  Normalized monetary/duration snapshots to two decimals; subsequent6/6 PASS0.301s.
- `python manage.py test inventory.test_property_determinations
  inventory.test_property_migration inventory.test_property_races`: initially8
  discovered/7 run/1 native skip PASS0.942s. Added receipt-version rejection and
  guarded-save/replay cases; final focused9/8 run/1 skip PASS1.073s.
- Initial full `python manage.py test --verbosity 1`:126 discovered,108 executed,
  18 native skips PASS39.469s (`.tmp/property-shell.log`,exit0).
- Initial `python scripts/run_mysql_tests.py`:126/126 PASS124.260s
  (`.tmp/property-shell-native.log`,exit0). Competing reviewers retain one decision;
  populated migration preserves assets and enforces pending/independent/life constraints.
- Initial `python scripts/run_grand_source_tests.py --grand-root
  C:/Users/Administrator/.codex/worktrees/gsov2-grand-source-validation --mysql`:
  116/116 PASS43.659s (`.tmp/property-grand-native.log`,exit0). New actual-GRAND tests
  prove native actor links, explicit permissions, owner/UAT/revocation denial,
  rendered/scoped history and zero Finance queries.
- Final versions of those three broad commands after guarded-save and presentation
  refinements: SQLite126 discovered/108 executed/18 native skips PASS41.953s;
  native126/126 PASS124.516s; actual GRAND32ab046116/116 PASS42.772s. All exit0.
  Logs use the same names with `-final` suffix.
- `python manage.py check`, `python manage.py makemigrations --check --dry-run`
  and `git diff --check`: PASS. No runtime migration was applied to operator data.

Disposable GRAND preview: `.tmp/preview_property.py`, final runtime
`.tmp/property-preview-bdk61_k6`. Copied prior stopped paired fixture; migration
preserves all preexisting inventory/claim/mapping/return rows and Finance bytes.
The first preview helper stopped because that fixture contained no owner-office
asset; supplied a clearly synthetic individual laptop in the copy, then continued.
This was a fixture setup failure, not a bypass of an application check. Its failed
copy `.tmp/property-preview-71fwhnni` is retained. Synthetic users retain explicit
permissions; these are not migration role grants.

Playwright `property`: clerk recorded PROPERTY-DOC-BROWSER-001, semi-expendable
as supplied, five years from supplied start basis, expiry blank. Separate reviewer
verified it; original asset cost12500/custody unchanged. Refined raw choice codes to
readable labels, restarted the preview on the same data, and visually inspected
`output/playwright/property-verified-desktop.png` and `property-verified-mobile.png`.
Mobile width390 client/390 scroll. Browser closed and server stopped before backup.
Existing synthetic logo/avatar404s are fixture limitations. No official-form acceptance.

`python .tmp/rehearse_property_recovery.py`: PASS, stopped paired SQLite backup and
restore at `C:/Users/Administrator/.codex/backups/gsov2-property-recovery-20261017-onipyxpj`.
215 default tables,83 finance tables,6 private files. Original and restored table/file
manifests agree. Supplied facts, events and prior workflow rows are retained. This
fixture has one property record with NULL predecessor; successor chains are covered
by unit tests, not this restore. Stale verification is denied, changed useful life and repeatedly
missing source file are detected. `check_property_evidence` reports1 checked and
no missing/changed/unsafe/unreferenced files. Source database/file hashes unchanged.
This does not prove live MySQL recovery, deployment or LGU operational acceptance.

Recovery predates the final internal save-guard tightening; its persisted schema,
file handling and read-only history checks are unchanged. Final focused tests
exercise the stricter save path; final broad native reruns passed as recorded above.

During validation, parallel Finance produced candidate a533482. Its inspected
diff adds Form 1 roles; GSO access helpers and native identity/dimension definitions
are unchanged. A separate clean detached checkout at
`C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation` is used for
the same actual-GRAND native harness:116/116 PASS40.854s, Python exit0, log
`.tmp/property-grand-v173-native.log`. Both disposable schemas were destroyed.
The active Finance checkout was preserved; this proves compatibility with that
candidate, not its hosted gates, deployment or LGU acceptance.

Publication: actual VM release9070496, branch CI38977539972 PASS, primary
CI38977725084 PASS. Remote master and release tag resolved to
907049686079bd609bdc15bf1edf1610a44d37f0. Canonical checkout clean0/0;
operator SQLite SHA256 unchanged at
5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
Disposable MySQL33317 shut down normally after all test schemas were removed.

## Native property-link ownership design — 2026-10-17

Previous turn: progress (published property workflow). Fresh fetch/status:
GSO9070496 clean0/0; Finance a533482 candidate, origin/master32ab046, only the
preserved GSO coordination note untracked. Reviewed actual source listed in
property-finance-links.md. Found the earlier design lacked explicit cross-office
property sharing and that native Department has no UUID. Selected a scoped GSO
request with separate Finance proposal/review and explicit import-ID remapping.
Reviewed setup UPDATE/issuance/readiness paths to distinguish direct dimension
lock order from journal-backed case-before-receipt order. Native concurrency proof
is a future implementation gate, not claimed by source inspection.

Some attempted reads used nonexistent paths or PowerShell wildcard arguments;
corrected via rg file discovery and inspected accounting/services.py and the GSO
adapter in their actual separate repositories. No missing API was assumed.
NOT RUN - OUT OF SCOPE: new application/native/browser/recovery suites for this
documentation-only design. Prior9070496 results remain historical evidence.
Documentation links/diff checks and hosted publication checks are the applicable
gates. No migrations, grants, operator changes or Finance application edits.

## Explicit property Finance requests — 2026-10-17

Previous turn: progress. Design checkpoint e9b3c74 had branch CI38978070046 and
primary CI38978241661 PASS. Fresh fetch/status GSO e9b3c74 clean0/0; Finance
a533482 candidate with remote master32ab046 and only GSO note untracked.
Feature branch codex/property-finance-links preserves the parallel work.

Adapter0005 adds two default tables, a unique virtual active-link marker and
independent-approval constraint. No data backfill or role grants. GSO explicitly
shares one verified property record/packet; selected Finance owner proposes
native UUID dimensions and a different actor reviews. Optional approved mapping
support checks exact materialized-asset lineage and retained source. Writes use
default only; Finance locks cover the durable default commit. Withdrawal does
not require unavailable current sources. Existing GSO URLs remain owner-scoped.

Executed validation:
- `python .tmp/run_property_links.py --grand-root .../gsov2-grand-v173-validation`:
  initial7/7 PASS0.688s, exit0, `.tmp/property-links-focused.log`.
- Same command with `--mysql`:12 tests, FAIL - CAUSED BY CURRENT WORK, one fixture
  error and one HTTP test failure. Journal fixture passed a newly created asset's
  integer100 cost into a snapshot compared against reloaded Decimal100.00. Refresh
  the persisted fixture before capturing its source. HTTP test used old names
  after browser-discovered form-prefix correction. Updated its payload; no source
  guard or independent-review requirement was weakened. Log
  `.tmp/property-links-native-focused.log`. Other10 tests passed, including native
  review/withdraw and actual GRAND setup archive concurrency.
- `python manage.py test inventory.test_property_determinations --verbosity 1`:
  7/7 PASS0.414s, exit0, `.tmp/property-links-shell-focused.log`.
- `python manage.py test --verbosity 1`:126 discovered/108 executed/18 native
  skips PASS46.216s, exit0, `.tmp/property-links-shell-full.log`.
- `python scripts/run_grand_source_tests.py --grand-root
  C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation --mysql`:
  full native130/130 PASS70.080s, exit0; `.tmp/property-links-grand-full.log`.
- Final focused native command also includes the new actual setup-edit race,
  in addition to archive/review/withdraw/property-successor checks and populated
  migration. Separate unique schemas, `.tmp/property-links-native-final.log`:
  15/15 PASS14.809s, exit0. Adding that test did not change application code after
  the broad run began.
- Strengthened the setup-race assertion: the native UPDATE must remain incomplete
  during a250ms execution window while approval holds its lock, not merely before
  its thread has been scheduled. Targeted actual archive/edit tests rerun through
  `.tmp/run_property_setup_locks.py`, `.tmp/property-links-setup-locks-final.log`:
  2/2 PASS2.984s, exit0; application code unchanged.
- Standalone check/migration drift, optional-adapter drift in copied preview and
  git diff check PASS. Operator databases were not migrated.

Populated preview copied stopped property fixture into
`.tmp/property-link-preview-4zdv8fr8`, using clean GRAND32ab046. Applying adapter0005
preserved all existing inventory/claim/mapping/property rows and exact Finance
bytes, before adding clearly synthetic Finance users/dimensions. No operator
grants or source-fixture edits. Browser initially reached citizen sign-in; followed
the documented employee route. The full workflow used separate requester,
proposer and reviewer logins. Proposer had no approval control. Corrected duplicate
reason-field IDs with separate form prefixes, added office codes for duplicate
department names, and styled controls using GRAND's existing conventions.
Inspected desktop/mobile screenshots under output/playwright/property-finance-
approved-*.png. Mobile client390/scroll390; approved page duplicate IDs empty.
Synthetic missing-logo/avatar assets remain fixture limitations.

Stopped preview before seeding a service-driven withdrawn predecessor/approved
replacement for recovery; verified those operations made no Finance writes.
`python .tmp/rehearse_property_link_recovery.py`: PASS, exit0; backup
`C:/Users/Administrator/.codex/backups/gsov2-property-link-recovery-20261017-4_u2xo4w`.
Retained217 default tables,83 Finance tables,6 private files, exact all-table/file
manifests, original property/custody and both link histories. Restore checks reject
stale approval, altered link/useful-life history, missing packet and missing native
Fund. Tamper probes roll back; restored manifests and untouched source hashes agree.
This is stopped synthetic paired SQLite recovery, not online MySQL recovery,
operator installation, official SPC/PAR/ICS acceptance or production readiness.

All native runs terminated and removed their disposable schemas. Owned MySQL33317
shut down normally. Clean source checkout a533482 is unchanged; canonical GSO
operator SQLite hash remains5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
Documentation links/diff checks PASS. VM inspect/preview selects a minor feature
release touching VERSION/CHANGELOG; actual publication and hosted gates follow.

## Property working register — 2026-10-17

Branch `codex/property-working-register`, baseline6c1ba3e after fresh fetch and
clean canonical0/0; Finance candidate a533482 unchanged with its GSO note preserved.
Rechecked ONAR record3842 metadata; no new executable COA rule or official form.
This is a scoped current preparation view, not a historical SPC balance. It adds
no models, migrations, write services, Finance queries or permission assignments.

- PASS: standalone affected `manage.py test inventory.test_property_determinations
  --verbosity 1`:9/9,0.559s. Latest verified filters ignore pending successors,
  successor verification replaces filters, missing/grouped/retired assets remain,
  owner/grant boundaries, stale/missing sources and POST denial tested.
- PASS: full standalone `manage.py test --verbosity 1`:128 discovered,110 run,
  18 native-only skips,45.688s; `.tmp/property-register-shell.log`, exit0.
  Full suite selected because the shared navigation helper now calls property access.
- PASS: `manage.py check`, `manage.py makemigrations --check --dry-run`,
  `git diff --check` (only Git line-ending notices).
- Browser PASS: actual GRAND candidate with isolated synthetic copied databases;
  GSO login, retained source/useful life, class filter, missing-document filter,
  clear and current custody display. Desktop1280 and mobile390 screenshots visually
  inspected: `output/playwright/property-register-desktop.png` and `-mobile.png`.
  Initial manual navigation used an incorrect prefix and returned404; corrected
  to the harness's actual `/gso/inventory/property-records/`. This was not an app defect.
  Login's missing default avatar/logo remain existing fixture limitations. Browser
  and preview server stopped. No operator files or grants touched.
- NOT RUN - OUT OF SCOPE: repeated populated migration/paired restore rehearsal;
  no schema, write path or evidence namespace changes. Prior6c1ba3e recovery remains
  historical evidence, not a new recovery result. Official SPC/form parity and
  local operational acceptance remain unfinished.

- PASS: actual GRAND candidate a533482, `scripts/run_grand_source_tests.py
  --grand-root C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation`:
  SQLite132 discovered,111 run/21 native-only skips,32.415s, exit0;
  `.tmp/property-register-grand.log`. Explicit native owner/UAT/superuser boundaries
  and zero Finance queries included. No SQLite concurrency claim.
- PASS: native MySQL8.4.11 focused `gso_integration_tests.grand_property`, same
  harness with `--mysql`, labels narrowed by ignored
  `.tmp/test_property_register_native.py`:3/3,1.760s, exit0;
  `.tmp/property-register-native.log`. Disposable schemas removed; owned
  MySQL33317 normal shutdown confirmed, exit0. No concurrent mutation changed.
- Final wording refinement: register cost replaces an unjustified original-cost
  label for mutable legacy assets; affected9/9 PASS0.566s. Screenshots precede this
  wording-only refinement; no layout change. Full suites precede this label change.
  A local documentation update hit the Windows default text encoding; corrected
  affected files back to UTF-8 and reviewed diffs before release.
  Source PDF hash matches its receipt; visually revisited AnnexA.2 page8 numbering
  and balances. Stock balance differs from continuing custody after issue.

Local gates complete; actual VM and hosted release checks follow.

## Supplied acquisition facts — 2026-10-17

Fresh sync at9acd9b9, canonical clean0/0; Finance a533482 candidate with only the
preserved GSO coordination note. Branch `codex/property-acquisition-facts`.
Reopened official ONAR3842 metadata and visually rechecked retained AnnexA.2 page8;
PDF hash remains1b00c4e1359868972a84a732dda442619eed040877fb6460acc502250fe15c53.
The selected engineering change reuses PropertyDetermination and its private packet,
source locks, grants, independent review and successor history. Inventory0025 adds
three supplied facts and a source-reference check constraint; no Finance writes,
number allocation, asset date/tag changes, role grants or operator migration.

- PASS: `manage.py test inventory.test_property_determinations --verbosity 1`,
  11/11,0.593s. Covers supplied/unknown dates, required source, future date rejection,
  immutable snapshot, exact replay, changed replay denial, preserved prior events,
  unchanged asset facts, detail/register rendering and tamper detection.
- PASS: `manage.py test inventory.test_property_migration --verbosity 1`,2/2,1.590s,
  `.tmp/property-acquisition-migration.log`. Populated0024-to0025 preserves asset
  rows, old pending/verified snapshots and checksums; new reference constraint tested.
- PASS: full shell `manage.py test --verbosity 1`,131 discovered,113 run/18 native
  skips,45.630s,exit0; `.tmp/property-acquisition-shell.log`. Broad scope selected
  for schema, shared property snapshots and Finance association dependencies.
- PASS: full standalone native `scripts/run_mysql_tests.py`, MySQL8.4.11,131/131,
  137.186s,exit0; `.tmp/property-acquisition-native.log`, disposable schema removed.
- PASS: final affected11/11,0.720s after clarifying the working register's purchase
  date wording; that label is distinct from the supplied acquisition date.
- PASS: `manage.py check`, `manage.py makemigrations --check --dry-run`,
  copied native-GRAND drift check for both apps, `git diff --check`.
- Populated actual-GRAND copy: initial broad equality assertion FAIL in ignored
  validation helper because native post_migrate seeded27 help guides/198 steps for
  synthetic departments added after the old fixture migration. Inspected actual
  departments app/signal/seed code and row changes; existing guide rows unchanged.
  Corrected helper permits only additions in those two native guide tables and
  still checks every prior row across216 non-migration tables. PASS: old property
  history, valid approved Finance link, other rows, evidence and Finance bytes
  preserved. Runtime `.tmp/property-acquisition-preview-vnf1wlwp`.
- Browser PASS: distinct GSO recorder/checker created and independently verified
  PROPERTY-ACQUISITION-BROWSER-001, acquisition2026-09-01/source reference/item26-01-01,
  while asset purchase_date remains unknown. Prior determination retained. Desktop
  and390px mobile screenshots visually inspected; no horizontal overflow. Screens
  precede the wording-only register purchase-date clarification. Existing login
  default image404s remain fixture limitations. Preview and browser stopped.
- Recovery PASS: stopped paired SQLite217 default/83 Finance tables/7 private
  packets restored with all row/file manifests equal. New acquisition facts and old
  unknowns retained; stale decisions, missing file, changed useful life and item
  number detected. Older approved Finance link retains its history but requires
  review after the verified property successor. Source copies unchanged.
  Backup `C:/Users/Administrator/.codex/backups/gsov2-property-acquisition-recovery-20261017-hr44lsyg`;
  `.tmp/property-acquisition-recovery.log`,exit0. Not online MySQL/operator recovery.

Full actual GRAND native regression PASS133/133 in55.510s, exit0; command
`scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation --mysql`, log
`.tmp/property-acquisition-grand.log`. Candidate a533482, real two-store router
and MySQL8.4.11; includes successor-to-Finance association invalidation, unchanged
approval history, native ownership and concurrent setup/property review tests.
All disposable schemas removed; owned MySQL33317 normal shutdown confirmed.
VM publication/hosted gates follow. Official SPC, movement numbering, openings, cost allocation and
operational acceptance remain incomplete; no compliance or deployment claim.

## Disposal lock order and fresh authority — 2026-10-17

Branch `codex/disposal-lock-order`, baseline9fc6acc, after fresh clean0/0 fetch.
Finance candidate a533482 unchanged except preserved GSO coordination notes;
remote Finance master32ab046. Source trace of future SPC movement support found
joined disposal case/asset locks, unlike existing asset-first handoff/maintenance.
Review/resubmission now use separate asset-before-case locks, reject retargeting
and recheck fresh scope; submission also rechecks scope after its asset lock.
Completion reuses the same locked asset. No schema, Finance, UI or evidence-format
changes. No production deadlock is claimed from source inspection alone.

- FAIL - PRE-EXISTING, reproduced: isolated SQLite baseline probe executes the
  actual9fc6acc services module in its own process and in-memory test database.
  `inventory.test_disposal_locking.DisposalLockingTests.test_review_and_response_recheck_locked_asset_scope`
  fails because PermissionDenied is not raised after the asset owner changes.
  `.tmp/disposal-lock-baseline.log`,exit1,1 test0.015s. The current implementation
  passes that same test; no operator code/database was substituted or migrated.
- PASS: `manage.py test inventory.test_disposal_locking --verbosity 1`,6 discovered,
  3 run/3 native-only skips,0.036s. Retargeted case denial, fresh owner checks and
  single completion with retained custody/cost/audit are exercised.
- PASS: full shell `manage.py test --verbosity 1`,137 discovered,116 run/21 native
  skips,46.387s,exit0; `.tmp/disposal-lock-shell.log`. Broad suite selected because
  shared asset services underpin handoff, maintenance, disposal and property work.
- PASS: `manage.py check`, `manage.py makemigrations --check --dry-run`,
  `git diff --check`. No migration changes.
- Native-only coverage: while an asset is locked, competing review/resubmission
  must wait before taking the case; after observing the worker's lock attempt and
  a250ms blocked window, the asset holder can lock the case NOWAIT. Competing
  completions must retain one event and one asset audit entry. Fresh GRAND owner
  denial and no Finance queries have an actual-native integration test.
- NOT RUN - OUT OF SCOPE: new browser/layout, populated schema and paired recovery
  rehearsals; no UI, schema, file namespace/format or recovery contract changes.
  Prior recovery evidence remains historical. Existing GRAND HTTP/authority tests
  are included in the broader integration run; no new browser pass is claimed.

Full standalone native `scripts/run_mysql_tests.py` PASS137/137 in132.057s,
exit0; `.tmp/disposal-lock-native.log`, schema removed. Full actual GRAND native
`scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation --mysql`
PASS134/134 in54.937s, exit0, against candidate a533482;
`.tmp/disposal-lock-grand.log`. Both disposable schemas removed and owned
MySQL33317 normal shutdown confirmed. Actual VM release/hosted gates follow. No operator migration, grant or
deployment; operator SQLite hash unchanged. The source map documents remaining
SPC gaps and legacy disposal attachment hash/service-validation prerequisites.


## Disposal evidence integrity — 2026-10-17
Baseline577c549, clean0/0 after fetch; new feature branch. Finance candidate a533482,
master32ab046 unchanged except the preserved coordination note. No operator changes.

- PASS: focused initial10 (7 run/3 native skips),0.092s.
- PASS: full shell `manage.py test --verbosity 1`,142 discovered,121 run/21 native
  skips,44.109s,exit0; `.tmp/disposal-evidence-shell.log`. Includes populated0025→0026
  preservation of attachment facts and old event snapshots. Broad scope selected
  for shared evidence checker and disposal workflow changes.
- PASS: system checks, migration drift and diff whitespace checks.
- PASS: actual GRAND populated copy,216 prior non-migration tables preserved,
  Finance bytes unchanged; `.tmp/disposal-evidence-preview.log`. No native guide
  seed additions. Synthetic case1 contains one legacy blank hash and one new hash.
- PASS: Playwright desktop1280 and mobile390 inspected, unknown/baseline labels
  present, no page overflow; existing table has horizontal scroll on mobile.
  Screens in output/playwright/disposal-evidence-{desktop,mobile}.png. Browser and
  preview stopped. Existing fixture image404s are not this workflow's regression.
- FAIL - CAUSED BY CURRENT WORK: first stopped recovery found ValueError when
  reopening a cached FieldFile whose file had disappeared after earlier access.
  Converted to controlled ValidationError; added explicit regression.
- PASS: after fix, focused `manage.py test inventory.test_disposal_evidence
  inventory.test_disposal_migration --verbosity 1`,6/6,0.351s,exit0.
- PASS: repeated stopped paired SQLite restore217 default/83 Finance tables/9 files;
  every table/file manifest equal, source unchanged, known hashes and unknowns
  preserved, missing and tampered sources rejected. Backup
  `C:/Users/Administrator/.codex/backups/gsov2-disposal-evidence-recovery-20261017-wm6udr7g`;
  `.tmp/disposal-evidence-recovery.log`,exit0. Not online MySQL/operator recovery.

Native standalone and actual GRAND full runs are active; final affected native
rerun required after reopened-file fix. VM publication and hosted gates pending.
No malware-scanning, legal authenticity, official-form or production acceptance
claim. Legacy unknown files remain operationally readable but are rejected by the
strict source verifier; missing/changed files cannot authorize/finalize a case.

Native full standalone142 finished in132.136s with one error (exit1):
FAIL - CAUSED BY CURRENT WORK, new HTTP test explicitly closed an already-consumed
streaming response. The second request_finished signal closed MySQL's TestCase
transaction, causing TransactionManagementError on the next HTTP request. Removed
redundant response.close in both new standalone and GRAND tests; stream consumption
already closes the response. Affected native rerun active; do not claim full native
pass from this run. `.tmp/disposal-evidence-native.log` retains the failure.

PASS: affected final native `scripts/run_mysql_tests.py inventory.test_disposal_evidence
inventory.test_disposal_migration inventory.test_disposal_locking`,12/12 in1.955s,
exit0; `.tmp/disposal-evidence-native-focused.log`. Covers reopened missing file,
HTTP integrity response, migration preservation and native disposal concurrency.
Operator database SHA256 remains5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.

Continuation: previous turn made progress. Fresh fetch confirms feature base577c549
still matches origin/master; intended edits preserved. Finance candidate unchanged.
Initial actual GRAND native run terminal21111 ended1:135 tests61.717s,26 errors.
FAIL - CAUSED BY CURRENT WORK: the old in-memory test still explicitly closed its
streaming response. First failure was the new download test; subsequent errors
were broken transactions after that close. Source line numbers in its traceback
reflect the subsequently edited file, not a fresh import. Retained log
`.tmp/disposal-evidence-grand.log`; both schemas removed by the runner. A fresh
full actual GRAND run uses final corrected tests (`.tmp/disposal-evidence-grand-final.log`).
Full standalone native final rerun also active (`.tmp/disposal-evidence-native-final.log`).
No release while these outcomes remain unresolved. VM inspect/preview selects
the dbd47c0 release and changes only VERSION/CHANGELOG. Remote rulesets empty/master
unprotected; normal hosted branch/master checks still required.

Final full standalone native PASS143/143 in124.530s, exit0; terminal66565 and
`.tmp/disposal-evidence-native-final.log`. Includes final reopened-file regression,
HTTP integrity check, populated migration, all native disposal races and dependent
inventory workflows. Test schema removed. Corrected full GRAND still active.

Handoff reconciled: historical checkpoints moved to continuity-history.md, linked
from a concise CONTINUE entry point. Obsolete bottom-of-file next-work instructions
are explicitly historical there. Preserved release identity by commit to prevent
Version Manager exact-version replacement from rewriting archived evidence; release
tags remain in CHANGELOG. Preview rechecked after adding the archive.

Final actual GRAND native PASS135/135 in55.812s, exit0, candidate a533482;
`scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation --mysql`.
`.tmp/disposal-evidence-grand-final.log` retains the corrected full result,
including scoped downloads, changed-evidence denial and zero Finance queries.
All disposable schemas removed; owned MySQL33317 normal shutdown confirmed.
Local validation complete. No live previews/browser/test processes remain.
Actual VM publication and hosted branch/master gates follow.


## Property movement schema foundation — 2026-10-17
Previous disposal milestone actually VM-publisheddbd47c0, branchCI38984917166 and
masterCI38985045378 PASS; remote master/tag verified and canonical clean0/0.
Fresh fetch for this feature: dbd47c0 clean0/0; Finance candidate a533482 unchanged
except preserved coordination notes. New branch codex/property-movement-records.
Reopened ONAR2024-006 index and visually re-read retained AnnexA.2 pages7–8;
no new applicability/effectivity claim. Selected source-linked annotation/opening
design documented in property-movements.md; no automatic custody/Finance writes.

PASS: `manage.py test inventory.test_property_movement_schema --verbosity 1`,4/4
in1.148s,exit0. Tests database pending uniqueness, source/effect/opening constraints,
independent decision constraint and immutable source writes; populated0026→0027
retains two historical disposal cases/events and assigns distinct nonempty UUIDs.
No old movement annotations are invented. PASS system checks/migration drift.
NOT RUN - OUT OF SCOPE for this unfinished foundation checkpoint: full/native,
HTTP/concurrency/browser/recovery acceptance. These are mandatory before feature
publication; schema-only tests are not workflow or integration evidence. No release,
operator migration, role grant or deployment performed. No live test processes.


## Property movement service checkpoint — 2026-10-17
Fresh fetch: feature base dbd47c0 matches remote master; intended local work preserved.
Finance a533482 unchanged except GSO note. Previous turn made schema/design progress.
Added reviewed-source services and working projection; no custody/stock/Finance write.

PASS: focused `manage.py test inventory.test_property_movements
inventory.test_property_movement_schema --verbosity 1`,14/14 in2.142s,exit0.
Covers model/migration invariants, independent review, replay, predecessor correction,
source/file drift, fresh owner denial, pending and missing source entries, negative
stock, duplicate chronology, pinned property basis drift and undated legacy retirement.
Known handoff/reassignment fixtures are accepted source rows; they do not replace
real end-to-end receipt/return/disposal or native race/HTTP tests. Full shell regression
is running (`.tmp/property-movement-services-shell.log`, terminal67240).
NOT RUN - OUT OF SCOPE for this incomplete checkpoint: native/race/actual GRAND,
UI/browser and paired recovery; mandatory before release, not waived. Feature remains
unpublished. No operator migration/grants/deployment or official-output claim.

Full standalone shell PASS157 discovered/136 run/21 native-only skips in55.870s,
exit0, terminal67240; `.tmp/property-movement-services-shell.log`. Includes all
existing workflows and migration tests after the new models/services. Broad scope
selected because0027 extends existing disposal identity and adds schema. PASS
migration drift and diff whitespace checks. No active test/preview remains.
Native/GRAND, real source-chain, UI and recovery gates remain open; no release.


## Property movement UI/integration checkpoint — 2026-10-17

Fresh fetch: feature HEAD and origin/master dbd47c0 have0/0 divergence; intended
unpublished changes preserved. Finance candidate a533482/master32ab046 unchanged,
only append-only GSO coordination file untracked. UI routes/forms/history/private
downloads and correction prefill now exist. No operator database change or release.

PASS: `manage.py test inventory.test_property_movement_http
inventory.test_property_movements inventory.test_property_movement_schema
--verbosity 1`,19/19 in2.780s. Later correction scenario: HTTP6/6 in0.771s.
PASS: migration drift, diff whitespace. HTTP uses enforced CSRF; covers signed actor,
source/expiry binding, independent review, replay, owner/read-only scope, fixed source
date, zero/unknown cost and retained correction predecessor.
FAIL - CAUSED BY CURRENT WORK: first20-test run, chain fixture attempted GRAND-only
employee lookup in standalone (ValidationError); moved the real-chain test into
`gso_integration_tests/grand_property_movements.py` using actual GRAND profiles.
No production authorization change made to accommodate the fixture.

PASS: `scripts/run_mysql_tests.py inventory.test_property_movement_concurrency
inventory.test_property_movement_http inventory.test_property_movements
inventory.test_property_movement_schema`,22/22 in6.292s, exit0, terminal77280;
`.tmp/property-movement-native-focused.log`. Includes competing records/decisions
and asset-before-annotation lock ordering. This run discovered5 HTTP tests before
the sixth correction test was added. Native broad regression remains required.
Actual GRAND SQLite/native and full shell runs are pending in CONTINUE; no pass
claimed yet. Browser, paired restore and populated actual-GRAND preservation gates
remain required before publishing this workflow.


Final local movement milestone gates:
- PASS full shell166 (142 executed/24 native skips),66.284s,exit0,terminal96868;
  `.tmp/property-movement-ui-shell.log`.
- PASS full MySQL166/166,169.779s,exit0,terminal72318;
  `.tmp/property-movement-native-full.log`.
- PASS actual GRAND MySQL137/137,62.934s,exit0,terminal58511;
  `.tmp/property-movement-grand-native.log`. Actual GRAND SQLite136 with21 native
  skips PASS31.050s,exit0,terminal10553; discovered before the added native authority
  test. Both include real receipt→named issue→witnessed return→disposal. Native also
  checks UAT/ungranted superuser/foreign office and zero Finance queries.
- PASS final HTTP6/6,0.725s after applying existing44px button classes to the new
  templates. Broad suites above plus this focused retest cover the final change.
- PASS populated actual-GRAND copied default migration0027:216 existing tables'
  rows preserved, Finance byte hash unchanged, historical disposal fields/events
  retained, distinct nonempty UUIDs. Expected additions2 content types/3 permissions;
  no grants automatically assigned. Initial preview assertion failed because it
  incorrectly prohibited those post-migrate additions; corrected the harness to
  require those exact counts while preserving all old rows. No app migration fix.
- PASS browser CLI: actual employee login, opening0 with unknown cost, independent
  verify, mobile correction1, pending-balance suppression, independent successor
  verify and two retained verified history rows. Desktop/mobile screenshots visually
  checked; mobile table scroll stays within its panel. Existing missing copied
  media/defaults/grand-mark.svg causes login/home404s; no movement-page errors.
  Initial browser helper used unavailable Buffer; rerun with a local synthetic PDF
  through the same file input. Button styling fixed using existing theme classes.
- PASS stopped synthetic paired recovery at
  `C:/Users/Administrator/.codex/backups/gsov2-property-movement-recovery-20261017-2q0dm5pv`:
  219 default/83 Finance tables and12 private files, exact row/file manifests, old
  legacy disposal unknowns, movement predecessor/event history and working balance1
  preserved. Missing/tampered movement packet rejects integrity and suppresses
  balance. Source copy unchanged. This is not live operator/MySQL restore acceptance.

No operator migration/grants/deployment. Operator SQLite SHA256 still
5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.
Browsers/previews stopped; owned MySQL55828/PID90792 normal shutdown after no remaining
schemas. Remote rulesets[] and master protected=false rechecked before release.


## GSO office Records entry — 2026-10-17

Previous turn: progress, actual VM movement releasece845fc integrated/pushed with
featureCI38987081260 and masterCI38987256429 PASS. Fresh sync on this turn: GSO0/0,
Finance a533482/master32ab046 unchanged except GSO notes. Separate feature branch
`codex/gso-office-records-entry`; no GRAND source/schema/operator edits.

Inspected actual native Records models, authorization, forms, source allowlist,
services/views/routes and tests. Reuse its general departmental filing through a
GSO dashboard link; no inventory association invented. The helper resolves only
installed/routed native Records for an active actually GSO-assigned user authorized
by native Records. Superuser inventory fallback does not select a registry office.

PASS standalone `manage.py test inventory.test_office_records --verbosity 1`,1/1;
system checks/migration drift/diff whitespace PASS. No migration or new storage.
Actual-GRAND focused runner `.tmp/test_office_records_grand.py` reuses the committed
isolated settings/router harness, discovering `gso_integration_tests.grand_office_records`
and `records.tests`. First SQLite17-test run:16 PASS/1 ERROR in3.861s. FAIL - CAUSED
BY CURRENT WORK (harness): existing native footer source test assumes GRAND cwd;
FileNotFoundError for templates/components/footer_links.html when launched in GSO.
Corrected focused runner to chdir to the explicit GRAND source, preserving absolute
isolated database paths. Final SQLite/native results pending; original logs retained.

PASS browser through actual GRAND: GSO dashboard card at desktop/mobile, click into
native /records/, register a synthetic general-office draft and see its created
event, native department record number and unassigned retention. No official output
or supplied signature is inferred. Preview `.tmp/office-records-preview-bzhdnbrg`
was copied from stopped synthetic data; operator files untouched. Screenshot review
confirms the new card fits mobile. Existing copied default logo/avatar/favicon files
are missing on native pages (404); no new dashboard-link error. Browser and preview
73243 are stopped. The native registry's full production/security/recovery acceptance
is not claimed by this entry or inherited test suite.

NOT RUN - OUT OF SCOPE: new migration/populated import, custody/stock races and new
paired-evidence restore; this change has no models, mutation service, file writes or
storage namespace. Existing Records regression plus real native filing/scope tests
cover the destination; the normal hosted release suite still applies.


Final office Records entry results: PASS actual GRAND SQLite17/17 in3.934s, exit0,
terminal64665 (`.tmp/office-records-grand-final.log`); PASS MySQL17/17 in4.743s, exit0,
terminal58452 (`.tmp/office-records-grand-native-final.log`). Both execute3 new GSO
integration cases plus14 existing Records cases. Original MySQL58810 ended1 with
the same cwd-relative footer test error (16 pass/1 error in6.964s), matching the
original SQLite harness issue; no production code changed for this correction.
Focused runner command: GRAND Python `.tmp/test_office_records_grand.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation [--mysql]`.
It is the normal isolated runner with discovery narrowed to the two named modules
and working directory set to that GRAND source for its existing file-source test.
The committed default runner includes the3 new GSO cases in future broad runs.
No locks/schema were changed; targeted native tests plus the normal hosted full
shell release suite are appropriate for this optional navigation addition.

PASS browser native draft creation and readable GSO mobile card; screenshot files
`output/playwright/office-records-*` inspected. Preview73243/browser stopped;
owned MySQL92116/PID81160 shut down normally after checking all test schemas gone.
Operator database hash unchanged. No Finance code/operator grants/deployment.
VM README reviewed, inspect/preview selected the patch released at a7cfb2d; only VERSION/CHANGELOG
are generated. Hosted feature/master receipts are checked after the actual release;
this paragraph does not claim those unperformed results.


## Completion audit — 2026-10-17

Fresh fetch: GSO clean0/0 at a7cfb2d; Finance candidate a533482/master32ab046,
only the existing untracked append-only GSO coordination file. Reverified previous
master CI38988402908 success on exact a7cfb2d. Previous feature CI38988203821 and
matching remote tag/master were verified at publication. The office Records release
was completed; earlier pre-release notes above are historical, not a pending gate.

Read AGENTS, handoff, roadmap, COA matrix, recovery/data/movement/Records designs
and current receiving models/service. Added completion audit and selected the next
receiving design pass; no model, service, settings or Finance rule changed.
A lookup initially used an incorrect GitHub owner and returned404; corrected to
the configured remote tepong32/GSOv2. Actual rulesets[] and master protected=false.
Two source reads initially targeted the Finance cwd and failed; repeated against
the GSO checkout. These were inspection errors, not test failures or code defects.

PASS: git diff --check and local Markdown link validation for changed documents.
NOT RUN - OUT OF SCOPE: local runtime, migration, browser and recovery reruns for
this documentation-only audit. Existing milestone evidence is retained without
claiming a new runtime pass. Normal hosted full shell gates apply to publication.


## Receiving follow-up acceptance — 2026-10-17

Fresh baseline78c19e8 clean0/0. Previous audit release was progress; its exact
featureCI38988773596 and masterCI38988917720 passed. Finance remains candidate
a533482/master32ab046 with only append-only GSO notes. Separate branch
`codex/receipt-followup-acceptance`; no operator/Finance source changes.

Implemented linked follow-up receiving header/source basis, exactly one line,
original-before-follow-up locks, cumulative capacity, signed request replay,
independent existing receiving review/materialization, staff entry/correction and
retained original history. Snapshot extensions are conditional on new follow-ups;
ordinary Finance/property bases retain their shape. Working property source uses
follow-up inspection date rather than earlier delivery. No accounting rule/posting.
Migration0028 adds optional relation/basis; adapter0006 declares its dependency
without schema/data operations. See receiving-followups.md.

PASS affected initial service/receiving/amendment/property suite41 in2.765s.
PASS focused8 follow-up service/HTTP cases in0.818s. The earliest focused invocation
discovered26 tests because a fixture TestCase was imported as a class; changed to
module import so the8 new cases are counted separately, without weakening tests.
PASS full native shell176/176 in165.538s, exit0, terminal77253,
`.tmp/followup-native-shell.log`. Includes actual competing follow-up acceptances.
PASS full standalone176 discovered,151 run/25 native skips,66.987s,exit0,terminal26625,
`.tmp/followup-shell-final.log`. These full runs preceded the added populated
migration test and final header-edit guard; targeted results below cover those.
PASS native focused10/10 in2.888s,exit0,terminal68553,
`.tmp/followup-native-final.log`:8 service/HTTP,1 real-connection race and1 populated
0027-to-0028 receipt/event-preservation test. The final header-only guard was added
while that run was already in progress. PASS final SQLite30/30 in2.108s,exit0,
`.tmp/followup-shell-guard-final.log`: receiving,follow-ups,populated migration;
includes rejecting replacement of original supplier through the service.
Commands: standalone Python `manage.py test <labels> --verbosity 1`; native
`scripts/run_mysql_tests.py [inventory.test_receiving_followups
inventory.test_receiving_followup_concurrency inventory.test_receiving_followup_migration]`
with isolated loopback credentials. System checks/migration drift/diff whitespace PASS.

PASS actual GRAND SQLite141 discovered/120 run/21 native skips in31.864s,exit0,
terminal96128,`.tmp/followup-grand-sqlite.log`. This included native identity/grant/
UAT/owner/zero-Finance-query follow-up integration; the additional approved-claim
retention case was added afterward for the native run. Native broad result pending.
Command GRAND Python `scripts/run_grand_source_tests.py --grand-root
C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation [--mysql]`.

PASS populated actual GRAND copy migration: all prior rows/columns in218 nonmigration
tables retained; Finance file hash unchanged. post_migrate populated7 existing
Budget Form1 content types and42 associated permissions, with no role assignment.
Initial harness wrongly expected no metadata additions (FAIL - CAUSED BY CURRENT
WORK, harness). Inspection identified all7 native Budget models and42 permissions;
a second harness check used the wrong permission tuple column index, corrected
after PRAGMA inspection. Final explicit comparison passed. Source copy stayed
unchanged; preview `.tmp/receiving-followup-preview-z7_ru0hv`.

PASS browser actual GRAND desktop/mobile: original remaining2 -> signed follow-up
draft1 -> correction1.5 -> retain delivery/inspection packets -> submit -> distinct
reviewer accepts -> original remaining0.5 with original accepted6 and original
events unchanged. Screens `output/playwright/receiving-followup-*`; form/original
mobile screenshots visually inspected. Initial navigation used the shell URL and
returned404; used harness /gso/inventory/ routes thereafter. Existing native logo/
favicon404s on login/public pages were from copied media; no new receiving error.
Browser receiving-followup and preview52001 stopped before recovery.

PASS stopped paired restore219 default/83 Finance tables and16 private files,
exact manifests/source hashes preserved. Original/follow-up lineage,6-event child
history,stock7.5,remainder0.5 retained. Missing/tampered original and follow-up
packets rejected; receiving evidence checker passed. Prior property/disposal
history/unknown evidence controls also retained. Backup:
`C:/Users/Administrator/.codex/backups/gsov2-receiving-followup-recovery-20261017-f7bss3tn`.
Helper `.tmp/rehearse_receiving_followup_recovery.py`,log`.tmp/followup-recovery.log`.
This is stopped synthetic SQLite recovery, not online/operator/RPO/RTO acceptance.
Operator database SHA256 remains5c6c3c66e46d8a6f4a95799806ec96f4ef3fda923027adba29d63e9f337a2039.

NOT RUN - OUT OF SCOPE: official-form acceptance, operator migration/grants,
production deployment and accepted-quantity reversal; none is claimed here.
VM README reread; actual repository rulesets[] and master protected=false.
Publication awaits final native/adapter checks and the ordinary hosted gates.


Native GRAND first run: FAIL - CAUSED BY CURRENT WORK (test fixture),141 pass/1
error among142,57.915s,exit1,terminal16344,`.tmp/followup-grand-native.log`. The new
approved-support test discarded finish(child)'s accepted return value, so its
related line retained a cached draft header and submitted a stale Finance basis.
The production stale-basis guard correctly rejected it. Corrected the fixture to
use the returned accepted receipt; no guard was weakened. Full native rerun on
final source is pending at terminal24710,`.tmp/followup-grand-native-final.log`.

PASS final actual-GRAND adapter dependency check on another populated copy:
`.tmp/check_followup_adapter.py --grand-root .../gsov2-grand-v173-validation`,
exit0,`.tmp/followup-adapter-check.log`. Adapter0006 plan includes inventory0028
before itself, the adapter migration is recorded after migrate, system checks and
makemigrations --check --dry-run pass. Original218 tables' old rows/columns remain
with the same explicitly checked native7/42 metadata additions; Finance bytes
unchanged. This empty dependency migration was added after the first broad run
started and is included in the final native rerun. VM inspect/preview selects
the receiving-follow-up minor release published at ad8b348 and generates only VERSION/CHANGELOG.


Final native GRAND: PASS142/142 in59.470s,exit0,terminal24710,
`.tmp/followup-grand-native-final.log`. Corrected fixture uses the accepted returned
child; both original approved60 and child approved40 remain valid against the same
100 claim, original receipt snapshot unchanged, with zero Finance queries. Full
native rerun includes final code and adapter0006. Owned MySQL33317 was shut down
normally after no disposable test schemas remained. No live owned test/preview.
Changed Python syntax, Markdown local links and whitespace checks PASS.
Feature/master hosted receipts will be checked after the actual VM transaction;
this pre-release note does not claim those unperformed outcomes.

## Reviewed GRAND carry-over checkpoint —2026-10-17

PASS: grand-auth-venv/Scripts/python.exe scripts/run_grand_source_tests.py --grand-root C:/Users/Administrator/.codex/worktrees/gsov2-grand-v173-validation --mysql. Full native147/147, zero skips,64.560s, exit0; both disposable schemas destroyed. Log .tmp/grand-integration-checkpoint.log. Includes new PAR native grant/UAT/no-write test. Scope: integration-boundary review and current GSO suite against paused Finance a533482. Actual destination configuration and combined release gates pending; not production acceptance.
