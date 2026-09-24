# Finance My Work retrieval — 2026-09-24

Development repair prepared from v0.7.145 in the isolated
`codex/finance-my-work-pagination` checkout while the unchanged baseline underwent
full SQLite/native regression. See the [foundation gate](FINANCE_FOUNDATION_GATE.md).
This is personal work retrieval, not a financial transition or acceptance decision.
The branch subsequently fast-forwarded to the documentation-only audit v0.7.146,
`b05fde6f6cab0bc7d767af0ca1daaef2b354f3f8`, [draft PR #107](https://github.com/tepong32/grand/pull/107).
No application/test code changed during that integration.

## Defect and behavior

The prior HTTP page returned only the first 100 authorized tasks. With 105 Waiting
sources, page 2 repeated page 1; its common footer suggested exact-queue links that
only rendered in Ready for me. The original reproduction is retained in the
integrated audit checkpoint.

All six personal views now use complete 50-item pages with total/range counts,
Next/Previous links and retained view/calendar parameters. Existing source adapters
still determine permission, attribution, current state, dates and deterministic
ordering before pagination. Completed events retain their stable identity tie-break.
Malformed page text selects page 1; numeric out-of-range pages select the last page,
using the existing Django paginator convention. Invalid view/window handling remains
unchanged. Empty scoped results show 0–0 of 0.

The projection accepts an explicit `display_limit=None` for page navigation. Its
default remains 100; the existing CSV exporter still requests its explicit 100-row
snapshot and retains eligible count, truncation and original archived bytes. Page
selection does not redefine export content or grant export permission. Separately
authorized read access continues after editing permission is withdrawn; removing
source read access hides Waiting records. UAT action exclusion remains.

No schema, posting, balance, custody or source transition changes. The projection
already built the complete task set before applying the old cap; this change does
not claim server-side query pagination or production-scale performance improvements.
Live source changes between requests can change pages; navigation is not a frozen
financial snapshot.

## Validation

Baseline synthetic reproduction: 105 eligible / 100 shown, page 2 repeated all
identities, exact-queue links absent. Source records remained retained.

First full `finance.test_work_tasks` run: 79 tests in 71.043s; 78 passed and one new
test failed because it expected removal of edit permission to remove independently
granted read access. Source inspection confirmed the existing access rule. Corrected
the test to retain the 105 Waiting records while read access remains, then require
zero after its removal. Application permission logic was not changed.

PASS — final affected/export rerun: 3/3, 12.058s, no skips, exit 0. Command:
`.tmp/my_work_sqlite.py finance.test_work_tasks.FinanceWorkTaskContractTests.test_waiting_pages_reach_every_personal_source_and_recheck_scope finance.test_work_tasks.FinanceWorkTaskContractTests.test_work_export_requires_explicit_grant_and_matches_bounded_live_projection finance.test_work_tasks.FinanceWorkTaskContractTests.test_work_export_preserves_view_filters_and_fails_closed_without_receipt`.
The other 78 task tests passed on the same application code in the first run; only
the permission test changed afterward. Both runs created/destroyed fresh default
and Finance test stores and terminated. Logs are `.tmp/my-work-regression.log`
and `.tmp/my-work-final.log`.

PASS — `.tmp/my_work_sqlite.py finance.test_operations finance.test_setup_discovery_register`:
16/16, 11.502s, no skips, exit 0; fresh stores destroyed and runner terminal.
Log: `.tmp/my-work-entry-regression.log`. This checks shared Finance entry/access,
attention-group navigation and setup/discovery source-register dependencies.

PASS — changed Python compilation, feature-document local links and
`git diff --check`. Operator database SHA-256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
NOT RUN — OUT OF SCOPE: a separate full-project/native rerun of this navigation
delta. SQL source queries, financial persistence and transitions are unchanged;
complete task construction already preceded the old slice. The baseline full
SQLite/native runs passed as recorded in the [integrated audit](FINANCE_RETRIEVAL_INTEGRATED_AUDIT.md),
but must not be reported as full regression of this later application change.

PASS — Playwright synthetic browser at 1440×1000 and 390×844: page 3 displays sources
101–105 with a truthful count, Previous preserves Waiting and 14-day parameters,
and the final Open record link reaches retained `WAIT-CAP-104`. Narrow document
width equals viewport width (390px). Screenshots:
[desktop](../output/playwright/my-work-pages-desktop.png) and
[narrow pagination](../output/playwright/my-work-pages-narrow.png).
The synthetic browser and owned Django server were stopped afterward.

No production configuration, local-form/physical-custody acceptance or master merge
is implied. Certified Budget expenditure, unconfirmed earmark semantics and the
remaining ordinary/output gates stay open; the overall goal remains active.
