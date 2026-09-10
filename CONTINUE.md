# GRAND Finance continuation handoff

Mandatory gate added 2026-09-07: [post-Finance operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md). **Finance production gate: NO-GO** pending functional completion, scrutiny, critical-gap verification and LGU acceptance. Run the full scrutiny only after the current functional phase; existing tests/container work do not satisfy it. Preserve all historical and deferred roadmap items.

Last updated: 2026-09-10

Turning-point decisions are recorded separately in [the implementation decision log](docs/IMPLEMENTATION_DECISIONS.md), as requested by the user. Keep each choice tied to the canonical product goal, alternatives, tradeoffs, evidence and revisit conditions.

Personal handoff coverage and the next source adapter are summarized in [the coverage table](docs/FINANCE_WORK_VIEW_COVERAGE.md).

## How to resume

The next task can begin with: **“continue”**

Before changing code, inspect the current branch, status, recent commits, this file, `docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md`, and `docs/FINANCE_MY_WORK.md`. Preserve user changes and never stage `db.sqlite3`. If this branch is already checked out in another worktree, continue in that owning worktree or create the next `codex/finance-*` branch from the pushed checkpoint; do not force-checkout or discard another worktree.

## Active direction — eGAPS-informed web modernization

The user accepted the 2026-09-10 comparison, requested that its goals be saved and implemented, and clarified the main outcome: familiar eGAPS office workflows improved in GRAND through individual web accounts, manageable future national/COA/DBM rule/form changes and authorized WFH. [Priorities M01–M08](docs/FINANCE_MODERNIZATION_PRIORITIES.md) retain the concrete gaps and acceptance criteria. eGAPS files/records/databases remain untouched references. This supersedes the earlier narrow “a little more work” scope, not financial or production gates.

User clarification: complete financial functionality and demonstrate source-to-ledger-to-output parity first, then finish the eGAPS inventory, ordinary office scenarios, exact outputs, usability and operational acceptance in the [authoritative order](docs/FINANCE_MODERNIZATION_PRIORITIES.md#authoritative-delivery-order-clarified-2026-09-10). eGAPS is the parity floor, not the design ceiling. Do not expand framework/collaboration/qualification or other surrounding infrastructure ahead of unresolved financial functionality unless required to complete or validate it. Further UX work follows functional completion.

M06's already implemented navigation slice is validated as v0.7.72 on `codex/finance-familiar-web-workspaces`: direct familiar register shortcuts, plain landing-page copy and expandable control explanations, using existing source access checks. [Validation](docs/FINANCE_NAVIGATION_VALIDATION_2026-09-10.md): PASS, 314 affected tests discovered in 595.617 seconds (311 executed; three native-only skips), system/drift/compilation/diff checks, desktop/narrow browser, permission-shaped links, keyboard disclosure and clean console. Browser/server/test processes ended. Full project/native suites were out of scope for this read-only navigation slice; real LGU/WFH acceptance remains open. M01 missing statements and M02 accrual/settlement linkage are next. Preserve the pre-existing draft `accounting/test_policy_concurrency.py`, local database change and native-blocker evidence below. Do not merge development history into master merely to publish direction documents.

The [printable seven-page comparison](output/pdf/GRAND-eGAPS-Assessment-2026-09-10.pdf) was delivered for colleague checking and remains a frozen v0.7.71 assessment. It is not a claim that subsequent navigation changes were present during eGAPS review. The user may close eGAPS and disconnect; current implementation does not need that connection.

Native prerequisite progress: the official Windows ZIP runtime is extracted at `C:/xxx/_INSTALLS/_HERE/_xxx/mysql-8.4.11-winx64`. The [Oracle download page](https://dev.mysql.com/downloads/mysql/8.4.html) supplied 8.4.11; its archive MD5 matched `2e833921898a9a030ea6bfe81bd811bc` and `mysqld.exe` has a valid Oracle America Authenticode signature. The owned fixture `.tmp/portable-mysql-20260910` initialized and served on loopback 33308; authenticated queries verified its exact data directory, version 8.4.11, bind address and strict mode. It was shut down after that check. No service, PATH or firewall change. This is Windows 8.4.11, distinct from the historical 8.4.12 Linux/container baseline; no native application tests passed yet. The initial helper wrongly imported MySQLdb directly (the app uses PyMySQL); corrected before the successful authenticated check. Ignored `.tmp/portable_mysql.py start` can restart the owned fixture with its private synthetic credentials; `test <labels>` uses the committed fresh two-store runner. Do not print or commit its private files. Use this prerequisite for current functional-gap validation; do not divert into unrelated policy scrutiny ahead of functionality. Docker remains unrepaired.

## Retained blocker - Native reproduction blocked by Docker startup

Historical attempt on `codex/finance-close-policy-conflicts`, based on pushed v0.7.71 (`2de0ce2`). Two uncommitted draft native HTTP regressions in `accounting/test_policy_concurrency.py` synchronize competing policy candidate locks for first activation and replacement. That attempt changed no application code/schema or VERSION and made no commit/push or verified defect/repair claim. Keep these regressions as drafts until they execute on MySQL. The current navigation work is separate and described above.

Validation: `.venv/Scripts/python.exe manage.py test accounting.test_policy_concurrency --noinput` discovered two tests, both skipped as native-only (0.000 seconds); this is discovery evidence, not a concurrency pass. `.venv/Scripts/python.exe -m compileall -q accounting/test_policy_concurrency.py` and `git diff --check` passed. Native tests NOT RUN - ENVIRONMENTAL. The user database hash is unchanged from the verified baseline below.

Stopping hurdle: Docker Desktop repeatedly fails before the engine starts. Its backend log records `initializing Ingest server` / `sailor-ingest.sock: The file cannot be accessed by the system`, then a similar `docker-secrets-engine/engine.sock` error. While Docker was stopped, socket-only runtime directories were preserved as `C:/Users/Administrator/AppData/Local/Docker/run-policy-rehearsal-stale-20260909` (four zero-byte sockets) and `C:/Users/Administrator/AppData/Local/docker-secrets-engine-policy-rehearsal-stale-20260909` (one zero-byte socket). Fresh runtime directories were created. Startup progressed past one socket but failed again on a newly created runtime path; a stale-file-only repair did not resolve the host issue. No Docker data/settings or credential contents were read or reset. Docker was stopped after the failed attempts; no Docker/test processes remain.

The intended container `grand-policy-native-20260909` (loopback 33308, label `grand.rehearsal=policy-20260909`) was never created: the initial Docker run failed because the engine was unavailable. Synthetic credentials in `.tmp/policy-native-20260909` were removed. Ignored `.tmp/policy_native.py` can provision a fresh fixture after Docker is healthy; `start` creates new credentials, then `test accounting.test_policy_concurrency` uses the committed native runner. Do not run its test mode before successful native startup/readiness. The SQLite discovery log is `.tmp/policy-concurrency-sqlite-discovery.log`.

Resume prerequisite: a working Docker Linux engine or another explicitly disposable native MySQL server. Do not factory-reset Docker or reboot the host as an implicit Finance operation. Once available, run the original native reproductions before choosing a bounded repair, then apply the regression/migration/history gates. The prior native identity audit and remaining process/persona work are preserved below.

## Current v0.7.71 checkpoint - Bounded native identity audit

Branch: `codex/finance-native-invariant-audit`, based on pushed and remotely verified `8c7643588a43e8c767ce7c75f91acc580eeecc70` (v0.7.70). The user cancelled the planned pause and requested a little more work; this additional audit slice is complete.

[The audit](docs/FINANCE_NATIVE_INVARIANT_AUDIT_2026-09-09.md) and its linked JSON inventory reconcile all 21 first-party conditional uniqueness declarations with the native warnings: 15 Finance-related and six supporting. Two third-party email-address warnings remain separately recorded. Service-lock and correction-path review provides concrete native reproduction cases; it does not establish concurrency safety or a new duplicate-record defect. D-064 records the decision and priorities.

PASS: AST inventory/warning reconciliation, 21 source locations, JSON parsing, 41 local document links and `git diff --check`. Runtime suites NOT RUN - OUT OF SCOPE for this documentation-only slice; application/schema are unchanged. The v0.7.70 baseline below remains authoritative. Remote CI NOT RUN - ENVIRONMENTAL because GitHub CLI authentication is invalid. No live/user database changes, new containers or software installations.

Next bounded implementation work: fresh disposable MySQL reproduction of competing first activations for close policies/accountability profiles, then cross-period bank outstanding-item correction. Preserve the full process/persona matrix and real LGU acceptance gates. Docker is stopped and the prior private credentials were removed; provision a fresh disposable setup before native work. No tests or app servers are left running.

## Verified v0.7.70 application baseline

Branch: `codex/finance-bank-match-conflicts`, based on pushed and remotely verified `93d587f` (v0.7.69). Bank matching now reports known conflicts after complete rollback, with an explicit reload/check/retry instruction and no implicit replay. Generated nullable keys enforce active bank-row and journal-line match identities while preserving superseded history. Migration accounting/0011 refuses historical duplicates before DDL. A committed fresh two-store MySQL runner and independent CI service job complement SQLite.

PASS: full SQLite run, 711 tests discovered in 355.841 seconds (710 executed; one MySQL-only case skipped); full MySQL 8.4.12 run through the committed native runner, all 711 tests in 767.251 seconds. System, migration-drift, compilation and diff checks passed.

FIN-GAP-035 is verified. [The validation report](docs/FINANCE_BANK_MATCH_VALIDATION_2026-09-09.md) records the HTTP reproduction, rollback/no-replay controls, duplicate-migration refusal and final native recovery/report reproduction. D-062/D-063 record decisions; [FINANCE_NATIVE_TESTING.md](docs/FINANCE_NATIVE_TESTING.md) provides the committed repeatable command. Remote CI: NOT RUN - ENVIRONMENTAL; GitHub CLI authentication for the configured account is invalid. Local execution of the same native runner passed; no remote workflow result is claimed. The workflow was manually reviewed against primary GitHub service-container syntax; optional local YAML parsers were unavailable. No new software was installed. No live/user database migration or real financial authority change. Production remains NO-GO.

All phase test processes have ended. Owned MySQL containers/network and synthetic credential files were removed. Docker Desktop was stopped, restoring its prior state. Ignored logs, receipts and image cache remain. Old rehearsal scripts requiring the deleted private.json cannot be resumed without a fresh disposable setup. The user database hash remains C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C.

The next-step detail is now in the v0.7.71 checkpoint above; remote CI still needs valid GitHub CLI authentication and the operational process/persona matrix remains incomplete. Actual LGU discovery, forms/openings/redacted replay, named-user/printer checks, approved off-host recovery and seven-party acceptance remain external gates. Generic following/shared views/notifications remain deferred. Do not infer a bug-free app or production acceptance from the passing suites.

## Active instructions and repository continuity

- The latest instruction authorizes the saved modernization priorities above. Continue bounded implementation and scrutiny phases; preserve all operational gates.
- Make meaningful versioned checkpoints: bump VERSION, commit as `v0.7.x — feat/fix(finance): ...`, and push stacked `codex/finance-*` branches to the explicitly authorized `https://github.com/tepong32/grand.git`. Do not merge feature work into master without a request.
- Keep turning-point decisions in [IMPLEMENTATION_DECISIONS.md](docs/IMPLEMENTATION_DECISIONS.md).
- Waiting means work the signed-in user prepared/submitted, with current source access. Administrators explicitly assign the separate My Work export permission to selected users/groups.
- The requested master guidance pull is complete: master `42fd662` was integrated by merge `9ac683f`, preserving local Finance work. Current feature development continues from the pushed checkpoint, not old master.
- Never stage or alter the existing user `db.sqlite3` change. Use explicit staging paths. Its retained SHA-256 is `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
- Legacy opening evidence without its required digest needs revalidation/controlled investigation; do not backfill historical approvals. No live database migration or role grant has been performed in these checkpoints.
- Older checkpoint details are preserved in [FINANCE_CHECKPOINT_HISTORY.md](docs/FINANCE_CHECKPOINT_HISTORY.md); their next-step/test/pause text is historical.

## Remaining implementation order

1. Finish M01–M03 concrete financial gaps and prove source-to-ledger-to-output behavior, starting with missing statements and earlier-payable linkage. Reproduce before repair; preserve source offices, independent decisions and immutable evidence. Use native testing when required by the financial change.
2. Complete the actual eGAPS inventory when a safe session is available; identify locally used unmatched functions/reports. Demonstrate ordinary Budget, Accounting and Treasury chains with corrections, then match DV/OBR/JEV/advice/RCI/RD/tax/statement layouts, signatories, copies and printing.
3. After functional coverage, validate familiar clerk workflows, next actions, My Work/status visibility, reduced duplicate encoding, audit transparency and authorized WFH. Retain the completed [personal-adapter baseline](docs/FINANCE_WORK_VIEW_COVERAGE.md); generic following/shared views/notifications stay deferred.
4. Complete [operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md), open [critical findings](docs/FINANCE_GAP_REGISTER.md), concurrency/recovery/access/change reproduction and real LGU gates. Do not expand qualification/discovery/acceptance machinery before financial gaps unless required to complete or validate the current priority. Synthetic checks never satisfy real LGU acceptance.

## Non-negotiable financial controls

- Never use floating-point arithmetic for money; retain exact decimal/centavo calculations and explicit rounding rules only where a locally accepted rule requires them.
- A required Budget, Accounting, Treasury, subsidiary, bank, remittance, or report control difference must equal exactly zero before the governed next step. A warning is not enough.
- Recompute controls at the service boundary under a transaction/row lock. Do not trust totals, permissions, office scope, or state supplied by a page or client.
- Preserve maker-checker separation, assigned-department/object scope, current-office custody, UAT exclusion, and attribution. Never let the creator/submitting actor perform an independent decision where separation is required.
- Never overwrite issued, posted, released, remitted, reviewed, approved, or otherwise retained evidence. Use an explicit returned correction before issuance, or a linked reversal, adjustment, cancellation/replacement, or successor after the governing point.
- Every report/export total must be reproducible from retained source identities, counts, snapshots, control equations, and checksums. Screen, task, and export scopes must select the same records.
- Keep COA/DBM/BIR and local-form claims honest: starters remain candidates until the implementing LGU records current local authority, exact forms, signatories, routes, copies, and independent acceptance.
- Do not claim production readiness from automated tests alone. Actual master data, opening balances, redacted replay, named-user acceptance, printer/device checks, backup/restore evidence, and LGU authority remain external gates.

## External acceptance gates

These steps require implementing-LGU evidence and must stay visibly blocked until supplied; code must not fabricate them:

1. Close F0/F1 discovery for the intended first deployment scope, including named owners/reviewers/signatories/support contacts, enabled transactions, actual systems/interfaces, unresolved decisions, and an independently accepted whole-scope decision.
2. Accept the exact F10 blank/redacted completed forms, resolve every candidate mapping, perform all required layout/print/accessibility tests, and retain independent acceptance.
3. Open F2 with actual approved configuration and opening balances; independently approve/post and reconcile every fund to signed controls.
4. Replay one complete redacted F3–F9 chain: authorized budget → allotment → obligation → payable → DV → JEV → payment/advice/release → bank reconciliation → accountability package. Resolve all differences by governed correction/reversal/successor.
5. Execute F11 field qualification with named roles, approved curricula/support/cadence, nonfunctional exercises, a production-compatible off-host two-store restore, and uninterrupted qualifying shadow/parallel cycles using the accepted form set.
6. Collect separate Requesting Office, Budget, Accounting, Treasury, IT, management, and audit decisions. Record go/no-go, date, signed authority reference/checksum/custody, and rollback criteria only after those gates pass.

## Checkpoint completion and verification

Follow [AGENTS.md](AGENTS.md) for proportional testing. Start with affected contracts; add relevant dependent integrations. Run the full project suite for security/shared-service/cross-module changes, major milestones and release/production gates. Isolated read-only adapter or low-impact changes do not automatically require a full suite; document their dependency scope and rationale.

Use `.venv\Scripts\python.exe manage.py test <labels> --noinput` (omit labels for the full suite), preserving both test database aliases. Capture routine output in ignored `.tmp` logs. Record PASS, FAIL with cause/evidence, or NOT RUN with scope/environment rationale. After final executable changes run relevant tests, `manage.py check`, `makemigrations --check --dry-run`, touched-file compilation and `git diff --check`. Documentation-only edits after passing tests do not invalidate that run.

Review the complete diff, update VERSION/CHANGELOG, this current handoff and relevant specialized docs with actual evidence, stage explicit files, commit and push the checkpoint. Verify push success. Continue the next authorized phase unless the user requested a pause or a real blocker remains. Keep this handoff current; retain historical evidence in the linked audit/changelog/archive rather than copying old instructions forward.
