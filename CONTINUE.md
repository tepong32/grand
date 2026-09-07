# GRAND Finance continuation handoff

Mandatory gate added 2026-09-07: [post-Finance operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md). **Finance production gate: NO-GO** pending functional completion, scrutiny, critical-gap verification and LGU acceptance. Run the full scrutiny only after the current functional phase; existing tests/container work do not satisfy it. Preserve all historical and deferred roadmap items.

Last updated: 2026-09-07

## How to resume

The next task can begin with: **“continue”**

Before changing code, inspect the current branch, status, recent commits, this file, `docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md`, and `docs/FINANCE_MY_WORK.md`. Preserve user changes and never stage `db.sqlite3`. If this branch is already checked out in another worktree, continue in that owning worktree or create the next `codex/finance-*` branch from the pushed checkpoint; do not force-checkout or discard another worktree.

## Current v0.7.11 checkpoint - Budget service authority

Branch: `codex/finance-budget-service-authority`, based on pushed `1ae2af4` (v0.7.10). FIN-GAP-008 is reproduced, fixed and verified: all six services now require explicit action permission, current owning/requesting-office custody and UAT exclusion, with Finance-database atomicity. Source mutation controls and My Work action selectors match while read scopes remain intact. Verification: all 32 focused Budget/My Work tests passed in 11.033 seconds; all 547 project tests passed on the final source in 140.140 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-008 is verified; production remains NO-GO pending functional completion, operational scrutiny and LGU acceptance. Commit/push, then continue attributed Budget completion. Preserve the user database.

## Prior v0.7.10 checkpoint - attributed Accounting completion

Branch: `codex/finance-completed-work`, based on pushed `a2e3f6b` (v0.7.9). Project completed JEV, opening-balance and period-close/reopen actions only from successful retained events attributed to the signed-in user, under current source office/read access. Current source status remains distinct from historical action completion. Exclude generated opening JEV events to avoid duplicating batch-level posting. Verification: the focused attributed-history test passed in 2.099 seconds; all 543 project tests passed on the final source in 135.649 seconds. System, migration-drift, compilation and diff checks are clean. Synthetic rendered layout checks passed at 1440px and 320px with no horizontal overflow. FIN-GAP-008 was identified in Budget transition services while tracing future completion events. Finish this independent Accounting checkpoint, then reproduce/fix/verify that critical Budget authority gap before Budget completion expansion. Preserve the user's database.

## Prior v0.7.9 checkpoint - retained-date work views

Branch: `codex/finance-work-dates`, based on pushed `552990b` (v0.7.8). Add Upcoming dates with explicit 7/14/30-calendar-day windows including today, and Past dates. Keep source date meaning and permissions, exclude undated records, and filter before the display limit. Verification: the focused calendar-boundary test passed in 1.682 seconds; all 542 project tests passed on the final source in 170.705 seconds. System, migration-drift, compilation and diff checks are clean. Edge layout checks passed at 1440px and 320px, with 320px document width at the narrow viewport. Next: attributed completion, remaining Waiting coverage and authorized export. Preserve the user's database.

## Prior v0.7.8 checkpoint - Budget Waiting

Branch: `codex/finance-budget-waiting`, based on pushed `52f373d` (v0.7.7). Extend personal Waiting to submitted proposals, allotment orders awaiting review and obligation requests awaiting certification. Preserve exact source read permissions, requesting-office scope and action exclusion. Verification: 4 focused tests passed in 3.041 seconds; all 541 project tests passed in 167.441 seconds. System, migration-drift, compilation and diff checks are clean. Continue remaining cross-cycle work afterward; preserve the user's database.

## Prior v0.7.7 checkpoint - personal Waiting and Returned views

Branch: `codex/finance-personal-waiting`, based on pushed `f13647b` (v0.7.6). Add personal contribution-based Waiting for JEVs, opening balances, submitted close checklists, advice and remittance review/release; exclude current actions before truncation. Returned uses current correction state, not historical JEV returns. Verification: 24 focused tests passed in 24.629 seconds; all 540 project tests passed on the final source in 195.115 seconds. System, migration-drift, compilation and diff checks are clean. Edge layout checks passed at 1440px and 320px; the final 320px document scroll width is 320px. Preserve the user database. Broader Waiting adapters, retained-target filters, attributed completion and authorized task export remain downstream.

## Prior v0.7.6 checkpoint — remittance and filing custody prerequisite

Branch: `codex/finance-remittance-custody`, based on pushed `6364132` (v0.7.5). Personal Waiting source review exposed FIN-GAP-007: Accounting remittance/filing review lacks office comparison and mutation permissions lack UAT exclusion. Reproduce, fix and verify before the dependent Waiting adapter. The user's confirmed personal Waiting scope remains unchanged. Final verification: all 536 project tests passed in 132.188 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-007 is verified; production remains NO-GO pending the full functional and operational gates. Commit/push this checkpoint, then continue the user-confirmed personal Waiting view. Preserve the user's database.

## Prior v0.7.5 checkpoint — initial advice assembly

Branch: `codex/finance-initial-advice-tasks`, based on pushed `d5e60e9` (v0.7.4). Project each issued instrument needing initial advice assembly; share the selector with the preselected form and attention count, keep returned advice in its correction tasks, and include instruments omitted from superseded versions. Shared-case advice/returned-item readiness now matches actual source actions. See `docs/FINANCE_SHARED_CASE_COVERAGE.md`. Validation: 2 focused tests passed in 4.550 seconds; all 534 tests passed on the final source in 130.759 seconds. System, migration-drift, compilation and diff checks are clean. Edge layout verification passed at 1440px and 390px; the final 390px document scroll width is 390px. FIN-GAP-003 is verified. Commit/push this checkpoint, then continue personal Waiting and the remaining cross-cycle views/authorized task export. Preserve the user's modified database.

## Prior v0.7.4 checkpoint — bank-advice service custody

Branch: `codex/finance-advice-custody`, based on pushed `58fb255` (v0.7.3). Reproduced FIN-GAP-006 for both foreign-office and UAT approval. Add service custody for Accounting advice decisions/responses and returned instruments, UAT mutation exclusion, and matching source action visibility. Preserve the documented Treasury submission role. Final verification: 3 focused tests passed in 5.389 seconds; all 532 project tests passed in 146.135 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-006 is verified. Commit/push and continue initial advice assembly coverage. Preserve the user's database.

## Prior v0.7.3 checkpoint — source-handoff tasks

Branch: `codex/finance-source-handoff-tasks`, based on pushed `1ee1e0e` (v0.7.2). Exact creation and synchronization tasks now derive from stored voucher/remittance source and journal states. Draft/review JEVs remain in existing tasks; shared-case posting readiness uses their actual actor gates. Source detail routes retain current-office scope. Synchronization can recover a lost core receipt through immutable source identity; a dangling retained journal link blocks creation. Validation: 3 focused tests passed in 4.509 seconds and all 531 project tests passed in 147.486 seconds. System, migration-drift, compilation and diff checks are clean. Captured Django-rendered pages were visually checked in Edge at 1440px and 390px; this is template-layout verification, not live LGU acceptance. After committing/pushing this milestone, reproduce and remediate FIN-GAP-006 bank-advice service custody before initial advice assembly coverage; FIN-GAP-003 stays open. Preserve the user's modified `db.sqlite3`.

## Prior v0.7.2 checkpoint — persisted posting handoff proof

Branch: `codex/finance-posted-handoff-controls`, based on pushed `90609d4` (v0.7.1).

Before proceeding with the remaining My Work handoff adapters, fix and verify FIN-GAP-005: voucher/remittance reconciliation trusted in-memory posted status, and remittance services lacked current-office custody. Both original status-bypass reproductions failed. This checkpoint introduces a shared stored-posting proof, retained source linkage verification, UAT exclusion and safe idempotent synchronization. Verification complete: 528 project tests passed in 301.697 seconds; system, migration-drift, compilation and diff checks are clean. Commit and push this checkpoint, then continue source-request task coverage. Preserve the legacy shadow route's separate scope and all prior milestones.

## Prior v0.7.1 checkpoint — legacy shadow Budget controls

Branch: `codex/finance-legacy-budget-controls`, based on pushed `29f8c44`.

The user explicitly requires versioned milestone commits: bump `VERSION` for each meaningful independently verified checkpoint and use a title such as `v0.7.1 — fix(finance): ...`, with a detailed body. Do not rewrite prior commits or tag unverified work.

This slice adds exact legacy shadow Budget certification tasks and fixes FIN-GAP-004 custody/input validation. FIN-GAP-003 remains open pending initial advice assembly and unmaterialized journal-handoff coverage. Continue that audit before cross-cycle views; keep the legacy route explicitly shadow-only and preserve the authoritative F4→F5 route. Final project suite: 524 tests passed across both databases in 139.139 seconds; system, migration, compilation and diff checks are clean. Commit and push this versioned checkpoint before continuing.

## Current opening-balance checkpoint

Branch: `codex/finance-f1-opening-tasks` (created from synchronized `master` at `8c0f366`).

Registered both attached operational-scrutiny documents as a mandatory post-functional completion gate in `docs/FINANCE_OPERATIONAL_SCRUTINY.md`, with Critical stop rules and a gap register. Do not run the full scrutiny prematurely or call Finance production-ready.

Added exact opening staging/correction, submission, independent review, posting and reconciliation tasks. Workspace action filters, export, attention and tasks share one current-office/permission/lifecycle/checker selector. UAT accounts cannot act. All eight opening mutation services now check current-office custody. Validation retains a source/resolved-row digest; submission/approval/posting compare live exact controls and retained events. Reconciliation verifies source-to-posted line classifications and amounts. Row correction locks the batch before the row to serialize against transitions. Posting failure rolls back before retry.

The cross-office and UAT validation defect was reproduced before remediation (two failing subcases). Focused Accounting plus the complete synthetic budget-to-Treasury-report replay: 51 tests passed in 10.679 seconds. Final complete project gate: 521 tests passed across both routed databases in 136.867 seconds. Django system checks, migration-drift checks, compilation and whitespace checks are clean.

Legacy validated evidence must be revalidated; submitted/approved evidence must be returned first. Posted legacy evidence without the digest requires controlled investigation; do not backfill historical approval proof. No production files/databases were migrated. No new authenticated desktop/mobile browser pass is claimed; source routes and screen/export parity were exercised by Django tests.

Do not redo completed adapters. Finish the remaining legacy shared-case coverage audit, then proceed with governed cross-cycle views and authorized task export. Real LGU discovery, forms, opening balances, redacted replay, backup/restore and seven-party acceptance remain external prerequisites. The full scrutiny must produce current-source research and a populated traceability matrix later; neither is represented as completed here.

## Prior merged checkpoint (historical evidence)

Branch: `master` (period-close checkpoint `d4a988c` merged and pushed)

This checkpoint adds exact, source-linked period-close checklist preparation/correction, independent close-review, and controlled-reopen decision tasks. The Accounting workspace, synchronized register export, Finance attention counts, and My Work projection now share the same permission-, office-, lifecycle-, maker-checker-, and UAT-aware action query. Evidence-sensitive revisions stop on pinned/current policy drift, checklist drift, required gate failures, one-cent trial-balance differences, submitted-event checksum drift, missing return reasons, retained reopen authority or event drift, and later-closed-period chronology. Period-close policy, checklist, close, and reopen services recheck current Accounting-office custody; preparers/submitters cannot decide their close, reopen requesters cannot decide their request, and Finance UAT preview accounts receive no close action even with an accidental permission combination. Period dates and close/reopen event times remain evidence rather than invented deadlines.

Verification on the final source:

- Focused period-close task/permission/service gate: 11 tests passed in 4.699 seconds.
- Finance/Voucher/Accounting/Reporting/guidance integration gate: 271 tests passed in 71.275 seconds.
- Complete project gate: 516 tests passed across both routed databases in 134.021 seconds.
- `manage.py check`: clean.
- `makemigrations --check --dry-run`: no drift.
- `compileall` for Accounting and Finance: clean.
- `git diff --check`: clean apart from informational LF-to-CRLF notices.

This checkpoint is merged into and pushed on `master`; its completed `codex/finance-f1-period-close-tasks` branch was retired with the other fully merged Finance branches. That branch-start instruction was completed for the current opening checkpoint. Continue on the current checkpoint branch until committed/pushed; do not discard it or restart from old master.

## Non-negotiable financial controls

- Never use floating-point arithmetic for money; retain exact decimal/centavo calculations and explicit rounding rules only where a locally accepted rule requires them.
- A required Budget, Accounting, Treasury, subsidiary, bank, remittance, or report control difference must equal exactly zero before the governed next step. A warning is not enough.
- Recompute controls at the service boundary under a transaction/row lock. Do not trust totals, permissions, office scope, or state supplied by a page or client.
- Preserve maker-checker separation, assigned-department/object scope, current-office custody, UAT exclusion, and attribution. Never let the creator/submitting actor perform an independent decision where separation is required.
- Never overwrite issued, posted, released, remitted, reviewed, approved, or otherwise retained evidence. Use an explicit returned correction before issuance, or a linked reversal, adjustment, cancellation/replacement, or successor after the governing point.
- Every report/export total must be reproducible from retained source identities, counts, snapshots, control equations, and checksums. Screen, task, and export scopes must select the same records.
- Keep COA/DBM/BIR and local-form claims honest: starters remain candidates until the implementing LGU records current local authority, exact forms, signatories, routes, copies, and independent acceptance.
- Do not claim production readiness from automated tests alone. Actual master data, opening balances, redacted replay, named-user acceptance, printer/device checks, backup/restore evidence, and LGU authority remain external gates.

## Remaining implementation in dependency order

### 1. Audit any remaining F1.5 count-only attention groups

The domain inventory in `docs/FINANCE_MY_WORK.md` identified and filled all five opening actions. Next inspect the legacy shared voucher `BUDGET_DRAFT` compatibility stage and verify every other shared-case stage maps to an exact source action. Do not claim full adapter coverage until this case-to-action audit is complete, and do not invent new groups. Then proceed with cross-cycle views.

For any gap, first identify or extract one shared permission/office/state/maker-checker queryset used by the authoritative workspace, register export, attention count, and task projection. Give each source/action a deterministic Task ID and a projection checksum that changes when relevant evidence changes. Include exact action, gate, queue, source state/version, timing basis, exception, and authoritative URL. Do not invent deadlines from transaction or period dates. Add negative tests for cross-office access, self-review, UAT preview, one-cent differences, stale/tampered evidence, and screen/export/task count parity.

### 2. Complete the cross-cycle My Work contract

After every supported summary group has an exact adapter, implement these as separate checkpoints:

1. Governed `Waiting`, `Returned`, `Due`, and `Completed by me` views based on authoritative source events—not inferred labels.
2. A separately permissioned, TraceSync-ready task/register export whose rows exactly match the filtered screen and include a manifest/checksum without leaking protected details.
3. Governed saved/shared views, search, follow/following, and notifications only after local ownership and privacy rules are recorded. Keep private saved views private by default.
4. Authenticated desktop and narrow-layout browser verification for the expanded task table and floating `?` guide, including keyboard/focus behavior and zero application-route console errors.

Commit and push each independently reversible checkpoint on its own `codex/finance-*` branch with a detailed bulleted commit body. Follow the risk-tiered verification policy below.

### 3. Finish the real LGU acceptance sequence

These steps require implementing-LGU evidence and must stay visibly blocked until supplied; code must not fabricate them:

1. Close F0/F1 discovery for the intended first deployment scope, including named owners/reviewers/signatories/support contacts, enabled transactions, actual systems/interfaces, unresolved decisions, and an independently accepted whole-scope decision.
2. Accept the exact F10 blank/redacted completed forms, resolve every candidate mapping, perform all required layout/print/accessibility tests, and retain independent acceptance.
3. Open F2 with actual approved configuration and opening balances; independently approve/post and reconcile every fund to signed controls.
4. Replay one complete redacted F3–F9 chain: authorized budget → allotment → obligation → payable → DV → JEV → payment/advice/release → bank reconciliation → accountability package. Resolve all differences by governed correction/reversal/successor.
5. Execute F11 field qualification with named roles, approved curricula/support/cadence, nonfunctional exercises, a production-compatible off-host two-store restore, and uninterrupted qualifying shadow/parallel cycles using the accepted form set.
6. Collect separate Requesting Office, Budget, Accounting, Treasury, IT, management, and audit decisions. Record go/no-go, date, signed authority reference/checksum/custody, and rollback criteria only after those gates pass.

## Checkpoint completion routine

At the end of every slice:

1. Review the complete diff and confirm that no unrelated or user-owned change was altered.
2. Run slice-specific tests while developing. Run a dependency gate once only when shared selectors, permissions, routing, services, or cross-domain lineage make it relevant.
3. Run `manage.py check`, `makemigrations --check --dry-run`, `git diff --check`, and `manage.py test --keepdb --noinput` once on final executable source before declaring the checkpoint clean. The complete suite subsumes the 271-test Finance integration gate; do not run both on unchanged code.
4. Update `CHANGELOG.md`, this file, `docs/FINANCE_MY_WORK.md`, and `docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md` with actual—not estimated—evidence and remaining work.
5. Stage explicit files only; exclude `db.sqlite3`, generated outputs, secrets, and unrelated changes.
6. Commit with a concise subject and a detailed bulleted body describing controls, authorization/immutability behavior, UX/guidance/exports, and verification.
7. Push the checkpoint branch and verify that local `HEAD` equals its upstream. Pause if the user requested a pause.

## Risk-tiered verification policy

- Development loop: run the smallest meaningful test class or method set for the changed behavior, with `--keepdb --noinput -v 0` and `--failfast` where useful.
- Dependency gate: broaden only when the change touches a shared task aggregator, permission/source query, database router, financial service boundary, or cross-domain lineage. Select the directly affected source tests and known integration regressions instead of the whole 271-test slice by habit.
- Checkpoint gate: run the complete project suite once after executable source is final. Documentation-only edits after that green run do not invalidate it; executable code, template, configuration, or migration changes do.
- Output control: capture full routine test output in an ignored `.tmp` log and surface only the summary or relevant failure trace. Preserve the log for diagnosis without loading ordinary application logging into the conversation.
- Current CI runs on pull requests and pushes to `master`, not ordinary feature-branch pushes, so a local final complete-suite pass remains required before a standalone checkpoint push.

User-confirmed cross-cycle scope (2026-09-07): Waiting shows work the signed-in user prepared or submitted that is now with another person. It does not expand to every office-visible record, and current source-record access still applies.
