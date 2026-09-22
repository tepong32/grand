# Voucher workbench queue and history retrieval

2026-09-22 development checkpoint, based on v0.7.125 / draft PR #87.
Branch: `codex/finance-voucher-retrieval`.

## Observed gap and repair

The workbench selected the newest 100 actionable case IDs, displayed those in the
queue, then excluded only those IDs from a second 100-row history slice. Older
otherwise-actionable cases therefore appeared under Shared case history, and older
records could disappear from both displayed sections. Existing filters, saved views,
role/requesting-office scope, next-action descriptions and complete exports already
existed; those contracts are reused.

The queue now contains all filtered cases in the same role/preview stages as before.
History is the complementary set of stages, independent of which queue page is
shown. Both have deterministic 50-row pages, complete counts/ranges and independent
page parameters. Navigation preserves active search, filters, saved-view identity and
the other section's page. Applying filters resets page numbers and scrolls to the
queue. The existing export still includes the whole filtered set, not one page.
This removes misleading placement of old actionable work and makes older records
reachable without reconstructing a search or using an external register.

## Controls preserved

Scope and filter application precede partitioning/pagination. Saved views remain
owner-only and re-evaluate current permissions; requesting-office visibility remains
bound to that office. UAT queue-stage selection and denied financial mutation remain
unchanged. Existing next-action semantics are not promoted to approval: opening a
case still requires its governed services and controls. No financial models, amounts,
state transitions, posting, correction lineage or cross-store routing change.

## Validation

PASS focused SQLite HTTP/database checks: 2/2, no skips, 3.478s, exit 0.
`python .tmp/earlier_sqlite.py vouchers.tests.VoucherWorkflowTests.test_workspace_pages_keep_actionable_cases_out_of_shared_history vouchers.tests.VoucherWorkflowTests.test_saved_case_view_pagination_retains_scope_and_owner`
Log: `.tmp/voucher-retrieval-focused.log`. They cover 111 queue plus 111 history
records, no overlap/omission, complete 222-row CSV, exact search, malformed page
recovery, saved-view ownership/preservation and requesting-office isolation.

PASS dependent regression: 122/122, no skips, 70.697s, exit 0:
`python .tmp/earlier_sqlite.py vouchers.tests finance.test_work_tasks.FinanceDVCustodyWorkTaskContractTests budget.test_payable_handoff`
Log: `.tmp/voucher-retrieval-regression.log`. Both test stores were destroyed; runner terminal.
`git diff --check`: PASS.

PASS Playwright: opened an actual private saved view, clicked through queue pages
1-3 and history pages 1-3, retained saved-view/other-page parameters, reached both
oldest records and saw 101-111 of 111 in each section. Actual browser CSV download
contains 222 unique cases: 111 Accounting DV preparation and 111 completed. Retained
screenshots and CSV: `output/playwright/voucher-queue-last-page.png`,
`voucher-history-last-page.png`, `voucher-history-narrow.png`,
`voucher-volume-register.csv`. The narrow viewport and document are both 390px;
tables remain horizontally scrollable, and footer page controls wrap inside the card.

Fixture `.tmp/voucher-browser-20260922` copies the prior synthetic stores offline and
adds retrieval-only rows. Its stage labels are test inputs, not evidence of performed
financial transitions or valid releases. No case action was performed. Browser and
loopback server are stopped. Both operator stores and eGAPS remain untouched;
operator SQLite SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

NOT RUN - OUT OF SCOPE: native MySQL and full-project local suites for this read-only
query/template repair with no schema or persistence changes. Dependent scope covers
voucher/source/custody controls. New remote CI and external acceptance remain separate.

## Remaining scope and next checkpoint

FG-11 remains partial. Budget annual proposal and allotment pages still slice at
100; direct inspection confirms existing filters/exports and full underlying
querysets before their display slice. Accounting period-close and bank reconciliation
caps also remain. Inspect and repair those registers before claiming complete
retrieval. Actual volume performance, configured deployment, official forms,
controlled-print/custody rehearsal and LGU acceptance remain open.
