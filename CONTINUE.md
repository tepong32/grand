# GRAND Finance continuation handoff

Last updated: 2026-09-06

## How to resume

The next task can begin with: **“continue”**

Before changing code, inspect the current branch, status, recent commits, this file, `docs/FINANCE_ROADMAP_COMPLETION_AUDIT.md`, and `docs/FINANCE_MY_WORK.md`. Preserve user changes and never stage `db.sqlite3`. If this branch is already checked out in another worktree, continue in that owning worktree or create the next `codex/finance-*` branch from the pushed checkpoint; do not force-checkout or discard another worktree.

## Last completed checkpoint

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

This checkpoint is merged into and pushed on `master`; its completed `codex/finance-f1-period-close-tasks` branch was retired with the other fully merged Finance branches. Confirm local `master` still equals `origin/master`, then create the next `codex/finance-*` branch from that pushed checkpoint before changing code.

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

Enumerate every existing Finance attention group and compare it with the stable item-level adapters. If any actionable group is still represented only by a count, add its exact adapter before starting the cross-cycle views. Do not invent a group solely to make the list longer.

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
