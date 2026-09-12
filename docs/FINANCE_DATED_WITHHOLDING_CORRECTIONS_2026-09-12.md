# Dated withholding capacity for deduction corrections

v0.7.92 development checkpoint on `codex/finance-dated-withholding-corrections`, based on v0.7.91 (`e5218a9`). This is a prerequisite to extending remitted-withholding corrections, not the operational returned-remittance route itself.

## Scope

A proposed deduction reversal must fit both its actual date and every subsequent posted withholding balance. The former request check used only the balance on the correction date. It could therefore overlook a later posted remittance. Checking only the latest balance would also be insufficient: a later restoration must not hide an intermediate shortfall.

The request now calculates the minimum available balance from its effective date through later posted daily movements. It retains the existing identity of fund, liability account, reference and deduction code, scoped to the Accounting owner and transaction type. Existing live remittance/correction reservations are deducted once at each boundary. Same-date movements are aggregated; subsequent first recognition cannot fund an earlier correction. The Accounting-owner reservation lock and immutable correction payload remain unchanged. No schema, posting recipe, source history or report layout changes.

## Validation record

The initial fixture attempts failed before reaching the capacity assertion because they did not configure the governed remittance rule: one error in 2.994 seconds (`.tmp/dated-withholding-before.log`, runner 83515 exited 1), then eight tests with two fixture errors in 5.691 seconds (`.tmp/dated-withholding-focused.log`, runner 16749 exited 1). These are FAIL - CAUSED BY CURRENT WORK (test setup), not evidence of the suspected production defect. The fixture now records a real reviewed/released remittance and independently posts its JEV.

- FAIL - PRE-EXISTING: the corrected fixture accepted the prohibited earlier correction under the v0.7.91 source implementation: one assertion failure, 2.894 seconds (`.tmp/dated-withholding-baseline.log`, runner 23370 exited 1). `.venv/Scripts/python.exe .tmp/dated_withholding_baseline.py` loads the exact committed deduction-correction module into an isolated test process; it changes no worktree files or operator data.
- FAIL - PRE-EXISTING: the first native run passed the earlier-date rejection but could not use a later actual journal restoration because generic reversal omitted the original transaction type. Nine tests, one error, 11.416 seconds (`.tmp/dated-withholding-native.log`, runner 25257 exited 1). Inspection of `accounting/services.py` confirms the original reversal snapshot retained tax reporting but omitted this classification. New reversals now retain an existing nonblank transaction type, including repeated reversal lineage; posted history is unchanged.
- FAIL - PRE-EXISTING: the voucher/work-task run launched before the classification repair reproduced the same restoration error: 307 discovered, one error and seven skips, 304.391 seconds (`.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers finance.test_work_tasks`; `.tmp/dated-withholding-dependent.log`, runner 9590 exited 1). Final full-project testing supersedes this intermediate run.

PASS — Full-project SQLite: 932 discovered / 900 passed / 32 skipped, 534.072 seconds; native MySQL: 9 passed, 16.507 seconds.

Commands: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py` (`.tmp/dated-withholding-project.log`, runner 70043 exited 0); `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_dated_withholding_corrections vouchers.test_deduction_correction_concurrency` (`.tmp/dated-withholding-native-final.log`, runner 35780 exited 0). Native cases include the real remittance, intermediate-shortfall/restoration and existing reservation/materialization/withdrawal race. Shared Accounting reversal code required broad project scope; no runtime edits followed these final launches. Skips are not passes.

PASS — system/migration drift (`.tmp/invoice_checks.py`), affected compilation, local documentation links and diff whitespace. NOT RUN - OUT OF SCOPE: browser layout, actual bank/recipient interaction, physical printing and LGU acceptance; no UI/layout change or live migration.

All runners ended and test stores were destroyed. Owned MySQL is stopped, port 33308 closed. Protected user DB SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. Version Manager uses an explicit manifest with managed updates limited to VERSION/CHANGELOG. Unrelated files and historical references remain preserved. No master merge, deployment or eGAPS access. Verify remote branch/tag on resume.

## Remaining boundary

An actual remittance refund or return needs a governed operational handoff, retained bank/recipient evidence, correct dates and independent posting. Merely reversing a journal does not establish that money was returned or reconcile the original remittance batch and tax-filing evidence. The synthetic restoration test isolates the dated capacity calculation; it does not establish that missing workflow. Continue that work and generated-history adoption under [the handoff](../CONTINUE.md). Full Finance parity, exact office outputs and operational/LGU acceptance remain open. eGAPS remains untouched.
