# Budget report explicit Accounting ownership — 2026-09-25

Work starts from v0.7.148 (`29be6b684849d64499fe4bdc8ada91d9bcbd0067`), draft PR #109,
in `codex/finance-budget-actual-owner`. This checkpoint addresses FG-03 source
ownership; certified expenditure, capital outlays and local acceptance remain open.

## Source contract and repair

Authorized Budget schedule lines point through their authorization and immutable
approved Budget version to a typed FiscalYear. That record carries the Accounting
ledger owner. Proposal planning context already uses this explicit identity.
Budget-versus-posted-actual reporting previously searched all default-store Department
names/slugs and requires exactly one name resembling Accounting/Finance. A rename
or unrelated similarly named office can therefore change the selected source.

Reuse the same captured authorized schedule rows for owner/year scope. Match actuals
with the owner included in the fiscal-year/fund/office/account key. Select each
owner only for its own Budget years; do not form a Cartesian product across owners
and years. Retain owner/year identity and date bounds in source/control evidence.
Identical codes across explicitly authorized ledgers must stay separate, with the
owner visible in each mapping status. No authority means no guessed ledger.

Reject inconsistent Budget ownership/call/year lineage and foreign Accounting
classifications or typed periods. Preserve compatible legacy periods with an
explicit owner/year and no typed-year link; do not invent a missing link. No journal,
authorization, permission, schema or earlier report output is changed.

## Validation

Baseline against unchanged v0.7.148 application code: six tests, six reproduced
assertion failures, 3.298s, exit 1; both fresh stores destroyed and runner terminal.
Log: `.tmp/budget-owner-baseline.log`. The read-only repair is now implemented;
focused Reporting/activity/planning regression PASS: 57/57, no skips, 20.914s, exit 0;
both stores destroyed (`.tmp/budget-owner-focused.log`). Added explicit owner/year
pair, missing-owner, legacy-period and generated-workbook assertions afterward.

Final tests against the same application code and expanded assertions:

```text
python .tmp/my_work_sqlite.py reporting budget accounting.tests
python .tmp/retrieval_native.py reporting.test_budget_actual_ownership reporting.test_budget_actual_activity reporting.test_finance_reporting budget.test_planning_context
```

PASS — SQLite: 292 discovered, 288 passed, four skipped, 101.763s, exit 0;
`.tmp/budget-owner-regression.log`. PASS — native MySQL 8.4.11: 60/60, no skips,
31.322s, exit 0; `.tmp/budget-owner-native.log`. Both runners terminated and destroyed
both disposable stores. Owned MySQL was stopped afterward, with no listener on port
33308. The canonical operator database SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
These runs cover the
shared Budget accountability payload, downstream reporting, Budget behavior and
Accounting dependencies. Prior whole-project/native baseline evidence is separate.

The generated workbook distinguishes 200 and 900 of activity in two explicit ledgers
sharing identical fiscal-year/fund/office/account codes. An unrelated 777 posting in
an unselected owner/year pair is excluded. Tests also prove renamed owners, unrelated
similarly named offices, missing authority, invalid Budget lineage, foreign expense
classification and foreign typed years. Legacy periods retain their null typed-year
link without being rewritten. Prior closing/reversal and retained-output tests pass.

NOT RUN — OUT OF SCOPE: a new whole-project suite, browser/printed-layout acceptance
or LGU certification. No schema, posting service or permission changes; the actual
workbook values and mapping labels are verified, not official form acceptance.

## Remaining work

Use the [source audit](FINANCE_BUDGET_ACTUALS_SOURCE_AUDIT.md) to complete the separate
certified-expenditure contract: explicit expenditure-purpose and capital-outlay
coverage, historical external certified sources, independent certification and
retained proposal references. Do not treat posted expense activity as that certificate.
Unknown local earmark rules, exact outputs and human acceptance remain open.
