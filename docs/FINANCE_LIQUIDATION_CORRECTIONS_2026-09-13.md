# Posted expense-liquidation corrections

Development checkpoint v0.7.103, `codex/finance-liquidation-corrections`, D-088.
This extends [expense applications](FINANCE_ADVANCE_LIQUIDATIONS_2026-09-12.md)
and [actual cash refunds](FINANCE_ADVANCE_REFUNDS_IN_PROGRESS.md).

## Supported workflow and retained evidence

Accounting opens a posted expense liquidation from its original officer advance,
retains an actual correction date and reason, and prepares a separate exact reversing
JEV. Another officer must post it. Reconciliation restores the original advance's
available amount only from that correction date; a Finance-posted reversal awaiting
the default-store handoff does not release the hold. A replacement expense application
can reuse the corrected document reference with explicit predecessor identity, or
Treasury can capture an actual cash refund through the existing collection workflow.

The original financial lines, officer subsidiary, DV state and previously issued export
bytes remain unchanged. The correction pins the original request, checksum, JEV,
financial rows and subsidiary, and validates their exact mirrored lines at submission,
posting and recovery. Correction debits are excluded from original-advance selectors.
History links original and correction JEVs and shows an existing correction's status.

Default case locks precede Finance locks. Competing proposals, materialization and
reconciliation share that boundary with expense/refund reservations. Discarded drafts
require witnessed independent withdrawal before a fresh correction request; neither
posted corrections nor original evidence are erased. Existing posting requests,
journals, subsidiaries and numbering are reused; no schema or second ledger is added.

## Validation

Both database aliases use disposable stores; no operator-store migration or eGAPS access.

- Full-project SQLite: PASS, 1,107 discovered / 1,041 passed / 66 skipped,
  610.806s, runner 7618 exit 0.
  Command: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`.
  Log: `.tmp/liquidation-correction-full.log`. Skips are not acceptance evidence.

- Initial focused SQLite: FAIL - CAUSED BY CURRENT WORK, three tests in 5.591s.
  The new CSV assertion assumed `0.00`; SQLite emitted `0`. The assertion now parses
  monetary columns as Decimal; financial behavior was not changed to satisfy it.
- Broad native MySQL 8.4.11: PASS, 40 tests in 71.096s, runner 31823 exit 0.
  Command: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_liquidation_corrections.LiquidationCorrectionTests vouchers.test_liquidation_correction_concurrency.LiquidationCorrectionConcurrencyTests vouchers.test_advance_refunds.AdvanceRefundTests`.
  Includes original advance, refund, correction, exact-mirror/independence, dated
  replacement, archived export and native concurrency coverage.
- System/migration drift: PASS, `.venv/Scripts/python.exe .tmp/invoice_checks.py`.
- Final supplemental native: PASS, two tests in 9.297s, runner 79483 exit 0.
  Command: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_liquidation_corrections.LiquidationCorrectionTests.test_corrected_expense_can_be_settled_by_actual_cash_refund vouchers.test_liquidation_corrections.LiquidationCorrectionTests.test_web_exact_correction_and_replacement_preserve_history_and_outputs`.
  Covers the final cash-refund alternative and refined correction-history display.
- Synthetic Chromium template inspection: PASS, 390px correction form without
  horizontal overflow and desktop retained history. See the committed
  `output/playwright/liquidation-correction-narrow.png` and
  `output/playwright/liquidation-correction-history.png`. HTTP tests exercise the
  real permissioned views; synthetic preview does not establish live LGU usability.

Full regression is appropriate because dated capacity and posting are shared with
Accounting, vouchers, Treasury and reporting. Native validation is required because
SQLite cannot establish locking behavior. The final cash-refund-after-correction test
and existing-correction status display were added after broad runners started and
receive separate final native coverage; do not attribute those additions to the earlier
full-suite discovery.

All runners ended. Owned MySQL and preview services stopped, their listening ports
closed and Chromium preview closed. `git diff --check` passed. The protected operator
`db.sqlite3` SHA-256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
Unrelated drafts/screenshots and the operator database are excluded from the checkpoint.
Version Manager stages the explicit reviewed manifest and updates VERSION/CHANGELOG
only, preserving historical release references. Publication targets the development
branch and v0.7.103 tag; no master integration or deployment is performed.

## Remaining work and pause boundary

Original advance-recognition corrections, other local advance scenarios, remaining
M01/M02/M03 functionality, exact official forms and wider Finance parity remain open.
This checkpoint does not establish correction of arbitrary historical/inactive-account
recipes, operational acceptance or production readiness. Production remains NO-GO.
After publishing this checkpoint, pause implementation at the user's request. Resume
from [CONTINUE.md](../CONTINUE.md), preserving functional breadth before office/output,
usability/WFH and operational/LGU acceptance work.
