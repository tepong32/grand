# Actual receipts into another authorized bank account

v0.7.97 development checkpoint on `codex/finance-receipt-bank-routing`, based on v0.7.96 (`086e508`). Extends [actual remittance receipts](FINANCE_REMITTANCE_RETURNS_IN_PROGRESS.md) and [posted receipt corrections](FINANCE_POSTED_RECEIPT_CORRECTIONS_2026-09-12.md).

Treasury can select the bank account that actually received returned money. The original account remains the default, preserving existing proposal/checksum shapes when no alternate bank is selected. Other choices come from the same Accounting office's active approved Finance setup and must be effective for the actual receipt date. The original fund and liability allocations remain unchanged.

An alternate account requires one explicit active bank-code mapping to an active posting asset account in that Accounting office. A generic wildcard mapping cannot identify an alternate receiving bank. The proposal retains the selected setup item/release/version, bank code/label, mapping identity and ledger account identity/code/title. Independent review rechecks that evidence; a changed mapping requires a fresh proposal. After approval, posting uses the retained ledger account, so a later mapping edit cannot redirect the receipt. An unavailable approved account blocks new posting rather than selecting another account implicitly.

The incoming JEV debits the actual receiving account and restores only the original allocated withholding. Its cash-flow purpose remains the original remittance purpose. Receipt posting-error correction reverses that actual incoming account through the existing exact reversal workflow. The remittance page displays the selected bank, and receipt exports include original and receiving ledger account codes and the receiving bank code. No posted source, prior proposal or original payment is rewritten.

## Validation

- FAIL - CAUSED BY CURRENT WORK: initial focused runner 49100, 16 tests in 17.213s with three errors (`.tmp/receipt-banks-focused.log`). The new helper referenced a nonexistent Finance release UUID; fixed to retain its existing release ID and code.
- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_receipt_banks`: 16 discovered / 16 passed / 0 skipped, 17.152 seconds; `.tmp/receipt-banks-focused-final.log`, runner 42412 exited 0.
- PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_receipt_banks`: 16 discovered / 16 passed / 0 skipped, 29.536 seconds; `.tmp/receipt-banks-native.log`, runner 55069 exited 0. The native run was still preparing stores when the helper was fixed; its alternate-bank scenarios execute the corrected helper (the original helper fails those scenarios). The final focused run also started after the fix.
- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers finance.test_work_tasks`: 396 discovered / 375 passed / 21 skipped, 395.040 seconds; `.tmp/receipt-banks-dependent.log`, runner 7759 exited 0. This covers the changed receipt proposal/form/export and dependent remittance, correction and My Work behavior, including the new bank scenarios after the helper fix.
- PASS: `.tmp/invoice_checks.py` system/migration drift, affected syntax, local document links, diff whitespace and retained post-fix source hashes.
- NOT RUN - OUT OF SCOPE: repeated full non-voucher project suite or new concurrency suite. No schema, shared posting validator, reservation boundary or lock order changed. The new stored receiving-bank shape runs on MySQL and the existing workflows run above. v0.7.96 remains the broad baseline (1005 discovered / 959 passed / 46 skipped, plus 24 native tests). These prior results are not new runs for this checkpoint.
- NOT RUN - OUT OF SCOPE: separate browser layout/physical printing, real bank/agency interaction and LGU acceptance.

All runners ended and disposable test stores were destroyed. The owned MySQL server was stopped and port 33308 verified closed. Operator DB SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. No schema change or operator migration. Version Manager uses an explicit manifest and updates VERSION/CHANGELOG automatically, preserving historical references and unrelated work. Verify remote branch/tag on resume. No master merge, deployment or eGAPS access.

## Remaining scope

This adds explicit gross receipt bank routing. Deducted fees/netted receipts, actual outgoing agency repayments and non-cash agency credit/offset dispositions remain open. The original fund is retained; this is not an inter-fund transfer. Setup selection and independent receipt review do not establish actual bank/agency or LGU acceptance. Preserve the full Finance, generated-history, inventory, office/output/usability/WFH and operational acceptance goals in [CONTINUE.md](../CONTINUE.md).
