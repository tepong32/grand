# Finance work-attention foundation

For a compact current view of implemented and remaining personal handoffs, see [the coverage table](FINANCE_WORK_VIEW_COVERAGE.md).

Status: F1.5 source-task adapters and the supported shared-case stage coverage audit are implemented; cross-cycle view coverage remains in progress; bounded, explicitly permissioned task export is implemented. `/finance/my-work/` provides a live, permission-filtered overview of supported Finance setup/discovery/field operation, Budget, shared voucher, Accounting, bank reconciliation, bank-advice, returned-payment, Treasury remittance, cash-policy, cash-position, period-close/reopen, Reporting, and local-form action groups. Finance Setup releases, discovery decisions, Budget proposal versions/allotment orders/obligation requests, payable-intake preparation/review, DV preparation and controlled print/custody/signature actions, independent Accounting validation, JEV preparation/posting, Treasury check preparation and individual instrument release, bank-reconciliation staging/correction/matching/review, period-close preparation/review/reopen decisions, bank-advice and returned-payment actions, Treasury remittance and cash-policy/position actions, report generation/reconciliation/review/approval, Field-operation cycle gates and named nested actions, and Local-form actions expose stable read-only work items over their existing governed records. Any further count-only domain must still pass an explicit adapter audit.

## What the page does

- Shows only action groups backed by a permission the current account actually holds.
- Applies the current department, requesting-office, central-register, or own-report scope before a count is calculated.
- Gives every count a plain definition, scope statement, generated time, and an **Open exact queue** link.
- Splits lifecycle states when one existing filter cannot reproduce a combined count—for example opening preparation versus ready-to-submit, and draft versus failed report runs.
- Uses the existing Voucher Workbench visibility and stage rules, including requesting-office isolation.
- Excludes Finance UAT preview stages from personal-action totals.
- Leaves zero-count groups visible so staff can distinguish “nothing waiting” from “no permission.”

The total is only the sum of the visible supported groups. It is not a count of every possible Finance responsibility, and overlapping duties may intentionally produce separate action rows for the same source area.

## Supported exact drill-downs

The first adapter set covers:

- Finance configuration releases needing preparation, independent review, future scheduling, or due activation;
- discovery decisions the signed-in owner/manager may prepare and submitted decisions the named independent reviewer may decide, without treating oversight-only blocker/overdue views as assignments;
- field cycles needing source locks, preparation, execution, or independent reconciliation; cycles containing named defect correction/review, readiness owner/witness, stakeholder-decision, or cutover-authority work; reconciled/authorized/returned cycle views remain oversight only;
- Budget proposal preparation/review, allotment preparation/review, requesting-office obligation preparation where that is the account's sole obligation scope, and Budget certification;
- requesting-office payable preparation/correction and independent Accounting payable review, constrained to the current acting office and excluding the preparer/submitter from review;
- Accounting DV preparation, controlled signing-copy creation, physical-print recording, counted packet/TracePoint assembly, and only the earliest eligible wet-signature return in the current round;
- independent Accounting validation of the signed/current DV packet and exact JEV draft preparation, returned correction, and posting actions;
- Treasury check preparation with exact remaining-net guidance, followed by one release task for each advised physical instrument;
- Treasury remittance preparation/returned correction/independent review/release and cash-policy/cash-position preparation/review;
- shared voucher cases whose current stage matches a held action permission;
- Accounting JEV draft/posting, opening-balance preparation/submission/review/post/reconcile, bank-statement staging/correction/matching/review, and period-close preparation/review/reopen decision;
- role-scoped bank-advice preparation/correction, independent review, approved bank submission, and submitted bank-response recording;
- returned-payment review versions awaiting an Accounting decision, Treasury clarification, or Accounting-cleared controlled replacement;
- Treasury cash-policy preparation/correction and independent review, kept separate from cash-position preparation/correction and independent review;
- Treasury remittance draft, returned, review, and release states;
- own-run or department-visible Reporting generation, failed rerun, control-blocked successor, independent-review, and approval actions with creator exclusion; and
- local-form mapping/reference/section preparation, returned correction, independent practical-test witnessing, and independent acceptance review; accepted/superseded form views remain oversight only.

The source workspace remains authoritative after the handoff. Its own permission, maker–checker, state-version, locking, correction, export, and audit controls still apply.

## Current item-level contract

For Finance Setup releases, discovery decisions, Budget proposal versions/allotment orders/obligation requests, payable-intake preparation/review, DV/custody/signature work, Accounting validation/JEV work, Treasury check preparation/instrument release, bank reconciliation, period close/reopen, bank-advice/returned-payment work, Treasury remittance and cash-policy/position work, report generation/reconciliation/review/approval, Field-operation cycle gates, named defects, readiness exercises, stakeholder/cutover decisions, and Local forms, each visible item now carries:

- a deterministic `finwork:v1:<source-kind>:<source-id>:<action>` Task ID and a controlled versioned task type;
- a stable case/source ID, recognizable reference, safe subject, transaction kind, and authoritative source/action link (or the containing cycle evidence for inline review decisions);
- the exact plain-language action and source-query gate;
- the permitted role queue and office/scope statement, without claiming that the item has been assigned;
- received age plus either the retained field-cycle plan date or an explicit statement that no structured target is available;
- ready/returned presentation state, authoritative source state and source version token; and
- a safe exception summary for the exact missing or returned gate where applicable.

One source may correctly produce more than one Task ID when it requires separate actions. Rebuilding the page does not change those IDs or write task, source, ownership, approval, signature, print, custody, or completion state. Setup and discovery projections retain the exact preparation/review/effectivity and owner/named-reviewer filters used by their source registers; a release creator or submitter is excluded from independent review. Budget projections likewise exclude a proposal, allotment, or obligation submitter from the corresponding independent review queue, preserve requesting-office visibility, display the actual Budget-call proposal due date, and flag a non-zero allotment or obligation control difference before posting. Payable projections preserve requesting/current-office scope, exclude the payable preparer/submitter from independent Accounting review, and surface obligation-link, claim-to-allocation, pending-document, duplicate-review, returned-correction, and missing-intake exceptions without copying protected source content. DV/custody projections require the acting Accounting office, preserve the Budget-certifier separation rule unless a current named exemption exists, keep file preparation, actual printing, packet assembly, and wet-signature receipt distinct, and expose only the earliest pending signature after any mandatory controlled packet is assembled. A gross-minus-deductions-to-net difference or mismatch with the certified obligation is shown as a stop-and-repair exception. Stable Task IDs are paired with deterministic projection checksums that change with relevant mutable evidence, active allocations, voucher controls, print/custody evidence, signature state, or template lock. No payable, DV/custody, or signature deadline is inferred when the source has none. Allotment effectivity and obligation dates remain source transaction/control dates rather than invented action deadlines. Exact effectivity or local review targets are displayed when stored, but are not recast as statutory approval deadlines. Every actionable named defect, exercise, stakeholder acceptance, and cutover decision receives an opaque deterministic identity derived from its actual retained source row; GRAND does not mislabel the parent cycle as that child task. Mutable pending stakeholder evidence also receives a deterministic projection checksum, so its Task ID stays stable while the displayed revision changes when governed source fields change. The page limits its rendered item table to 100 deterministic rows and directs users to the exact source queues for the complete register.

The shared voucher attention group counts cases at every currently actionable voucher stage held by the account. The exact table counts actions: payable preparation/review, current DV/custody/signature actions, Accounting validation, and Treasury payment actions. One awaiting-signatures case can expose one current print/custody action or one ordered signature action; one Treasury-release case can expose several physical-instrument tasks, while the shared group still counts each case once. These totals are intentionally not compared as if they measure the same level when a user holds several duties. Shared rows use the same current-office, UAT, payable maker-checker, DV Budget-certifier, and Treasury custody controls.

Accounting-validation projections independently recheck the current signed packet, exact gross-minus-deductions-to-net equation, certified obligation, allocation total, payable recognition route, and governed posting rule. JEV projections expose draft/returned preparation and submitted posting separately, exclude the creator or submitter from posting without a current named exemption, preserve returned reasons, and stop on fewer than two lines, non-positive totals, any debit-credit difference, or a closed period. Their stable Task IDs use evidence-sensitive revisions over the relevant voucher, allocation, packet, journal, subsidiary, source-snapshot, and return evidence. Voucher and journal dates remain transaction/control dates rather than invented action deadlines.

Treasury payment projections reuse the current-office and permission-scoped Voucher source query. Check preparation displays the exact remaining DV net and changes to advice handoff guidance only when eligible issued checks equal net. It blocks an over-issued total, gross-deduction-net or obligation mismatch, inactive pinned bank account, or mixed-bank pilot advice. Release is one Task ID per advised instrument and stops when the current advice is not bank-acknowledged, a stale/returned exception is open, the active-instrument total exceeds net, or no currently effective claimant exists. Direct issue, advice handoff/preparation, release, cancellation, and return services independently enforce current-office custody; issue rejects non-finite, non-positive, sub-cent, blank, and unconfigured bank/check inputs, while release re-locks the instrument and claimant and requires an actual receipt reference. Transaction and acknowledgement dates are not recast as deadlines.

Bank-reconciliation projections share the exact permission-, Accounting-office-, lifecycle-, maker-checker-, and UAT-aware action query used by the source workspace, attention count, and synchronized register export. Statement staging, control correction, returned correction, matching/exception resolution, and independent close review remain separate Task IDs. Each evidence-sensitive revision rechecks retained source and row controls, exact deposit/withdrawal/closing equations, running balances, validation summary, match and timing-item checksums, live snapshots, unmatched rows, unclassified ledger lines, and the exact bank-to-book difference. Close review additionally requires the current zero-difference snapshot to reproduce the retained submission checksum. Direct services recheck current-office custody, deny both return and approval by the creator/submitter, and suppress Finance UAT preparation/review even if an action permission is accidentally combined with that role. Statement period, receipt, and expected-clearance dates remain evidence dates rather than inferred deadlines.

Period-close projections share the exact permission-, Accounting-office-, lifecycle-, maker-checker-, and UAT-aware action query used by the source workspace, attention count, and synchronized register export. Checklist preparation/returned correction, independent close review, and controlled-reopen decision remain separate Task IDs. Each evidence-sensitive revision rechecks the pinned and current policy, retained and current checklist, required close gates, exact trial-balance difference, submission event checksum, return reason, reopen authority/event evidence, and later-closed-period chronology. Direct services recheck current-office custody, exclude the preparer/submitter from both close decisions, exclude the reopen requester from that decision, and suppress Finance UAT actions even with accidental permission combinations. Period dates and event times remain evidence rather than inferred deadlines.

Bank-advice projections share the exact action query used by the source workspace, attention count, and visible-evidence export. Draft and returned correction, independent review, bank submission, and bank-response recording stay distinct; independent review excludes the preparer and submitter, current-office scope is preserved, and Finance UAT preview accounts receive no action. The projection rechecks item count, exact centavo total, retained item checksum, current instrument state, advice status, and pending authority before the next step. Returned-payment projections separately expose Accounting decision, Treasury clarification, and Accounting-cleared replacement. They retain the operational-exception lineage and notes and stop on stale instrument/advice evidence, incomplete or altered original posting evidence, non-zero exact amount differences, missing reversal setup, duplicate replacement, or altered replacement posting evidence. Bank, transaction, acknowledgement, and return dates are evidence dates rather than inferred deadlines.

Remittance projections now share their exact source-register filters: preparation, correction, and release stay within the owning Treasury office; independent review may span permitted Finance offices but excludes the creator and submitter; UAT preview accounts receive no action. Each projection compares active immutable line versions with the batch total, current posted-liability availability, effective configured fund/bank/agency/variant, and the pinned posting-rule checksum before review or release. Cash projections keep policy and position actions separate, show the exact `book + inflows - outflows - holds - reserve = available cash` equation, and expose missing/stale/tampered reconciliation evidence as a stop. Submitted, returned, active, or approved cash evidence cannot be edited in place; a reasoned successor replaces a returned item in the preparation queue while retaining the prior version.

Reporting projections now share the exact source-register action filters and keep draft generation, failed rerun, control-blocked correction, independent review, and approval distinct. Review and approval exclude the creator and re-lock the current department-scoped run before recomputing dataset/row, source/count, control, reproduction, and actual output-file SHA-256 evidence. A control difference, missing file, stale count, or checksum mismatch is a blocking exception. Generated evidence cannot be rewritten through an ordinary save; corrections stay in the governed source or mapping and produce a retained successor report.

## Deliberately deferred adapters

Accounting validation, JEV preparation/posting, Treasury check preparation/release, bank reconciliation, period close/reopen, bank advice/returned payment, remittance, cash policy/position, and Reporting actions now use shared permission-, office/department-, maker-checker-, and UAT-aware source filters in My Work and their source queues.

Any further count-only group must gain a shared filter reproducing the same work item, role scope, and state before its task adapter is added. Local-form preparation, test witnessing, and acceptance review remain separate from accepted/superseded oversight, and a user never receives independent work for that user's own test or submitted form. A field attention-group count means visible cycles containing the named action; the exact-item table separately counts the actual nested defects, exercises, or decisions, so those totals must not be compared as though they measure the same level. Field personal actions remain distinct from oversight; setup states remain effectivity-aware; discovery owner/reviewer actions remain separate from oversight; returned-payment actions separate Accounting decision, Treasury clarification, and controlled replacement; and cash policy and position versions stay distinct. Omitting any still-unsupported number is safer than showing a plausible count that opens a different list.

The broader F1 My Work contract remains open. Ready, personal Waiting, Returned, retained-date views, Accounting/Budget completion history and the separately authorized bounded portable export are implemented for their documented coverage. Later rollbackable slices must extend Waiting and completion to remaining supported domains and define assignment/following rules and governed shared views. Notifications must remain signals over that same source contract, never a parallel queue.

## Internal How-To

`seed_internal_howtos` now publishes a versioned guide selected by department kind:

- requesting offices learn office-isolated shared-case triage and the pre-DV/check modification boundary;
- Budget users learn proposal/allotment/obligation authority boundaries;
- Accounting users learn setup/discovery/field-operation/payable/DV/controlled-custody/signature/JEV/opening/bank/close/advice/returned-payment/cash/reporting/local-form handoffs;
- named field participants learn to open only defect, exercise, witness, or stakeholder rows assigned to them and to distinguish a cycle count from nested work;
- Budget, Accounting, and Treasury users learn to distinguish local-form preparation, returned correction, independent test witnessing, final acceptance review, and non-action oversight; and
- Treasury users learn voucher/advice/remittance triage, returned-payment clarification/replacement boundaries, and separate cash-policy and cash-position queues.

The floating `?` panel stays over the current page. Its checkmarks are optional private resume state, not an assignment, notification, submission, attendance record, competence rating, UAT result, or approval.

## Acceptance and authority boundary

This checkpoint does not prove that an LGU accepts the workflow, terminology, role design, local form, COA/DBM/BIR interpretation, device layout, accessibility behavior, or production deployment. Named users must still compare the displayed groups and source queues with actual local duties and retained authority. A green automated test proves the software contract exercised by that test only.

## Regression contract

Automated coverage verifies the stable route and Finance-entry link, denial for reporting-only/ordinary users, exact local-form preparation/witness/review parity, exact field lifecycle/role/object parity, setup lifecycle/effectivity and discovery owner/reviewer parity, Budget source/task/export scope and submitter exclusion, requesting-office voucher count parity, payable preparation/review source parity and maker-checker/current-office exclusion, DV current-office and Budget-certifier separation, mutually exclusive print/custody states, controlled-copy signature gating and order, amount-difference stops, Accounting-validation and JEV preparation/posting source parity, Treasury check-preparation and individual-release source parity, bank-reconciliation, period-close/reopen, and bank-advice/returned-payment source/task/export parity, one-cent balance stops, row/snapshot/event tamper stops, payment-total/bank/advice/claimant/receipt stops, service-boundary office/permission enforcement, cash-policy, cash-position, and Reporting parity with their filtered source queues, hidden-office isolation, independent review exclusions, named cross-office defect/exercise/stakeholder visibility, UAT preview exclusion, permission-shaped action choices, synchronized exports, boundary copy, and publication of page-relevant department guides. The item-contract checkpoints add deterministic-ID, separate-action, source-link, office-isolation, timing-basis, read-only, UAT-exclusion, zero-control warning, data-integrity blocker, exact nested-record, cycle-count-versus-child-count, maker–checker, projection-revision, retained-posting/checksum drift, output-file checksum, and page-rendering coverage. The 271-test Finance integration gate passed in 71.275 seconds, and the final complete gate passed all 516 project tests across both routed databases in 134.021 seconds. The preceding authenticated isolated browser pass verified five exact source-linked tasks, stacked mobile rows at 390×844, the floating nine-step guide, and zero application-route console errors; current payable, Budget, setup/discovery, nested-record, DV/custody, Accounting-validation, JEV, Treasury payment, bank reconciliation, period close/reopen, bank-advice/returned-payment, remittance, cash-control, and Reporting rendering is additionally covered by authenticated Django route and projection tests. Future task adapters must use risk-tiered verification: focused development tests, only justified dependency gates, and one complete suite on final executable source.

## 2026-09-07 opening adapter and attention audit

Opening balances now expose exact staging/returned correction, submission, independent review, posting and reconciliation tasks. A shared action selector drives workspace filters, register export, attention counts and tasks. Review/posting exclude the preparer and submitter; UAT accounts receive no opening action, and all mutation services verify current-office custody. Status-only lists remain read-only oversight for Accounting viewers. Opening/period dates are not deadlines.

Task IDs remain stable while retained source/row controls, validation/event evidence, period/year state, posting lines or return evidence change the projection checksum. Submission, approval and posting recompute exact controls and verify retained evidence. Reconciliation compares source-to-ledger classifications and line amounts as well as totals. Existing staged/validated evidence without the new checksum must be revalidated; submitted/approved evidence must be returned first. Posted legacy evidence without a checksum requires controlled investigation, not an automatic historical checksum backfill.

The count-adapter inventory is now:

| Attention domain | Exact adapter / remaining audit |
|---|---|
| Setup (4 release actions), discovery (owner/reviewer) | `_setup_tasks`, `_discovery_tasks` |
| Field (source/preparation/execution/review and 6 named actions) | `_field_operation_tasks`; cycle counts and child-action rows intentionally differ |
| Budget (proposal/allotment preparation/review and obligation preparation/certification) | `_budget_tasks` |
| Opening (5 actions) | `_opening_tasks` added in this checkpoint |
| Journal (preparation/posting) | `_journal_tasks` |
| Bank reconciliation, period close/reopen | `_bank_reconciliation_tasks`, `_period_close_tasks` |
| Advice, returned instruments, remittance, cash policy/position, reports, local forms | Respective existing exact adapters |
| Shared voucher ready count | Payable, DV/custody, validation, JEV, Treasury and returned-payment adapters exist; still audit the legacy `BUDGET_DRAFT` compatibility stage and case-to-action completeness before declaring all count-only gaps closed |

The remaining shared-case audit precedes cross-cycle Waiting/Returned/Due/Completed-by-me views and the separately authorized task export. Full post-functional operational scrutiny remains mandatory under [the completion gate](FINANCE_OPERATIONAL_SCRUTINY.md).

Checkpoint verification: 51 focused Accounting/complete-cycle replay tests passed in 10.679 seconds; 521 full-project tests passed in 136.867 seconds on final executable source. Django, migration-drift, compilation and whitespace checks passed. Browser/device and real LGU acceptance remain separate.

## v0.7.1 — legacy shadow Budget coverage

The shared-case Budget draft stage now has a stable task tied to the exact unlinked shadow case. Current office, explicit certification permission, UAT exclusion, no-existing-OBR and shadow-only guards are shared by queue and task selection; detail actions apply the same selector. Its revision covers retained case/events, setup codes, numbering and fiscal readiness. No draft allocation amount or deadline is invented. The task plainly distinguishes referenced shadow sources from authoritative appropriation/allotment availability.

Continue the shared-case audit for initial advice assembly and unmaterialized JEV handoff; current batch and journal task coverage alone cannot prove those transitions covered. Cross-cycle views remain downstream of this audit.

Final project suite: 524 tests passed across both databases in 139.139 seconds; system, migration, compilation and diff checks are clean. Five focused legacy/authoritative-chain tests passed in 5.146 seconds.

## v0.7.2 — posting-handoff prerequisite

The shared-case audit exposed FIN-GAP-005 before further task adapters. Voucher/remittance synchronization now reloads the stored JEV and verifies current-office custody, recorded posting attribution and exact posting-event totals, plus source-to-ledger identity and retained digests. UAT journal permissions are excluded at the access boundary. A successful retry returns the same verified handoff receipt without moving a later workflow stage. Remaining advice-assembly and posting-request task projections remain open; no new task coverage is claimed by this control fix.

Verification: all 528 project tests passed in 301.697 seconds, including both affected chains and negative/recovery regressions. FIN-GAP-005 is verified; continue FIN-GAP-003 source-action coverage.

## v0.7.3 — source-handoff task coverage

Voucher and remittance requests now project exact journal creation and posted-source synchronization actions with stable IDs, retained-evidence revisions and current-office detail routes. Existing drafts and independent posting stay in the journal adapter, preventing duplicate source tasks. Shared-case posting readiness matches actual source and maker-checker-aware journal actions. A missing core receipt can recover from immutable source identity; a retained link without its journal blocks creation for investigation. No JEV date is treated as a deadline. Validation: 3 focused tests passed in 4.509 seconds and all 531 project tests passed in 147.486 seconds. System, migration-drift, compilation and diff checks are clean. Captured Django-rendered pages were visually checked in Edge at 1440px and 390px; this is template-layout verification, not live LGU acceptance.  initial advice assembly remains open before cross-cycle views.

## v0.7.4 — advice custody prerequisite

FIN-GAP-006 was reproduced for foreign-office and UAT advice approval. The fix enforces the owning Accounting office for advice review/response and current/pinned office for returned-item decisions, excludes UAT mutation combinations, and aligns source task selectors/detail controls. Explicit Treasury bank submission remains authorized across its documented office boundary. Final verification: 3 focused tests passed in 5.389 seconds; all 532 project tests passed in 146.135 seconds. System, migration-drift, compilation and diff checks are clean.  initial advice assembly and cross-cycle views remain downstream.

## v0.7.5 — initial advice assembly and shared-case coverage

Initial check-to-advice work now has an exact task, source-form selection and instrument-count queue. The selector excludes active/returned advice, preserves its existing batch/correction tasks, and includes checks omitted from a superseded version. Stale and foreign UUID selections fail closed. Shared-case advice and returned-item readiness now follow their actual source selectors. See [the supported shared-case stage audit](FINANCE_SHARED_CASE_COVERAGE.md). Validation: 2 focused tests passed in 4.550 seconds; all 534 tests passed on the final source in 130.759 seconds. System, migration-drift, compilation and diff checks are clean. Edge layout verification passed at 1440px and 390px; the final 390px document scroll width is 390px.  FIN-GAP-003 is verified for these supported routes.

User-confirmed cross-cycle scope (2026-09-07): Waiting shows work the signed-in user prepared or submitted that is now with another person. It does not expand to every office-visible record, and current source-record access still applies.

## v0.7.6 — remittance and filing-review custody

Remittance and linked filing-evidence decisions require the retained owning Accounting office as well as explicit permission and independent review. UAT accounts cannot mutate remittance schedules or filing evidence. Register action selection and detail controls use the same office/UAT boundary, preserving authorized read/audit visibility and Treasury preparation/release ownership. FIN-GAP-007 was reproduced by both foreign-office and UAT batch approvals before remediation. Final verification: all 536 project tests passed in 132.188 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-007 is verified; production remains NO-GO pending the full functional and operational gates. Personal Waiting remains the next functional slice.

## v0.7.7 - personal Waiting and Returned views

My Work now offers Ready for me, personal Waiting and Returned. Waiting projects retained preparer/submission attribution for submitted JEVs, opening balances awaiting review/posting/reconciliation, submitted period-close checklists, advice awaiting review/submission/response, and remittances awaiting review/release. Each record must remain visible under its source route's current access rules; current actionable records are excluded before the display limit. UAT preview receives no personal work. Missing handoff times are disclosed rather than replaced with document dates.

Returned filters current correction tasks before truncation. Historical JEV returns no longer label a resubmitted posting task Returned. No assignments, deadline policy or source status is created. Browser QA also corrected narrow navigation overflow and wrapped long source hashes within balanced task columns. Other Waiting sources (including post-release remittance journal chains), structured target filters, attributed completion and bounded authorized export remain next. Verification: 24 focused tests passed in 24.629 seconds; all 540 project tests passed on the final source in 195.115 seconds. System, migration-drift, compilation and diff checks are clean. Edge layout checks passed at 1440px and 320px; the final 320px document scroll width is 320px.

## v0.7.8 - Budget Waiting handoffs

Extend personal Waiting to submitted Budget proposal versions, allotment orders awaiting independent review and obligation requests awaiting certification. The exact source route's read permission and current office/requesting-office scope still apply. Current actions are excluded before truncation. A preparer's office move or loss of allotment read permission removes now-inaccessible rows; Budget-call and obligation document dates are not inferred review deadlines. Verification: 4 focused tests passed in 3.041 seconds; all 541 project tests passed in 167.441 seconds. System, migration-drift, compilation and diff checks are clean.

## v0.7.9 - retained-date work views

Upcoming dates filters actionable records to an explicit 7-, 14- or 30-calendar-day window including today; Past dates selects stored dates before today. Records without a structured date remain outside both date views. Source permissions, current action eligibility, retained date meaning and counts apply before display truncation. Review targets, effectivity dates and scheduled dates stay distinguished; there is no inferred holiday, working-day or official-deadline rule. Verification: the focused calendar-boundary test passed in 1.682 seconds; all 542 project tests passed on the final source in 170.705 seconds. System, migration-drift, compilation and diff checks are clean. Edge layout checks passed at 1440px and 320px, with 320px document width at the narrow viewport.

## v0.7.10 - attributed Accounting completion history

Completed by me projects successful retained JEV submission/posting/return, opening-balance submission/decision/posting/reconciliation, and period-close/reopen events attributed to the signed-in user. Current source read access and office scope still apply. Events appear newest first with stable event-based identities, historical action descriptions and a separate current source state. Terminal status or preparer identity alone never credits completion. Generated opening JEV posting events are excluded because the batch posting is the user action. Failed events remain outside completion history. Other domain completion adapters remain pending. Verification: the focused attributed-history test passed in 2.099 seconds; all 543 project tests passed on the final source in 135.649 seconds. System, migration-drift, compilation and diff checks are clean. Synthetic rendered layout checks passed at 1440px and 320px with no horizontal overflow.

## v0.7.11 - Budget service authority prerequisite

Budget transition and consolidation services now require the exact action permission, current owning-office custody (requesting office for obligation submission), and non-UAT authority. All six service transactions use the routed Finance database so failed persistence rolls back states, snapshots and movements. Source buttons, write routes and My Work action selectors share the UAT-safe predicate while authorized read scopes remain unchanged. Existing maker-checker rules remain enforced, including actors with combined permissions. FIN-GAP-008 was reproduced for foreign-office, missing-permission and UAT proposal approval and for failed allotment-audit rollback. Verification: all 32 focused Budget/My Work tests passed in 11.033 seconds; all 547 project tests passed on the final source in 140.140 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-008 is verified; production remains NO-GO pending functional completion, operational scrutiny and LGU acceptance.

## v0.7.12 - attributed Budget completion history

Completed by me now includes attributed Budget call submission/publication/return/closure, proposal submission/review/consolidation, appropriation submission/authorization/return, allotment submission/posting/return, and obligation submission/certification/return. Each retained event must still resolve to a currently readable source and matching owning office. Appropriation events require an exact retained authority-to-version link; missing or mismatched links are omitted. Requesting-office users retain their own obligation submission history under the source read scope. Historical actions stay distinct from current source status; repeated submissions retain distinct stable event identities. Verification: both focused Budget event-history tests passed in 2.928 seconds; all 549 project tests passed on the final source in 178.424 seconds. System, migration-drift, compilation and diff checks are clean.

User-confirmed export authority (2026-09-07): administrators assign the separate My Work portable-export permission explicitly to selected users or groups. Do not add it automatically to seeded operational Finance roles. Source-record access must still be rechecked at export time.

## v0.7.13 - permissioned portable My Work export

My Work can export the current view as a bounded 100-row CSV only with the separate `finance.export_finance_work` permission. Administrators explicitly assign it to selected users or groups; no seeded operational role receives it automatically. The export rebuilds current source permissions and filters, excludes UAT, escapes spreadsheet formulas, preserves source links and revisions, and discloses eligible count and truncation. The existing portable export root retains the CSV and checksum manifest, with a matching append-only Finance audit receipt. A persistence failure prevents a successful download response. Migration 0020 adds permission metadata only; deployment must apply the migration and explicit grants. Verification: both focused export tests passed in 4.289 seconds; all 551 project tests passed on the final source in 143.952 seconds. System, migration-drift, compilation and diff checks are clean. Synthetic Django-rendered layout checks passed in Edge at 1440px and 320px, with no mobile horizontal overflow.

## v0.7.14 - attributed payment handoff completion

Completed by me now includes retained bank-advice review submission/decision, bank submission and response recording, plus remittance submission/decision/release and posted-source synchronization. Attribution uses the recorded actor and office for the actual step, with current source access rechecked. Treasury bank submission preserves its established cross-office scope. Resubmissions keep distinct stable event identities, while current source state remains separate. Draft preparation and terminal status alone do not credit completion. Turning-point choices and project-goal reasoning are recorded separately in `docs/IMPLEMENTATION_DECISIONS.md`. Verification: both focused payment-handoff tests passed in 3.328 seconds; all 553 project tests passed on the final source in 147.078 seconds. System, migration-drift, compilation and diff checks are clean.

## v0.7.15 - personal Waiting through remittance posting

Personal Waiting now follows released remittances until their Accounting posting handoff finishes. Retained creators, submitters and the actor who requested posting at release can follow the existing batch under current source read access. The release timestamp remains evidence, not an invented deadline. Related posting-request and journal actions are resolved back to the remittance before truncation, so combined duties and missing core receipts do not mislabel actionable work as Waiting. Completed batches leave Waiting. Decision D-005 records the goal, alternatives and tradeoffs. Verification: both focused remittance Waiting tests passed in 5.368 seconds; all 555 project tests passed on the final source in 139.218 seconds. System, migration-drift, compilation and diff checks are clean.

## v0.7.16 - Finance control UAT authority

Finance control mutation predicates now require an active, authenticated, non-UAT actor as well as their existing explicit permission and office scope. Configuration submission/approval, template management, shadow management/reconciliation/cutover and discovery management use the shared check; named discovery ownership/review cannot bypass it. Authorized preview reads remain separate. Original reproduction accepted UAT release submission, independent approval and workbook preflight despite the read-only contract. Ordinary maker-checker and governed exemption behavior remain intact. FIN-GAP-009 is verified: all 20 focused Finance control tests passed in 3.225 seconds; all 557 project tests passed on the final source in 144.110 seconds. System, migration-drift, compilation and diff checks are clean.


## v0.7.17 - governed setup review correction

Submitted setup releases can be returned to draft by an independent, explicitly authorized reviewer with a mandatory correction reason. Submitted child records follow the release back to draft; submission attribution and immutable return history are retained. Draft workbook correction preserves the prior file and checksum evidence, clears preflight, and requires fresh preflight before resubmission/approval. Current release/template state and office/UAT authority are checked under release-first locks. Source pages expose return, correction and retained return guidance. Approved records remain locked. FIN-GAP-010 is verified for the bounded return/workbook-correction flow: all 24 focused Finance tests passed in 3.942 seconds; all 561 project tests passed in 143.087 seconds. System, migration-drift, compilation and diff checks are clean. Synthetic review/correction layout checks cover desktop and 320px, with corrected narrow forms and wrapping draft actions.; scope covers workbook correction and missing preflight, not arbitrary master-data editing.


## v0.7.18 - personal setup handoff views

Personal Waiting now includes submitted Finance setup releases under current source read scope and retained preparer/submitter attribution. Draft releases with matching retained return events appear in Returned with the reviewer reason and return time; resubmission removes that label. Stable source identities and authorized-action exclusion apply before display truncation. The setup review selector recognizes existing active self-approval exemptions without granting them; task/source guidance distinguishes exempt approval from independent return. Effective dates remain separate from submission deadlines. Verification: four focused setup handoff tests passed in 2.864 seconds; all 564 project tests passed in 152.521 seconds. System, migration-drift, compilation and diff checks are clean.


## v0.7.19 - attributed setup completion history

Completed by me now includes retained setup release submission, return, approval, scheduling, activation, restoration and retirement actions attributed to the signed-in account. Current source read scope and event/target/office consistency are required. Repeated submissions keep separate stable event identities, and current release state remains distinct from historical completion. Draft creation or terminal status alone does not credit a handoff. Template/preflight and other child actions remain outside this adapter. Verification: both focused setup completion tests passed in 1.814 seconds; all 566 project tests passed in 215.253 seconds. System, migration-drift, compilation and diff checks are clean.


## v0.7.20 - personal discovery handoffs and history

Personal discovery Waiting now uses retained preparer/submitter attribution and the current named-owner/reviewer or office read boundary, preserving established cross-office access. Stored review targets retain their local review meaning. Completed by me uses retained submission, return and recording events, with stable identities and current source access. Recording an unresolved finding remains distinct from LGU-confirmed acceptance and keeps the current named-scope blocker visible. Evidence locks and decision authority are unchanged. Verification: all three focused discovery handoff tests passed in 2.879 seconds; all 569 project tests passed in 149.738 seconds. System, migration-drift, compilation and diff checks are clean.


## v0.7.21 - personal payable handoffs

Personal Waiting now follows attributed payable intake through independent Accounting review and accepted-payable DV preparation. Current workbench scope, consistent intake/case stages and the shared voucher-case identity govern visibility and action exclusion before truncation. Completion uses retained payable submission, return and acceptance events with historical actor-office attribution and current source access. Acceptance means readiness for DV preparation, not authorization to release payment. Later signature, journal, advice and exception Waiting remains outside this bounded adapter. Verification: all three focused payable tests passed in 2.093 seconds; all 572 project tests passed in 153.168 seconds, including service-generated handoffs in the full transaction replay. System, migration-drift, compilation and diff checks are clean.


## v0.7.22 - signature custody and voucher mutation authority

Wet-signature return now locks and reloads the stored task within the authorized voucher case before checking pending state, round and sequence. Caller-supplied stale state or altered linkage/order cannot overwrite prior custody or write another case. The shared voucher-service mutation guard also excludes UAT despite combined operational permissions; separate workbench read predicates remain intact. Original isolated reproduction accepted all four forbidden paths (5 tests, 4 failures). Normal ordered recording and same-key retry remain supported. FIN-GAP-012/013 are verified: all five focused boundary tests passed in 0.070 seconds; all 577 project tests passed in 162.985 seconds. System, migration-drift, compilation and diff checks are clean.


## v0.7.23 - personal DV handoffs and signature packet parity

Personal Waiting now follows attributed payable/DV work through wet-signature custody and independent Accounting validation under current source read access. The DV preparer or retained intake preparer/submitter qualifies; arbitrary case creation does not. Authorized signature child actions suppress the parent case before truncation. Stage age uses the latest retained transition into the current stage; partial signature events do not restart it, and missing evidence is disclosed. Controlled signature actions now require the source-required TracePoint link as well as the matching print job, preserving legacy/non-controlled rules. Journal/advice handoffs and DV completion history remain future work. Verification: all nine focused DV tests passed in 3.594 seconds; all 579 project tests passed in 260.708 seconds. System, migration-drift, compilation and diff checks are clean. FIN-GAP-014 is verified.


## v0.7.24 - attributed DV completion history

Completed by me now includes retained DV preparation/correction, ordinary partial/final signature-return recording and Accounting-validation events. Each action requires current source read access and matching source transition semantics. Repeated corrections have distinct event identities; historical acting office and current case stage remain separate. Signature-return completion credits custody recording, not the recorder’s signature, and validation does not authorize payment release. Amendment, print/packet and later payment event history remain future work. Verification: both focused tests passed in 2.707 seconds; all 581 project tests passed in 336.250 seconds, including service-generated signature events and the full Budget-to-payment replay. System, migration-drift, compilation and diff checks are clean.


## v0.7.25 - personal voucher posting handoffs

Personal Waiting now continues through Accounting posting for the retained intake/DV preparer or submitter and the requester of an open recognition posting request. Already-authorized source-creation, journal preparation/posting and source-synchronization actions resolve to the shared voucher case before the display cap. Current source read access and retained stage-handoff timing remain required; ledger dates are not deadlines. Treasury preparation and later exception/payment stages remain separate coverage. Verification: both focused handoff/replay tests passed in 8.410 seconds; all 582 project tests passed in 187.761 seconds. System, migration-drift, compilation and diff checks are clean. The full suite was run because action mapping spans vouchers, Accounting and both databases.


## v0.7.26 - Treasury and advice personal handoffs

Waiting includes Treasury preparation and Accounting advice on the shared case. Current authorized initial-assembly/batch actions suppress the case; issued/advised instrument issuers retain personal advice attribution. Historical batch membership and cancelled checks do not determine the current queue. See [D-016](IMPLEMENTATION_DECISIONS.md#d-016--preserve-current-instrumentadvice-lineage-in-personal-waiting) for rationale and [the completion audit](FINANCE_ROADMAP_COMPLETION_AUDIT.md) for validation. Release and post-release work remains separate coverage.


## v0.7.27 - release and event-posting personal handoffs

Personal Waiting now covers Treasury release and Accounting event posting. Issued/advised instrument issuers retain release-phase attribution; open payment/remittance/cancellation/replacement/reversal requesters retain event-posting attribution. Authorized returned-payment, source and journal actions resolve to the shared case before truncation. Current read scope and retained stage transitions remain authoritative. A physical release does not imply that required journal posting is complete; completed cases leave Waiting. See [D-017](IMPLEMENTATION_DECISIONS.md) for attribution choices and [the completion audit](FINANCE_ROADMAP_COMPLETION_AUDIT.md) for verification. Returned-item-specific Waiting remains outside this adapter.


## v0.7.28 - returned-payment personal handoffs

Personal Waiting now includes attributed returned-payment reviews through independent review, clarification, reversal posting and controlled replacement. It uses the existing role-shaped register scope, current stage/status consistency and exact review anchors. Superseded reviews leave Waiting; authorized review, case, source and journal actions are excluded before truncation. Open posting-request authorship can qualify during posting, while existing preparer attribution persists through the handoff. See [D-018](IMPLEMENTATION_DECISIONS.md) and [the audit](FINANCE_ROADMAP_COMPLETION_AUDIT.md) for rationale and validation. Historical completion remains separate work.


## v0.7.29 - attributed returned-payment history

Completed by me now includes retained returned-payment submission, clarified submission, return-for-clarification and Accounting-decision events. Projection requires matching review/case identity, stored actor attribution, valid transitions and matching clarification/outcome evidence, under current review-register and case read access. Superseded versions retain their own historical entries. These decisions do not claim that required posting, replacement or payment release is complete. See [D-019](IMPLEMENTATION_DECISIONS.md) and [validation](FINANCE_ROADMAP_COMPLETION_AUDIT.md). Posting synchronization and replacement issuance history remain separate adapters.
