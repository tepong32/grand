# Budget and remittance retained history — 2026-09-24

Development checkpoint on `codex/finance-budget-remittance-history`, based on
v0.7.141 `766fa809c30dd773f11a3d9753cbfa4b66b8ddd0`, draft PR #102.

Budget proposal history was fetched but never rendered. It now has a retained
decisions section restricted by the existing `view_budget_audit` permission.
Proposal and quarterly histories use stable 30-event pages scoped to the authorized
record and department. Quarterly history preserves its existing reader access.
Explicit navigation keeps the section open, including returning to page 1.

Remittance history now has stable 50-event pages, full counts and navigation under
its existing audit permission. Events remain scoped to the authorized batch. No
approval, allocation, release, posting, financial calculation or persistence change.

## Validation

FAIL - PRE-EXISTING, reproduced before application edits: two tests, 9.490s,
two assertion failures and one subtest error. Proposal history was absent,
quarterly pagination context absent, and remittance page 2 repeated page 1.
Log `.tmp/budget-remit-history-baseline.log`.

PASS: `python .tmp/earlier_sqlite.py budget.tests budget.test_quarterly vouchers.test_remittance_register`:
54/54, 50.322s, no skips, exit 0. Both test stores destroyed.
Log `.tmp/budget-remit-history-sqlite.log`. Coverage traverses every retained
proposal/quarterly event including genuine original decisions, and all 61 batch
events. It verifies no duplicates, foreign-office/other-batch exclusion, permission
denial and no audit writes from retrieval, alongside existing workflow regressions.

Browser inspection found that Previous initially collapsed the section on page 1.
The expansion flag now reflects explicit history navigation; the regression checks
the rendered open state on every requested page. Final affected rerun PASS:
`python .tmp/earlier_sqlite.py budget.test_quarterly`, 8/8, 4.632s, no skips,
exit 0. Both test stores destroyed; runners terminal. Log `.tmp/budget-history-final.log`.
The other 46 tests passed before this isolated Budget expansion adjustment.

PASS: Playwright desktop 1440×1000 and narrow 390×844 inspection on disposable
two-store synthetic data. Proposal page 2 reaches events 31–47; Next/Previous
returns to visible page 1 history. Quarterly page 2 reaches events 31–46.
Screenshots visually inspected:
[desktop](../output/playwright/budget-proposal-history-desktop.png),
[narrow page 2](../output/playwright/budget-proposal-history-mobile.png),
[narrow return to page 1](../output/playwright/budget-proposal-history-first-mobile.png).
One screenshot invocation used a positional filename and failed; the corrected
`--filename` invocation succeeded. Browser and its server closed after validation.
Remittance browser interaction was not repeated; rendered HTTP assertions cover it.

PASS: `git diff --check` and changed-document local Markdown targets.
Operator database SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

NOT RUN - OUT OF SCOPE: native MySQL and full cross-module suites. This checkpoint
changes read selection and history presentation only, with no migration, lock or
financial service change. Separate default/Finance test aliases are preserved.
These checks do not establish office acceptance or production-volume performance.

## Remaining gate

FG-11 remains partial. Next assess Accounting reconciliation history (first 25),
opening-balance row/correction reachability (disclosed first 500) and event history,
then clear navigation to Reporting's existing complete run register. Bank-match
suggestions require checking the full manual route before treating their cap as a
defect. Retain Budget certified actuals, unconfirmed earmark semantics and exact
output/LGU acceptance gaps in the [foundation gate](FINANCE_FOUNDATION_GATE.md).
No master merge or deployment. Production remains NO-GO; overall goal active.
