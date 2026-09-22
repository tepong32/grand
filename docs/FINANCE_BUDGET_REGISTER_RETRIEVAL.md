# Budget proposal and allotment register retrieval

2026-09-22, development branch `codex/finance-budget-register-retrieval`, based on
v0.7.126 / draft PR #88. This continues FG-11 of the foundation gate.

## Existing capability and repaired gap

The annual proposal and allotment workspaces already scoped records by Budget
owner and offered fiscal-year, kind, status and next-action filters, source links,
control totals and archived full-register exports. Their display querysets were
then silently sliced at 100. Neither offered text search for familiar titles or
ARO numbers. The displayed-length counters concealed older matches.

Both registers now use deterministic 50-row pages, complete matching counts and
visible ranges, with filter-preserving links. Annual search matches proposal title,
requesting-office label or linked ordinance; allotment search matches ARO number,
purpose or linked ordinance. Search is bounded to 160 characters and shared by
screen/export query helpers. Export buttons say all matching versions/orders and
include every match regardless of the current page. Export archive and audit
metadata retain the normalized search along with existing filters.

## Controls and boundaries

Budget-owner scoping still precedes filtering. Financial authority, appropriation
balances, review, release and correction services are unchanged. The department-wide
authority overview explicitly remains independent of order filters. Neither proposal
approval nor a draft ARO becomes spending authority. No schema migration or new
financial transition is introduced. Existing invalid-filter behavior was not broadened
by this search change. Native focused checks cover the added retained audit metadata.

## Validation

PASS focused SQLite: 2/2, no skips, 3.583s, exit 0.
`python .tmp/earlier_sqlite.py budget.tests.AnnualBudgetPreparationTests.test_annual_register_pages_search_and_export_share_all_matches budget.tests.AnnualBudgetPreparationTests.test_allotment_register_pages_search_and_export_share_all_matches`
Log `.tmp/budget-register-focused.log`. Tests retrieve 111 records per register
across three pages, check exact/empty searches, complete exports, retained search
metadata and outsider isolation. The initial setup was interrupted before tests
to add missing CSV/io test imports; it did not establish a result.

Initial dependent SQLite: FAIL - CAUSED BY CURRENT WORK (counter-label expectation),
63 discovered, 59 passed, 3 skipped and one failed;33.125s, exit1. The existing
annual filter test expected "1 visible version"; it now expects "1 matching version"
and asserts the complete matching count. Final same-scope rerun PASS: 63 discovered, 60 passed, 3 native-only skips;
31.885s, exit 0. Skips are not passes. Both fresh SQLite stores destroyed:
`python .tmp/earlier_sqlite.py budget finance.test_work_tasks.FinanceBudgetWorkTaskContractTests`
Logs `.tmp/budget-register-regression.log` (initial) and `.tmp/budget-register-final.log` (final).
PASS native focused: 2/2, no skips, 5.348s, exit 0; same two labels using `.tmp/retrieval_native.py`,
log `.tmp/budget-register-native.log`. Disposable MySQL 8.4.11 loopback 33308;
fresh test stores destroyed and owned server stopped.

PASS browser: actual Next links reach records 101-111 in both registers; entering
an exact proposal title or ARO number returns one match and resets the page.
Both downloaded CSVs contain 111 rows. Screenshots and CSVs retained under
`output/playwright/budget-*`. Narrow viewport/document widths both 390px;
tables preserve horizontal scrolling. No financial action used.

The isolated fixture `.tmp/budget-register-browser-20260922b` is copied offline
from the previous synthetic fixture and seeded with 111 proposal drafts and 111 ARO
drafts, plus service-created synthetic authority. It is not a production benchmark
or LGU financial evidence. The first fixture seed hit an existing synthetic username;
a fresh copy with prefixed users resolved that fixture-only issue. Browser/server
are stopped. Operator DB SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
`git diff --check`: PASS.

NOT RUN - OUT OF SCOPE: full-project local suite for bounded Budget query/template
and additive export-metadata changes. Full Budget/dependent checks and focused
native coverage are the selected scope. Remote CI remains separate evidence.
No operator migration, master merge, deployment, official-form or LGU acceptance.

## Remaining work

FG-11 remains partial: Accounting period-close and bank-reconciliation caps still
need repair. Budget calls and department-wide authority summaries remain unsliced;
large-volume query cost needs separate operational qualification. Required outputs,
local earmark basis, controlled-print/custody rehearsal and live deployment acceptance
remain open. eGAPS stays untouched.
