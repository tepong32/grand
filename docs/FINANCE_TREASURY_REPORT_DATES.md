# Treasury register period boundaries

Development checkpoint, 2026-09-22, branch `codex/finance-treasury-report-dates`,
based on v0.7.134 / `27c0209fe80d431c0b623612b901bd493ad1703e` / PR #95.
See [required output map](FINANCE_REQUIRED_OUTPUT_MAP.md) and
[foundation gate](FINANCE_FOUNDATION_GATE.md).

## Reproduction and repair

The payment instrument report selects issue/release/cancellation activity using
Django DateTimeField `__date` filters in the active timezone. Its control totals
and source date instead used `.date()` on UTC timestamps read from the database.
Two baseline tests failed against the unchanged implementation (0.100s, exit 1):
three local March 1 instruments were included but issued totals were 0 instead of
600; a local April 1 release was counted in March as 200 instead of 0.
Log: `.tmp/treasury-date-baseline.log`.

Convert issue, release and cancellation timestamps to the active timezone before
period comparison, matching database row selection. Use that same issue date in
source evidence. Preserve naive timestamp behavior when timezone support is off.
UTC instants and retained instrument/advice/journal/receipt records are unchanged.
A row can legitimately appear in different periods for different events; issuing
an instrument is not evidence that it was physically released.

Tests cover a positive UTC offset, an active negative offset, the start of a
local day, release/cancellation crossing into the next month, and naive timestamps.
They use explicitly synthetic retained states to test projection, not actual bank
approval or operational acceptance. Dependent regression includes generated Finance
reports and the ordinary Budget-to-reconciled-Treasury replay.

## Actual validation

PASS: SQLite 47/47 tests, no skips, 23.253s, exit 0:

```text
python .tmp/earlier_sqlite.py reporting.test_treasury_report_dates reporting.test_finance_reporting vouchers.tests.VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay vouchers.tests.VoucherWorkflowTests.test_payment_release_creates_event_jev_resumes_and_exports_register
```

PASS: native MySQL 8.4.11, 5/5 tests, no skips, 1.710s, exit 0:

```text
python .tmp/retrieval_native.py reporting.test_treasury_report_dates reporting.test_finance_reporting.FinanceAccountabilityReportingTests.test_treasury_register_reconciles_issue_advice_release_and_receipt_evidence
```

Both runs destroyed fresh default/Finance test stores. Owned native server stopped.
Logs: `.tmp/treasury-date-tests.log` and `.tmp/treasury-date-native.log`.
Python compilation and `git diff --check` PASS. Operator database SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
Full repository suites NOT RUN - OUT OF SCOPE for this isolated report projection;
Finance report generation, controls and ordinary cycle dependencies were exercised.
Remote CI is separate evidence and is not replaced by local results.
No schema, posting, permission, lock-order or financial source mutation.
Native MySQL is included because date conversion differs by database and requires
valid named timezone tables; SQLite alone is insufficient evidence for this fix.
Existing stored reports remain immutable; only newly generated reports use the
corrected local-date projection.

## Remaining output review

The same raw-date pattern was found in the governed tax report's payment-release
basis (`_governed_tax_payload`). This is a concrete follow-up candidate requiring
its own source/rule/reversal tests; it is not fixed or claimed validated here.
Continue that boundary audit, then finish bank-advice/payment output comparison.
Exact local forms, physical printing, local earmark semantics and LGU acceptance
remain open. Full Finance goal incomplete; production NO-GO. eGAPS remains closed.
No master merge, deployment or operator data changes.

Subsequent checkpoint: [governed tax release dates](FINANCE_TAX_RELEASE_DATES.md)
reproduces and fixes that specific follow-up with generated-output, reversal and
native tests. The earlier Treasury validation above remains its original scope.
