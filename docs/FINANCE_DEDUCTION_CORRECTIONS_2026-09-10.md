# Posted deduction correction before payment

Checkpoint v0.7.82 on `codex/finance-deduction-corrections`, based on pushed v0.7.81 (`ebe2f85`). This advances M02 under the [Finance modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md). Production remains **NO-GO**.

## Functional coverage

| Office action | Implemented result and boundary |
|---|---|
| Correct a posted prior-payable deduction | The owning Accounting office records an actual correction date/reason. The original posted adjustment, rule checksum, claim reservation and withholding identities remain pinned in an existing posting request. |
| Protect Treasury's reserved balance | Pending corrections reserve their withholding amount. Remittance reservation and correction creation serialize on the Accounting owner's default-store row. The identity spans setup-release versions. Already-reserved/remitted balances cannot be reused by this route. |
| Create the reversal | The draft mirrors the original journal's exact accounts, amounts, sides, subsidiary/tax evidence and claim reservation. Current mapping changes cannot silently substitute another account. This is an exact source reversal, not a fabricated replacement posting rule or legacy pre-F7 recipe. |
| Independently post and reopen | Existing journal posting authority and maker-checker controls apply. Only a posted exact reversal with zero remaining applications retires the old gross-claim hold. The DV returns to preparation with prior print/signature evidence superseded and original journals retained. |
| Correct and pay | New DV deductions undergo new signatures, validation and posting against a fresh reservation of the same original claim. Payment reduces that claim without another expense. The claim CSV retains the full dated application history. |
| Report tax changes | Reversal subsidiary lines retain the original governed tax snapshot and actual reversal ancestry. Signed tax movements cancel the original report amount; the earlier source remains reproducible. Remittance balances group by deduction identity, not changeable display labels. |
| Withdraw before posting | A reasoned withdrawal retains the original deduction and returns to Treasury preparation. An existing draft must be discarded first; its governed successor may then be withdrawn. A posted correction cannot be withdrawn. |
| Recover interrupted work | Default/Finance materialization and posting handoffs can be retried without duplicate reversal. If Finance retires the old hold before the default DV return completes, the same immutable correction decision completes recovery. |

## Design decision and remaining scope

The existing `VoucherPostingRequest`, journal/reversal, subsidiary and reservation mechanisms remain authoritative; no new model, schema migration or configuration framework was added. D-075 in [implementation decisions](IMPLEMENTATION_DECISIONS.md) records why a corrective reversal follows its original journal rather than a new configurable posting recipe.

Correction materialization/withdrawal/synchronization use the case lock; native reversal creation locks its original adjustment and claim source. Native source-presence checks include drafts whose default link failed. Withholding holds deliberately remain conservative until posting synchronization completes. A transient double deduction from displayed availability during an interrupted cross-store posting must not be treated as free remittance capacity.

This route is **before any payment instrument exists** and requires enough unreserved posted withholding balance. It does not implement post-issuance correction, correction/refund of already-remitted taxes, amended external filings, historical claim attribution or consolidated multi-claim DVs. Those remain financial work, not completed acceptance gates. Existing general journal/manual-adjustment operations are not a claim of global withholding-reservation enforcement. Exact local forms, eGAPS inventory, ordinary office scenarios, usability/WFH and operational/LGU acceptance also remain open.

See [prior-payable settlement](FINANCE_PRIOR_PAYABLE_DV_2026-09-10.md), [earlier accruals](FINANCE_EARLIER_ACCRUAL_2026-09-10.md) and the [continuation handoff](../CONTINUE.md).

## Validation

Final PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_deduction_corrections`, all six tests in 5.157 seconds. Final PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_deduction_corrections vouchers.test_deduction_correction_concurrency`, all seven tests in 9.884 seconds. These runs cover the final functional code and the repaired discarded-source successor: correction-to-payment/CSV, repeated signed-tax reversal, authorization/date/issued-instrument guards, interrupted native/default recovery, withdrawal, competing remittance/correction holds, duplicate materialization and withdrawal/creation races.

PASS: `manage.py check`, `manage.py makemigrations --check --dry-run`, compilation, diff checks and local documentation links. No schema change. The broader 582-test run below passed before the narrow final withdrawal/successor work; it was not repeated after that repair.

NOT RUN - OUT OF SCOPE: full-project/full-native regression, real office printing/forms, external filing amendments, actual WFH and production operational/LGU acceptance. The affected Finance suite and explicit native source/reservation/recovery races were selected for this checkpoint. No production acceptance is inferred from synthetic tests.

- Initial SQLite command: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_deduction_corrections`, four tests in 3.596 seconds: one pass, one UI failure and two fixture errors. The owning-office correction button was incorrectly nested under the current-routing return permission; it was moved to its own ownership gate. A payment-denial assertion now accepts the earlier office-permission rejection, and the remittance fixture now reuses the already configured bank instead of trying to create it twice.
- Initial native command: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_deduction_corrections`, four tests in 4.260 seconds: two passed, the same two fixture errors. The page used the corrected template by then. These are FAIL - CAUSED BY CURRENT WORK, not pre-existing failures.
- Corrected SQLite four-test run PASS, 4.273 seconds. The later five-test run including repeated correction/governed signed-tax output PASS, 5.399 seconds. Both preceded unposted withdrawal coverage.
- An intermediate native six-test command failed during URL import because it overlapped the addition of the withdrawal form and loaded old forms with updated views. No native test completion is claimed for that mixed-source run. Final reruns use the stable final implementation.

The ignored wrappers invoke Django's ordinary test command and the committed fresh two-store MySQL runner, with separate development log files. The native server is the owned loopback MySQL 8.4.11 fixture at port 33308. No eGAPS access or user-store migration is part of this work. The user database and unrelated policy-concurrency draft remain outside the checkpoint.

- PASS: `.venv/Scripts/python.exe manage.py test vouchers accounting finance reporting departments --noinput`, 582 discovered / 570 passed / 12 native-only skips, 294.859 seconds. This broad run covers the correction/remittance integration and existing Finance regressions; it preceded the final withdrawal/successor repair.
- FAIL - CAUSED BY CURRENT WORK: withdrawal coverage exposed the generic discarded-draft handler's assumption that every event has a posting recipe. SQLite six tests: five passed / one error, 5.411 seconds. Native seven tests: five passed / two errors, 9.100 seconds; the concurrency test reached the same missing-successor failure after its earlier reservation/materialization assertions. The repair recognizes a verified, discarded exact-source correction, checks owner/source identity and locks its case before creating the existing governed successor.

All runners ended; the owned MySQL server was stopped and loopback port 33308 verified closed. The user database retains SHA-256 `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. No eGAPS access or user-store migration occurred; the unrelated policy-concurrency draft remains unmodified/uncommitted.
