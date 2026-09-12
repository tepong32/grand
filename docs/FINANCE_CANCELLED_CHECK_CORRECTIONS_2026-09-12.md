# Deduction correction after check cancellation

v0.7.89 development checkpoint on `codex/finance-cancelled-check-corrections`, based on pushed v0.7.88 (`ee24bab`). This advances the remaining M02 correction work. Generated-history adoption, corrections after released/bank-returned payments or remitted withholding, and the broader Finance/operational/LGU gates remain open.

## Office behavior

A prior-payable DV with an incorrect posted deduction previously could not be corrected once any check record existed, even after every unreleased check was cancelled. The existing exact deduction-reversal route now accepts a reconciled cancelled cycle:

- Under payment-at-release accounting, cancellation retains an explicit no-entry decision and must have no payment journal.
- Under payment-at-issuance accounting, the original payment and its exact independently posted cancellation must reconcile before requesting correction.
- Every check must be cancelled and unreleased; the actual correction date cannot precede cancellation or its posting dates. Outstanding payment postings block correction. Existing remittance/correction balance protection remains authoritative.
- The correction pins check identity, amount, cancellation actor/date/reason and payment-request checksums. Materialization and completion reproduce this evidence. No check or posted journal is deleted or rewritten.
- After independent posting of the deduction reversal, Accounting prepares the corrected DV with fresh approval and signatures. Treasury issues a new check against its newly validated amount. Earlier cancelled checks remain in history and cannot be selected or submitted as replacements of the corrected DV.
- Controlled signing-copy preparation recognizes checks retired by the posted correction. Active or unresolved checks retain the existing block. Old print/output evidence follows existing supersession behavior.

## Financial boundary

Use the existing case lock shared by issuance, cancellation and correction. No new ledger or schema is introduced. Cancellation evidence is added only to new correction payloads that use it; old correction payloads and checksums remain unchanged. Current read and mutation paths verify the posted correction before treating old checks as retired. The existing source/fund/reservation locking, independent posting, dated capacity and recoverable cross-store handoff remain in force.

Discarded/superseded payment-event requests require additional reconciliation and remain blocked here. This checkpoint does not authorize adopting generated journals into historical claims, rewriting tax evidence, or correcting a payment that has actually been released without its downstream governed resolution.

See [the earlier deduction boundary](FINANCE_DEDUCTION_CORRECTIONS_2026-09-10.md), [shared claims](FINANCE_SHARED_APPLICATIONS_IN_PROGRESS.md), [native testing](FINANCE_NATIVE_TESTING.md), and [current handoff](../CONTINUE.md).

## Validation

- FAIL - PRE-EXISTING (functional limitation reproduced) — two actual issued/cancelled scenarios both reached Treasury check preparation but correction was rejected by the unconditional instrument-exists guard. `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_cancelled_check_corrections.CancelledCheckCorrectionTests.test_cancelled_release_time_check_allows_deduction_correction vouchers.test_cancelled_check_corrections.CancelledCheckCorrectionTests.test_posted_issuance_and_exact_cancellation_allow_deduction_correction`; two tests, two expected reproduction errors, 3.168 seconds; `.tmp/cancelled-corrections-before.log`, runner 82682 exited 1. No source guard was bypassed in the reproductions.
- PASS — initial correction plus inherited deduction regressions: eight tests, 6.105 seconds; `.tmp/cancelled-corrections-first.log`, runner 23906 exited 0. This preceded complete corrected-payment scenarios and additional posting-evidence checks.
- PASS — extended SQLite scenarios: ten tests, 7.747 seconds; `.tmp/cancelled-corrections-cycle.log`, runner 84683 exited 0. Both accounting policies reach corrected DV validation, new check/advice/release, completed case and claim CSV (1,500 original / 1,000 applied / 500 outstanding). Old-check replacement is rejected and hidden; changed cancellation evidence and correction dates before cancellation are rejected. Later posting-evidence refinements are covered by the final native/dependent runs below.
- PASS — fresh native MySQL: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cancelled_check_corrections.CancelledCheckCorrectionTests vouchers.test_cancelled_correction_concurrency.CancelledCorrectionConcurrencyTests`; `.tmp/cancelled-corrections-native.log`, runner 90054 exited 0: 12 tests, 17.147 seconds. Includes replacement versus correction using the same case version, plus existing remittance/materialization/withdrawal races.
- PASS — dependent SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers accounting reporting`; `.tmp/cancelled-corrections-dependent.log`, runner 36626 exited 0: 493 discovered / 464 passed / 29 native-only skips, 289.409 seconds. This preceded the final signing-copy selector change; full-project validation below covers that final change. Broad scope covers shared voucher services/forms/printing, claim posting/capacity and retained report paths.
- PASS — protected user `db.sqlite3` SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`; diff whitespace check passes. No eGAPS access or user-store migration. Preserve unrelated drafts/screenshots.
- NOT RUN - OUT OF SCOPE — real office acceptance, exact local printer/form acceptance and production operational scrutiny. These synthetic scenarios do not establish complete Finance parity. No browser layout change was made; conditional form controls are exercised through Django responses/forms.

### Final checkpoint evidence

- PASS — intermediate final HTTP scenarios on MySQL: ten tests, 11.202 seconds; `.tmp/cancelled-corrections-final-native.log`, runner 64471 exited 0. The synthetic issuance policy is configured before DV validation. This preceded the signing-copy queue refinement.
- PASS — final `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cancelled_check_corrections.CancelledCheckCorrectionTests`: 10 tests, 13.566 seconds; `.tmp/cancelled-corrections-print-native.log`, runner 40880 exited 0. Actual HTTP correction, corrected signing-copy queue and generated workbook, print recording, packet assembly, wet-signature return, new validation/check/advice/release and claim CSV pass under both payment policies. Synthetic print records do not establish physical printer or operator acceptance.
- PASS — final full-project `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`: 893 discovered / 864 passed / 29 skipped, 453.210 seconds; `.tmp/cancelled-corrections-project.log`, runner 22119 exited 0. Full scope covers the shared voucher/print selectors and Finance work views as a release gate; skips are not passes. No runtime/test changes followed this launch.
- PASS — system/migration-drift checks (`.tmp/invoice_checks.py`), affected-file compilation and diff checks. All runners exited and destroyed their disposable stores. The verified owned MySQL server is stopped, port 33308 closed. The protected user database hash remains unchanged. No eGAPS access, user-store migration, master merge or deployment.
- Version Manager prepares v0.7.89 with explicit staging and managed updates limited to VERSION/CHANGELOG, preserving historical references and unrelated work. Verify the actual branch/tag remote state when resuming. Remaining Finance functionality and acceptance are not complete.
