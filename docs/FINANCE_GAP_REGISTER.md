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
- Severity/status: **CRITICAL - VERIFIED**, reproduced and repaired in v0.7.22.
- Code evidence: `record_signature_return` locks/reloads the case but validates `task.case_id`, `task.status`, round and sequence from the supplied model instance before saving that instance by its primary key. A stale or altered instance may therefore diverge from the locked case's stored task.
- Expected behavior: re-fetch and lock the stored task within the authorized case before checking pending state, sequence and custody evidence. A completed return must not be overwritten, and an altered in-memory case link must not permit writing another case's task.
- Next step: reproduce stale re-recording and altered task/case linkage with unchanged-state/audit assertions, then repair and verify before dependent signature handoff work. No real misuse or operational-data mutation is asserted.

- FIN-GAP-012 reproduction: the original isolated tests accepted stale pending state, altered case linkage and altered sequence instead of raising the workflow error. In the same five-test run, combined UAT/signature permission was also accepted; normal ordered/idempotent recording passed (5 tests, 4 failures, 0.068 seconds). The supplied object is now reloaded and locked by stored primary key within the authorized case. FIN-GAP-012/013 are verified: all five focused boundary tests passed in 0.070 seconds; all 577 project tests passed in 162.985 seconds. System, migration-drift, compilation and diff checks are clean.

## FIN-GAP-013 - Shared voucher mutation helper lacks UAT exclusion

- Process/module: voucher service mutation authority, including signature recording.
- Severity/status: **CRITICAL - VERIFIED**, reproduced and repaired in v0.7.22 while closing FIN-GAP-012.
- Code evidence: `vouchers.services._require` checks raw explicit permission without UAT exclusion. Its callers are voucher service mutations, including case preparation, payable handoffs, DV/validation, payment, custody and generated case outputs. Read predicates are separate. The original combined-permission signature test completed instead of raising `PermissionDenied`.
- Repair: exclude UAT at this shared mutation guard while preserving current explicit permission, office checks, normal governed exemptions and read-only workbench predicates. Other modules' separate guards are not changed by this helper repair.
- Verification: isolated reproduction is part of the five-test signature boundary run (4 failures total); five focused tests and all 577 project tests passed. No real misuse or operational-data mutation is asserted.


## FIN-GAP-014 - Controlled signature queue omits the packet-presence gate

- Process/module: source signature action selector and My Work action parity.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.23.
- Code evidence: `dv_signature_task_queryset` accepts a matching awaiting-signatures print job without requiring the case's TracePoint item. `record_signature_return` requires both the matching job and a linked TracePoint item for controlled templates. The existing selector fixture likewise marks a job ready without linking an item.
- Expected behavior: controlled signature tasks become actionable only with the source-required packet link; preserve the existing non-controlled/legacy source rules. Waiting exclusion must not rely on an action that the source rejects for missing custody evidence.
- Next step: after FIN-GAP-012/013 verification, reproduce the queue/source mismatch, correct the shared selector, and regress packet gating and parent-case action exclusion before expanding signature Waiting. The source already rejects the missing-packet mutation; this finding concerns misleading action readiness.

- FIN-GAP-014 reproduction: the source rejected the missing TracePoint packet while the selector still returned an actionable task (1 test, 1 failure, 2.110 seconds). The controlled selector now requires both the matching print job and the linked TracePoint item. Verification: all nine focused DV tests passed in 3.594 seconds; all 579 project tests passed in 260.708 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-014 is verified.


## FIN-GAP-015 - Cash-service mutation guard appears to omit UAT exclusion

- Process/module: Treasury cash policy/position mutations and instrument-exception service entry points.
- Severity/status: **CRITICAL - VERIFIED**, reproduced and repaired in v0.7.32.
- Code evidence: vouchers.cash_positions._require checks raw explicit permission without the UAT exclusion used by cash task selectors. Policy creation/submission/decision, position creation/submission/decision and exception entry points use it. Cash policy create views also check raw permission before calling the service.
- Expected behavior: a Finance UAT Viewer with combined operational permissions cannot mutate cash controls or exception evidence. Preserve legitimate cross-office cash approval and separate existing read/export authority.
- Next step: reproduce accepted UAT mutations against isolated fixtures, then repair the service boundary and regress normal source flows before expanding cash projections. No real operational misuse is asserted.

- FIN-GAP-015 reproduction: both isolated policy submission/approval denial tests failed (2 tests, 1.762 seconds). Shared mutation guard and page controls repaired in v0.7.32; all 597 project tests passed in 424.974 seconds. Export retains its separate explicit read permission.

## FIN-GAP-016 - Cash custody checks precede stored-record reload

- Process/module: cash policy submission, position creation/submission, manual instrument-exception resolution and policy-specific export.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.33.
- Code evidence: submit_policy, create_position and submit_position call _require_preparer_scope on caller-supplied objects before their select_for_update reload. resolve_instrument_exception likewise checks caller-supplied policy ownership before loading the stored exception. Policy-specific export also compares the supplied policy owner before querying stored data.
- Expected behavior: owning-office authority must be checked on locked persisted records, regardless of altered or stale caller attributes. Preserve explicitly authorized independent cross-office approvals.
- Next step: reproduce with isolated foreign-office records and altered in-memory ownership, then repair and verify before cash projections. No operational misuse is asserted.

- FIN-GAP-016 reproduction: altered in-memory ownership permitted another office's policy submission (1 failed denial test, 1.818 seconds). Four mutation boundaries and policy export now check stored ownership; all 599 project tests passed in 370.798 seconds.

## FIN-GAP-017 - Review Finance reporting UAT mutation authority

- Process/module: Finance manual report generation and run review/approval/supersession.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.35.
- Code evidence: reporting.access._authorized does not distinguish the Finance UAT Viewer role; reporting.services.transition_run uses can_review_reports/can_approve_reports. create_manual_run relies on callers for action authority. Reporting also serves non-Finance domains, so the correct boundary needs domain-aware verification.
- Expected behavior: Finance preview access cannot become Finance report mutation authority through combined grants. Preserve separately governed non-Finance reporting roles, read/download permissions and trusted scheduled execution.
- Next step: reproduce against a Finance report fixture before the reporting personal-handoff phase, audit generation and review callers, and document the domain boundary before repair. No production misuse is asserted.

- FIN-GAP-017 reproduction: both UAT generation and department-head review succeeded (2 failed denial tests, 1.137 seconds). Finance run service/selector/page repair implemented in v0.7.35; all 606 project tests passed in 217.869 seconds. Non-Finance operations and trusted scheduled generation retain their existing policy.

## FIN-GAP-018 - Audit related Finance reporting governance authority

- Process/module: Finance report definition/template/schedule mutations, statement/control mappings and notes, reference comparisons, accountability packages and local form acceptance.
- Severity/status: **HIGH - VERIFIED**, repaired across v0.7.36–38.
- Code evidence: shared reporting permission helpers do not exclude Finance UAT Viewer membership. Statement, accountability, form-acceptance and template-promotion services also omit their own action/office checks in inspected entry points. Definition/template views use permission helpers directly; schedule creation remains to audit.
- Expected behavior: financial governance services must enforce action authority and current stored owning-office custody, including UAT exclusion, independently of their HTTP callers. Preserve existing non-Finance reporting roles, explicit read/export authority and authorized automated execution.
- Next step: inspect each source entry point, reproduce representative financial governance mutations, and apply domain-aware checks before expanding dependent reporting handoffs. Findings here are not yet all reproduced.

- FIN-GAP-018 statement slice: UAT/head, foreign-office and ungranted note review all succeeded (3 failed denial tests, 1.397 seconds). Seven statement service entry points and corresponding source mutation controls repaired in v0.7.36; all 28 focused tests and 612 project tests passed. Accountability, local-form and template/schedule boundaries remain OPEN; this partial repair does not close the parent finding.

- FIN-GAP-018 package/form slice: UAT profile review, foreign-office profile review and UAT local-form return succeeded (3 failed denial tests, 2.699 seconds). Eight accountability and six local-form service entry points plus page controls repaired in v0.7.37; all 31 focused tests and 622 project tests passed. Template/definition/schedule governance remains OPEN.


- FIN-GAP-018 template/configuration slice: foreign-office promotion review, UAT template approval, UAT definition editing and UAT schedule creation all succeeded before repair (4 failed denial tests, 2.415 seconds). Stored template/promotion services and definition/schedule forms now enforce current office/action authority; Finance sources exclude UAT while non-Finance roles remain supported. All 65 focused reporting tests passed in 8.300 seconds. All 629 project tests passed in 187.484 seconds. FIN-GAP-018 is verified across its three implementation slices.

## FIN-GAP-019 - Report generation trusts caller-supplied evidence context

- Process/module: manual report template snapshots, generation entry state and scheduled execution context.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.39.
- Code evidence: create_manual_run reloads the definition but uses supplied template fields for readiness and retained snapshots. generate_report checks supplied run status and related objects without a stored reload. execute_schedule likewise consumes supplied schedule relations and parameters.
- Expected behavior: persisted source identity, template evidence and run lifecycle must govern generation. An altered in-memory object must not change approved template evidence or regenerate an already retained output. Preserve trusted scheduled execution and failed-run recovery.
- Next step: reproduce on isolated fixtures, then repair the confirmed boundaries before reporting handoff adapters. No operational misuse is asserted.


- FIN-GAP-019 reproduction: unsaved manual and scheduled template titles were pinned into generated evidence (2 assertion failures), and a forged failed status entered the dataset builder for an already generated run (1 error from the intentionally empty mocked builder), in 1.130 seconds. Repair reloads the manual template, serializes generation on stored run state, and reloads/locks schedule configuration and advancement. Failed-attempt evidence remains committed before the exception is propagated; inactive stored schedules reject execution. All 69 focused reporting tests passed in 8.257 seconds; all 633 project tests passed in 191.264 seconds. System, migration-drift, compilation and diff checks passed.


## FIN-GAP-020 - Named field-operation assignments omit operational-actor exclusion

- Process/module: readiness exercise submission/witness review, assigned defect resolution and named stakeholder acceptance.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.42.
- Code evidence: cutover_services.submit_cutover_readiness_exercise, review_cutover_readiness_exercise, submit_shadow_defect_resolution and decide_stakeholder_acceptance reload records but authorize by assigned account id without the active/non-UAT gate used by ordinary Finance action helpers. The field task selectors already exclude UAT, so source and queue authority may differ.
- Expected behavior: named assignments preserve their legitimate cross-office access, but cannot authorize mutation by an inactive or UAT account. Keep assigned read/export access separate.
- Next step: reproduce isolated assigned-actor mutations, then repair source/service/queue controls before adding field personal projections. No operational misuse is asserted.


- FIN-GAP-020 reproduction: UAT assigned-owner exercise submission and assigned-witness return both succeeded (2 failed denial tests, 1.980 seconds). Four named-assignment service boundaries now require an authenticated active non-UAT assigned actor; the existing authorized manager alternative for defect correction remains intact. Page controls and task role selection share the exclusion. All 52 focused field/My Work tests passed in 25.593 seconds; all 644 project tests passed in 196.190 seconds. System, migration-drift, compilation and diff checks passed.


## FIN-GAP-021 - Local-form action queues omit completion and retain locked witness work

- Process/module: local-form source action selector and My Work readiness.
- Severity/status: **MEDIUM - VERIFIED**, reproduced and repaired in v0.7.46.
- Code evidence: witness_tests selects any form with an unreviewed test, although review_test_attempt rejects non-editable forms. A reasoned newer attempt may supersede an older unreviewed test before form submission. Existing preparation actions cover mapping/reference/candidate/returned work but not a fully ready draft's submission.
- Expected behavior: witness work must respect the source form's editable gate, and a valid fully tested draft must expose its existing submission step. Preserve test lineage, independent witness/acceptance and current source validation.
- Closure: shared selectors and local-form handoffs verified in v0.7.46. No unauthorized source mutation was asserted.


- FIN-GAP-021 reproduction: the fully tested draft had no submission task, and a locked form with an older unreviewed attempt still appeared in the witness queue (2 failed assertions, 1.267 seconds). Shared witness selection now requires current attempts on editable forms. Preparation validation distinguishes actual preparer work from only pending witnesses; new preparation/submission actions use the unchanged source validation result. All 26 focused local-form tests passed in 26.042 seconds; all 200 reporting/My Work/operations dependency tests passed in 183.489 seconds. System, migration-drift, compilation and diff checks passed.


## FIN-GAP-022 - Field evidence drift blocks the instructed return path

- Process/module: reconciliation/readiness/qualification plan review, qualification evidence, exercise/run and cycle review.
- Severity/status: **MEDIUM - VERIFIED**, reproduced and repaired in v0.7.47.
- Code evidence: checksum comparisons in cutover_services reject both positive acceptance and negative return, even where the error instructs the reviewer to return altered evidence. The normal model guards prevent ordinary edits of submitted controls; this concerns recovery from detected drift, not permission to edit submitted evidence.
- Expected behavior: preserve the acceptance block, independent reviewer, current-office or assigned authority, and required reason. A governed return should retain the original submission and the observed integrity difference rather than silently relabeling changed evidence as valid.
- Closure: traced negative decisions and full regression verified in v0.7.47; remaining personal adapters continue separately.


- FIN-GAP-022 reproduction: one isolated seven-path test produced seven blocked-return errors in 2.738 seconds, after separately verifying positive acceptance denial, outsider/self-review denial and required reasons. The repair retains stored/observed checksums and mismatch status in the new decision audit without rewriting earlier events. All 112 focused field/My Work tests passed in 65.532 seconds; all 657 project tests passed in 239.539 seconds. System, migration-drift, compilation and diff checks passed.


## FIN-GAP-023 - Qualification evidence has submission and return but no reference-correction route

- Process/module: draft/returned qualifying-cycle evidence on the field acceptance screen.
- Severity/status: **MEDIUM - VERIFIED**, reproduced and repaired in v0.7.49.
- Code evidence: cutover_qualification_evidence_create always constructs a new record. Existing draft/returned rows expose only submission; the form has editable execution/rules references, but there is no existing-record correction route. The unique plan/cycle and plan/sequence constraints prevent replacing an existing row with an identical new one.
- Expected behavior: a preparer should correct draft/returned evidence references under the owning plan's office and existing state gates, with retained correction attribution. Submitted/accepted evidence remains locked and qualifying-cycle lineage must not be silently replaced.
- Closure: reference-correction service, authenticated route and full regression verified in v0.7.49. Real cycle reruns remain separate from reference correction; personal qualification-evidence projections continue next.


- FIN-GAP-023 reproduction: both draft and returned evidence lacked the correction link (2 failed assertions in 3.552 seconds). A reference-only correction form/service now reloads stored identity, locks and validates state/office authority, requires a reason, and atomically retains before/after audit evidence. All 46 focused field tests passed in 38.724 seconds; all 662 project tests passed in 273.285 seconds. System, migration-drift, compilation and diff checks passed.


## FIN-GAP-024 - Non-financial DV amendment lacks a stored office boundary

- Process/module: reasoned DV date/signatory amendment before payment-instrument issuance.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.51.
- Code evidence: amend_nonfinancial_voucher reloads the case and checks an explicit permission, stage and payment cutoff, but does not bind the actor's office to the stored case. The source button likewise checks permission/stage. Existing tests deliberately allow the owning Accounting preparer to amend after the case reaches Treasury.
- Expected behavior: preserve legitimate owning-Accounting amendment and unchanged financial/posting evidence, while preventing an unrelated office with the same generic grant from amending another office's DV. Do not substitute a current-custody-only check that breaks the established Accounting workflow.
- Closure: stored pinned-owner service/page boundaries and full regression verified in v0.7.51, preserving owning-Accounting amendment after Treasury handoff.


- FIN-GAP-024 reproduction: unrelated-office mutation succeeded and the current Treasury custodian saw the amendment control when given the generic grant (2 failed denial assertions, 3.461 seconds). Shared authority now binds the acting office to the stored pinned Finance release, preserving owning Accounting access across custody stages. All 69 focused voucher-workflow tests passed in 42.735 seconds; all 668 project tests passed in 272.103 seconds. System, migration-drift, compilation and diff checks passed.


## FIN-GAP-025 - Controlled reprint may lose pending amendment signature lineage

- Process/module: replacing a printed signing copy while a non-financial amendment awaits signatures.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.52.
- Code evidence: prepare_controlled_dv_print starts a new signature round from the current active release signatories when replacing printed/circulating copies. record_signature_return completes an amendment only when its immutable original round equals the returned task round. A reprint can therefore lose the amendment's selected signatories or leave its original amendment pending after replacement signatures finish.
- Expected behavior: replacing damaged paper must preserve the governed signatory/custody snapshots and follow retained print-supersession lineage back to the pending amendment, without rewriting the immutable original amendment or treating old signed copies as current.
- Closure: selected signature/custody and generated output snapshots are preserved; repeated reprints complete through retained lineage. Broken lineage refuses final advancement.


- FIN-GAP-025 reproduction: the replacement round added an unselected old department head, and a completed replacement signature round left the amendment pending (2 failed assertions, 3.120 seconds). Replacement rounds now copy retained signatory/custody snapshots; final amendment completion resolves the same-case, descending-version print lineage to the original immutable round. All 76 focused voucher/signature tests passed in 43.931 seconds. All 670 project tests passed in 272.577 seconds. System, migration-drift, compilation and diff checks passed.

## FIN-GAP-026 - DV return correction may retain an obsolete signing copy or pending amendment

- Process/module: returning a DV from wet signatures or validation to preparation, then preparing its correction.
- Severity/status: **HIGH - VERIFIED**, reproduced and repaired in v0.7.53.
- Code evidence: return_case declines pending tasks but does not supersede existing controlled print jobs or resolve a pending non-financial amendment. prepare_voucher creates a fresh round, while the old print job can remain active. A later reprint may follow the obsolete round, and a pending amendment may retain a resume stage that is no longer appropriate for a material correction.
- Expected behavior: a reasoned financial/document correction must invalidate obsolete signing-copy authority while retaining the old files and signature evidence. Its new review round must follow the corrected DV, and must not inherit the prior amendment's shortcut to a later stage.
- Closure: obsolete signing authority and interrupted amendments are explicitly superseded, with original evidence and affected identities retained. Fresh correction and renewed-signature flows verified.

- Reproduction: both assertions failed in 3.056 seconds. The reasoned return left the old signing job ready to print and the interrupted amendment awaiting signatures. Repair introduces explicit pending-amendment supersession, invalidates obsolete signing jobs/outputs, and records affected identities in the return event. All 80 focused voucher/signature tests passed in 43.644 seconds. All 674 project tests passed in 304.236 seconds. System, migration-drift, compilation and diff checks passed.

## FIN-GAP-027 - Voucher detail offers self-validation excluded from the real action queue

- Process/module: DV source detail action form and next-task banner.
- Severity/status: **MEDIUM - VERIFIED**, reproduced and repaired in v0.7.55.
- Evidence: the isolated accounting.preparer account sees a validation form and a next-task banner on its own corrected DV. The same case correctly appears in personal Waiting. case_detail derives validation permission and its banner from generic permission/stage checks; accounting_validation_action_queryset additionally enforces current custody and preparer exclusion, honoring governed exceptions. validate_accounting independently checks the source controls and self-validation exception.
- Expected behavior: the source page should use the existing source-action selector so it does not invite a blocked self-review or a wrong-office review. Preserve legitimate independent reviewers and separately governed self-validation exceptions.
- Closure: source-page validation and main-step visibility share the existing action selector; authorized exceptions remain. Source notices, template label, evidence-table scrolling and reason-field sizing verified in the isolated browser.

- Reproduction: one source-page test produced two failed assertions in 3.190 seconds: the unapproved preparer saw both the validation form and the next-task banner. The page now uses accounting_validation_action_queryset; All 77 focused voucher tests passed in 46.346 seconds. All 84 My Work/operations/signature dependency tests passed in 56.615 seconds. System, migration-drift, compilation and diff checks passed. Scoped source-page styles also address white-on-pale notices, raw template labeling, uncontained evidence tables and fixed-width reason textareas found in the isolated browser.

## FIN-GAP-028 - Voucher return form lists routes unavailable from the current stage

- Process/module: reasoned voucher return form.
- Severity/status: **MEDIUM - OPEN**, browser/source finding awaiting reproduction.
- Evidence: at Accounting validation the source form defaults to Requesting-office payable preparation, while return_case permits only Accounting preparation or renewed signatures from that stage. ReturnCaseForm defines a static destination list rather than consuming the service's stage map. The source service rejects unsupported destinations; the form still invites a predictable failed submission.
- Expected behavior: source return controls should offer current permitted destinations, respect current-office authority and disclose retained-posting restrictions. Preserve the reason, state-version/idempotency and posted-JEV correction boundaries.
- Next step: reproduce source form/return-service parity, then reuse an explicit shared return-route contract without weakening source mutation checks. Complete this before detailed DV history projections.
