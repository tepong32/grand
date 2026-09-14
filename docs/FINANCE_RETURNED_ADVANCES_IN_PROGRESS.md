# Returned advance correction — v0.7.106 checkpoint

Branch `codex/finance-returned-advance-corrections`, based on verified remote v0.7.105
(`119e75b953eae73bb61c4ec40cc0e4d71a2b6ad9`). This record describes the v0.7.106 development checkpoint.
The preceding goal turn published the cancelled/unreleased advance checkpoint.

## Verified gap and current changes

The initial original advance → release → bank exception → independent return review →
posted bank-return JEV scenario could not correct its original recognition: it reached
the cancelled-only guard. Source inspection also showed that ordinary advance bank
returns did not receive the exact original-payment reversal linkage available to prior
payables. Do not open the original-correction guard merely by accepting BANK_RETURNED.

New bank-return requests now carry a distinct `advance_payment_return` purpose and pin
the original payment identity/checksums. Existing `advance_payment_cancellation` payloads
retain their meaning and bytes. The shared materializer preserves exact financial lines,
payable subsidiary evidence and cash-flow purposes. Submission/posting/reconciliation
verify the event kind, recognition point, trigger and retained original payment; default
case locks precede Finance locks. Cash-purpose validation also protects cancellations.

An availability read must recognize the exact reviewed return without rejecting its
otherwise valid original release. The new `released_payment` helper verifies that source
and returns the original payment plus its return proof. Existing observed-date withholding
then reports zero available release. This is not an original-recognition correction or
permission to spend returned money. The original-correction acceptance test was still red
at that source-link checkpoint; the later integration results are recorded below.

## Original-correction integration history

The original-correction increment adds `advance_returned_cycles`: capture the independent
REISSUE review and exact payment/return sources; reject an existing replacement; close
the authorization and resolve its exception in the original-correction reconciliation
transaction. A retained case event pins the review's exact state-version transition.
Later validation compares immutable evidence and verifies the explicit closure instead
of pretending the old review status is still current. Retired original checks are excluded
from the replacement recognition's release calculation only through posted correction proof.

Pending/outstanding liquidation or refund history remains excluded. Independently withdrawn
unposted sources retain their existing validation. The later corrected-liquidation increment
below adds dated proof for posted expense history; the later refund increment extends
that proof to receipts and deposits. Neither increment establishes a release boundary.

PASS: SQLite 29911, 1/1, 12.837s, exit 0 (`.tmp/returned-advance-cycle-sqlite.log`),
tests the full no-application Budget/recognition/replacement-payment cycle. PASS: native
20497, 5/5, 30.374s, exit 0 (`.tmp/returned-advance-retirement-native.log`), tests that cycle, interrupted default-store
closure/retry and changed closure-version rejection, dated availability, and both previous
cancelled-advance payment policies. Both runners have ended.
PASS: SQLite 23087, 2/2, 3.766s, exit 0
(`.tmp/returned-advance-safeguards-sqlite.log`): actual posted liquidation blocks original
correction without altering the expense journal, plus closure/retry/version-rejection
regression. All runners have ended; owned MySQL is stopped and port 33308 has no listener.

Integration commands:

```powershell
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_bank_returned_advance_reaches_corrected_budget_and_payment
.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_bank_returned_advance_reaches_corrected_budget_and_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_return_retirement_rolls_back_and_recovers_after_finance_posting vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_return_withholding_begins_on_observed_date vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment_at_issuance
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_posted_liquidation_blocks_original_returned_advance_correction vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_return_retirement_rolls_back_and_recovers_after_finance_posting
```

## Actual validation

### Final issuance, concurrency and full regression verification

The returned-advance acceptance fixture now exercises actual posting at instrument
issuance as well as posting at release. PASS: SQLite 56532, 2/2, 10.366s, exit 0
(`.tmp/returned-advance-issuance-sqlite.log`), the full corrected Budget/new-payment
cycle and a mixed corrected liquidation/refund/deposit history under issuance policy.
No runtime service changes were needed for those two scenarios.

Native 8944 (`.tmp/returned-advance-issuance-races-native.log`) ran both
issuance scenarios and new `ReturnedAdvanceConcurrencyTests`: correction versus check
replacement, stale review decision versus original-correction closure, and duplicate
reconciliation retaining one closure. Result: 5 tests, 27.837s, exit 1; four passed,
and duplicate reconciliation failed because its expected review version used a stale
fixture instance from before payment-posting reconciliation (actual 4 versus expected 3).
FAIL - CAUSED BY CURRENT WORK, test-fixture expectation. The fixture now refreshes
the persisted review before capturing the starting version; runtime services are unchanged.
These tests use the existing native transaction/race fixture and actual service calls.
PASS: SQLite 25473, 1/1, 3.001s, exit 0 (`.tmp/returned-advance-withdrawal-sqlite.log`),
draft discard/independent withdrawal retaining the reviewed replacement route.

PASS: fresh native 70192, 6/6, 29.099s, exit 0
(`.tmp/returned-advance-issuance-races-fixed-native.log`), two issuance scenarios,
withdrawal and all three races. Full-project SQLite 15478
(`.tmp/returned-advance-full-sqlite.log`) has ended. This is the broad
regression for the complete uncommitted returned-advance service changes, not a Finance
completion claim. Result: 1,195 discovered, 1,108 passed, 86 skipped, one error,
621.333s, exit 1. FAIL - CAUSED BY CURRENT WORK: `refund_setup` called
`self.configure_refund_rules`, but the existing liquidation test borrows `refund_setup`
without inheriting that helper. The fixture now uses an explicit class-qualified call.
Production files have not changed. Native work has ended and owned MySQL is stopped.

PASS: focused SQLite 50804, 3/3, 15.718s, exit 0
(`.tmp/returned-advance-fixture-fix-sqlite.log`), covering the previously failing
liquidation-to-refund scenario, issuance mixed history and existing refund/deposit
regression. PASS: fresh full SQLite 7356, 1,195 discovered / 1,109 passed / 86 skipped,
647.082s, exit 0 (`.tmp/returned-advance-full-fixed-sqlite.log`). This full-project run
covers the final fixture repair; native 70192/29584 cover unchanged production code.
The skipped tests are not passes. Native-specific selected races have their separate
MySQL results above; broader operational/LGU acceptance remains unperformed.

All runners have ended. System checks, migration drift and diff checks pass. The
reviewed Version Manager adapter gates v0.7.106 on the actual completed full SQLite
and final native logs, with explicit files and preserved historical release references.
No master integration, deployment, live migration or eGAPS access is part of this checkpoint.

Commands for issuance/race verification:

```powershell
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_returned_advance_at_issuance_reaches_corrected_budget_and_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_issuance_advance_retains_corrected_liquidation_refund_and_deposit
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_withdrawn_original_correction_preserves_reviewed_replacement_route
.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_returned_advance_at_issuance_reaches_corrected_budget_and_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_issuance_advance_retains_corrected_liquidation_refund_and_deposit vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_withdrawn_original_correction_preserves_reviewed_replacement_route vouchers.test_returned_advance_concurrency.ReturnedAdvanceConcurrencyTests.test_returned_advance_correction_and_replacement_are_exclusive vouchers.test_returned_advance_concurrency.ReturnedAdvanceConcurrencyTests.test_stale_return_decision_cannot_race_original_correction_closure vouchers.test_returned_advance_concurrency.ReturnedAdvanceConcurrencyTests.test_duplicate_reconciliation_retires_return_once
.venv/Scripts/python.exe .tmp/earlier_sqlite.py
```

### Active corrected-refund increment

`advance_corrected_refunds` now checks each receipt and allocated deposit separately:
an independently posted exact correction must exist by the original-correction date.
It retains reviewed source facts, request/rule checksums, full journal rows/subsidiaries
and source snapshots. Original refund identity is validated before capturing history;
replay reproduces retained evidence without authorizing a new use of the reversed
advance. The existing deposit-before-receipt correction rule remains in force. Outstanding
refunds and active/unreconciled corrections block; independently rejected/withdrawn
sources require retained witness and no active journal. No aggregate-zero shortcut.

Initial SQLite 66819 (`.tmp/returned-advance-refund-history-sqlite.log`) exercised
receipt/deposit/corrections through the full Budget/new-payment cycle and changed retained
deposit-decision rejection and FAILED - CAUSED BY CURRENT WORK (1 test, 4.841s, exit 1).
Replay still called the full receipt validator, which tried to reuse the now-reversed
original advance. SQLite 34004 (`.tmp/returned-advance-refund-dates-sqlite.log`)
and native 80599
(`.tmp/returned-advance-refund-history-native.log`) covers that full cycle, corrected
liquidations, the no-application cycle, closure recovery, existing refund/deposit/correction
and refund print/withdrawal scenarios, and cancelled issuance-policy regression.
were deliberately stopped after this verified failure, before changing runtime code;
both handles returned terminal exit 1. Their incomplete runs are not validation passes.

The fix limits full collection/source validation to initial capture, before the original
advance correction exists. Replay always checks source/rule linkage, independent posted
totals, exact reversal links, chronology and the complete retained snapshots/financial/
subsidiary rows. It cannot accept changed evidence merely because the net balance is zero.
PASS: fresh SQLite 96559, 2/2, 8.337s, exit 0
(`.tmp/returned-advance-refund-history-fixed-sqlite.log`), covers the full cycle and
dated/outstanding boundaries. Fresh native 84934
(`.tmp/returned-advance-refund-history-fixed-native.log`) repeats the seven related
scenarios plus the new dated/outstanding boundary (eight labels): PASS, 8/8, 49.918s,
exit 0. The source and date checks pass after the replay-loop fix.

Review then identified that retained journal projections needed explicit fund identity,
in addition to financial rows and source snapshots. The shared projection now pins fund
and department; refund/deposit journals must also retain their approved source fund.
Returned-payment cycle evidence now includes complete original/return journal projections.
Tests move both sides of a corrected pair to a different synthetic fund and require
rejection, then restore the test records. No posted operator record is altered.
PASS: native 29584, 3/3, 17.364s, exit 0 (`.tmp/returned-advance-history-funds-native.log`),
corrected refund and liquidation cycles plus closure recovery. PASS: SQLite 38710,
2/2, 10.828s, exit 0 (`.tmp/returned-advance-history-funds-sqlite.log`), both corrected
cycles. These final checks cover the fund projection added after the eight-label run.
All runners ended and owned MySQL is stopped. No release or deployment was performed.

The refund fixture's existing configuration setup was factored into a helper so the
same actual released advance can use it; no operator configuration or database was touched.

Successful refund/fund commands (the initial failed run used the first test label alone):

```powershell
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_refund_and_deposit_survive_original_correction_and_new_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_refund_correction_must_be_posted_by_original_correction_date
.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_refund_and_deposit_survive_original_correction_and_new_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_refund_correction_must_be_posted_by_original_correction_date vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_liquidation_survives_original_correction_and_new_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_bank_returned_advance_reaches_corrected_budget_and_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_return_retirement_rolls_back_and_recovers_after_finance_posting vouchers.test_advance_refunds.AdvanceRefundTests.test_refund_expense_deposit_and_exact_corrections_retain_original_advance vouchers.test_advance_refunds.AdvanceRefundTests.test_web_refund_retains_printed_officer_source_and_unposted_withdrawal vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment_at_issuance
.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_refund_and_deposit_survive_original_correction_and_new_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_liquidation_survives_original_correction_and_new_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_return_retirement_rolls_back_and_recovers_after_finance_posting
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_refund_and_deposit_survive_original_correction_and_new_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_liquidation_survives_original_correction_and_new_payment
```

### Active corrected-liquidation increment

`advance_corrected_applications.evidence` now captures complete request checksums,
financial rows, subsidiary rows and source snapshots for an original liquidation and
its exact independently posted correction. Capture uses the full existing liquidation
validator before the original advance correction exists. Subsequent original-correction
validation reproduces those retained records without recursively authorizing a new use
of the reversed original advance. Pending or unmatched applications still block; each
correction must be reconciled and dated no later than original-recognition correction.
The original advance subsidiary identity is also checked explicitly.

PASS: SQLite runner 24089, 2/2, 6.677s, exit 0 (`.tmp/returned-advance-liquidation-history-sqlite.log`):
full Budget/new-payment cycle with a corrected posted liquidation, changed retained
subsidiary rejection, and the existing outstanding-liquidation guard. PASS: native
runner 98511, 7/7, 28.697s, exit 0 (`.tmp/returned-advance-liquidation-history-native.log`): those two tests,
the no-application cycle, closure recovery, both cancelled-advance payment policies,
and existing liquidation web/correction/replacement/output regression (seven labels).
PASS: separate SQLite runner 94250, 1/1, 3.326s, exit 0
(`.tmp/returned-advance-liquidation-dates-sqlite.log`) tests a real prior-day release,
liquidation and bank return followed by today's liquidation correction: original correction
dated yesterday fails, while today's correction posts. Corrected refund history remains blocked.
All runners have ended. Owned MySQL is stopped; no listener remains on port 33308.

Commands for this increment:

```powershell
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_liquidation_survives_original_correction_and_new_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_posted_liquidation_blocks_original_returned_advance_correction
.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_corrected_liquidation_survives_original_correction_and_new_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_posted_liquidation_blocks_original_returned_advance_correction vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_bank_returned_advance_reaches_corrected_budget_and_payment vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_return_retirement_rolls_back_and_recovers_after_finance_posting vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment_at_issuance vouchers.test_liquidation_corrections.LiquidationCorrectionTests.test_web_exact_correction_and_replacement_preserve_history_and_outputs
.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_later_liquidation_correction_cannot_enable_earlier_original_correction
```

### Earlier completed checks

- FAIL - PRE-EXISTING functional limitation reproduced: one test, 3.606s, runner 8283
  exit 1, `.tmp/returned-advance-baseline.log`. The actual reviewed bank-return cycle
  reaches the cancelled-only original-recognition guard; no guard was bypassed.
- PASS: focused SQLite payment/return lineage and changed-cash-purpose rejection,
  one test, 3.488s, runner 45031 exit 0, `.tmp/returned-advance-payment-lineage.log`.
  This precedes the final purpose-identity and availability-reader refinements.
- PASS: first native source check plus both cancelled-advance payment-policy regressions,
  3/3, 14.162s, runner 59244 exit 0, `.tmp/returned-advance-payment-native.log`.
  This predates the new availability helper and zero-available assertion.
- PASS: availability helper and cancellation regression, 3/3, 12.475s, runner 47483
  exit 0, `.tmp/returned-advance-capacity-native.log`. The returned advance has zero
  available release and retains the exact return-posting reference.
- PASS: native runner 82889, 3/3, 11.424s, exit 0,
  `.tmp/returned-advance-notice-native.log`, repeats the three labels after adding
  notice-kind/instrument identity checks and a changed-notice rejection test.
- PASS: dated availability, native runner 4004, 1/1, 3.011s, exit 0,
  `.tmp/returned-advance-dates-native.log`. A governed payment two days before the
  actual observed return retains availability on release day and the intervening day;
  the observed return date withholds the amount. Test clock control supplies dates;
  no posted source rows are rewritten to manufacture historical chronology.
- PASS: dated availability and source-lineage regression on SQLite, runner 79521,
  2/2, 3.154s, exit 0, `.tmp/returned-advance-dates-sqlite.log`.
- System/migration-drift checks pass. No schema migration. Operator DB remains unchanged:
  `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

Commands:

- Full scenario reproduction: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_bank_returned_advance_reaches_corrected_budget_and_payment`.
- Focused SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_reviewed_advance_bank_return_retains_payment_and_cash_flow_lineage`.
- Native source/capacity and cancellation regression: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_reviewed_advance_bank_return_retains_payment_and_cash_flow_lineage vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment vouchers.test_cancelled_advance_corrections.CancelledAdvanceCorrectionTests.test_cancelled_advance_reaches_revised_budget_and_actual_payment_at_issuance`.
- Dated native: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_return_withholding_begins_on_observed_date`.
- Dated SQLite plus lineage: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_return_withholding_begins_on_observed_date vouchers.test_returned_advance_corrections.ReturnedAdvanceCorrectionTests.test_reviewed_advance_bank_return_retains_payment_and_cash_flow_lineage`.

## Required next work — keep the entire corrected-source cycle

1. Source-link, notice-identity and before/after-return availability checks now pass.
   These focused checks do not establish the full corrected-source route below.
2. Reviewed-return capture, exact payment reversal, explicit closure and replacement
   exclusion now pass both payment policies. Mixed corrected expense/refund/deposit
   history, changed-fund rejection, independent withdrawal and three native races pass.
   Retain this coverage; the final broad regression passed as recorded above.
3. Liquidation and corrected refund/deposit history now pass the demonstrated cycles.
   Retain dated, independently verified evidence and no outstanding holds through mixed
   histories and additional instrument chains. Keep full source validation at initial
   capture and exact retained-history validation afterward; the refund replay regression
   shows why recursive source-use authorization must not be reintroduced.
4. The new `advance_returned_cycles` retains its own closure transition proof without
   changing prior-payable `returned_corrections.evidence`. Default-store closure rollback
   and retry pass. Preserve this behavior through the application-history extension.
5. Verified retired old instruments are now excluded from new recognition release
   calculations. Preserve source/closure checks and test additional mixed/replacement
   histories; do not substitute an unconditional status filter.
6. The demonstrated Budget/claim/DV/signature/new-recognition/new-payment/output cycles
   under both payment policies now pass, with the specific recovery, withdrawal,
   changed-evidence and native-race checks recorded above. Shared-service
   regression passed; these checks are not full Finance parity.

A v0.7.106 Version Manager adapter and preview are prepared for the explicit checkpoint
files. The final full-project regression passed; its results
are recorded above. Paid-unreturned advances, close-without-reissue outcomes, wider
instrument chains, other Finance functions, exact local forms and office/WFH/operational
acceptance remain open. eGAPS is untouched.

All native runners have ended and owned MySQL is stopped. System/migration-drift and
diff checks pass; the protected operator DB hash remains unchanged. No schema migration,
master integration or deployment was performed. Earlier increment-level limitations and
failed runs above are historical evidence, not a replacement for the final validation gate.
