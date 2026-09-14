# Cancelled advance corrections — v0.7.105 development checkpoint

Branch `codex/finance-cancelled-advance-corrections`, based on verified remote v0.7.104
(`b14972d17218333faa65d67a80dc881eb880bdc7`). Development checkpoint; full Finance and production acceptance remain open.
The preceding goal turn made verified progress by publishing unpaid corrections.

## Behavior and remaining verification

A cancelled, never released check previously stranded original-advance correction.
The new route pins the actual cancellation decision, instrument identity, amount,
actor/date/reason and source checksums. Only independently posted and reconciled
corrections retire an old check's replacement route. Historical verification selects
the exact pinned instrument set; later valid checks do not invalidate earlier corrections.
Budget, signing-copy and replacement selectors share this evidence. Legacy payloads
remain unchanged. Released/bank-returned checks remain outside this advance route.

New issuance-time cancellation payloads also pin their actual original payment JEV.
The existing posting recipe must exactly reverse its financial lines and payable
subsidiary evidence, retaining cash-flow purposes. Submission, posting and reconciliation
verify that link. Default-case-before-Finance locks remain mandatory. Historical
cancellations are not relabeled to fabricate missing reversal lineage.

## Actual validation

| Check | Result and scope |
|---|---|
| Baseline reproduction | FAIL - PRE-EXISTING functional limitation: 1 test, 3.543s, runner 77319 exit 1. An actual cancelled/unreleased check reached the old unconditional guard. |
| Initial SQLite cycle | PASS: 1/1, 4.545s, runner 78725 exit 0. Payment-at-release: 1,000 advance/check/cancellation → exact original reversal → reviewed Budget reduction to 800 → revised allocation/claim/DV/signatures/recognition → actual 800 payment and officer output. Predates final issuance/UI additions. |
| Native payment-policy cycles | PASS: 2/2, 10.029s, runner 10658 exit 0. Both payment-at-release and payment-at-issuance, including exact issuance cancellation lineage. |
| Expanded native regression | PASS: 67/67, 130.895s, runner 12187 exit 0. New dated/pinned-evidence guards and old-check replacement race; inherited advances, existing cancelled-check corrections and Budget regressions. |
| Final signing-copy cycle | PASS: 1/1, 8.202s, runner 79369 exit 0. HTTP correction link, corrected print queue, generated DV workbook, recorded copy, packet assembly, signatures and actual payment under payment-at-issuance. |
| Full-project SQLite | PASS: 1,158 discovered / 1,079 passed / 79 skipped, 1387.707s, runner 41031 exit 0. |
| System, migration drift, diff | PASS. No schema migration. |

The final signing-copy test was added after the broad runners started and is covered
by its separate fresh native run. Runtime did not change after the broad runs started.
Skipped tests are not passes. Generated/recorded synthetic copies do not establish
physical printer, exact local-form or real-office acceptance.

Actual commands:

- Initial SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment`.
- Native policy cycles: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment_at_issuance`.
- Expanded native: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests vouchers.test_cancelled_advance_concurrency.CancelledAdvanceConcurrencyTests vouchers.test_cancelled_check_corrections.CancelledCheckCorrectionTests budget.tests.AnnualBudgetPreparationTests`.
- Final print cycle: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_corrected_advance_signing_copy_and_packet_reach_payment`.
- Full SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`.
- Checks: `.venv/Scripts/python.exe .tmp/invoice_checks.py` and `git -c core.safecrlf=false diff --check`.

Logs: `.tmp/cancelled-advance-baseline.log`, `.tmp/cancelled-advance-first.log`,
`.tmp/cancelled-advance-native-first.log`, `.tmp/cancelled-advance-native-expanded.log`,
`.tmp/cancelled-advance-print-native.log`, `.tmp/cancelled-advance-full.log`.
The local wrappers isolate logging/fixture configuration; the committed native runner
is `scripts/run_mysql_tests.py` with the same test labels and disposable-server
configuration described in [native testing](FINANCE_NATIVE_TESTING.md).

## Cleanup and remaining scope

Native runners terminated sequentially and destroyed both test stores. Owned MySQL
is stopped and port 33308 is closed. Protected operator DB SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
No operator-store migration or eGAPS access. Unrelated draft/screenshots remain intact.
The full SQLite runner also terminated successfully. Version Manager uses the reviewed
19-file checkpoint plus VERSION/CHANGELOG, preserving historical release references
and unrelated work. Verify the remote development branch/tag after publication.

Released/returned original advances and downstream expense/refund corrections, other
Finance domains, exact forms, ordinary office/WFH and operational/LGU acceptance remain
open. Cross-year correction numbering is not specifically validated. No master
integration, deployment or complete Finance parity is established. See D-090,
CONTINUE.md and the Finance roadmap.
