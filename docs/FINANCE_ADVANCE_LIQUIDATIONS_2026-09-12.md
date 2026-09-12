# Expense liquidation of an original officer advance

Development checkpoint v0.7.100 on `codex/finance-advance-applications`, based on v0.7.99. This extends
[advance recognition](FINANCE_ADVANCES_IN_PROGRESS.md) within M03 and follows the
[functionality-first direction](FINANCE_MODERNIZATION_PRIORITIES.md). It is not complete
Finance, full advance/liquidation parity, official-form acceptance or a production gate.

## Demonstrated financial route

| Step | Source and control | Financial effect |
| --- | --- | --- |
| Original recognition | Explicit governed employee advance, original DV request, independent JEV and immutable officer subsidiary | Debit advance asset, credit payable |
| Actual release | Reconciled payment JEV, original payable/fund, check identity, claimant receipt and actual release date | Debit payable, credit releasing bank |
| Expense liquidation | Select the original advance, an effective reviewed liquidation recipe and explicit accepted expense rows/document references | Debit accepted expenses, credit that original advance; no second bank payment |
| Independent posting | Lock the default case before the Finance journal; recheck dated released capacity and exact financial/subsidiary evidence | Post once and reconcile the retained request without rerouting the completed DV |
| Output | Original-advance page, request/expense history, linked JEV, reconciled subsidiary and archived CSV | Retain earlier issued bytes after later liquidations |

The supported example recognizes 1,000, actually releases 1,000, posts accepted expenses
of 600 and then 400, and closes the advance asset to zero. A second proposed 400.01 after
a 600 reservation is rejected. A date before actual release cannot use later cash.
The original recognition remains distinct from disbursement and from liquidation.

## Durable controls

- Use the existing immutable `VoucherPostingRequest` and ordinary independent JEV path.
  No second ledger, generic workflow engine or inferred allocation is introduced.
- The original officer identity, recognition request/checksum, fund, asset and payable
  must reproduce posted/audited evidence. Ambiguous multiple original advances in one
  DV case cannot share an unspecified payment pool.
- Record a unique active liquidation document reference per original advance and retain
  an idempotency identity. The existing case lock serializes competing reservations;
  native request-version uniqueness remains intact.
- Pending and posted applications consume the same hold once. Check the requested date
  and every subsequent known release, return and application boundary. An observed bank
  return withholds its original release even while Accounting resolution is pending;
  a replacement needs its own actual release evidence.
- General-ledger/subsidiary differences block individual applications. Retained expense
  account identities/classifications and the exact original-officer subsidiary credit
  are checked again at submission and posting. Liquidation is non-cash.
- Self-posting is refused even if the maker also holds posting permission. Finance UAT
  Viewer mutation denial and office/ledger read boundaries remain effective.
- Recovery finds one retained active JEV. Discarded drafts remain in history; an
  independent reviewer withdraws their reservation before a fresh corrected request.
  Every retained JEV must be voided before withdrawal; a posted application cannot be
  erased this way. The withdrawal actor/reason are retained in the default case event.
- Source history remains visible when a release needs attention. Never reinterpret an
  aggregate officer balance as authority to liquidate an unspecified advance.

## Entry and review

Open Accounting → Officer advances and liquidations → original officer advance. Enter the actual
liquidation date, reviewed accounting basis, liquidation document and expense rows.
Additional rows retain distinct form identities. Invalid input remains on the form.
The generated JEV uses existing submission, independent posting and source recovery.
The page exposes retained applications, original documents, applied/reserved and remaining
amounts, recovery and independent unposted withdrawal. Accounting preparer/reviewer roles
have explicit officer-advance read/export permissions; journal preparation/posting reuse
their existing authority. Read-only UAT membership does not grant the new export permission.

The browser preview uses the production page template and row-control asset with
synthetic fields/data and the local theme. It does not connect to operator stores or
constitute clerk/LGU usability acceptance. Actual Django HTTP tests exercise form
validation, source preparation, independent posting/reconciliation and archived CSV.

## Validation chronology

- FAIL — CAUSED BY CURRENT WORK: `.tmp/advance-source-focused.log`, five tests,
  2.638s, runner 57770 exit 1. Audited totals compared Decimal string formatting
  rather than numeric equality; fixed with finite Decimal comparisons.
- FAIL — CAUSED BY CURRENT WORK: `.tmp/advance-application-focused.log`, six tests,
  4.058s, runner 74110 exit 1. New test omitted the `PermissionDenied` import; fixed.
- PASS — `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_advances`:
  six tests, 3.793s, runner 3196 exit 0 (`.tmp/advance-application-second.log`).
- PASS — initial native source/workflow and two races: ten tests, 14.916s, runner
  22772 exit 0 (`.tmp/advance-application-native.log`).
- PASS — `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_advances vouchers.test_advance_concurrency.AdvanceConcurrencyTests`:
  twelve tests, 20.495s, runner 11518 exit 0 (`.tmp/advance-application-native-final.log`).
  Covers actual HTTP-to-posted-expenses/CSV, independent withdrawal, UAT denial,
  competing reservations, duplicate materialization and competing posting.

- PASS — intermediate full-project SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`,
  1,056 discovered / 1,004 passed / 52 skipped, 482.617s, runner 89420 exit 0
  (`.tmp/advance-application-full.log`). The subsequent role, remaining-amount and
  reservation-evidence refinements have a separate final run.
- FAIL — CAUSED BY CURRENT WORK: the later return-test fixture used nonexistent
  cash-policy fields. Fifteen tests, 25.623s, runner 33608 exit 1
  (`.tmp/advance-application-final-native.log`). Corrected the synthetic fixture to
  the existing policy model; no production policy schema was changed for this error.
- PASS — final source/role/native races:
  `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_advances vouchers.test_advance_concurrency.AdvanceConcurrencyTests`,
  16 discovered / 16 passed / 0 skipped, 26.325s, runner 99810 exit 0
  (`.tmp/advance-application-release-native.log`). Includes corrupted/unwitnessed holds,
  actual pending bank return, standard preparer access without general-ledger permission,
  separate export authorization, and payment recovery versus reservation without lock inversion.
- PASS — synthetic Chromium template/row-control inspection at 1440px and 390px:
  page width remains 390px; the register table scrolls within its 343px container.
  Adding a third expense retains unique field names and entered account/amount/document.
  The remaining amount is displayed numerically. See `output/playwright/advance-liquidation-desktop.png`,
  `advance-liquidation-narrow.png`, `advance-liquidation-narrow-top.png` and `advance-register-narrow.png`.
  This is presentation evidence over synthetic fields/data, not LGU or full-shell browser acceptance.

- PASS — final full-project SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py`,
  1,060 discovered / 1,007 passed / 53 skipped, 543.265s, runner 97271 exit 0
  (`.tmp/advance-application-release-full.log`). Broad regression is appropriate for
  the shared posting, permission, source-recovery and reporting changes. Skips are
  not passes; the focused native run separately exercises the four advance races.
- PASS — `.venv/Scripts/python.exe .tmp/invoice_checks.py`: system and migration-drift
  checks; `git diff --check`. Operator and LGU acceptance remain NOT RUN — OUT OF SCOPE
  for this functional development checkpoint.

All test runners ended; owned MySQL and preview services were stopped. The protected
`db.sqlite3` SHA256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
Version Manager uses an explicit checkpoint manifest and preserves historical references;
publication targets the development branch/tag only, with no master merge or deployment.
Finance migration
0025 adds the selected-original-advance rule choice; Accounting 0030 adds read/export
permissions. Only disposable test stores are migrated. No role command is run against
operator stores. Preserve the protected DB/unrelated work and keep eGAPS unchanged.

## Remaining functionality and acceptance

Actual cash refunds, governed posted liquidation/recognition corrections, alternative
recognition timings, capital/other non-expense liquidation recipes, historical adoption,
exact local liquidation forms and fuller payment/return scenarios remain open. This
expense route does not implement them by relabeling a journal or silently reversing a
source. Continue concrete source workflows before the later inventory, office/output,
usability/WFH and operational/LGU gates. Production remains NO-GO.
