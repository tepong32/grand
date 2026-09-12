# Withdrawal of an unposted remittance-return approval

v0.7.94 development checkpoint on `codex/finance-remittance-return-withdrawal`, based on v0.7.93 (`c5559da`). This extends [actual remittance receipts](FINANCE_REMITTANCE_RETURNS_IN_PROGRESS.md), D-082. Final scoped validation passes; broader Finance acceptance remains open.

## Behavior

An authorized independent Accounting reviewer can withdraw an approved return before any receipt JEV remains live. The batch lock serializes withdrawal with receipt proposals and materialization. Withdrawal locks the original Finance journal and every retained receipt JEV in the request/successor chain; any draft, submitted or posted journal blocks it. Staff must discard an unposted draft first. Missing retained journal links or inconsistent source checksums require investigation instead of silently freeing capacity.

Withdrawal cancels the current source request, marks the receipt `withdrawn`, and releases its original-liability allocation for a corrected proposal. It preserves the proposal, original approval actor/date/reason, request history and discarded journal evidence. An append-only withdrawal event records the independent actor, reason and retained source chain. Repeating withdrawal creates no second event. No financial line is created, reversed or erased. Posted receipts, including those still awaiting default-store reconciliation, cannot use this route.

The ordinary remittance detail page offers the action and shows its reason. The return CSV appends withdrawal reason, actor ID and timestamp while retaining the earlier approval columns. A corrected receipt follows fresh independent review and posting. Original payment and filing history remain unchanged. UAT denial and Accounting ownership/maker-checker boundaries remain enforced.

## Validation

- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_remittance_return_withdrawal`: 15 tests, 8.249 seconds (`.tmp/return-withdrawal-focused.log`, runner 99229 exited 0). Includes actual HTTP withdrawal, repeated requests, UAT denial, unchanged approval evidence, corrected receipt posting/export, draft/successor handling and posted-receipt refusal, plus inherited receipt regressions.
- PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_remittance_return_withdrawal vouchers.test_remittance_return_withdrawal_concurrency`: 20 tests, 32.556 seconds (`.tmp/return-withdrawal-native.log`, runner 81539 exited 0). Native races cover withdrawal versus materialization and independent posting, alongside inherited receipt/correction concurrency. Both native test stores were destroyed; the owned server is stopped and port 33308 closed.
- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers finance.test_work_tasks`: Dependent SQLite: 343 discovered / 328 passed / 15 skipped, 242.387 seconds. Native MySQL: 20 passed, 32.556 seconds. (`.tmp/return-withdrawal-dependent.log`, runner 28856 exited 0). All voucher workflows and Finance task consumers cover the new status, source cancellation, receipt capacity and web/export changes.
- PASS: system/migration drift (`.tmp/invoice_checks.py`), affected compilation, local document links and diff whitespace.
- NOT RUN - OUT OF SCOPE: repeat of the complete non-voucher project suite. This bounded pre-posting closure changes no financial calculation, shared journal-posting implementation or Accounting/Budget schema; direct native races and actual source/posting/export services are exercised above. v0.7.93 remains the broad baseline (948 discovered / 913 passed / 35 skipped). Full Finance completion and operational acceptance still require their broad gates.
- NOT RUN - OUT OF SCOPE: separate browser layout/physical printer, actual bank/agency interaction, operator-store migration and LGU acceptance.

Migration vouchers/0027 changes status choices only and ran in disposable stores. All runners ended; owned MySQL stopped and port 33308 closed. Runtime/template hashes remained unchanged since the final launches. User DB SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. Version Manager uses explicit staging and updates VERSION/CHANGELOG only, preserving historical versions and unrelated work. No eGAPS access, master merge or deployment. Verify remote branch/tag on resume.

## Boundaries

This is pre-posting correction of an approval, not an actual outgoing refund or a posted-ledger correction. Later correction of a posted return must account for downstream usage of restored withholding and preserve its journal/source evidence. Different receiving accounts, fees/netted refunds, non-cash agency dispositions, generated-history adoption and the wider Finance/office/output/usability/operational/LGU gates remain open in [CONTINUE.md](../CONTINUE.md). Keep eGAPS and operator stores untouched.
