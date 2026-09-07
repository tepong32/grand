# Finance gap register

Started 2026-09-07 during continued functional implementation. This is not the completed post-Finance scrutiny. See the [mandatory gate](FINANCE_OPERATIONAL_SCRUTINY.md) for severity, stop rules and verification requirements.

## FIN-GAP-001 — Opening-balance service custody

- Process/module: F2 opening staging, correction, submission, independent decision, posting and reconciliation; Accounting services.
- Severity/status: **CRITICAL — VERIFIED** on 2026-09-07. This defect is cleared; the overall production gate remains NO-GO for incomplete functional/scrutiny/acceptance work.
- Basis: intended current-office custody and UAT exclusion in `CONTINUE.md`; an explicitly permissioned actor must not mutate another office's financial records.
- Previous behavior: opening services checked the action permission but load batches by primary key without verifying the actor's current office. Opening permissions also do not exclude a Finance UAT account with accidentally combined action permissions.
- Expected behavior/impact: deny unauthorized calls before mutation, retain maker-checker separation and current-office scope. Otherwise a privileged actor from another office can change opening financial state through the service boundary.
- Cause: implementation-level authorization defect; no architectural redesign currently required.
- Priority/remediation: immediate; deterministic direct-service regressions, shared action selector for workspace/export/count/task, guarded services, then opening lifecycle and cross-cycle regression.
- Evidence/verification: initial direct-service validation regression failed for both cross-office and UAT actors before the fix (`.tmp/opening-reproduction.log`). All eight mutation services now reject those actors; the expanded regression checks unchanged state/events. The 51-test Accounting/affected complete-cycle run and 521-test full suite passed.

## FIN-GAP-002 — Cached opening validation and incomplete reconciliation lineage

- Process/module: F2 submission → approval → posting → reconciliation.
- Severity/status: **CRITICAL — VERIFIED** on 2026-09-07 after focused, full-project and affected-chain validation.
- Basis/expected behavior: the project requires exact controls at the service boundary and preservation of approved source evidence; reportable balances must agree with retained financial history.
- Previous behavior: submission trusted `validation_summary.valid`, approval did not recompute row evidence, posting checked individual valid rows and journal balance but not a retained approved source digest, and reconciliation compared totals/counts without checking source-to-posted line classifications.
- Impact: stale/tampered rows or a balanced classification change could escape the appropriate approval/reconciliation gate.
- Cause: implementation-level evidence validation; no architecture change required for this correction. Two-store atomicity and production recovery remain separate operational gates.
- Remediation: retained source/resolved-row digest, fresh exact controls at transitions, matching submission/approval events, source-to-posting comparisons, and read-only task exceptions. Legacy retained evidence fails closed; never fabricate a historical digest.
- Reproduction/regression: tests for memo drift before submission, one-cent review drift, approved row changes before posting, balanced ledger classification drift, and failure after journal posting followed by a clean retry. The 51-test focused Accounting/affected complete-cycle run passed in 10.679 seconds; the 521-test full suite passed in 136.867 seconds. Tests are retained in `accounting/tests.py`; the affected chain is `VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay`.
- Priority: immediate. This defect is cleared. Production gate remains NO-GO pending the larger functional/operational and LGU acceptance gates.

## FIN-GAP-003 — Shared-case item coverage audit remains open

- Process/module: F1.5 My Work; shared Voucher Workbench attention.
- Severity/status: **HIGH — OPEN**, functional completion remains incomplete. This is a task-discoverability gap; no financial corruption or authority bypass has been demonstrated by this finding.
- Basis/current behavior: `voucher-ready` includes legacy `BUDGET_DRAFT` cases under `vouchers.certify_budget_obligation`, while `_budget_tasks` projects authoritative Budget obligation requests under separate permissions. The existing adapters do not establish an exact item for that legacy stage.
- Expected behavior/impact: every supported actionable count has a reproducible source-action projection. Users can currently follow the source queue, but the exact cross-cycle item list may omit that work.
- Workaround: use the existing permission-scoped Voucher Workbench “Open exact queue”; its service controls remain authoritative. Do not equate case counts with instrument/child-action counts.
- Cause/priority: missing adapter or obsolete-stage routing; investigate actual supported legacy behavior before choosing implementation. No architectural redesign yet established. Complete this before cross-cycle views.
- Next evidence: enumerate each shared-case stage, reproduce visibility with its actual role, test source/task correspondence, and determine whether the legacy stage needs a governed adapter or retirement. Do not invent business authority or lower severity if investigation finds an integrity defect.

## FIN-GAP-004 — Legacy shadow Budget certification custody

- Process/module: Voucher Workbench shadow Budget draft certification.
- Severity/status: **CRITICAL — VERIFIED**. Five focused tests including both affected chains passed in 5.146 seconds; the full suite passed 524 tests in 139.139 seconds.
- Basis: current-office financial custody and UAT action exclusion are mandatory even for a synthetic compatibility route.
- Reproduction: `test_legacy_budget_certification_rejects_cross_office_and_uat` failed before remediation because a foreign-office actor certified the case and advanced it to Accounting (`.tmp/legacy-budget-reproduction.log`).
- Previous behavior: certification checked the permission only; allocation normalization silently discarded nonpositive rows and did not recheck current configured codes at the service boundary.
- Remediation: current-office check, UAT denial, actor/office-bound idempotency receipt, strictly positive finite centavo amounts, configured source codes and nonblank source reference. Compatibility certification requires an unlinked shadow case. Invalid input leaves numbering and event state untouched.
- Classification/priority: implementation defect; immediate. No architectural redesign required for these custody and input guards.
- Operational boundary: this legacy route is explicitly a shadow compatibility exercise with referenced sources; it does not perform authoritative appropriation/allotment availability checks. Full Finance use must follow F4→F5. No production authority is granted by its new task projection.

### FIN-GAP-003 progress — v0.7.1

The legacy Budget action now has an exact source-linked projection using the same selector as shared-case action filters and detail controls. Remaining audit items include cases waiting for initial advice batch assembly and cases whose JEV handoff has not yet materialized a JournalEntry; a batch-only or journal-only adapter is not automatically complete coverage. Keep this High finding open until every supported shared-case stage has been checked.

## FIN-GAP-005 — Posting handoff trusts caller state / lacks service custody

- Process/module: voucher and remittance Finance-to-core posting synchronization; remittance draft materialization.
- Severity/status: **CRITICAL — VERIFIED** in v0.7.2. The full project suite passed 528 tests in 301.697 seconds, including both affected chains. Functional work may continue; the overall production gate remains NO-GO.
- Basis/current behavior: handoff functions inspect the supplied JournalEntry object's status rather than reload its persisted posting evidence. Both lack a current-office service check; remittance materialization also uses the source department without checking the actor's department.
- Expected behavior/impact: only the current Accounting office may create or synchronize its source journal; no in-memory claimed posted status may advance a voucher/remittance while the stored ledger remains draft.
- Classification: implementation-level authority and cross-module integrity defect; apply one shared persisted-posting proof and source/ledger identity check. Preserve recoverable two-store behavior and idempotent retries.
- Required verification: forged-status reproduction; foreign-office/UAT denial; payload/link/event/centavo drift; failed/retried synchronization and both affected complete chains. No production-ready claim before verification.

FIN-GAP-005 reproduction: both `test_voucher_handoff_requires_persisted_posting` and `test_remittance_handoff_requires_persisted_posting` failed against the original functions; each accepted an in-memory `POSTED` label while the stored journal remained draft (`.tmp/handoff-reproduction.log`). The fix reloads the current-office stored entry, requires attributed posting and matching event totals, verifies source/ledger identities and payload/rule digests, restricts remittance draft materialization to its Accounting office, excludes UAT journal actions and makes successful synchronization retries idempotent. Final validation: 528 tests passed in 301.697 seconds, including forged status, foreign-office/UAT denial, posting-event centavo drift, payload drift, interrupted synchronization and idempotent retry. System, migration-drift, compilation and diff checks are clean.
