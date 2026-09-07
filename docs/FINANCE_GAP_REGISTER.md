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

## FIN-GAP-003 — Shared-case item coverage audit

- Process/module: F1.5 My Work; shared Voucher Workbench attention.
- Severity/status: **HIGH — VERIFIED** in v0.7.5 for the supported routes in `FINANCE_SHARED_CASE_COVERAGE.md`. Cross-cycle functionality remains incomplete. This is a task-discoverability gap; no financial corruption or authority bypass has been demonstrated by this finding.
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

### FIN-GAP-003 progress — v0.7.3

Added exact source creation/synchronization tasks for voucher and remittance requests. Existing JEV drafts and independent posting remain their original task types, and shared-case posting counts now follow the actual source/journal actor gates. Source pages preserve current-office access; the stored-proof synchronization recovers missing receipt pointers through immutable source identity. Dangling retained journal links fail closed before new creation. Validation: 3 focused tests passed in 4.509 seconds and all 531 project tests passed in 147.486 seconds. System, migration-drift, compilation and diff checks are clean. Captured Django-rendered pages were visually checked in Edge at 1440px and 390px; this is template-layout verification, not live LGU acceptance. Initial advice assembly is still open; this checkpoint does not close the High coverage finding.

## FIN-GAP-006 — Bank-advice service custody investigation

- Process/module: independent advice review, bank submission/response and returned-instrument decisions.
- Severity/status: **CRITICAL — VERIFIED** in v0.7.4. Identified during v0.7.3 source audit. Dependent functional advice coverage may continue; production remains NO-GO.
- Previous code evidence: `review_advice`, `record_advice_submission` and `record_bank_response` load a batch by primary key through `_lock_batch`, which checked version but not actor office. `_require` checked explicit permission without excluding UAT actors. Returned-instrument decision custody had the same omission.
- Expected behavior: owning Accounting-office custody for review/response and returned-item decisions, plus UAT denial at mutation boundaries. Preserve the documented Treasury bank-submission role: cross-office submission is intentional and must not be restricted to Accounting. Its existing permissioned scope requires separate review before any change.
- Cause/next step: likely implementation-level authorization defect. Reproduce foreign-office/UAT calls, add shared service custody guards, regress unchanged financial/events state and the affected complete advice/return chain. Do not advance dependent advice tasks before verification.

FIN-GAP-006 reproduction: the original `test_advice_review_rejects_foreign_office_and_uat` failed for both actors; each could approve an advice belonging to the Accounting office (`.tmp/advice-custody-reproduction.log`). The repair adds owning-office locks for Accounting review/response, current/pinned-office guards for returned-item decisions and UAT denial for advice mutations and Treasury clarification. Source action selectors and visible detail controls follow the same custody boundary. Treasury submission remains explicitly permissioned across the documented Accounting-to-Treasury boundary. Final verification: 3 focused tests passed in 5.389 seconds; all 532 project tests passed in 146.135 seconds. System, migration-drift, compilation and diff checks are clean.

### FIN-GAP-003 progress — v0.7.5

Initial advice assembly now projects eligible issued checks into stable tasks and the same scoped source-form/count selector. Returned advice stays in its correction task; instruments omitted from superseded versions can re-enter initial assembly. Shared-case advice/returned-item readiness uses exact source actions. The [stage coverage audit](FINANCE_SHARED_CASE_COVERAGE.md) maps all supported shared-case action stages to their adapters. Validation: 2 focused tests passed in 4.550 seconds; all 534 tests passed on the final source in 130.759 seconds. System, migration-drift, compilation and diff checks are clean. Edge layout verification passed at 1440px and 390px; the final 390px document scroll width is 390px.  the High finding is verified for the documented supported routes.

## FIN-GAP-007 — Remittance and filing-review custody

- Process/module: F8 remittance batch mutation and F9 linked filing-evidence review.
- Severity/status: **CRITICAL — VERIFIED**, identified while checking personal Waiting source access after v0.7.5. The dependent remittance Waiting projection can resume; production remains NO-GO.
- Code evidence: remittance `review_batch` and filing `review_evidence` check the approval permission and maker-checker identity but do not compare the actor's office with the retained remittance `finance_department_id`. Their mutation permission helpers do not exclude UAT accounts.
- Expected behavior: explicit action permission plus current owning Accounting custody for review; UAT accounts cannot mutate Treasury schedules or filing evidence even with accidentally combined permissions. Preserve authorized read/audit scope and the existing Treasury preparation/release ownership checks.
- Cause/next step: implementation-level authorization defect. Reproduce foreign-office/UAT review, apply shared permission/custody guards and matching action visibility, then verify unchanged state/events and the full remittance/filing chain before resuming dependent work.

- FIN-GAP-007 verification: the original negative batch test failed for both foreign-office and UAT approval (1 test, 2 failures, 2.970 seconds). After service and action-scope fixes, rejected review, allocation, submission and release calls preserve retained state/events, numbering and posting requests; linked filing verification and the authorized completion chains pass. Final verification: all 536 project tests passed in 132.188 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-007 is verified; production remains NO-GO pending the full functional and operational gates.

## FIN-GAP-008 - Budget transition service authority

- Process/module: Budget call/proposal, appropriation, allotment and obligation transition services; consolidation.
- Severity/status: **CRITICAL - VERIFIED** in v0.7.11, identified while tracing Budget event attribution after v0.7.9. Budget completion-history expansion may resume. The isolated Accounting history slice can finish independently; production remains NO-GO.
- Code evidence: `budget/services.py` transition entry points check lifecycle and selected maker-checker identities, but do not consistently enforce explicit action permission, owning Budget office and UAT exclusion. Obligation submission/certification has some office checks, which do not replace permission/UAT checks.
- Expected boundary: mirror the source view's action permission and owning/requesting-office authority at the service boundary; retain exact balance, immutable movement and maker-checker controls. Read scopes must not become mutation authority.
- Next step: reproduce foreign-office, missing-permission and UAT proposal approval; audit all six write entry points, add guards and meaningful financial-chain regressions. No local acceptance or regulatory conclusion is inferred.

- FIN-GAP-008 transaction evidence: all six write entry points use the default atomic decorator even though `FinanceDatabaseRouter` routes Budget models to `finance`. Add a deterministic post-movement audit-failure rollback test and move transaction ownership to the routed Finance database.

- FIN-GAP-008 reproduction: the isolated proposal-review test failed for all three actors (foreign office, missing permission and UAT). The corrected allotment audit-failure fixture then failed independently: the order remained posted at state version 3 instead of remaining for review at version 2 after the synthetic persistence failure (1 test, 1 failure, 1.931 seconds). All six services now use the routed Finance transaction and explicit action/office/UAT guards; focused and full verification are pending.

Verification: all 32 focused Budget/My Work tests passed in 11.033 seconds; all 547 project tests passed on the final source in 140.140 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-008 is verified; production remains NO-GO pending functional completion, operational scrutiny and LGU acceptance.


## FIN-GAP-009 - Finance setup UAT mutation boundary

- Process/module: Finance setup configuration preparation, approval and template management.
- Severity/status: **CRITICAL - VERIFIED**, reproduced, fixed and regressed in v0.7.16.
- Code evidence: `can_manage_finance_configuration`, `can_approve_finance_configuration` and `can_manage_finance_templates` use current department plus explicit permission without excluding `Finance UAT Viewer`. `transition_release` relies on those checks at its mutation boundary. Setup action projections already exclude UAT, so an accidental permission combination can diverge from the source service.
- Expected behavior: UAT remains read-only even when combined with setup action permissions. Preserve current explicit office authority, independent approval and existing governed exemption rules; preserve authorized preview reads.
- Next step: reproduce direct UAT submission/approval with unchanged source/audit assertions; guard shared setup mutation predicates and corresponding routes, then verify the lifecycle and broader project suite before dependent setup work. This finding does not establish that any real data was changed by a UAT account.

- FIN-GAP-009 reproduction: the original isolated UAT mutation test failed all three subcases (submission, independent approval and workbook preflight) because `PermissionDenied` was not raised (1 test, 3 failures, 1.866 seconds). No operational data was used. Audit of the shared helper family also found the same missing UAT condition in shadow management/reconciliation/cutover and discovery management/named action checks. The shared mutation repair covers those callers while leaving read predicates intact. FIN-GAP-009 is verified: all 20 focused Finance control tests passed in 3.225 seconds; all 557 project tests passed on the final source in 144.110 seconds. System, migration-drift, compilation and diff checks are clean.


## FIN-GAP-010 - Setup review lacks its advertised correction return

- Process/module: submitted Finance configuration review and pre-approval correction.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.17 for return, workbook correction and missing preflight. Broader master-data edit coverage is not implied.
- Code evidence: `SETUP_ATTENTION_SPECS["awaiting_review"]` promises an approve-or-return decision, but `transition_release` implements no return action and the release detail offers only approval for a submitted release. Template preflight also accepts draft templates only, while submission moves them to submitted.
- Expected behavior: an independent authorized reviewer can return a submitted, unapproved release with a retained reason; the preparer can make governed corrections and resubmit. Approved/active data must not be unlocked. The correction path must be usable for the affected evidence, not merely a new button.
- Next step: after FIN-GAP-009 verification, reproduce the missing return and implement/regress a bounded pre-approval return/correction flow, preserving immutable audit evidence and normal approval gates. This is a source-workflow gap, not proof of local policy acceptance.

- FIN-GAP-010 reproduction: original isolated return test failed with `Unsupported finance release action` (1 test, 1 error, 1.560 seconds). The bounded return/workbook-correction repair is implemented. FIN-GAP-010 is verified for the bounded return/workbook-correction flow: all 24 focused Finance tests passed in 3.942 seconds; all 561 project tests passed in 143.087 seconds. System, migration-drift, compilation and diff checks are clean. Synthetic review/correction layout checks cover desktop and 320px, with corrected narrow forms and wrapping draft actions.


## FIN-GAP-011 - Setup review queue omits authorized exemption actions

- Process/module: setup review queue and personal Waiting exclusion.
- Severity/status: **MEDIUM - VERIFIED**, identified, corrected and regressed in v0.7.18.
- Code evidence: the prior setup `awaiting_review` selector excluded every preparer/submitter; `transition_release` permits their approval when explicit office permission and an active administrator-authorized self-approval exemption both apply. Using the old queue to exclude Waiting would mislabel such a record as someone else's handoff.
- Repair: the selector includes those existing authorized actions; the personal task explains the exemption and keeps independent return separate. No exemption or permission is granted by this change.
- Verification: tests cover future/inactive/active exemptions, source approval parity, personal scope and action exclusion before the display cap. Four focused tests and all 564 project tests passed. This is projection drift, not an unauthorized source mutation.


## FIN-GAP-012 - Signature return trusts caller-supplied task state

- Process/module: recorded wet-signature custody and immutable return attribution.
- Severity/status: **CRITICAL - OPEN**, identified 2026-09-08 during the downstream case-action audit. Signature projection expansion is blocked until reproduction, remediation and verification. The independent payable checkpoint may finish.
- Code evidence: `record_signature_return` locks/reloads the case but validates `task.case_id`, `task.status`, round and sequence from the supplied model instance before saving that instance by its primary key. A stale or altered instance may therefore diverge from the locked case's stored task.
- Expected behavior: re-fetch and lock the stored task within the authorized case before checking pending state, sequence and custody evidence. A completed return must not be overwritten, and an altered in-memory case link must not permit writing another case's task.
- Next step: reproduce stale re-recording and altered task/case linkage with unchanged-state/audit assertions, then repair and verify before dependent signature handoff work. No real misuse or operational-data mutation is asserted.
