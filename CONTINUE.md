# GRAND Finance continuation handoff

Mandatory gate added 2026-09-07: [post-Finance operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md). **Finance production gate: NO-GO** pending functional completion, scrutiny, critical-gap verification and LGU acceptance. Run the full scrutiny only after the current functional phase; existing tests/container work do not satisfy it. Preserve all historical and deferred roadmap items.

Last updated: 2026-09-09

Turning-point decisions are recorded separately in [the implementation decision log](docs/IMPLEMENTATION_DECISIONS.md), as requested by the user. Keep each choice tied to the canonical product goal, alternatives, tradeoffs, evidence and revisit conditions.

Personal handoff coverage and the next source adapter are summarized in [the coverage table](docs/FINANCE_WORK_VIEW_COVERAGE.md).

## How to resume

The next task can begin with: **“continue”**

Before changing code, inspect the current branch, status, recent commits, this file, `docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md`, and `docs/FINANCE_MY_WORK.md`. Preserve user changes and never stage `db.sqlite3`. If this branch is already checked out in another worktree, continue in that owning worktree or create the next `codex/finance-*` branch from the pushed checkpoint; do not force-checkout or discard another worktree.

## Current v0.7.65 checkpoint - Independent source-layout review tasks

Branch: `codex/finance-source-drift-handoffs`, based on pushed and remotely verified `0f57428`. Independent reviewers now receive an exact task for a current pending source-layout drift in a draft field cycle. Register attention, counts, My Work, cycle-page links and review forms share current-office, explicit-permission, UAT and maker-checker eligibility. Rejected, superseded and completed source versions retain their evidence without offering another decision. PASS: 133 cutover/My Work/operations tests in 101.312 seconds; system, migration-drift, compilation and diff checks passed. Initial reproduction failed one real source-staging task assertion (1 test, 2.249 seconds). Tests cover independent task/source navigation, self-review exclusion, acceptance/start, rejected-source replacement, supersession, UAT and permission loss. Full suite NOT RUN - OUT OF SCOPE for this read-only selector and form-eligibility refinement: affected field lifecycle and shared work/operations suites cover the changed contracts, with v0.7.64 full-project baseline recorded separately. Browser NOT RUN - OUT OF SCOPE: existing layout unchanged; rendered links and form responses verified by integration tests. No schema/service mutation changes or live migration; user database unchanged. The first 133-test affected run errored on a missing import in the new external-lock test (100.629 seconds; FAIL - CAUSED BY CURRENT WORK, test setup); the import was corrected and the entire affected suite rerun. FIN-GAP-031 verified; D-055 records the decision. Next: source-stager Waiting and retained source staging/drift history, resolving immutable cycle/version identity rather than attributing work to the cycle creator.

## Active instructions and repository continuity

- Continue until the user pauses or an actual hurdle requires input. Earlier pause instructions in the historical snapshots are superseded.
- Make meaningful versioned checkpoints: bump VERSION, commit as `v0.7.x — feat/fix(finance): ...`, and push stacked `codex/finance-*` branches to the explicitly authorized `https://github.com/tepong32/grand.git`. Do not merge feature work into master without a request.
- Keep turning-point decisions in [IMPLEMENTATION_DECISIONS.md](docs/IMPLEMENTATION_DECISIONS.md).
- Waiting means work the signed-in user prepared/submitted, with current source access. Administrators explicitly assign the separate My Work export permission to selected users/groups.
- The requested master guidance pull is complete: master `42fd662` was integrated by merge `9ac683f`, preserving local Finance work. Current feature development continues from the pushed checkpoint, not old master.
- Never stage or alter the existing user `db.sqlite3` change. Use explicit staging paths. Its retained SHA-256 is `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
- Legacy opening evidence without its required digest needs revalidation/controlled investigation; do not backfill historical approvals. No live database migration or role grant has been performed in these checkpoints.
- Older checkpoint details are preserved in [FINANCE_CHECKPOINT_HISTORY.md](docs/FINANCE_CHECKPOINT_HISTORY.md); their next-step/test/pause text is historical.

## Remaining implementation order

1. Finish the open source-authority findings in [FINANCE_GAP_REGISTER.md](docs/FINANCE_GAP_REGISTER.md), starting with the next family named in the current checkpoint. Reproduce before repair, and preserve source office, actor, maker-checker and immutable evidence rules.
2. Complete remaining personal adapters in [FINANCE_WORK_VIEW_COVERAGE.md](docs/FINANCE_WORK_VIEW_COVERAGE.md): reporting/accountability, field cycles/nested controls, local forms and remaining detailed custody/posting/reopen history. Do not redo completed source adapters or infer completion from current status alone.
3. Assignment/following, governed shared views and notifications remain future work pending ownership/privacy rules. Preserve private views by default. Complete expanded desktop/narrow-layout, keyboard/focus and browser-console verification as applicable.
4. Only after functional completion, run the mandatory [operational scrutiny](docs/FINANCE_OPERATIONAL_SCRUTINY.md), current-source research and traceability matrix, then the real LGU gates below. Synthetic tests do not satisfy those gates.

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
