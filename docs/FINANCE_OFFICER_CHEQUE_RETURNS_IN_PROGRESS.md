# Actual bank returns of officer refund cheques

2026-09-15: validated v0.7.115 development checkpoint on `codex/finance-officer-cheque-returns`
in `C:/Users/Administrator/.codex/worktrees/grand-officer-cheque-returns`.
The pending-officer-cheque base is pushed as v0.7.114 `ad7a300`
([draft PR #75](https://github.com/tepong32/grand/pull/75)). The candidate index and
continuity documents are aligned to that checkpoint; tested Python/templates were
preserved and the database still matches its committed baseline.
No master integration or operator database change is established.

## Financial boundary

Use the retained actual bank-return source and one reviewed selected-original-advance
debit plus original-bank credit. Preserve the original refund purpose, original officer
subsidiary and actual date. A posted Finance journal alone does not release a default
reservation: source reconciliation must complete before the return restores dated
capacity. Earlier applications still face the original earlier-date limits.

Correcting a mistaken return consumes capacity again. Reserve that amount from its
proposed correction date under the original case lock, checking every later commitment.
Keep the hold through posting/reconciliation, and release an unposted hold only through
independent rejection or withdrawal with discarded journals. Mirror the exact original
return subsidiary; never substitute an unrelated advance account or officer.

Replacement principal receipts reuse the original refund reservation/subsidiary and
the returned-cheque identity. A later return of a replacement cheque restores only its
dated amount; the earlier redemption remains occupied. New redemption selects the new
return. Preserve original receipts, deposits, reviewed clearing and issued copies.

Mutations and Accounting posting acquire the original default-store case before
Treasury/source and Finance locks. Return debits are not original advance recognitions
and must not enter the original-advance picker. Original-recognition correction still
requires its existing exact refund/deposit correction history; this module does not
automatically treat actual dishonour as a source-error correction.

## Validation

- PASS: `.tmp/component_sqlite.py vouchers.test_advance_cheque_returns`, initial 30
  sequential tests, 33.933s, exit 0. This precedes retaining the current disbursement
  evidence on replacement receipts and the later added tests below.
- PASS: `.tmp/component_native.py vouchers.test_advance_cheque_returns`, all 39 tests
  including nine races, 116.052s, exit 0. Three new races cover return-correction versus
  expense, replacement versus expense, and return reconciliation versus expense.
  The financial runtime is unchanged since this native run.
- PASS: system check, missing-migration check and `git diff --check` using isolated
  fixture stores. No schema migration is required for the new recipe validation.
- PASS: browser actual-return capture, independent review of visible original-advance
  and bank rows, service posting/reconciliation and original receipt showing the dated
  adjustment. Desktop 1440px and narrow 390px views are readable without page overflow.
  Screenshots were inspected; owned browser/server are stopped.
- PASS: `.tmp/component_sqlite.py vouchers.test_advance_cheque_returns vouchers.test_advance_refunds vouchers.test_advance_refund_concurrency vouchers.test_cheque_returns vouchers.test_cheque_redemptions vouchers.test_advance_recognition_corrections vouchers.test_returned_advance_corrections vouchers.test_cancelled_advance_corrections finance accounting reporting`,
  600 passed and 48 native-only skips (648 discovered), 430.873s, exit 0. Includes
  two later invalid-counterpart/officer-subsidiary cases. Scope covers the shared
  Accounting posting dispatch and dependent advance, rule and report contracts.
- PASS: `.tmp/component_sqlite.py vouchers.test_advance_cheque_returns.OfficerReturnTests.test_return_and_correction_outputs_retain_original_officer`,
  1/1, 4.462s, exit 0. Both register rows and frozen return/correction copies retain
  the original officer/JEV; the earlier copy stays unchanged. This final output-only
  addition follows the broad pass; the financial runtime is unchanged.

Paused after this checkpoint at the user's 2026-09-15 request. Resume only when asked.
The main operator database hash is unchanged, and this worktree's database matches
its committed baseline. Only disposable fixture stores were used.

Full LGU operational acceptance remains NOT RUN; these synthetic tests do not establish
prescribed-form or production acceptance.

See [pending officer cheques](FINANCE_OFFICER_CHEQUES_IN_PROGRESS.md),
[redemption](FINANCE_CHEQUE_REDEMPTIONS_IN_PROGRESS.md) and
[public-source exception design](FINANCE_CHEQUE_EXCEPTION_DESIGN.md).
