# Liquidation after issuance-time payment posting

Development checkpoint v0.7.101 on `codex/finance-advance-issuance`, following v0.7.100. The existing advance
source reader required a release-time payment request, excluding ordinary advances
whose reviewed recipe posts the payable-to-bank entry at check issuance.

The reader selects the actual issuance or release request and requires exactly one
financial posting decision. It verifies the retained event, check, original payable,
fund, independently posted journal and the appropriate posting date. Issuance alone
does not supply liquidation capacity: actual release, claimant and receipt remain
required. New application evidence records both posting and release dates. Earlier
requests and posted journals are not rewritten. Numeric event amounts compare as
finite decimals, retaining historical serialization such as `1000` and `1000.00`.

Native testing also reproduced a payment-recovery deadlock: the ordinary reconciler
could lock a posting request before its joined case while advance preparation already
held that case. Voucher posting reconciliation now acquires the case before the request
for every event, matching source workflows. Financial actions are not automatically retried.

The source-to-output scenario posts the advance payment at issuance, demonstrates zero
available capacity before release, completes advice and claimant release, then posts
1,000 of expense liquidation. The officer subsidiary closes to zero without another
bank line. Unreconciled payment, changed check identity and missing receipt are refused.
Existing release-time workflow and native reservation races are regression targets.

## Validation

- FAIL — CAUSED BY CURRENT WORK: initial SQLite advance run, 13 tests in 9.834s,
  runner 42199 exit 1, `.tmp/advance-issuance-focused.log`. String comparison of
  event amounts rejected issuance evidence; corrected to finite Decimal equality.
- PASS — focused corrected SQLite, `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers.test_advances`,
  13 tests in 10.115s, runner 73517 exit 0, `.tmp/advance-issuance-final-sqlite.log`.
- FAIL — native intermediate run, 17 tests in 32.059s, runner 61177 exit 1,
  `.tmp/advance-issuance-native.log`: the process retained the earlier amount check,
  and payment recovery versus reservation reproduced MySQL deadlock 1213. Treat both
  as current-work failures; fix the lock order rather than dismissing a timing failure.
- PASS — final native: `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_advances vouchers.test_advance_concurrency.AdvanceConcurrencyTests vouchers.test_issuance_bank_returns`,
  32 tests / 32 passed / no skips, 48.970s, runner 67415 exit 0,
  `.tmp/advance-issuance-final-native.log`. Covers advance source/role/output and four
  races, plus issuance-bank-return and inherited prior-payable workflows. Owned MySQL
  was stopped after completion.
- PASS — final dependent SQLite: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py vouchers`,
  360 discovered / 332 passed / 28 skipped, 244.196s, runner 90431 exit 0,
  `.tmp/advance-issuance-dependent-final.log`. Broadened to the complete voucher app
  because payment reconciliation is shared across voucher events and corrections.
- PASS — `.venv/Scripts/python.exe .tmp/invoice_checks.py`: system checks and no migration
  drift; `git diff --check`. Full-project regression is NOT RUN — OUT OF SCOPE for
  this bounded source-reader/reconciliation change; v0.7.100 retains the preceding
  full-project evidence. Native checks cover selected actual concurrency scenarios,
  not every skipped SQLite test or full operational acceptance.
- NOT RUN TO COMPLETION — ENVIRONMENTAL: the first dependent voucher runner 84061
  lost its process handle during a host interruption. No matching Python process or
  terminal test summary remained; `.tmp/advance-issuance-dependent.log` is incomplete.
  The fresh completed run is recorded above.

No schema change or operator migration. All runners ended; native/preview ports are closed.
The protected database remains unchanged (SHA256
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`).
Version Manager stages only this checkpoint with VERSION/CHANGELOG; unrelated files
and historical references remain preserved. Publication is to the development branch/tag;
this evidence does not establish primary-branch integration or deployment.
Full Finance regression, replacement/returned-advance breadth, exact forms and LGU
acceptance are not established by this bounded source-reader change.

## Next functionality

Actual officer cash refunds still need Treasury receipt evidence linked to the original
advance, dated reservations shared with expense applications, independent Accounting,
advance subsidiary credit and retained receipt/deposit outputs. The ordinary collection
receipt currently credits revenue or a liability, so it must not be reused unchanged
to recognize an officer refund. Governed posted corrections remain unfinished.

Implementation entry points for that next source route are `collections.record_receipt`
and `collection_posting.review_source/materialize/reconcile`: retain the ordinary
receipt identity and deposit allocation, but explicitly pin the original advance and
officer subsidiary. `advance_applications.capacity` must count both receipt holds and
expense holds under the same case lock. Collection review, posting, withdrawal and
correction must share that order before Treasury/source and Finance locks; existing
collection-only financial-row validation is insufficient to validate an advance credit.
Do not expose the refund form before its receipt-to-subsidiary and deposit/correction
paths have evidence. This is an implementation map, not delivered refund functionality.
See [advance liquidation](FINANCE_ADVANCE_LIQUIDATIONS_2026-09-12.md) and the
[completion audit](FINANCE_ROADMAP_COMPLETION_AUDIT.md). Production remains NO-GO.
