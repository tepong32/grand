# Finance work-attention foundation

Status: F1.5 foundation plus the returned-payment source-adapter checkpoint implemented. `/finance/my-work/` provides a live, permission-filtered overview of supported Budget, shared voucher, Accounting, bank-advice, returned-payment, Treasury remittance, cash-policy, cash-position, period-close/reopen, and Reporting action groups. It is a read model over existing governed registers, not yet the complete item-level My Work task contract.

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

- Budget proposal preparation/review, allotment preparation/review, requesting-office obligation preparation where that is the account's sole obligation scope, and Budget certification;
- shared voucher cases whose current stage matches a held action permission;
- Accounting JEV draft/posting, opening-balance preparation/submission/review/post/reconcile, bank-statement staging/correction/matching/review, and period-close preparation/review/reopen decision;
- role-scoped bank-advice preparation/correction, independent review, approved bank submission, and submitted bank-response recording;
- returned-payment review versions awaiting an Accounting decision, Treasury clarification, or Accounting-cleared controlled replacement;
- Treasury cash-policy preparation/correction and independent review, kept separate from cash-position preparation/correction and independent review;
- Treasury remittance draft, returned, review, and release states; and
- own-run or department-visible Reporting draft, failed, control-ready review, and approval states.

The source workspace remains authoritative after the handoff. Its own permission, maker–checker, state-version, locking, correction, export, and audit controls still apply.

## Deliberately deferred adapters

Field-operation, setup/discovery, local-form, and other cross-cycle action groups are not counted until their source workspaces expose a filter that reproduces the same work item, role scope, and state. Bank advice, returned payment, period close/reopen, and cash control now use shared filter services in both My Work and their source workspaces. Returned-payment actions are separated into Accounting decision, Treasury clarification, and controlled-replacement states; cash policy and position versions are likewise kept distinct. Omitting any still-unsupported number is safer than showing a plausible count that opens a different list.

The broader F1 My Work contract also remains open. Later rollbackable slices must add stable task identity and type, case and authoritative record links, exact action/gate, owner or permitted queue, timing/due state, source state/version, exceptions, Waiting/Returned/Due/Completed-by-me views, assignment/following rules, and governed shared views. Notifications must remain signals over that same source contract, never a parallel queue.

## Internal How-To

`seed_internal_howtos` now publishes a versioned guide selected by department kind:

- requesting offices learn office-isolated shared-case triage and the pre-DV/check modification boundary;
- Budget users learn proposal/allotment/obligation authority boundaries;
- Accounting users learn JEV/opening/bank/close/advice/returned-payment/cash/reporting handoffs; and
- Treasury users learn voucher/advice/remittance triage, returned-payment clarification/replacement boundaries, and separate cash-policy and cash-position queues.

The floating `?` panel stays over the current page. Its checkmarks are optional private resume state, not an assignment, notification, submission, attendance record, competence rating, UAT result, or approval.

## Acceptance and authority boundary

This checkpoint does not prove that an LGU accepts the workflow, terminology, role design, local form, COA/DBM/BIR interpretation, device layout, accessibility behavior, or production deployment. Named users must still compare the displayed groups and source queues with actual local duties and retained authority. A green automated test proves the software contract exercised by that test only.

## Regression contract

Automated coverage verifies the stable route and Finance-entry link, denial for reporting-only/ordinary users, exact requesting-office voucher count parity, bank-advice, returned-payment, period-close, cash-policy, and cash-position count parity with their filtered source queues, preparation-office isolation, independent cross-office review scope, UAT preview exclusion, permission-shaped action choices, boundary copy, and publication of the page-relevant department guide. The focused 30-test adapter/Finance/guidance run and all 438 project tests pass across both routed databases; the full suite completed in 87.573 seconds. Authenticated desktop and 390×844 browser checks confirmed the exact Treasury-clarification row, responsive register, in-page clarification-successor form, floating guide, and zero console errors. Future source adapters must continue through the same release regression gate.
