# Budget report expense activity and closing — 2026-09-25

Development branch `codex/finance-budget-actual-closing` starts at v0.7.147,
`ff3dbeb379a5c54bdbfbe59ffb18529199797ac6`, [draft PR #108](https://github.com/tepong32/grand/pull/108).
This repairs the existing Budget-versus-posted-actual dataset. It does not supply
certified expenditure or establish local output acceptance. See the
[source audit](FINANCE_BUDGET_ACTUALS_SOURCE_AUDIT.md), FG-03 in the
[foundation gate](FINANCE_FOUNDATION_GATE.md), and [proposal context](FINANCE_BUDGET_PLANNING_CONTEXT.md).

## Reproduction and calculation

The prior dataset reduced 20,000 of posted expense to zero after a balanced typed
nominal closing entry, while still reporting reconciled controls. Four retained
regressions also expose a missing-activity `KeyError`, inclusion of explicitly typed
legacy direct-equity movements, and failure to check invalid retained reversal
lineage. Baseline: three assertion failures and one error, four tests, 1.395s,
exit 1; fresh stores destroyed. These are reproduced pre-repair defects.

The changed dataset follows the journal's existing `statement_origin` lineage,
using retained purpose rather than descriptions. Opening, nominal-closing and
direct-equity expense movements and their reversals are excluded from expense
activity, consistent with existing Budget proposal context. Ordinary expense
corrections remain included on their journal dates. Drafts and dates after
the selected cutoff remain excluded by the original source query.

Every selected expense journal remains in source evidence. New snapshots retain
the origin identity/purpose, exact expense-line identity/sequence, whether it
contributes to activity, and signed excluded movement. An excluded source contributes
zero to reported actual expense; its original amount is preserved separately.
The new calculation-basis identifier and control totals expose the bridge:

`posted expense activity + excluded expense movement = posted expense ledger movement`

For the reproduction, that is `20,000 + (-20,000) = 0`. The ledger remains closed,
while reported period activity retains the original expense. No journal or earlier
output is rewritten. Existing archived dataset snapshots and issued bytes remain
unchanged as later closes and actual corrections are posted.

Budget keys without included activity show an explicit no-activity status and zero
posted expense instead of indexing a missing dictionary entry. Excluded-only keys
do not create false actual-mapping exceptions. Ambiguous or unmatched included
activity retains the existing exception controls. Zero posted activity does not
certify historical completeness or replace unavailable certified expenditure.

## Controls and remaining scope

No financial write service, schema, permission, Budget authority, source date or
correction workflow changes. Existing source ownership and report approval/export
checks remain. Cyclic or cross-office reversal lineage is rejected by the existing
journal-origin contract rather than silently included or discarded.

The existing Accounting-owner selection based on department identity remains a
separate limitation to reconcile against explicit fiscal-year ownership. Capital
outlay/classification coverage, actual certification, local earmark rules, exact
outputs and human acceptance remain open. Current posting controls already reject
expense-bearing direct-equity journals; the explicit legacy fixture exercises
historical read behavior without weakening that validation.

## Validation

Commands use the canonical Python 3.11 environment and disposable test stores:

```text
python .tmp/my_work_sqlite.py reporting.test_budget_actual_activity
python .tmp/my_work_sqlite.py reporting.test_budget_actual_activity reporting.test_finance_reporting budget.test_planning_context
```

The first command is the failed baseline above. PASS — the second command: 51/51,
19.565s, no skips, exit 0; fresh stores destroyed and runner terminal. Log:
`.tmp/budget-actual-focused.log`. Additional explicit workbook-value and cross-office
lineage assertions were then added. Final validation against those tests:

```text
python .tmp/my_work_sqlite.py reporting budget.test_planning_context accounting.tests
python .tmp/retrieval_native.py reporting.test_budget_actual_activity reporting.test_finance_reporting budget.test_planning_context
```

PASS — broader SQLite: 228 discovered, 227 passed, one skipped, 78.871s, exit 0;
`.tmp/budget-actual-regression.log`. PASS — native MySQL 8.4.11: 51/51, no skips,
29.459s, exit 0; `.tmp/budget-actual-native.log`. Both runners terminated and destroyed
both test stores. Owned MySQL was stopped afterward; port 33308 has no listener.
The canonical operator database SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

These scopes cover the changed dataset, generated workbook, retained source/output
evidence, Budget planning and dependent Accounting behavior. NOT RUN — OUT OF SCOPE:
a new whole-project suite and browser/layout acceptance for this read-only calculation
delta. The earlier integrated full-suite baseline is separately recorded; this change
does not establish certified expenditure, local form acceptance or production readiness.
