# Returned remittance to corrected settlement

v0.7.95 validation checkpoint on `codex/finance-returned-remittance-settlement`, based on v0.7.94 (`a63c605`). This closes an end-to-end evidence gap in [actual remittance returns](FINANCE_REMITTANCE_RETURNS_IN_PROGRESS.md); it does not add a posted-receipt correction route.

## Ordinary scenario

The synthetic two-store scenario starts with a posted invoice deduction of 100 and an actual outward remittance of 100. Treasury records the actual refund of 100 against the original liability, an independent Accounting reviewer approves it, and a separate incoming JEV is independently posted and reconciled. A deduction correction dated after the refund reverses the original adjustment; staff prepare a fresh DV with a corrected deduction of 50, complete its signature handoff and independent Accounting validation, and post the adjustment and actual payment.

The test then remits the corrected 50 through Treasury preparation, independent review, release, journal creation, posting and reconciliation. Withholding must move from 100 restored, through the correction and new 50 deduction, to zero after the corrected remittance. The invoice claim must retain 500 outstanding after 1,000 is settled from its original 1,500. The old outward remittance and refund remain separately posted and unchanged; their CSV exports retain their own JEV identities. The claim CSV must reproduce 1,500 / 1,000 / 500, and remitting the corrected amount must leave the earlier refund CSV bytes unchanged.

## Validation state

Initial scenario through corrected payment and separate remittance exports: PASS, one SQLite test in 3.182 seconds (`.tmp/returned-remittance-settlement.log`, runner 79375 exited 0).

Final scenario adds the claim CSV and re-remittance of the corrected deduction:

- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_remittance_settlement.ReturnedRemittanceSettlementTests.test_actual_return_corrected_dv_payment_and_retained_outputs` — one scenario, 4.245 seconds; runner 91246 exited 0, `.tmp/returned-remittance-settlement-final.log`.
- PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_returned_remittance_settlement.ReturnedRemittanceSettlementTests.test_actual_return_corrected_dv_payment_and_retained_outputs` — one scenario, 4.398 seconds; runner 96894 exited 0, `.tmp/returned-remittance-settlement-native.log`.
- PASS: Python syntax, local documentation links, diff whitespace and unchanged test-source hash across the final runs.
- NOT RUN - OUT OF SCOPE: broad regression repeat. Only the new regression scenario and documentation change; no production code, schema or posting contract changed. This adds direct workflow evidence to the prior checkpoints, not a new full-suite claim.

Both final runners destroyed their disposable test stores. The owned native server was stopped and loopback port 33308 verified closed. Operator DB SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. No eGAPS operation, master integration, deployment or operator-store migration occurred. Version Manager stages only the test, this evidence document and CONTINUE.md, plus its managed VERSION/CHANGELOG updates; preserve unrelated files and historical release references. Verify the remote development branch and v0.7.95 tag on resume.

Only a regression scenario and documentation change in this phase. The existing broad and native evidence for v0.7.93/v0.7.94 remains historical; this test does not establish full Finance parity, physical printing, real agency acceptance, or complete browser usability. In particular, correcting an incorrectly posted receipt, other receiving banks, fees/netted receipts and agency credit/offset dispositions remain open. Continue the full objective in [CONTINUE.md](../CONTINUE.md).
