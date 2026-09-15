# Outgoing cheque presentation reports

Date: 2026-09-15. Validated v0.7.110 development implementation on
`codex/finance-payment-presentations`; not integrated or production acceptance.

## Implemented boundary

Treasury records a reported presentation against an issued cheque. The original issue
event determines Treasury ownership; the pinned Finance release determines Accounting
ownership. Instrument identity, amount, fund, original advice state, source evidence,
reporter and dates are retained with a checksum. No bank acknowledgement, release or
journal is manufactured by reporting an attempt.

Accounting independently records pending, paid, returned, confirmed-not-paid or mistaken
findings. Decisions are append-only, versioned and chained to the original report.
Bank effective dates remain distinct from review timestamps. Pending findings require
a next action. Confirmed nonpayment or a mistaken report can close without financial
mutation. A new report retains the closed predecessor as history.

Verified payment/return cannot be dismissed using a generic outcome. A payment finding
can close only against its original completed payment source and actual release evidence;
a return finding can close only against its completed Accounting return review and
posted/reconciled JEV or governed no-entry decision. Source selectors stay on the same
instrument and case. Neither closure creates another journal. A release payment request
takes precedence over issuance, including an unfinished request; no-entry replacement
issuance cannot conceal an unfinished release payment.

Case-first locking serializes capture, decisions and financial actions. A stored generated
nullable instrument key enforces one open report on MySQL and SQLite. Unresolved verified
bank findings block conflicting issue, release and cancellation on the case, including a
replacement already issued before a late finding on its predecessor. Ordinary pending
reports do not prevent the normal approved/acknowledged advice and release route.

The case and Bank Advice workspace link to retained reports. Treasury capture and
Accounting findings use the existing form style. JSON exports recheck source visibility
and export permission, capture one locked report version and archive the exact downloaded
bytes with the standard manifest. Prior exports remain unchanged.

New explicit role permissions are included in `configure_finance_roles`; no operator
role setup has been executed. Finance UAT membership denies mutation despite additional
operational grants. Current read/export authority remains independently required.
Migrations vouchers/0034–0035 affect the default store only and have been exercised in
disposable stores; no operator migration.

## Remaining boundary

A bank-paid cheque without recorded actual release or a completed governing payment
source stays open for Accounting/Treasury reconciliation. Do not use a fabricated
acknowledgement, ordinary source cancellation or retrospective automatic release to
close it. Actual incoming dishonour, redemption/custody and officer refund timing are
separate modules in [the modular design](FINANCE_CHEQUE_EXCEPTION_DESIGN.md).

## Validation record

- Initial SQLite: five tests passed, 3.501s (`.tmp/presentation-sqlite.log`).
- Initial native: eight passed, one error, 27.526s (`.tmp/presentation-native.log`).
  The run loaded an older service before the new export view; its missing `export_evidence`
  error invalidates this as final snapshot validation. Native race cases passed in that run.
- Dependent SQLite: 125 discovered, 120 passed, three native skips, two errors, 156.645s
  (`.tmp/presentation-dependent-sqlite.log`). FAIL - CAUSED BY CURRENT WORK: the new
  test helper `release` collided with the fixture's Finance release attribute. Renamed
  it to `release_instrument`. No existing regression failed in this run.
- Two later preliminary focused runs were stopped before completion to add source-linked
  resolution; they are not passes (`presentation-final-native.log`, `presentation-final-sqlite.log`).
- Resolution SQLite: 13 discovered, ten passed, three native skips, 5.505s
  (`.tmp/presentation-resolution-sqlite.log`). Includes actual payment posting and
  returned-payment reversal/replacement through the linked closure.
- Resolution native: all 13 passed, 15.733s (`.tmp/presentation-resolution-native.log`).
- PASS final SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_payment_presentations vouchers.tests vouchers.test_advice_register vouchers.test_cash_register`:
  128 discovered, 125 passed, three native-only skips, 63.870s, exit 0
  (`.tmp/presentation-final-regression.log`).
- PASS final MySQL: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_payment_presentations`:
  all 14 passed, including three races, 17.456s, exit 0
  (`.tmp/presentation-final-verified-native.log`). Includes real payment/return source
  closure and unfinished release precedence over no-entry replacement issuance.
- Browser: synthetic Treasury capture, rejected future date with retained input, independent
  pending/nonpayment decisions, visible closed history, new report after closure, and
  1440px/390px layout checked. Narrow document width equals viewport width (390px).
  Fixture-only missing default images were copied into its isolated media directory.
  Screenshots: `output/playwright/payment-presentation-{desktop,narrow,form-narrow}.png`.
  Final case list placement was verified after restarting the fixture server: immediately
  before Checks and release, outside the audit-only header controls.
- System checks, migration generation and whitespace checks pass. Full project suites
  are not claimed; affected voucher/advice/cash regression and native concurrency are
  the required scope for this module.

Operator `db.sqlite3` SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
Unrelated policy-test drafts and prior screenshots remain untouched. No deployment,
bank contact, eGAPS access or production migration occurred.
