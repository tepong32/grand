# Correction of an incorrectly posted remittance receipt

v0.7.96 development checkpoint on `codex/finance-posted-receipt-corrections`, based on v0.7.95 (`f4abaa4`). Extends the [actual receipt workflow](FINANCE_REMITTANCE_RETURNS_IN_PROGRESS.md), [unposted withdrawal](FINANCE_RETURN_WITHDRAWAL_2026-09-12.md) and [corrected settlement scenario](FINANCE_RETURNED_REMITTANCE_SETTLEMENT_2026-09-12.md).

## Office behavior

Treasury can propose correction of a receipt entered incorrectly, with its actual correction date, supporting evidence, reason and tax-filing disposition basis. Independent Accounting review creates an exact reversal request. Accounting prepares the JEV and a different user posts it. Reconciliation then marks the original receipt corrected and frees its original-remittance allocation from the correction date onward. A corrected receipt follows fresh entry, review and posting. The original receipt proposal, approval, incoming JEV and original outward remittance remain retained.

This route corrects a posting error. It does not authorize an actual outgoing payment or invent a bank movement. An actual repayment to the agency requires its own governed payment evidence. The implementation reverses the full incorrect receipt before replacement; it does not silently edit individual posted lines.

The remittance page shows correction history and independent review/withdrawal actions. My Work exposes the exact review queue with correction amount and evidence changes. A separate correction CSV retains original and reversing JEV identities, proposal checksum, review and withdrawal evidence. The receipt CSV retains its original posted receipt amount even after correction; the correction CSV explains the separate reversal. Existing tax-filing evidence remains unchanged; any filing amendment still requires its own review.

## Financial and recovery boundaries

- Pending proposals and approvals reserve the restored withholding under the existing Accounting-owner lock. The requested date must fit every subsequent posted withholding boundary and other current reservations. An already consumed or reserved refund cannot fund a second correction. Review checks the existing hold once; rejection releases it.
- The original receipt and correction source are immutable. Both journal submission and posting verify exact mirrored financial rows, subsidiary identities, transaction classification, cash-flow category and original reversal lineage. A changed draft cannot become an independently posted correction merely because it balances.
- Batch-first default-store locks serialize proposal versions, review, filing changes and source successors. Materialization holds the Accounting-owner reservation lock and original receipt Finance journal lock. Competing materializations recover one journal. A Finance commit followed by a failed default-store link is recovered using the original request identity.
- A posted correction remains reserved until operational reconciliation. Reconciliation preserves its source and prior receipt, marks the receipt corrected and releases the allocation atomically in the default store. Replacement receipts cannot consume that allocation before the correction date. Repeating reconciliation preserves both original and correction evidence.
- Independent withdrawal of an approved unposted correction requires every retained correction journal to be discarded. It keeps the original approval and source chain, adds an append-only withdrawal event, cancels the current source and releases its hold. A live or posted journal blocks withdrawal. Discarded source successors retain the same approval payload.
- Migration `vouchers/0028` adds the correction model with unconditional receipt/version uniqueness and the corrected receipt status. No operator-store migration is performed. Native validation is required; SQLite alone does not establish the lock behavior.

## Validation

- PASS: initial focused SQLite, 17 tests in 12.289 seconds (`.tmp/receipt-corrections-focused.log`, runner 58403 exited 0), before final withdrawal support.
- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_receipt_corrections` — 18 discovered / 18 passed / 0 skipped, 16.421 seconds; `.tmp/receipt-corrections-focused-final.log`, runner 49052 exited 0. Covers HTTP proposal/review/withdrawal, UAT denial, My Work, exact reversal, replacement date/allocation, retained approval/export, downstream reserved and posted usage, rejection, interrupted materialization, discarded successor and altered-line submission, plus inherited receipt regressions.
- PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_receipt_corrections vouchers.test_receipt_correction_concurrency` — 24 discovered / 24 passed / 0 skipped, 51.936 seconds; `.tmp/receipt-corrections-native.log`, runner 74635 exited 0. Includes receipt-versus-deduction reservation, duplicate reversal materialization, withdrawal-versus-posting, and inherited native races.
- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py` — full project 1005 discovered / 959 passed / 46 skipped, 626.922 seconds; `.tmp/receipt-corrections-project.log`, runner 45573 exited 0. Broad regression covers the changed withholding availability, schema/status, My Work and conditional shared journal validation. Skipped tests remain skipped, not passes.
- PASS: `.tmp/invoice_checks.py` system/migration drift, affected Python syntax, document links, diff whitespace and unchanged runtime/template hashes across the final launches.
- NOT RUN - OUT OF SCOPE: separate browser layout/physical printer, actual agency/bank interaction, operator-store migration and LGU acceptance. Test flows do not establish these gates.

All runners ended and disposable stores were destroyed. The owned MySQL server was stopped and loopback port 33308 verified closed. Protected operator DB SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. Migration vouchers/0028 ran only in disposable stores. Version Manager uses explicit staging and updates only VERSION/CHANGELOG automatically, preserving historical release references and unrelated work. Verify remote development branch/tag on resume; no master merge, deployment or eGAPS access.

## Remaining work

Different receiving banks, fees/netted receipts, actual outgoing repayments and non-cash agency credit/offset dispositions remain open. This phase does not establish complete remitted-tax correction, generated-history adoption, full Finance parity, exact local print layouts, real tax-filing acceptance or operational/LGU acceptance. Keep the full Finance objective and later inventory, office/output/usability/WFH and assurance gates in [CONTINUE.md](../CONTINUE.md).
