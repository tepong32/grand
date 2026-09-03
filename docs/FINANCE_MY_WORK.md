# Finance work-attention foundation

Status: F1.5 foundation plus the first item-level task-contract checkpoint implemented. `/finance/my-work/` provides a live, permission-filtered overview of supported Finance setup/discovery/field operation, Budget, shared voucher, Accounting, bank-advice, returned-payment, Treasury remittance, cash-policy, cash-position, period-close/reopen, Reporting, and local-form action groups. Field-operation cycle gates and local-form actions also expose stable read-only work items over their existing governed records; the remaining domains and nested field records are not yet represented at item level.

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
- shared voucher cases whose current stage matches a held action permission;
- Accounting JEV draft/posting, opening-balance preparation/submission/review/post/reconcile, bank-statement staging/correction/matching/review, and period-close preparation/review/reopen decision;
- role-scoped bank-advice preparation/correction, independent review, approved bank submission, and submitted bank-response recording;
- returned-payment review versions awaiting an Accounting decision, Treasury clarification, or Accounting-cleared controlled replacement;
- Treasury cash-policy preparation/correction and independent review, kept separate from cash-position preparation/correction and independent review;
- Treasury remittance draft, returned, review, and release states;
- own-run or department-visible Reporting draft, failed, control-ready review, and approval states; and
- local-form mapping/reference/section preparation, returned correction, independent practical-test witnessing, and independent acceptance review; accepted/superseded form views remain oversight only.

The source workspace remains authoritative after the handoff. Its own permission, maker–checker, state-version, locking, correction, export, and audit controls still apply.

## First item-level contract

For Field-operation cycle gates and Local forms, each visible item now carries:

- a deterministic `finwork:v1:<source-kind>:<source-public-id>:<action>` Task ID and a controlled versioned task type;
- a stable case/source ID, recognizable reference, safe subject, transaction kind, and direct authoritative-record link;
- the exact plain-language action and source-query gate;
- the permitted role queue and office/scope statement, without claiming that the item has been assigned;
- received age plus either the retained field-cycle plan date or an explicit statement that no structured target is available;
- ready/returned presentation state, authoritative source state and source version token; and
- a safe exception summary for the exact missing or returned gate where applicable.

One source may correctly produce more than one Task ID when it requires separate actions. Rebuilding the page does not change those IDs or write task, source, ownership, approval, or completion state. Named defects, readiness exercises, stakeholder decisions, and cutover decisions remain group-only until their own nested record identity can be projected; GRAND does not mislabel the parent cycle as that task. The page limits its rendered item table to 100 deterministic rows and directs users to the exact source queues for the complete register.

## Deliberately deferred adapters

Other remaining cross-cycle action groups are not counted until their source workspaces expose a filter that reproduces the same work item, role scope, and state. Local forms, field operation, setup, discovery, bank advice, returned payment, period close/reopen, and cash control now use shared filter services in both My Work and their source workspaces. Local-form preparation, test witnessing, and acceptance review remain separate from accepted/superseded oversight, and a user never receives independent work for that user's own test or submitted form. A field count means visible cycles containing the named action, not the number of nested defects, exercises, or decisions. Field personal actions remain distinct from oversight; setup states remain effectivity-aware; discovery owner/reviewer actions remain separate from oversight; returned-payment actions separate Accounting decision, Treasury clarification, and controlled replacement; and cash policy and position versions stay distinct. Omitting any still-unsupported number is safer than showing a plausible count that opens a different list.

The broader F1 My Work contract remains open. Later rollbackable slices must extend the same stable contract to the other supported domains, then add Waiting/Returned/Due/Completed-by-me views, assignment/following rules, governed shared views, and a separately authorized bounded portable export. Notifications must remain signals over that same source contract, never a parallel queue.

## Internal How-To

`seed_internal_howtos` now publishes a versioned guide selected by department kind:

- requesting offices learn office-isolated shared-case triage and the pre-DV/check modification boundary;
- Budget users learn proposal/allotment/obligation authority boundaries;
- Accounting users learn setup/discovery/field-operation/JEV/opening/bank/close/advice/returned-payment/cash/reporting/local-form handoffs;
- named field participants learn to open only defect, exercise, witness, or stakeholder rows assigned to them and to distinguish a cycle count from nested work;
- Budget, Accounting, and Treasury users learn to distinguish local-form preparation, returned correction, independent test witnessing, final acceptance review, and non-action oversight; and
- Treasury users learn voucher/advice/remittance triage, returned-payment clarification/replacement boundaries, and separate cash-policy and cash-position queues.

The floating `?` panel stays over the current page. Its checkmarks are optional private resume state, not an assignment, notification, submission, attendance record, competence rating, UAT result, or approval.

## Acceptance and authority boundary

This checkpoint does not prove that an LGU accepts the workflow, terminology, role design, local form, COA/DBM/BIR interpretation, device layout, accessibility behavior, or production deployment. Named users must still compare the displayed groups and source queues with actual local duties and retained authority. A green automated test proves the software contract exercised by that test only.

## Regression contract

Automated coverage verifies the stable route and Finance-entry link, denial for reporting-only/ordinary users, exact local-form preparation/witness/review parity, exact field lifecycle/role/object parity, setup lifecycle/effectivity and discovery owner/reviewer parity, requesting-office voucher count parity, bank-advice, returned-payment, period-close, cash-policy, and cash-position parity with their filtered source queues, hidden-office isolation, independent review exclusions, named cross-office defect/exercise/stakeholder visibility, UAT preview exclusion, permission-shaped action choices, synchronized exports, boundary copy, and publication of page-relevant department guides. The item-contract checkpoint adds deterministic-ID, separate-action, source-link, office-isolation, timing-basis, read-only, UAT-exclusion, and page-boundary coverage. Its focused gate passed 81 tests and the complete gate passed all 457 project tests across both routed databases in 96.742 seconds. An authenticated isolated browser pass verified five exact source-linked tasks, stacked mobile rows at 390×844, the floating nine-step guide, and zero application-route console errors. Future task adapters must continue through the same gate.
