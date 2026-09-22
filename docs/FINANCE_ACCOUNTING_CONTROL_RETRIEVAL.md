# Accounting close and bank-control register retrieval

2026-09-22, branch `codex/finance-accounting-control-retrieval`, based on v0.7.127
and draft PR #89. Continues FG-11; not whole-goal completion.

## Existing capability and repair

Period-close and bank-reconciliation registers already had scoped filters, exact
source links, workflow guidance, truthful complete-match export counts and full
CSV exports. However, both displayed only 100 records without page navigation.
The complete queryset was available to exports but inaccessible through the register
beyond its first page.

Both now use stable 50-row pages and explicit matching ranges. Page links preserve
existing status/attention/bank filters and return to the relevant register. Applying
filters resets the page. Existing complete counts, filtered CSVs, source detail
links and permissions are unchanged. Users can reach old close evidence and bank
statements without guessing a source URL or reconstructing the register externally.

## Controls and limits

Department/filter scoping precedes pagination. Period-close policy, independent
review, reopen chronology, bank matching, posting, immutable source evidence and
export authorization are unchanged. GET only retrieves records; no financial
transition, migration, amount, audit schema or persistence service changes.

## Validation

Initial focused SQLite: FAIL - CAUSED BY CURRENT WORK (new test fixture), 2 discovered,
1 passed and 1 error, 3.982s, exit 1. The bank fixture omitted the required received_on
date. The same missing field affected browser seeding; both were corrected. The
application schema correctly rejected incomplete synthetic data. Close retrieval
passed in that run. Log `.tmp/accounting-control-focused.log`.
Focused command: `python .tmp/earlier_sqlite.py accounting.tests.StandaloneAccountingTests.test_bank_register_retrieves_every_statement_and_exports_all_matches accounting.test_period_close.GovernedPeriodCloseTests.test_close_register_retrieves_every_retained_version_and_exports_all`.

First dependent run: FAIL - CAUSED BY CURRENT WORK, 67 discovered, 66 passed and
one error, 17.512s, exit 1. The existing close attention/source test requires the
`runs` context to retain its queryset interface. The view now exposes the page's
queryset as `runs` and keeps Page metadata separate. Financial selection is unchanged.
Final same-scope PASS: 67/67, no skips, 17.619s, exit 0:
`python .tmp/earlier_sqlite.py accounting.tests accounting.test_period_close finance.test_work_tasks.FinanceAccountingWorkTaskContractTests`
Logs `.tmp/accounting-control-regression.log` (initial) and
`.tmp/accounting-control-final.log` (final). Additional directly dependent task checks:
`python .tmp/earlier_sqlite.py finance.test_work_tasks.FinanceBankReconciliationWorkTaskContractTests finance.test_work_tasks.FinancePeriodCloseWorkTaskContractTests`,
log `.tmp/accounting-control-tasks.log`: PASS 13/13, no skips, 10.962s, exit 0.
All fresh test stores destroyed; all runner sessions terminal.
Tests cover 111 matches per register, every page without duplication, full 111-row
exports, retained filters, exact bank search, empty/malformed-page recovery,
department isolation and unchanged draft/open state.

PASS Playwright: actual Next navigation reached both third pages and displayed
101-111 of 111. Actual browser downloads both contain 111 rows. Desktop and 390px
screenshots plus CSVs retained under `output/playwright/`; viewport/document both
390px and existing tables retain horizontal scrolling. Browser/server stopped.
Fixture `.tmp/accounting-control-browser-20260922` is an offline copy of earlier
synthetic stores with retrieval-only draft statement/close records. Duplicate close
versions are test input, not evidence of real repeated closing or accepted policy.
No match, approval, close or reopen button used.

PASS `git diff --check`. Operator database SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
NOT RUN - OUT OF SCOPE: native MySQL/full-project local suites for this read-only
pagination change. Dependent scope exercises Accounting/close services and task
boundaries. No owned native server started. New remote CI remains separate evidence.
No operator migration, master merge, deployment or LGU/form acceptance.

## Remaining retrieval audit and next checkpoint

Fixed-string scan of Accounting, Budget and voucher views finds no remaining
`[:100]` display slices in those files after this change. This is not a repository-wide
proof of complete retrieval. Reporting still limits local-form register results
and source drill-through; drill-through explicitly says up to 100 and therefore is
not a silent count, but complete source navigation still needs inspection. FG-11
remains partial until that route-level audit is complete. Existing unsliced overview
lists still need realistic-volume performance qualification.
Then resume controlled-print/custody and output proof, preserving unresolved local
earmark semantics, official-form acceptance and configured deployment gates.
