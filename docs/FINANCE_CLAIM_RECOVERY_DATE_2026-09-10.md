# Dated claim recovery

Status: v0.7.86 repair implemented and validated on `codex/finance-claim-recovery-date`, based on v0.7.85 (`e6607dc`). This prerequisite was found while tracing historical source-line allocation; it does not implement source-line splitting or complete the Finance goal.

## Reproduced problem

An interrupted default-store validation leaves its immutable Finance hold available for recovery. The existing-key path verified the original source and amount but skipped the requested-date capacity check used when first creating a hold.

The regression uses a 1,000 original claim, an 800 application on September 4 and an exact reversal on September 8. A 700 hold fits on September 9. Retrying the same hold for September 5 previously succeeded even though only 200 was available then. The new denial test failed before the repair: one test, 0.130 seconds, `ValidationError not raised` (`.tmp/claim-recovery-date-before.log`).

## Repair and scope

Recovery now verifies the retained source, then recomputes capacity for the requested date and subsequent posted movements under the existing original-credit lock. The original hold is already included, so recovery requires nonnegative capacity; it must not reserve the amount twice. A valid retry returns the same reservation and checksum. An invalid retry leaves that hold intact for a valid later retry or an explicit return/correction.

No schema, original financial evidence, posting rule, approval policy or database boundary changes. Consolidated groups continue to require their exact immutable allocation/date snapshot. This repair closes the date-change gap in the existing single-claim retry path; it does not fabricate a historical reservation date.

## Validation

- Before repair: the denial reproduction failed as described above.
- **PASS:** all 39 affected SQLite tests, 24.122 seconds (`.tmp/claim-recovery-date-sqlite.log`).
- **PASS:** all 39 selected native tests, 33.655 seconds, including five reservation races (`.tmp/claim-recovery-date-native.log`).
- New coverage includes an exact-capacity successful retry and an actual interrupted DV validation: reject an earlier retry through the page, retain the original Finance evidence and workflow stage, recover at a valid later date, pay and verify the archived claim CSV.

Commands:

```text
.venv/Scripts/python.exe .tmp/earlier_sqlite.py accounting.test_dated_claim_reservations.DatedClaimReservationTests.test_recovery_cannot_move_a_later_hold_into_an_earlier_shortfall
.venv/Scripts/python.exe .tmp/earlier_sqlite.py accounting.test_dated_claim_reservations accounting.test_payable_claims accounting.test_claim_attributions vouchers.test_prior_payables vouchers.test_consolidated_payables vouchers.test_deduction_corrections
.venv/Scripts/python.exe .tmp/prior_native_authority.py accounting.test_dated_claim_reservations accounting.test_payable_reservations_concurrency accounting.test_claim_group_concurrency accounting.test_claim_attributions vouchers.test_prior_payables vouchers.test_consolidated_payables vouchers.test_deduction_corrections
```

The ignored wrappers only isolate runtime artifacts and invoke the documented Django/[native two-store runner](FINANCE_NATIVE_TESTING.md). No live/user-store migration or eGAPS access. Preserve the existing user database and unrelated policy-test draft.

System, migration-drift, touched-file compilation, diff and local documentation-link checks pass. Both final runners ended; the owned MySQL fixture was stopped and its port closed. The user database hash remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. No migration or original reservation backfill was needed.

The affected claim, attribution, DV, correction and group workflows are the relevant regression boundary for this existing-key guard. The v0.7.85 full project baseline remains separately recorded in [consolidated settlement](FINANCE_CONSOLIDATED_DV_2026-09-10.md). Full project/native suites, browser/named-user/UAT and operational/LGU acceptance: **NOT RUN — OUT OF SCOPE** for this bounded repair. They are not claimed as newly performed or completed.

Continue the planned historical source-line allocations and remaining corrections under the [current handoff](../CONTINUE.md) and [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md).
