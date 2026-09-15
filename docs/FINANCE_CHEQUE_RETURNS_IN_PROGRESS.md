# Incoming cheque bank returns

2026-09-15: validated development v0.7.111 checkpoint on `codex/finance-cheque-returns`,
based on development v0.7.110. This does not establish primary integration or production acceptance.

## Scope

The first return treatment retains a whole-principal bank debit against the original
posted cheque receipt and its exact whole allocation in a posted deposit. A combined
deposit is not reversed. Approved prior clearing stays historical evidence. Pending or
contradictory later clearing requires reconciliation before capture.

Reuse `TreasuryCollectionSource` with explicit receipt/deposit foreign keys and a
MySQL-compatible generated active receipt identity, instead of a second independent
return approval model. The existing `CollectionPostingRequest` carries the reviewed
recipe into independent JEV preparation, posting and cross-store recovery. This refines
the proposed `CollectionChequeReturn` class in the [design](FINANCE_CHEQUE_EXCEPTION_DESIGN.md)
while preserving its source and ownership boundaries.

The supported recipe debits an explicitly reviewed non-cash receivable and credits the
original deposit bank for the whole principal. It is selected from active Finance Setup,
with retained authority and a transaction-specific applicability basis covering all
original charge components. The first recipe preserves the original single cash-flow
purpose; mixed-purpose receipts require explicit component return treatments. No
statutory account code, penalty, fee or residual amount
is inferred. Different treatments, partial bank debits, bank-reversed debits and officer
refund capacity require their own adapters. A current bank mapping cannot reroute the
approved original bank account.

Source corrections use an independently posted exact reversal of the return JEV. Only
reconciliation retires that return identity; a later correction cannot authorize an
earlier replacement return. Original receipts/deposits remain protected while a return
is pending or posted. Detached manual reversals remain prohibited. Treasury locks precede
source locks and Finance fund/journal locks. Finance and default databases remain separate.

The collection detail/register, ordinary capture/review forms and retained printable
copies expose the original cheque, receipt, deposit, bank memo, treatment and history.
Earlier copies retain their original bytes. Read/export permissions and UAT mutation
denial remain independent. Redemption and physical custody are still separate phases.

## Validation

- PASS: initial system check.
- FAIL - CAUSED BY CURRENT WORK: initial focused SQLite discovered eight tests; six
  setup errors and two native-only skips (2.591s). Calling an inherited fixture setup
  without its parent class caused a `super()` error; replaced it with the direct workflow
  fixture and explicit read/export grants. Log: `.tmp/cheque-return-initial-sqlite.log`.
- FAIL - CAUSED BY CURRENT WORK: first native run, six passed/two errors, 13.252s;
  affected SQLite, 144 discovered/93 passed/12 native skips/39 errors, 50.026s. Two
  edited HTML files contained a Windows-encoded punctuation byte; repaired their UTF-8
  content. One SQLite error was a nonexistent `vouchers.test_collection_outputs` label;
  those tests are in the workflow suite. Logs: `.tmp/cheque-return-native-1.log` and
  `.tmp/cheque-return-dependent-sqlite.log`. These are not final passes.
- PASS: focused native `.venv/Scripts/python.exe .tmp/prior_native_authority.py vouchers.test_cheque_returns`:
  all 12 passed, including four races, 48.862s, exit 0
  (`.tmp/cheque-return-native-final.log`).
- PASS: final purpose-preservation native command above: all 13 passed, including four
  races, 20.796s, exit 0 (`.tmp/cheque-return-purpose-native.log`).
- PASS: `.venv/Scripts/python.exe .tmp/earlier_sqlite.py finance accounting reporting vouchers.test_cheque_returns vouchers.test_collection_workflow vouchers.test_cheque_clearing vouchers.test_bank_collections`:
  627 discovered, 588 passed, 39 native-only skips, 403.972s, exit 0
  (`.tmp/cheque-return-broad-sqlite.log`). This broad snapshot precedes the final pure-Python
  purpose guard; the final native run covers that guard. The shared review-table labels
  were separately browser-verified. Local discovery also includes the unrelated untracked
  Accounting policy-test draft, which is excluded from this checkpoint.
- PASS: synthetic browser capture and independent approval; original-source links,
  proposed debit/credit and authority visible before review; 1440px/390px layouts with
  document width 390px at a 390px viewport. Browser fixture only.
- PASS: migration drift check; system check; operator DB SHA256 unchanged.
- PASS: touched text UTF-8, Python compilation and final whitespace checks.

Migrations accounting/0031, finance/0026 and vouchers/0036 were exercised only in disposable
stores. Screenshots: `output/playwright/cheque-return-{desktop,narrow,treatment-narrow}.png`.
Full-project and LGU operational acceptance are NOT RUN - OUT OF SCOPE for this bounded
return adapter; the broad Accounting/Finance/reporting and dependent collection suites
cover the shared contracts changed here. Redemption/custody and remaining treatment
adapters remain open and must retain this evidence.

No operator migration, bank contact or production configuration has occurred.
