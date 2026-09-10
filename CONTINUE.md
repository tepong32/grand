# GRAND Finance continuation handoff

Mandatory gate added 2026-09-07: [post-Finance operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md). **Finance production gate: NO-GO** pending functional completion, scrutiny, critical-gap verification and LGU acceptance. Run the full scrutiny only after the current functional phase; existing tests/container work do not satisfy it. Preserve all historical and deferred roadmap items.

Last updated: 2026-09-10

Turning-point decisions are recorded separately in [the implementation decision log](docs/IMPLEMENTATION_DECISIONS.md), as requested by the user. Keep each choice tied to the canonical product goal, alternatives, tradeoffs, evidence and revisit conditions.

Personal handoff coverage and the next source adapter are summarized in [the coverage table](docs/FINANCE_WORK_VIEW_COVERAGE.md).

## How to resume

The next task can begin with: **“continue”**

Before changing code, inspect the current branch, status, recent commits, this file, `docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md`, and `docs/FINANCE_MY_WORK.md`. Preserve user changes and never stage `db.sqlite3`. If this branch is already checked out in another worktree, continue in that owning worktree or create the next `codex/finance-*` branch from the pushed checkpoint; do not force-checkout or discard another worktree.

## Active direction — eGAPS-informed web modernization

Current v0.7.86 on `codex/finance-claim-recovery-date`, based on pushed and verified v0.7.85 (`e6607dc`): [dated claim recovery](docs/FINANCE_CLAIM_RECOVERY_DATE_2026-09-10.md), a D-076 follow-up. A recovered single-claim hold must fit the requested date and later movements, with its existing amount counted once. The earlier-date bypass reproduced before repair (one failed denial test, 0.130 seconds). PASS: 39 affected SQLite tests (24.122 seconds), 39 native tests including five selected races (33.655 seconds). Actual interrupted DV validation, rejected earlier retry, unchanged hold/stage, valid later recovery/payment and archived claim CSV are covered. System/drift/compile/diff and local document links pass. No migration. Both runners ended; owned MySQL is stopped/port closed; user DB hash unchanged. Check Git/remote state for publication status. Preserve the user DB and unrelated policy-test draft; do not merge into master. This prerequisite does not implement historical source-line splitting; continue that work and the preserved corrections/Finance gates next.

Previous v0.7.85 on `codex/finance-consolidated-dv`, based on remotely verified v0.7.84 (`245a7d2`): [consolidated settlement](docs/FINANCE_CONSOLIDATED_DV_2026-09-10.md), D-078. Accounting allocates gross/deductions/net across original claims for one payee/fund; Finance creates all reservations atomically. Partial checks retain explicit shares, exact payment/return/replacement lineage and recoverable handoffs. Closing one returned check frees only its posted shares on the actual date; other checks remain usable. Posted deduction correction retires the group atomically. Invalid allocation/check forms retain input. PASS: seven focused SQLite scenarios (7.321 seconds), 31 native tests including four selected races (29.817 seconds), final full project 805 discovered / 788 passed / 17 native-only skips, 313.148 seconds. The report records earlier new-fixture errors and the older Budget scenario reproduced on clean v0.7.84, then repaired without relaxing the actual-date guard. System/drift/compile/diff and local document links pass. Migrations accounting/0020-0021 and vouchers/0025 generated/tested only in disposable stores; no user-store migration or eGAPS access. All runners ended, owned MySQL is stopped/port closed and temporary baseline worktree removed. User DB hash unchanged. Check Git/remote state for publication status. Preserve the user DB and unrelated policy-test draft; do not merge into master.

Next after this checkpoint: consolidated historical source-line allocations, safe generated-history adoption and remaining post-instrument/remitted-withholding corrections; then the preserved M01/M03, inventory, ordinary-office, exact-output, usability/WFH and operational/LGU gates. The full Finance goal remains active.

Earlier v0.7.70–v0.7.84 checkpoint details, superseded next steps and historical Docker attempts are retained in [checkpoint history](docs/FINANCE_CHECKPOINT_HISTORY.md). They do not override the current checkpoint.

The [printable seven-page comparison](output/pdf/GRAND-eGAPS-Assessment-2026-09-10.pdf) remains the frozen v0.7.71 assessment delivered for colleague review. No eGAPS connection is needed for current implementation.

Native runtime: owned MySQL 8.4.11 at `C:/xxx/_INSTALLS/_HERE/_xxx/mysql-8.4.11-winx64`, fixture `.tmp/portable-mysql-20260910`, loopback 33308, strict mode and named time zones. It is stopped. `.tmp/portable_mysql.py start|stop` verifies the owned directory; `.tmp/prior_native_authority.py <labels>` invokes the committed fresh two-store runner with isolated logs and private fixture credentials. Never print/commit private files or run concurrent native suites. No user-store migration, service, PATH or firewall changes.

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
