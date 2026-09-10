# Consolidated prior-payable DV settlement

Status: v0.7.85 software checkpoint implemented and validated on `codex/finance-consolidated-dv`, based on v0.7.84 (`245a7d2`). This is not a claim of complete Finance coverage or production readiness.

## Intended office outcome

Accounting selects several original invoice claims for one payee and fund, enters each gross share of the DV and explicitly distributes each existing deduction line. Treasury retains each claim's share of a check. A partial check needs explicit shares; paying the exact remaining amount can use the uniquely determined remaining allocation. Returns and replacements preserve the original instrument's allocation.

The original expense is not recognized again. The existing governed liability instruction expands into original-claim application lines; deduction and bank counterparts retain their actual amounts. Different liability accounts require the original-claim instruction or a mapping that matches every selected account.

## Implemented behavior

- One immutable Finance reservation group records the exact DV, settlement date, payee, fund, claim gross/net shares and per-deduction allocations. Deterministic case/version identity supports recovery across the separate stores.
- All original source credits are locked in ascending order; the group and every member reservation commit together. Recovery rejects changed amounts or deduction shares.
- Existing single-claim evidence remains readable without backfilling a group or changing historical snapshots.
- Instrument allocation evidence is retained separately from the DV allocation. Payment, cancellation and replacement use exact retained shares.
- Accounting validation includes an expandable allocation table. Invalid validation/check submissions retain their entered form values.
- Posted deduction correction mirrors every source application and retires the group atomically after independent posting.

## Partial return and replacement behavior

Partial returned-check closure now records immutable retirement shares against the exact independently posted reversal. It preserves the other check allocations and applies the retirement on its actual date for capacity checks. Replacement advice includes already-released checks in the net control; resolved returned instruments no longer keep a fully paid replacement case in the release queue. Direct/HTTP, selected native concurrency/recovery and full project regression pass as recorded below. Claim CSV amounts and visible gross/deduction/net/check shares are covered. Exact local forms, large-register performance and browser/named-user acceptance remain separate gates.

## Validation record

| Run | Scope and outcome |
|---|---|
| `.tmp/consolidated-focused.log` | 22 SQLite tests: 20 passed; two new fixture errors (wrong withholding-account attribute and treating the correction service's returned case as a request), 35.888 seconds. Corrected. |
| `.tmp/consolidated-focused-final.log` | 26 SQLite tests: 24 passed; two new return fixtures lacked the reviewed Treasury cash policy, 16.975 seconds. Corrected. |
| `.tmp/consolidated-native.log` | 30 MySQL tests: 28 passed; the same two missing-policy fixture errors, 26.611 seconds. No native race failure. |
| `.tmp/consolidated-return-sqlite.log` | **PASS:** all seven new consolidated scenarios, 7.321 seconds. |
| `.tmp/consolidated-native-final.log` | **PASS:** all 31 selected MySQL tests, 29.817 seconds; includes the seven new scenarios, existing single-claim/deduction/date paths and four selected native claim/group races. |
| `.tmp/consolidated-project-regression.log` | Full project: 805 discovered, 787 passed, 17 native-only skips, one older Budget scenario error, 313.377 seconds. It requested an earlier accrual with no actual date/recognition setup. |
| `.tmp/consolidated-baseline-reproduction.log` | **FAIL — PRE-EXISTING:** the exact Budget error reproduced on clean detached v0.7.84 `245a7d2`, one test, 2.753 seconds. Neither the test nor the earlier-accrual service had been changed by this implementation. |
| `.tmp/consolidated-budget-fixture.log` | **PASS:** corrected Budget scenario, one test, 2.742 seconds. It now proves rejection of missing accrual evidence, then exercises its configured ordinary DV-recognition relationship/export route. Actual earlier accrual remains covered by `vouchers.test_earlier_accruals`. No runtime guard was relaxed. |
| `.tmp/consolidated-project-regression-final.log` | **PASS:** 805 discovered / 788 passed / 17 native-only skips, 313.148 seconds. Required because shared payment/advice/model and claim-capacity contracts changed. No runtime edits followed this run; only continuity documentation was finalized. |

Commands:

```text
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_consolidated_payables vouchers.test_prior_payables vouchers.test_deduction_corrections
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_consolidated_payables vouchers.test_prior_payables vouchers.test_deduction_corrections accounting.test_dated_claim_reservations
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_consolidated_payables
.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_consolidated_payables accounting.test_claim_group_concurrency accounting.test_payable_claim_concurrency accounting.test_dated_claim_reservations vouchers.test_prior_payables vouchers.test_deduction_corrections
.venv/Scripts/python.exe .tmp/earlier_sqlite.py
.venv/Scripts/python.exe .tmp/earlier_sqlite.py budget.tests.AnnualBudgetPreparationTests.test_payable_relationships_recognition_modification_window_and_portable_export
```

The SQLite wrapper changes only disposable runtime-log destinations before calling Django's test runner. The baseline reproduction used that wrapper in a clean detached v0.7.84 worktree, with separate disposable stores/logs; the verified temporary worktree was removed after its runner ended. The native wrapper invokes the committed [fresh two-store runner](FINANCE_NATIVE_TESTING.md) using the private owned fixture configuration; no credentials are included in this report. Both wrappers are local ignored helpers. Reproduce the corresponding labels with the documented project/native runners. Local full discovery includes two untouched native-only drafts in untracked `accounting/test_policy_concurrency.py`; they remain excluded from this commit and are not counted as passes.

The seven new scenarios cover actual HTTP allocation and invalid-form retention; gross/deduction/payment split; original-claim CSV amounts; bank return/replacement; atomic reservation rollback and interrupted default-store recovery; explicit partial checks and cancellation; exact posted deduction correction; partial closing-return recovery and dated capacity; and replacement advice with another already-paid check. They do not establish every possible concurrent workflow or named-user acceptance.

System, migration-drift, touched-file compilation, diff and local documentation-link checks pass. Migrations accounting/0020–0021 and vouchers/0025 were generated/tested in disposable stores only. The native runner ended, the owned MySQL fixture was stopped and its listener closed. User DB hash remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. All test runners ended. No eGAPS access. Browser/named-user/form-stock/printer/UAT and operational/LGU acceptance: **NOT RUN — OUT OF SCOPE** for this software checkpoint. Full native project regression is not claimed.

## Continuing boundaries

This work allocates a DV across independently identified original claims. It does not split a consolidated historical source journal line into multiple claims. Historical generated-cycle adoption, post-instrument/remitted-withholding correction, collection/liquidation breadth, exact local forms, usability and operational/LGU acceptance remain open under the [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md).

See [historical claim attribution](FINANCE_HISTORICAL_CLAIMS_2026-09-10.md), [prior-payable settlement](FINANCE_PRIOR_PAYABLE_DV_2026-09-10.md), [dated capacity](FINANCE_DATED_CLAIM_RESERVATIONS_2026-09-10.md), [posted deduction correction](FINANCE_DEDUCTION_CORRECTIONS_2026-09-10.md), and [continuation](../CONTINUE.md).
