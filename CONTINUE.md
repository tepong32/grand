# GRAND Finance continuation handoff

Mandatory gate added 2026-09-07: [post-Finance operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md). **Finance production gate: NO-GO** pending functional completion, scrutiny, critical-gap verification and LGU acceptance. Run the full scrutiny only after the current functional phase; existing tests/container work do not satisfy it. Preserve all historical and deferred roadmap items.

Last updated: 2026-09-08

Turning-point decisions are recorded separately in [the implementation decision log](docs/IMPLEMENTATION_DECISIONS.md), as requested by the user. Keep each choice tied to the canonical product goal, alternatives, tradeoffs, evidence and revisit conditions.

Personal handoff coverage and the next source adapter are summarized in [the coverage table](docs/FINANCE_WORK_VIEW_COVERAGE.md).

## How to resume

The next task can begin with: **“continue”**

Before changing code, inspect the current branch, status, recent commits, this file, `docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md`, and `docs/FINANCE_MY_WORK.md`. Preserve user changes and never stage `db.sqlite3`. If this branch is already checked out in another worktree, continue in that owning worktree or create the next `codex/finance-*` branch from the pushed checkpoint; do not force-checkout or discard another worktree.

## Current v0.7.31 checkpoint - bank-reconciliation personal handoffs

Branch: `codex/finance-bank-reconciliation-handoffs`, based on pushed `cd1249b`. Personal Waiting now includes the user’s submitted bank reconciliations under current bank-register access. Completed by me includes retained submission, return and reconciliation events with matching event/batch office and actor attribution. Current batch state remains separate from historical actions. Statement coverage dates are not deadlines; individual matching/classification actions remain outside this completion slice. Verification: all 7 focused bank contracts passed in 9.872 seconds; all 128 My Work/Accounting/dependent replay tests passed in 124.300 seconds. System, migration-drift, compilation and diff checks passed. D-021 records scope. Next priority: reproduce and close FIN-GAP-015 (cash UAT mutation guard) before dependent cash projections. Continue remaining Finance phases; preserve the user database.

## Prior v0.7.30 checkpoint - attributed instrument-action history

Branch: `codex/finance-instrument-completion-history`, based on pushed `4938e5b`. Completed by me now credits retained check issuance, controlled replacement issuance, advice submission, cancellation and physical release events. Instrument actions require matching current case read scope, stored actor, instrument identity, check number and replacement lineage where applicable. Current instrument/case states remain separate from the recorded action. Final physical release is labelled as such even when required Accounting posting remains open. Verification: all three focused attribution/payment/cancellation replays passed in 10.454 seconds; all 169 My Work/voucher dependency tests passed in 91.877 seconds. System, migration-drift, compilation and diff checks passed. D-020 records scope and terminology. Continue remaining Finance phases; preserve the user database.

## Prior v0.7.29 checkpoint - attributed returned-payment history

Branch: `codex/finance-returned-payment-history`, based on pushed `c6705d5`. Completed by me now includes retained returned-payment submission, clarified submission, return-for-clarification and Accounting-decision events. Projection requires matching review/case identity, stored actor attribution, valid transitions and matching clarification/outcome evidence, under current review-register and case read access. Superseded versions retain their own historical entries. These decisions do not claim that required posting, replacement or payment release is complete. Verification: all three focused identity/outcome/replay tests passed in 5.961 seconds; all 168 My Work/voucher dependency tests passed in 84.528 seconds. System, migration-drift, compilation and diff checks passed. D-019 records the decision. Continue remaining Finance phases; preserve the user database.

## Prior v0.7.28 checkpoint - returned-payment personal handoffs

Branch: `codex/finance-returned-payment-waiting`, based on pushed `2c69730`. Personal Waiting now includes attributed returned-payment reviews through independent review, clarification, reversal posting and controlled replacement. It uses the existing role-shaped register scope, current stage/status consistency and exact review anchors. Superseded reviews leave Waiting; authorized review, case, source and journal actions are excluded before truncation. Open posting-request authorship can qualify during posting, while existing preparer attribution persists through the handoff. Verification: all three focused tests passed in 6.576 seconds; all 166 My Work/voucher dependency tests passed in 82.166 seconds. System, migration-drift, compilation and diff checks passed. D-018 records scope and verification policy. Continue remaining Finance phases; preserve the user database.

## Prior v0.7.27 checkpoint - release and event-posting personal handoffs

Branch: `codex/finance-release-posting-waiting`, based on pushed `dcef952`. Personal Waiting now covers Treasury release and Accounting event posting. Issued/advised instrument issuers retain release-phase attribution; open payment/remittance/cancellation/replacement/reversal requesters retain event-posting attribution. Authorized returned-payment, source and journal actions resolve to the shared case before truncation. Current read scope and retained stage transitions remain authoritative. A physical release does not imply that required journal posting is complete; completed cases leave Waiting. Verification: all four focused attribution/action/replay tests passed in 11.728 seconds; all 586 project tests passed in 190.924 seconds. System, migration-drift, compilation and diff checks passed. Full regression covers cross-module source/journal/returned-payment mapping; operational LGU acceptance is not claimed. D-017 records the decision. Continue remaining Finance phases; preserve the user database.

## Prior v0.7.26 checkpoint - Treasury and advice personal handoffs

Branch: `codex/finance-treasury-advice-waiting`, based on pushed `2abb39e`, with the user-requested master guidance merged at `9ac683f` (master `42fd662`). The AGENTS.md add/add conflict preserves master’s publication distinction and this branch’s decision/scrutiny links; the Finance changes were restored and the database SHA-256 was unchanged. Personal Waiting now follows attributed cases through Treasury check preparation and Accounting bank advice. Initial advice assembly and authorized current-batch actions resolve to the same voucher case before truncation. An issuer retains Waiting while their issued/advised instrument is in the advice phase; cancelled instruments alone do not confer attribution. Current workbench scope, historical handoff time and the existing advice maker-checker controls remain intact. Treasury release and post-release exceptions are not included in this slice. Verification: all three focused cap/issuer/replay tests passed in 9.558 seconds; all 584 project tests passed in 187.754 seconds on the merged branch. System, migration-drift, compilation and diff checks passed. Broad regression covers the cross-module case/instrument/advice relationships; LGU acceptance remains unperformed. D-016 records the scope. Continue remaining Finance work under the user’s instruction; preserve the user database.

## Prior v0.7.25 checkpoint - personal voucher posting handoffs

Branch: `codex/finance-voucher-posting-waiting`, based on pushed `96bc968`. Personal Waiting now continues through Accounting posting for the retained intake/DV preparer or submitter and the requester of an open recognition posting request. Already-authorized source-creation, journal preparation/posting and source-synchronization actions resolve to the shared voucher case before the display cap. Current source read access and retained stage-handoff timing remain required; ledger dates are not deadlines. Treasury preparation and later exception/payment stages remain separate coverage. Verification: both focused handoff/replay tests passed in 8.410 seconds; all 582 project tests passed in 187.761 seconds. System, migration-drift, compilation and diff checks are clean. The full suite was run because action mapping spans vouchers, Accounting and both databases. D-015 records the decision. The user requested continued Finance implementation until complete, a stopping hurdle or a pause instruction. Preserve `db.sqlite3`. Root AGENTS.md is included as required portable repository context.

## Prior v0.7.24 checkpoint - attributed DV completion history

The user explicitly confirmed `https://github.com/tepong32/grand.git` as the authorized source/document destination; v0.7.24 (`96bc968`) was pushed successfully. The prior automatic-review hurdle is resolved.

User resumed with “continue”. Branch: `codex/finance-dv-completion-history`, based on pushed `fe6d93b`. Completed by me now includes retained DV preparation/correction, ordinary partial/final signature-return recording and Accounting-validation events. Each action requires current source read access and matching source transition semantics. Repeated corrections have distinct event identities; historical acting office and current case stage remain separate. Signature-return completion credits custody recording, not the recorder’s signature, and validation does not authorize payment release. Amendment, print/packet and later payment event history remain future work. D-014 records attribution and authority distinctions. Verification: both focused tests passed in 2.707 seconds; all 581 project tests passed in 336.250 seconds, including service-generated signature events and the full Budget-to-payment replay. System, migration-drift, compilation and diff checks are clean. Preserve the user database.

## Prior v0.7.23 checkpoint - paused, then resumed

Branch: `codex/finance-dv-personal-handoffs`, based on pushed `4df5f15`. Personal Waiting now follows attributed payable/DV work through wet-signature custody and independent Accounting validation under current source read access. The DV preparer or retained intake preparer/submitter qualifies; arbitrary case creation does not. Authorized signature child actions suppress the parent case before truncation. Stage age uses the latest retained transition into the current stage; partial signature events do not restart it, and missing evidence is disclosed. Controlled signature actions now require the source-required TracePoint link as well as the matching print job, preserving legacy/non-controlled rules. Journal/advice handoffs and DV completion history remain future work. Verification: all nine focused DV tests passed in 3.594 seconds; all 579 project tests passed in 260.708 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-014 is verified. Finish commit/push, then remain **PAUSED** under the latest user instruction. Do not begin another phase until the user resumes. Preserve the user database. Turning-point rationale is recorded in D-013.

## Prior v0.7.22 checkpoint - signature custody authority

Branch: `codex/finance-signature-task-authority`, based on pushed `cfdb118`. Wet-signature return now locks and reloads the stored task within the authorized voucher case before checking pending state, round and sequence. Caller-supplied stale state or altered linkage/order cannot overwrite prior custody or write another case. The shared voucher-service mutation guard also excludes UAT despite combined operational permissions; separate workbench read predicates remain intact. Original isolated reproduction accepted all four forbidden paths (5 tests, 4 failures). Normal ordered recording and same-key retry remain supported. FIN-GAP-012/013 are verified: all five focused boundary tests passed in 0.070 seconds; all 577 project tests passed in 162.985 seconds. System, migration-drift, compilation and diff checks are clean. Next: reproduce/fix FIN-GAP-014 and resolve child signature actions to their case before expanding DV Waiting. Preserve the user database and keep the side decision log current.

## Prior v0.7.21 checkpoint - personal payable handoffs

Branch: `codex/finance-payable-personal-handoffs`, based on pushed `cf4fea3`. Personal Waiting now follows attributed payable intake through independent Accounting review and accepted-payable DV preparation. Current workbench scope, consistent intake/case stages and the shared voucher-case identity govern visibility and action exclusion before truncation. Completion uses retained payable submission, return and acceptance events with historical actor-office attribution and current source access. Acceptance means readiness for DV preparation, not authorization to release payment. Later signature, journal, advice and exception Waiting remains outside this bounded adapter. Verification: all three focused payable tests passed in 2.093 seconds; all 572 project tests passed in 153.168 seconds, including service-generated handoffs in the full transaction replay. System, migration-drift, compilation and diff checks are clean. Next priority: reproduce and close FIN-GAP-012 before expanding signature projections. Preserve the user database and side-document turning-point decisions.

## Prior v0.7.20 checkpoint - personal discovery handoffs

Branch: `codex/finance-discovery-personal-handoffs`, based on pushed `e85288e`. Personal discovery Waiting now uses retained preparer/submitter attribution and the current named-owner/reviewer or office read boundary, preserving established cross-office access. Stored review targets retain their local review meaning. Completed by me uses retained submission, return and recording events, with stable identities and current source access. Recording an unresolved finding remains distinct from LGU-confirmed acceptance and keeps the current named-scope blocker visible. Evidence locks and decision authority are unchanged. Verification: all three focused discovery handoff tests passed in 2.879 seconds; all 569 project tests passed in 149.738 seconds. System, migration-drift, compilation and diff checks are clean. Continue remaining source handoff/history coverage after verification. Preserve the user database and side-document turning-point decisions.

## Prior v0.7.19 checkpoint - attributed setup completion

Branch: `codex/finance-setup-completion-history`, based on pushed `a1d3a7b`. Completed by me now includes retained setup release submission, return, approval, scheduling, activation, restoration and retirement actions attributed to the signed-in account. Current source read scope and event/target/office consistency are required. Repeated submissions keep separate stable event identities, and current release state remains distinct from historical completion. Draft creation or terminal status alone does not credit a handoff. Template/preflight and other child actions remain outside this adapter. Verification: both focused setup completion tests passed in 1.814 seconds; all 566 project tests passed in 215.253 seconds. System, migration-drift, compilation and diff checks are clean. Continue remaining source handoff/history coverage after verification. Preserve the user database and side-document turning-point decisions.

## Prior v0.7.18 checkpoint - personal setup handoffs

Branch: `codex/finance-setup-personal-handoffs`, based on pushed `1be3493`. Personal Waiting now includes submitted Finance setup releases under current source read scope and retained preparer/submitter attribution. Draft releases with matching retained return events appear in Returned with the reviewer reason and return time; resubmission removes that label. Stable source identities and authorized-action exclusion apply before display truncation. The setup review selector recognizes existing active self-approval exemptions without granting them; task/source guidance distinguishes exempt approval from independent return. Effective dates remain separate from submission deadlines. Verification: four focused setup handoff tests passed in 2.864 seconds; all 564 project tests passed in 152.521 seconds. System, migration-drift, compilation and diff checks are clean. Continue broader handoff and attributed history coverage after verification. Preserve the user database and side-document turning-point decisions.

## Prior v0.7.17 checkpoint - governed setup review correction

Branch: `codex/finance-setup-review-correction`, based on pushed `87a1484`. Submitted setup releases can be returned to draft by an independent, explicitly authorized reviewer with a mandatory correction reason. Submitted child records follow the release back to draft; submission attribution and immutable return history are retained. Draft workbook correction preserves the prior file and checksum evidence, clears preflight, and requires fresh preflight before resubmission/approval. Current release/template state and office/UAT authority are checked under release-first locks. Source pages expose return, correction and retained return guidance. Approved records remain locked. FIN-GAP-010 is verified for the bounded return/workbook-correction flow: all 24 focused Finance tests passed in 3.942 seconds; all 561 project tests passed in 143.087 seconds. System, migration-drift, compilation and diff checks are clean. Synthetic review/correction layout checks cover desktop and 320px, with corrected narrow forms and wrapping draft actions.; scope covers workbook correction and missing preflight, not arbitrary master-data editing. Continue setup projections once the source correction gate passes. Preserve the user database and keep the side decision log current.

## Prior v0.7.16 checkpoint - Finance control UAT authority

Branch: `codex/finance-control-uat-authority`, based on pushed `3cd16c0`. Reproduce direct UAT setup submission/approval/template-preflight with combined permissions, then fix FIN-GAP-009 before dependent setup expansion. Inspect shared Finance mutation predicates and preserve current preview reads, normal explicit office authority and governed exemptions. FIN-GAP-009 is verified: all 20 focused Finance control tests passed in 3.225 seconds; all 557 project tests passed on the final source in 144.110 seconds. System, migration-drift, compilation and diff checks are clean. Commit/push, then reproduce and address FIN-GAP-010 before dependent setup coverage. Keep turning-point choices side-documented and preserve the user database.

## Prior v0.7.15 checkpoint - released remittance Waiting

Branch: `codex/finance-remittance-waiting-handoff`, based on pushed `b6d7640`. Extend personal Waiting through Accounting posting after release. Use current remittance read scope and retained preparer/submitter/releaser attribution; remove Waiting when the user has a related posting-request or journal action, before truncation. Verification: both focused remittance Waiting tests passed in 5.368 seconds; all 555 project tests passed on the final source in 139.218 seconds. System, migration-drift, compilation and diff checks are clean. Commit/push, then reproduce and fix FIN-GAP-009 before setup Waiting expansion. Continue autonomous work; keep the side decision log current and preserve the user database.

## Prior v0.7.14 checkpoint - payment handoff completion

User resumed autonomous work after the v0.7.13 pause. Branch: `codex/finance-payment-completion-history`, based on pushed `abfe160`. Extend attributed completion to bank-advice and remittance actions under current source read access, preserving cross-office Treasury advice submission. Verification: both focused payment-handoff tests passed in 3.328 seconds; all 553 project tests passed on the final source in 147.078 seconds. System, migration-drift, compilation and diff checks are clean. Commit/push, then extend personal Waiting through released remittance posting with source/journal action exclusion. Continue autonomous work under the user's latest request. Preserve the user database.

## Prior v0.7.13 checkpoint - permissioned portable work export

Branch: `codex/finance-work-portable-export`, based on pushed `5da4103` (v0.7.12). The current implementation is complete: explicitly administrator-assigned My Work export permission, bounded live CSV, scope/filter parity, retained checksum/manifest and audit event. No seeded role grants. Verification: both focused export tests passed in 4.289 seconds; all 551 project tests passed on the final source in 143.952 seconds. System, migration-drift, compilation and diff checks are clean. Synthetic Django-rendered layout checks passed in Edge at 1440px and 320px, with no mobile horizontal overflow. Commit/push this checkpoint, then remain PAUSED as the user requested. Do not begin another phase without a new continuation request. Deployment requires migration 0020 and an explicit permission grant; no live database migration or role grant was performed. Remaining future work includes broader Waiting/completion adapters and assignment/following/shared-view/notification rules. Production remains NO-GO pending the recorded functional and operational gates. Preserve the user database.

## Prior v0.7.12 checkpoint - attributed Budget completion

Branch: `codex/finance-budget-completed-work`, based on pushed `23bef64` (v0.7.11). Extend Completed by me to retained Budget call/proposal/consolidation/appropriation/allotment/obligation actions. Require exact current source read access and event actor/office/target consistency. Resolve appropriation events to their retained authority link; keep requesting-office obligation access. Verification: both focused Budget event-history tests passed in 2.928 seconds; all 549 project tests passed on the final source in 178.424 seconds. System, migration-drift, compilation and diff checks are clean. Commit/push, then start bounded My Work portable export. User confirmed that administrators assign its separate permission explicitly to selected users or groups; do not seed grants into operational roles. Preserve the user database.

## Prior v0.7.11 checkpoint - Budget service authority

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
