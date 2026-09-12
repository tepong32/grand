# Accountable advances and liquidation — M03

v0.7.99 development checkpoint on `codex/finance-advance-liquidation`, based on v0.7.98.
This is a bounded advance-recognition step, not completed liquidation or Finance parity.
The governing order remains [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md).

## Confirmed gap and current approach

The prior checkout offered cash-advance/liquidation transaction kinds and a liquidation
posting decision inside the DV route. It had no advance subsidiary category or explicit
original-advance application controls. Payable/withholding schedules used credit balances.

An explicit reviewed advance instruction now identifies a debit-normal asset, a governed
employee payee and a cash-advance variant. The supported recipe recognizes the gross
advance asset against one payable credit at DV validation, without deductions. Existing
independent JEV posting, signatures, advice and payment then discharge the payable
against the actual releasing bank. This is a synthetic locally reviewed accounting
recipe; it does not assert that every LGU advance uses this recognition timing.

The immutable subsidiary retains the officer's party ID, code and version, variant and
original voucher/posting evidence. Existing recipes without the explicit instruction
retain their original payload shape. No posted history is inferred or reclassified.
The recognized asset is reported debit minus credit and reconciled against every posted
movement on that asset account, including otherwise unexplained manual movements.
The comparison includes other funds using an identified advance control account even
when those funds have no subsidiary detail. A payable mapping must select a credit-normal
liability; balanced debits/credits alone do not establish this recipe's meaning.

## Boundary and next implementation

A recognized asset is not proof of cash release and is not liquidation capacity.
Next connect each liquidation/refund to an explicitly selected original advance and its
actual disbursement, under dated amount controls and independent review. Retain partial
applications, concurrent reservations, corrections and exact reversal lineage. An officer's
aggregate balance must never authorize an application to an unspecified advance.
No liquidation/refund action is introduced by the recognition-only instruction.
Generic detached reversal of an advance subsidiary is refused: it would not resolve the
original DV/payment handoff. A governed correction route remains part of the next source
work, while original evidence and unrelated journal reversal behavior are preserved.

Advance authorization documents, exact local forms/outputs, ordinary operator scenarios,
other recognition timings, legacy adoption and operational/LGU acceptance remain open.
Keep eGAPS and operator databases unchanged. Production remains NO-GO.

## Validation

Focused source-to-recognition-to-payment/schedule tests are in `vouchers/test_advances.py`.
PASS — initial SQLite `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_advances`:
three tests, 3.312s, runner 83642 exit 0 (`.tmp/advance-focused.log`).
FAIL — CAUSED BY CURRENT WORK: the first native run of four tests (3.275s, runner
92153 exit 1, `.tmp/advance-native.log`) granted a nonexistent test permission name;
the new page assertion received the expected access denial. Corrected the fixture to
grant the existing `accounting.view_general_ledger`; no production permission was weakened.

Migrations accounting/0029 and finance/0024 alter explicit choice metadata and were run
only in disposable two-store SQLite and native MySQL tests.

PASS — intermediate native: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_advances`,
four tests, 3.805s, runner 43458 exit 0 (`.tmp/advance-native-final.log`). Includes real
signature/advice/payment posting, HTTP schedule, archived CSV and unexplained GL control gap.
PASS — intermediate broad SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_advances vouchers.tests accounting.tests finance.tests reporting.test_finance_reporting`,
209 tests, 78.059s, runner 81755 exit 0 (`.tmp/advance-dependent.log`).
Final validation follows the added detached-reversal/payable-account guards and cross-fund assertion.

PASS — final broad SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_advances vouchers.tests accounting.tests finance.tests reporting.test_finance_reporting`:
210 discovered / 210 passed / 0 skipped, 81.374s, runner 4525 exit 0,
`.tmp/advance-dependent-final.log`.
PASS — final native MySQL: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_advances accounting.tests`:
55 discovered / 55 passed / 0 skipped, 21.314s, runner 56422 exit 0,
`.tmp/advance-native-guards.log`. This includes cross-fund control gaps, rejected detached
advance reversal and ordinary Accounting/reversal regression, as well as the actual payment/output scenario.

PASS — `.venv/Scripts/python.exe .tmp/invoice_checks.py`: system and migration-drift checks;
`git diff --check`: no whitespace errors. All runners ended. Owned MySQL was stopped and
its loopback listener closed. No operator-store migration, eGAPS access, master merge or deployment.
Protected DB SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

Scope rationale: direct source/payment/output plus affected Accounting, Finance setup,
voucher and reporting suites cover this bounded instruction/category change. Native tests
also cover Accounting persistence and reversal behavior. NOT RUN — OUT OF SCOPE: full-project
release/production gate, dedicated new concurrency races (no new reservation or uniqueness
mechanism here), browser visual acceptance and LGU/official-form acceptance. HTTP rendering
and controlled CSV are exercised, but do not count as human usability acceptance.
Version Manager publication includes only the explicit feature/docs and VERSION/CHANGELOG;
historical release references, the protected DB, unrelated test draft and screenshots are excluded.
