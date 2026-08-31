# Finance cash position and instrument ageing

Status: **F8.3 implemented synthetic control; local cash policy, bank terms, and official template acceptance remain required**.

## What GRAND now controls

F8.3 gives Treasury a bank-and-fund workspace separate from Budget authority. A controlled route has:

- a versioned cash policy with **Observe** or **Enforce** mode, minimum reserve, maximum position age, unclaimed/stale thresholds, effective dates, reviewed authority, and a local-applicability decision;
- independent policy preparation and Accounting review;
- a cash-position version pinned to the latest independently reconciled bank evidence and its checksum;
- separately entered confirmed later inflows, confirmed later outflows, other restricted/held cash, and reviewed evidence;
- independent position review and a checksum-backed approved snapshot;
- an issue-time reservation pinned to the exact approved position;
- evidence-backed unclaimed, stale, and returned classifications without rewriting issue, advice, release, or cancellation history; and
- portable CSV evidence archived with its manifest under the configured `department/user/finance-cash-position/year/month` export tree.

The downloadable planning starter is a plain CSV that can be edited in ordinary spreadsheet software. It helps named offices discuss and record starter values; it is not an automatic import or an accepted official form.

## Cash equation and issue gate

For an approved position:

```text
position before issued reservations
  = reconciled book balance
  + confirmed later inflows
  - confirmed later outflows
  - other restricted/held cash
  - minimum reserve

available to issue
  = position before issued reservations
  - all still-reserved issued instruments for the route
```

Observe mode displays and reserves against a current approved position when one is available, but it does not block a legacy issue when the position is absent or insufficient. Enforce mode requires a current approved position and enough available cash for the new instrument. It does not bypass the separate budget, obligation, payable, posting, advice, claimant, and release gates.

Existing voucher routes remain compatible until a named bank/fund policy is independently activated in Enforce mode. This avoids silently converting a starter assumption into operating authority.

## Modification allowance and corrections

Before a check exists, eligible voucher dates/signatories and upstream payable or obligation evidence continue through their existing guided, reason-required correction routes. Cash-policy and cash-position corrections are retained as successor versions:

1. a reviewer returns the submitted version with a specific instruction;
2. Treasury prepares a new policy or same-date position version;
3. a successor position requires a preparation note explaining the change;
4. the prior returned version remains visible; and
5. a different reviewer decides the successor.

After issue, GRAND never edits the check number, amount, bank/fund route, or original reservation in place. Use the controlled cancellation/replacement route before release, or the applicable Accounting reversal/adjustment route after a released item is returned. An ageing label alone never releases reserved cash.

## Instrument ageing rules

Thresholds are local policy values rather than source-code constants:

- **Unclaimed** applies only to an advised, unreleased instrument after the accepted follow-up threshold. A later valid claimant release resolves it.
- **Stale** applies only to an advised, unreleased instrument after the accepted validity threshold. GRAND blocks release; cancellation/stop-payment and replacement or Accounting treatment must follow reviewed local practice.
- **Returned** applies to a released instrument after the bank returns it. The exception records the bank evidence and starts F8.4's Accounting review; the pinned local payment-return rule—not the ageing label—governs the reversal or explicit no-entry decision.

Escalating an unclaimed item to stale resolves the earlier classification through retained evidence. Cancellation resolves open pre-release classifications and releases the issue reservation; actual claimant release consumes it. For a returned released check, replacement remains blocked until Accounting completes the governed decision and selects Reissue; the linked replacement then closes the review and exception without rewriting the original instrument.

## Public guidance and acceptance boundary

The COA Government Accounting Manual for NGAs defines cancelled, outstanding, and returned checks and describes bank reconciliation as the settlement of bank/book differences ([GAM Chapter 21, scope and definitions](https://coa.gov.ph/wp-content/uploads/abc-help/gam_b/br1.1.htm)). It also says checks drawn during the day—including released, unreleased, and cancelled checks—are recorded chronologically in the check/ADA record, with actual release dates indicated ([GAM Chapter 6](https://www.coa.gov.ph/wp-content/uploads/ABC-Help/GAM_A/g5.htm)). Its year-end treatment for unreleased checks includes restoration to cash and a reversing entry in the ensuing year ([GAM, adjustments for unreleased checks](https://www.coa.gov.ph/wp-content/uploads/abc-help/gam_b/fr1.28.htm)).

DBM's current PFM reform action plan identifies continuous cash-flow updating and harmonized cash-programming procedures as active reform work, while also noting fragmented guidance and the need for consultation and formal endorsement ([PFM Reforms Roadmap 2024–2028, Cash Management](https://www.dbm.gov.ph/wp-content/uploads/DBM%20Publications/PFM-Reforms/Midterm-Update/Action-Plans/SFA%202-%20Cash%20Management-v2.pdf)).

These sources support GRAND's conservative evidence, reconciliation, and local-policy design. They do **not** establish that an NGA rule, threshold, form, or accounting entry automatically applies to this LGU. Before Enforce mode or official use, named Treasury, Accounting, bank, COA/local audit, and legal/process owners must confirm applicability, thresholds, stop-payment/cancellation practice, returned-item entries, reports, signatories, deadlines, copies, retention, and exact official layouts.

## Acceptance and replay still required

Official rollout still requires:

- redacted replay from reconciled bank evidence through position approval, check issue, advice, release or exception, reservation closure, Accounting treatment, reconciliation, and export;
- accepted bank/fund ownership and minimum-reserve method;
- accepted position frequency and evidence for summarized later movements;
- accepted unclaimed follow-up, stale validity, cancellation/stop-payment, replacement, returned-item, and year-end rules;
- comparison with the exact locally required cash program, check/ADA record, accountability schedule, and official report templates;
- maker/checker, custody, printing, bank acknowledgement, retention, and TraceSync safekeeping review; and
- named-office UAT and cutover approval.
