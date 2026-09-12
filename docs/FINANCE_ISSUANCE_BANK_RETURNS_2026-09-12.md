# Bank returns of issuance-time payments

v0.7.90 development checkpoint on `codex/finance-issuance-bank-returns`, based on v0.7.89 (`53d8ae5`). This is a prerequisite for remaining returned-payment corrections, not completion of that broader scope.

## Reproduced missing path

A prior-payable check can be posted at issuance, included in acknowledged bank advice and released successfully. Under that policy, release correctly creates no second payment request. Bank-return intake nevertheless searched only for a release-time request and refused to open the Accounting review. The same gap affected an issued replacement subsequently returned by the bank.

The lookup now preserves the existing release-time route and, when no release request exists, selects exactly one posted issuance request for the actual check. A replacement selects its own replacement request. The retained rule must identify the corresponding issuance/replacement recognition point; check identity, number, bank account, amount and issuance date must match. The linked journal must reproduce its immutable source identity/checksums, remain posted with posting attribution, and have no active reversal. Missing, ambiguous, unreconciled or mismatched evidence is rejected.

The existing independent return decision, exact payment reversal, replacement and close-without-reissue workflows remain authoritative. No current-policy inference, new payment journal, schema change or history rewrite is introduced. The current instrument/case locking and role/department/UAT boundaries are unchanged.

## Validation

- FAIL - PRE-EXISTING — actual issuance/payment/advice/release succeeded, but bank-return intake raised `Complete the governed payment-release Accounting decision before recording a bank return.` One test, one reproduced error, 2.560 seconds; `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_issuance_bank_returns.IssuanceBankReturnTests.test_issuance_and_replacement_payments_can_each_be_returned`; `.tmp/issuance-return-before.log`, runner 71320 exited 1.
- PASS — corrected end-to-end SQLite scenario: one test, 3.071 seconds, same command; `.tmp/issuance-return-after.log`, runner 89954 exited 0. First payment is returned and replaced; the replacement is then returned and closed. Each review and exact reversal points to its own payment. Original lines remain unchanged. The final claim CSV reconciles 1,500 original, 100 retained deductions and 1,400 outstanding, with restored available claim capacity.
- PASS — native `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_issuance_bank_returns.IssuanceBankReturnTests`; `.tmp/issuance-return-native.log`, runner 59860 exited 0: 15 tests, 15.522 seconds. Includes the new full cycle, unreconciled/wrong-journal rejection with rolled-back intake, and inherited prior-payable regression.
- PASS — dependent `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers finance.test_work_tasks`; `.tmp/issuance-return-dependent.log`, runner 52393 exited 0: 283 discovered / 279 passed / 4 skipped, 222.201 seconds. Skips are not passes. All voucher workflows and Finance work-task regressions cover the bounded return-source lookup and its downstream register/task/settlement consumers.
- NOT RUN - OUT OF SCOPE — repeat of the complete project/non-Finance and entire Accounting/reporting suites. The isolated lookup changes no schema, posting calculation, permission policy, output layout or shared reporting service. Actual posting/reversal/capacity/CSV services are exercised above; the preceding v0.7.89 full-project baseline passed 893 discovered / 864 passed / 29 skipped. The full Finance completion and operational/LGU gates still require their broader validation.
- NOT RUN - OUT OF SCOPE — browser layout checks (no layout change), physical printer and real office acceptance, live migration and eGAPS access. No such acceptance is implied by synthetic execution.

## Remaining work

The current bank-return outcomes still authorize replacement or closure. Deduction/DV correction after an actually released and returned check, remitted-withholding corrections and generated-history adoption remain unfinished. Continue these and the preserved M01/M03, actual inventory, ordinary-office, exact-output, usability/WFH and operational/LGU gates in [the handoff](../CONTINUE.md) and [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md). See [the earlier cancelled-check checkpoint](FINANCE_CANCELLED_CHECK_CORRECTIONS_2026-09-12.md) and [native testing](FINANCE_NATIVE_TESTING.md).


Final checks: PASS — system/migration drift (`.tmp/invoice_checks.py`), affected-file compilation, diff whitespace and local document links. No runtime/test edits followed the final native/dependent launches. Both runners destroyed their disposable stores; the verified owned MySQL server is stopped and port 33308 is closed. User DB SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. Unrelated drafts/screenshots are excluded. No eGAPS access, live migration, master merge or deployment. Version Manager uses explicit checkpoint staging and managed updates limited to VERSION/CHANGELOG, preserving historical references; verify actual remote branch/tag on resume.
