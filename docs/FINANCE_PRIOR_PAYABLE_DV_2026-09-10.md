# Prior-payable DV settlement

v0.7.80 on `codex/finance-prior-payable-dv`, based on v0.7.79 (`3ea35c2`). Read the validation results and remaining boundaries below. Production remains **NO-GO**.

## Office workflow

The earlier-accrual and existing-payable intake decisions can select an independently posted original claim during Accounting validation. The selected source must match the governed payee key, fund, Accounting ledger and date. This route settles an existing liability; it does not debit the original expense again.

| Step | Accounting result | Workflow result |
|---|---|---|
| Select a prior claim with no deductions | No new recognition JEV | Reserve DV gross against the claim; proceed to Treasury |
| Select a prior claim with deductions | Debit original payable; credit configured withholding/deduction liabilities | Existing independent JEV preparation/posting/reconciliation before Treasury |
| Pay at configured issuance or release | Debit original payable; credit mapped bank | Retain the existing payment, advice, custody and release controls |
| Cancel before release under a release-time policy | No financial entry | Keep reservation for replacement and retain the explicit no-entry decision |
| Cancel an issuance-time payment | Exact reversal of the original payment JEV | Restore the same reservation; replacement needs its own governed payment entry |
| Bank returns a released payment unpaid | Exact reversal of the original posted payment JEV | Existing independent returned-item review; hold restored amount for replacement |
| Close the bank return without replacement | Retain the posted reversal and any earlier deduction applications | Release only the unused reservation after independent posting; recover a failed default-store closing update from the same retained decision |
| Return an unused DV for correction | Release unused source reservation with actor/date/reason | Existing allowed return routes and a new validation decision |
| Attempt to consume held capacity from another DV or manual JEV | Refuse conflicting reservation/posting | Preserve the previously retained claim commitment |

The case detail retains validation records, amounts and links to original JEVs. The existing archived claim CSV reproduces recognized, applied and outstanding ledger amounts after actual settlement. Its outstanding amount is an accounting balance, not free capacity: an unpaid DV reservation still occupies part of that balance.

One DV currently selects one original claim and one fund, including a partial amount of that claim. Multiple DVs may settle separate portions when total capacity permits. This does not establish consolidated multi-claim DVs or automatically attribute historical unnamed liabilities.

## Retained evidence and separate stores

`PayableClaimReservation` lives in Finance. It retains the original journal line, source snapshot/checksum, case UUID, reserved amount and actor. It is a commitment against existing journal capacity, not another payable ledger or a replacement for Treasury cash reservations. Accounting validation and governed posting payloads in the default store retain the reservation UUID and identical source evidence. No cross-database foreign key or database merge is introduced.

All source-capacity writers lock the original credit line. Reservation capture locks that row without joining/locking its fund; mixed recognition/application entries retain their fund-before-source order. Capacity subtracts posted applications and the unused portions of active reservations. Applications carrying a reservation consume that reservation, rather than charging capacity twice. The existing dated application checks still reject backdated overpayment. A reversal restores the same reservation; a fully consumed reservation remains as evidence, with zero unused capacity. The validator must belong to the source Accounting ledger even if a case was routed to another office.

The default-store case lock serializes validation decisions for one case. A deterministic case/state-version key recovers an already committed Finance reservation when the subsequent default-store decision fails. A retry with different source/amount refuses to repurpose that retained evidence. Use the existing return-for-correction action to release a pristine reservation and advance to a new validation version. That correction route refuses release while non-voided journal applications or unresolved instruments remain. If the Finance release commits but the default return fails, the same return can be retried; released evidence cannot authorize payment.

The separate close-without-replacement outcome retires unused capacity only after the reviewed bank-return reversal is independently posted. Prior posted deductions remain applied; the closing decision does not silently reverse them. Other pending posting requests/applications block retirement. A Finance retirement followed by a failed default-store closure is recoverable through the same retained review/JEV identity. Subsequent DVs can reserve the remaining original claim amount.

Draft generation retains the existing recoverable posting request identity. If Finance saves the JEV but the default-store link fails, retry locates and verifies the same JEV. Materialization and release serialize on the source claim, so a released hold cannot acquire a new draft unnoticed. Posting remains an independent Accounting decision, followed by the existing stored-evidence reconciliation.

Generated returns pin exact original payment lineage. Account, amount, side, fund, claim and reservation must mirror the original, with original line sequence and cash purpose retained. A detached manual reversal of a reserved voucher JEV is refused because it would leave the operational payment workflow unchanged. Other original/manual claim reversal behavior is preserved.

## Governed rules

Use the existing versioned Finance posting-rule editor. A new `prior_payable` account source resolves the explicitly selected original claim. Existing `payable_mapping` instructions are accepted only when their configured account is that same liability account.

- Deductions at DV validation: exactly one debit to prior payable using total deductions, and one repeated credit instruction using each configured deduction mapping.
- Payment/replacement: exactly one debit to prior payable and one bank credit, both using the event amount.
- Cancellation/return with ledger effect: the corresponding exact reversed pair.
- Issuance-time payments require journal-producing cancellation and replacement policies. Release-time payments retain no-entry pre-release cancellation/replacement policies and journal-producing actual release/return rules.

Validation, issuance and release check supported policy shape. No expense/allocation instruction can silently replace settlement. These are implementation constraints for this supported route, not claims that one universal recipe satisfies every LGU transaction or future COA rule.

## Validation record

- Initial SQLite: 10 discovered; five existing claim tests passed and five new tests failed because the new synthetic intake fixture used incorrect field names. Fixture corrected.
- Second SQLite: 10 discovered; nine passed, one selector test failed because its default-store allocation queryset was embedded in a Finance query. Native first run: 14 discovered; 13 passed, the same selector failed. The four native race tests passed, including competing reservations and manual-posting/reservation contention. The selector now materializes fund codes before querying Finance.
- PASS: expanded native run, 17 tests in 9.912 seconds, including HTTP validation/UAT denial, claim CSV, both payment timings, cancellations, returned replacement, source holds and four races. A strengthened interrupted-draft/core-return check passed separately on native MySQL: one test in 2.911 seconds.
- PASS: `.venv/Scripts/python.exe manage.py test --noinput`, 766 discovered / 757 passed / nine skipped in 332.350 seconds. This preceded the final close-without-replacement retirement path.
- PASS: `.venv/Scripts/python.exe manage.py test vouchers accounting reporting finance departments --noinput`, 569 discovered / 560 passed / nine skipped in 291.275 seconds. Covers the closing path and Finance dependencies after the earlier full-project run. The subsequent owning-ledger guard and source-only lock query are covered by their focused native checks below.
- PASS: `.venv/Scripts/python.exe .tmp/portable_mysql.py test vouchers.test_prior_payables accounting.test_payable_claims accounting.test_payable_claim_concurrency accounting.test_payable_reservations_concurrency`, 18 tests in 11.612 seconds. Includes close-without-replacement, a Finance retirement followed by interrupted default-store closure, recovery and a new DV using the remaining claim balance.
- PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py`, one test in 3.188 seconds. This wrapper invokes the committed native runner for `vouchers.test_prior_payables.PriorPayableDVTests.test_http_validation_and_uat_denial`, isolating its development log. It verifies UAT denial, denial in a differently assigned office even when routed there, and successful owning-office HTTP validation.
- PASS: `.venv/Scripts/python.exe .tmp/prior_native_authority.py accounting.test_payable_reservations_concurrency`, three tests in 5.082 seconds. Final source-only locking passes competing reservations, manual application/reservation contention, and mixed transfer-recognition/reservation contention without duplicate capacity. This adds the final native-only transfer race after the broad discovery counts above.
- PASS: `.venv/Scripts/python.exe manage.py check`; `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run`; `.venv/Scripts/python.exe -m compileall -q accounting finance reporting vouchers`; local document-link checks and `git diff --check`.

The initial/repeated focused SQLite command was `.venv/Scripts/python.exe manage.py test vouchers.test_prior_payables accounting.test_payable_claims --noinput`. Native initial/core runs used the same four module labels as the 18-test command above. The strengthened draft-recovery test ran with `.venv/Scripts/python.exe .tmp/portable_mysql.py test vouchers.test_prior_payables.PriorPayableDVTests.test_finance_draft_survives_interrupted_core_link_and_recovers_once`.

Run limitation: parallel Django commands shared the existing development `logs/app.log` rotating handler. Windows emitted `WinError 32` rotation errors while another process held that log; the unittest commands completed with the results above. This is not a passing multi-process logging check. The final focused native wrapper isolates logging; production/logging operational scrutiny remains separate. No application logging configuration was changed.

NOT RUN - OUT OF SCOPE: full native-project regression, actual printing, real office/form acceptance and production recovery. Full SQLite plus affected Finance regression and explicit native financial/cross-store/concurrency scenarios were selected for this checkpoint; they do not replace the remaining release and operational gates.

All test records use disposable synthetic stores. All runners ended; the owned native server was stopped and loopback port 33308 verified closed. User `db.sqlite3` retains SHA-256 `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. No user-store migration or eGAPS access was performed. The unrelated untracked policy-concurrency draft remains outside this checkpoint.

## Remaining M02 and acceptance work

Complete configured earlier-accrual request generation at the actual recognition point, controlled historical attribution and the remaining financial correction routes. This path requires an existing named posted claim; choosing an earlier-accrual decision does not itself generate the earlier JEV. A posted deduction adjustment cannot simply be returned and rewritten; a governed correction/replacement path is still required for that scenario. Consolidated multi-claim settlement is not implemented here.

Continue [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md) and the [Finance roadmap](FINANCE_ROADMAP.md). Exact forms, actual eGAPS inventory, ordinary office scenarios, usability, operational scrutiny and real LGU acceptance remain separate unfinished gates. The [original claim checkpoint](FINANCE_PAYABLE_CLAIMS_2026-09-10.md) retains its historical scope; this document records its DV integration.
