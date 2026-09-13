# Officer advance cash refunds — development checkpoint

Checkpoint v0.7.102 on `codex/finance-advance-refunds`, based on published v0.7.101. This connects
actual officer cash returns to the original advance, existing Treasury receipt/deposit
sources and independent Accounting. It is not full advance/Finance parity or production acceptance.

The supported workflow records the original officer advance on an ordinary receipt,
retains its actual release and Treasury office evidence, debits reviewed receiving cash
and credits the same original advance asset/subsidiary. Pending refunds and expense
liquidations share dated capacity under the original default case lock. Rejection and
unposted withdrawal retain independent evidence; posted receipt correction restores
the advance only from the correction date. Deposited receipts require their deposits
to be corrected first. Existing sources, posted JEVs and issued printable bytes remain
unchanged. No new source model or accounting store is introduced.

Receipt entry offers the original advance only from the user's Treasury release cases.
The officer identity comes from the original advance, not free text. Accounting's
original-advance page includes refund holds and history. Refund printable copies identify
the original JEV and officer. Refund correction debits are excluded from original-advance
pickers while remaining in subsidiary/control balances.

The rule editor also needs to permit the deposit service's existing internal-transfer
credit over allocated cash receipts. The exception is restricted to deposit-time credit,
each-allocation amount and internal cash purpose; other non-cash instructions retain
the existing restriction.

## Validation status

- FAIL — CAUSED BY CURRENT WORK: first focused SQLite, one test / 2.680s, runner 1774
  exit 1 (`.tmp/advance-refund-focused.log`). Synthetic setup used an invalid cash purpose
  and validated rule edits against an active release. Corrected to the existing
  `op_other_in` category and synthetic draft-to-active setup.
- FAIL — CAUSED BY CURRENT WORK: second focused SQLite, two tests / 2.700s, runner
  93936 exit 1 (`.tmp/advance-refund-second.log`). The existing rule editor rejected
  internal allocated-cash deposit credits. Added the narrowly defined deposit exception.
- PASS — system/migration-drift checks through `.tmp/invoice_checks.py`; no schema change.
- PASS — focused SQLite: two receipt/expense/deposit/correction and HTTP/print/withdrawal
  tests, 5.715s, runner 56117 exit 0 (`.tmp/advance-refund-third.log`).
- PASS — initial native workflow and races: eight tests, 28.826s, runner 5792 exit 0
  (`.tmp/advance-refund-native.log`). Includes competing refund/expense and refund/refund
  reservations plus existing advance concurrency scenarios.
- PASS — Chromium inspection of the production printable template using synthetic data,
  `output/playwright/advance-refund-print.png`: original JEV, officer, amount, balanced
  cash/advance rows, review attribution and retained-record footer are legible. This is
  not official-form or full-shell clerk acceptance. Browser and preview server stopped.
- PASS — expanded native: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_advance_refunds.AdvanceRefundTests vouchers.test_advance_refund_concurrency.AdvanceRefundConcurrencyTests vouchers.test_collection_workflow.CollectionWorkflowTests`,
  41 discovered / 41 passed / no skips, 52.119s, runner 1503 exit 0
  (`.tmp/advance-refund-final-native.log`). Includes inherited advance/collection
  regressions, dated correction, interrupted materialization/UAT, CSV and native races.
  Owned MySQL was stopped after completion.
- PASS — full-project SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`,
  1,084 discovered / 1,025 passed / 59 skipped, 550.802s, runner 95480 exit 0
  (`.tmp/advance-refund-full.log`). Broad regression covers shared Finance setup,
  collection, Accounting posting, source recovery, permissions and outputs. Skips are
  not passes; native scope is separately stated above.
- NOT RUN — OUT OF SCOPE: exact prescribed forms, full-shell clerk/WFH testing and
  operational/LGU acceptance. The synthetic preview does not substitute for these gates.

Current scenarios exercise a 400 refund plus 600 expense liquidation, deposit of returned
cash, ordered exact corrections, restored original balance, actual HTTP receipt entry,
retained printable source and independent unposted withdrawal. Native tests also race
refund versus liquidation and competing refunds over the same original advance.

All runners ended; native and preview services were stopped. No schema or operator migration.
Protected `db.sqlite3` SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
eGAPS is untouched. Version Manager preserves unrelated drafts/artifacts and historical
release references; verify the published development branch/tag. This is not primary-branch
integration or deployment evidence.
Next implement governed posted expense-liquidation
and original advance corrections, remaining M03/M01/M02 coverage and the separate
actual inventory, ordinary office, exact-form, usability/WFH and operational/LGU gates.
See [continuation](../CONTINUE.md), [liquidation](FINANCE_ADVANCE_LIQUIDATIONS_2026-09-12.md)
and [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md).
