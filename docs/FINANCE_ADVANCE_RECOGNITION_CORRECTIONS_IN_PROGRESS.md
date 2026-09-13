# Unpaid original advance corrections - v0.7.104 development checkpoint

Branch `codex/finance-advance-recognition-corrections`, based on verified published
v0.7.103 (`d36c713757daa109076bf1347bd094281d774ca6`). Implementation resumed after
the user's later `continue`; the older nightly pause is not the active instruction.

## Baseline gap and required end state

The posted expense correction route does not correct original advance recognition.
Before this checkpoint, for an unpaid recognized advance, `vouchers.return_routes.return_route_blocker`
refuses a return to Accounting because its JEV is posted. A detached Accounting
reversal also refuses an advance subsidiary. These guards preserve financial history;
neither is an implemented source correction workflow.

An amount correction additionally crosses Budget. Both `prepare_voucher` and
`validate_accounting` require DV gross to match the certified obligation.
The baseline `budget.services.downstream_issuance_boundary` treated an existing DV as issued and
blocked obligation amendments, even when no check exists. Merely reversing the JEV
and reopening DV preparation would strand an amount correction at that boundary.
Do not weaken the guard or claim that such a partial route completes this gap.

Required implementation must demonstrate an actual original-source correction through
the reviewed obligation/allocation (where affected), corrected DV and signature copies,
new independently posted recognition, actual payment and officer schedule/export.
Retain original OBR/DV/JEV versions and all previously issued bytes. Any later
obligation capacity release must occur only after the corresponding source correction
is independently posted and reconciled; interrupted cross-store recovery must fail
closed. Keep the existing fiscal-foundation, case and Finance lock boundaries coherent.

Unreleased cancelled checks need their own exact cancellation/no-entry evidence.
Released cash, expense applications, actual refunds and their corrections cannot be
erased by reversing original recognition: their linked amounts and officer identity
must remain accounted for. Keep these later scenarios explicitly open until implemented
and demonstrated. A historical case must not become a second freely payable advance.

## Implemented unpaid workflow

The retained correction request produces an exact reversing JEV with original financial
and officer/payable subsidiary evidence. Independent posting precedes default-case
reconciliation. That reconciliation supersedes the old DV/signature output in history
and reopens existing payable preparation (or Accounting DV preparation without intake).
Existing Budget adjustments, allocation revisions and claim review then supply the new
DV, fresh signatures and independently posted replacement recognition. New recognition
pins the predecessor correction. Replacement DV, Budget and recognition dates cannot
precede the correction. Any payment instrument excludes this route.

The verified correction window requires every posted recognition to have its exact
posted/reconciled correction. Pending, discarded or merely posted-but-unsynchronized
corrections do not reopen Budget. Recovery and ordinary pre-posting returns use the
same evidence. Independent withdrawal requires all unposted drafts to be discarded.
No posted source or initial intake allocation is rewritten: initial allocation validation
applies at creation, while guided revisions validate current versioned allocations.

Linked Budget transitions acquire default fiscal issuance boundaries and sorted case
locks before Finance locks. Replacement DV preparation shares this boundary. Native
races check that simultaneous Budget approval and replacement DV preparation cannot
both succeed. Original correction preparation, check issuance and materialization also
serialize on the existing case, with Finance fund/source locks during materialization.

The web route exposes the reason/date, retained correction, JEV and voucher next action.
The corrected payable screen explains required Budget/allocation review. Expense
preparation is hidden on an original advance with an active correction. Existing role,
owner and Finance UAT mutation-denial rules apply. No schema migration is introduced.

## Validation

All tests use disposable default and Finance stores. SQLite cannot establish native
locking behavior, so workflow and concurrency checks also run on MySQL 8.4.11.

| Check | Actual result and scope |
|---|---|
| Existing return guard | PASS: 1 test, 2.364s, runner 39198 exit 0. Baseline only. |
| Account replacement | PASS: 1 test, 3.311s, runner 92424 exit 0. Exact original/reversal, new advance account and fresh signature round. |
| Amount and account replay | PASS: 2 tests, 5.540s, runner 98825 exit 0. Real 1,000 recognition → reversal → reviewed 200 Budget reduction → 800 allocation/claim → DV/signatures/recognition → actual 800 payment and schedule/export. |
| Initial native workflows/races | PASS: 24/24, 52.203s, runner 59543 exit 0. Before final shared Budget/recovery additions. |
| Final native workflows/races | PASS: 25/25, 60.830s, runner 68429 exit 0. Includes final Budget-versus-DV race, recovery, HTTP permissions, exact mirror, maker-checker, withdrawal, check issuance and duplicate materialization. |
| Existing Budget native suite | PASS: 32/32, 17.967s, runner 91070 exit 0. Broadened for changes to shared amendment transitions. |
| Initial full-project SQLite | PASS: 1,132 discovered / 1,059 passed / 73 skipped, 727.025s, runner 61878 exit 0. Predates final shared-service changes. |
| Final full-project SQLite | PASS: 1,133 discovered / 1,059 passed / 74 skipped, 699.061s, runner 50416 exit 0. Final shared-service state. |
| System, migration drift, diff | PASS. No schema change. |
| Browser templates | PASS: synthetic 390px form without horizontal overflow and 1360px retained history. Not real-office or authenticated end-to-end acceptance. |

Commands and logs:

- Baseline: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_advance_recognition_corrections.AdvanceRecognitionCorrectionTests.test_current_return_does_not_reopen_a_posted_unpaid_advance`.
- Amount/account replay: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_advance_recognition_corrections.AdvanceRecognitionCorrectionTests.test_budget_amount_correction_to_new_recognition_actual_payment_and_output vouchers.test_advance_recognition_corrections.AdvanceRecognitionCorrectionTests.test_unpaid_correction_reopens_dv_and_retains_original_accounting`.
- Native workflows/races: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_advance_recognition_corrections.AdvanceRecognitionCorrectionTests vouchers.test_advance_recognition_correction_concurrency.AdvanceRecognitionCorrectionConcurrencyTests`.
  Final log: `.tmp/advance-recognition-correction-native-final.log`.
- Native Budget: `.venv/Scripts/python.exe .tmp/prior_native_authority.py budget.tests.AnnualBudgetPreparationTests`.
  Log: `.tmp/advance-recognition-correction-budget-native.log`.
- Full SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`.
  Initial/final logs: `.tmp/advance-recognition-correction-full.log`, `.tmp/advance-recognition-correction-full-final.log`.
- Checks: `.venv/Scripts/python.exe .tmp/invoice_checks.py` and `git -c core.safecrlf=false diff --check`.

Earlier failures, corrected before successful replay:

- FAIL - CAUSED BY CURRENT WORK: runner 32048, one test/2.427s, exit 1;
  synthetic fixture omitted required JEV numbering. Reused existing approved numbering
  fixture without weakening production validation.
- FAIL - CAUSED BY CURRENT WORK: runner 58526, one test/2.500s, exit 1;
  fixture tried to return previously completed signatures. Restricted it to pending tasks
  with distinct retained request identities.
- FAIL - CAUSED BY CURRENT WORK: runner 67469, two tests/4.990s, exit 1;
  the new amount-reduction route exposed initial-allocation/current-claim validation.
  Initial evidence is now preserved while existing guided revisions validate current amounts.

Browser evidence: `output/playwright/advance-recognition-correction-narrow.png` and
`output/playwright/advance-recognition-correction-history-final.png`. Owned preview
browsers/servers and MySQL are stopped; ports 8877/33308 are closed. The operator
`db.sqlite3` checksum remains unchanged; eGAPS is untouched. The final native run
precedes a wording-only generalization of advance validation/withdrawal messages;
final SQLite covers those messages.

## Remaining work and limits

This is development coverage for unpaid advances before any instrument exists.
Original-recognition corrections involving issued, cancelled or released instruments,
later expense/refund applications, other advance scenarios and historical adoption
remain open. Cross-year correction numbering is not specifically validated. Exact
local forms, printing/signatories, ordinary-office/WFH and operational/LGU acceptance
remain separate unperformed gates. No master integration, deployment or full Finance
parity is established. See CONTINUE.md, D-089 and the Finance roadmap.
