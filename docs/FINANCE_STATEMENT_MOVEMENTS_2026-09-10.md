# Statement movements and contra-account presentation

Implemented and validated in v0.7.74 on `codex/finance-statement-movements`, based on v0.7.73 (`bd09f9f`). This advances M01 financial functionality; Cash Flow, full statement-package composition, exact local forms and LGU acceptance remain open. Production remains NO-GO.

## Verified numerical defect

Native MySQL reproduction of the existing aggregation failed both assertions (2 tests, 1.285 seconds). Against cash/revenue of 1,250.00, a 100.00 credit contra asset produced assets of 1,350.00 instead of 1,150.00. A 50.00 debit revenue-refund account produced revenue of 1,300.00 instead of 1,200.00. Natural debit/credit balance describes the account's usual balance, not its contribution to its statement class.

The statement calculation now uses debit minus credit for assets/expenses and credit minus debit for liabilities/equity/revenue. This preserves contra signs without changing general-ledger natural-balance presentation.

## Net-assets functionality

The Accounting report preset generates a comparative XLSX statement by fund from posted journal lines. Rows distinguish opening and restated balances, policy changes, prior-period corrections, other opening restatements, revenue recognized directly in equity, current operating surplus/deficit, other equity movements and closing net assets. Diagnostic rows retain unclassified movements and reconciliation differences.

Five explicit JEV source choices use existing preparation, independent posting and immutable reversal lineage. Direct-equity entries require equity and exclude current revenue/expense accounts. Nominal closes and reversals are retained in source evidence but excluded from operating activity. No historical entry is relabelled. Migration accounting/0013 changes source choices only.

Each fund's opening balance plus classified movements must equal its closing assets less liabilities, with both opening and closing accounting-equation checks. The same period one year earlier is computed independently. Missing comparative evidence is blank and keeps the control in exception; absent history is not proof of a zero opening. Existing independently approved/reconciled zero-opening declarations are retained as source evidence, including their checksum checks. Later duplicate opening imports or a zero declaration contradicted by earlier balances are exceptions. An ordinary journal does not by itself establish a complete opening baseline.

Exact fund filters apply to sources, controls and exported rows together. Definitions cannot hide required movement rows/columns, regroup subtotals or reorder the statement. Unclassified ordinary direct-equity adjustments require explicit correction and cannot pass review merely because totals balance. An original and its actual reversal may offset within the reporting period, allowing a properly classified replacement; unrelated offsetting adjustments do not clear each other's exceptions. All originals and reversals remain in source evidence. Complete source snapshots include account types used in calculation.

## Source and output boundary

The [Municipality of Coron 2024 accomplishment report](https://coron.gov.ph/wp-content/uploads/2025/10/Accomplishment-Report-CY-2024.pdf), printed page 131 (PDF page 139), publishes the SEF net-assets statement with policy-change, prior-error, restated-opening, direct-equity revenue and period-result distinctions. This is a primary municipal example of the accounting presentation, not proof of this implementing LGU's current accepted layout or legal applicability. The preceding municipal comparison research also found comparative-year examples. The preset remains a candidate for local acceptance.

The synthetic export scenario starts with 400.00 opening equity, adds 50.00 prior-period correction, 20.00 direct-equity revenue and 1,250.00 current surplus. Its exported closing balance is 1,720.00, with prior-year closing 400.00. A nominal close preserves the operating result. Independently posting a reversal of the 50.00 correction produces 1,670.00 in a new run while the earlier retained report remains unchanged.

## Validation and remaining work

Commands (project Python 3.11; the ignored native helper verifies the owned loopback server and invokes the committed fresh two-store runner):

```powershell
.venv/Scripts/python.exe manage.py test reporting.test_finance_reporting --noinput
.venv/Scripts/python.exe manage.py test reporting accounting vouchers finance.test_work_tasks --noinput
.venv/Scripts/python.exe .tmp/portable_mysql.py test reporting.test_finance_reporting accounting.tests
.venv/Scripts/python.exe .tmp/portable_mysql.py test reporting.test_finance_reporting.FinanceAccountabilityReportingTests.test_net_assets_missing_baseline_and_unclassified_equity_block_review
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
git diff --check
```

The native reproduction used the two `test_contra_*` methods before the sign repair. Affected reporting/Accounting/voucher/work-task regressions cover shared journal validation, correction lineage, retained output, permissions, presets and downstream source behavior. Full project regression, unrelated native policy/concurrency drafts and human printer/form acceptance are NOT RUN - OUT OF SCOPE for this bounded calculation feature; their broader gates remain open.

- PASS: initial focused SQLite reporting run, 37 tests in 9.787 seconds, including numerical contra repairs and XLSX/reversal assertions.
- PASS: subsequent focused SQLite run, 40 tests in 11.589 seconds, including all movement categories, fund scope and actual zero-opening approval/posting/reconciliation with evidence-drift refusal.
- FAIL - CAUSED BY CURRENT WORK: initial native run, 39 tests in 20.753 seconds, one zero-opening fixture error. The shared reporting helper grants reporting permissions only; the new fixture now explicitly grants Accounting opening permissions. No production permission check was weakened.
- FAIL - CAUSED BY CURRENT WORK: first broad SQLite run, 402 discovered (399 executed, three native-only skips), 187.430 seconds; only the same already-corrected fixture permission error. The corrected final broad run below passes.
- PASS: affected MySQL reporting and Accounting suite, all 90 tests in 37.646 seconds. A targeted native rerun covers the subsequent unclassified reversal/replacement change.
- PASS: final native unclassified-adjustment reversal/replacement regression, 1 test in 1.746 seconds. The new report reconciles after the controlled correction and retains the original evidence. The owned MySQL fixture was shut down after native validation.
- PASS: final broader SQLite suite, 403 discovered / 400 executed / three native-only skips in 173.975 seconds, including the latest reversal/replacement path. System, migration-drift, compilation and diff checks passed. Both stores remained separate; the existing user database SHA-256 remains C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C.
- Tests run only against disposable stores. eGAPS and the existing user `db.sqlite3` change are outside this work. Preserve the unrelated draft `accounting/test_policy_concurrency.py`.
- Next: complete the remaining M01 Cash Flow source classification and statement-package/notes integration, then M02 earlier-payable linkage. Operational scrutiny and exact local print acceptance remain separate gates.
