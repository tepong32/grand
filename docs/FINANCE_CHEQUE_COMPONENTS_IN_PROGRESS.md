# Mixed-purpose cheque return and redemption

2026-09-15: validated v0.7.113 development checkpoint in the isolated
`C:/Users/Administrator/.codex/worktrees/grand-cheque-components` checkout on
`codex/finance-cheque-components`, based on pushed v0.7.112 (`ce0c724`,
[draft PR #73](https://github.com/tepong32/grand/pull/73)).
This is not master integration or a completed Finance gate.

## Boundary

One cheque may cover several reviewed collection charges with different cash-flow
purposes. Retain their exact source cash amounts through return and redemption. The new
posting-rule amount instruction selects the original cheque amount for an explicit
purpose; the complete set must reproduce the whole principal. No residual amount or
free-text interpretation supplies an omitted category.

The return uses one reviewed receivable debit and one original-bank credit for every
original purpose. Redemption uses one debit per original purpose on the same actual
collection account and one selected-original-return receivable credit. It recognizes
no second revenue and retains one whole receipt/deposit amount. Incomplete purpose sets,
reclassification and multiple collection assets are rejected.

Single-purpose sources keep their existing proof fields and recipe semantics. The
component evidence is added only to newly supported mixed-purpose return sources;
no posted history, earlier receipt, approval or issued copy is rewritten. Existing
Treasury/source locks, independent review, generated active identities and correction
dates remain in force.

## Validation

- PASS: `.tmp/component_sqlite.py vouchers.test_cheque_components`, three initial
  scenarios, 4.302s, exit 0.
- PASS: `.tmp/component_native.py vouchers.test_cheque_components vouchers.test_cheque_returns vouchers.test_cheque_redemptions`,
  all 25 tests, including six existing races, 57.800s, exit 0. Source runtime is unchanged
  since this run; two later configuration/evidence cases are covered below.
- PASS: `.tmp/component_sqlite.py vouchers.test_cheque_components finance`, all 184
  tests, 141.377s, exit 0. Includes the later invalid-configuration and one-cent evidence
  drift cases. Scripts use the canonical Python 3.11 venv and documented fresh two-store
  MySQL runner; fixture stores/logs are isolated in this checkout.
- PASS: `.tmp/component_sqlite.py accounting reporting vouchers.test_cheque_components vouchers.test_collection_charges vouchers.test_cheque_returns vouchers.test_cheque_redemptions`,
  320 passed and 29 native-only skips (349 discovered), 133.063s, exit 0. This covers
  dependent statements and Accounting plus affected collection lifecycle regressions.
- PASS: system check, migration drift and `git diff --check`. The operator database
  hash is unchanged; the worktree database matches its committed baseline.
- PASS: synthetic browser manager-cheque redemption, independent approval with visible
  60/40 purpose amounts, and posted receipt showing bank clearing still pending. Desktop
  1440px and mobile 390px source views are readable without horizontal page overflow.
  Full clearing/physical handover replay is NOT RUN - OUT OF SCOPE for this allocation
  adapter; the existing lifecycle is covered by dependent native service tests.

The owned browser/server are stopped. Only disposable databases are used; no operator migration or bank action.
Fee/penalty combinations, external delivery and officer cheque-refund timing remain
separate adapters. See the [exception design](FINANCE_CHEQUE_EXCEPTION_DESIGN.md) and
[redemption scope](FINANCE_CHEQUE_REDEMPTIONS_IN_PROGRESS.md).
