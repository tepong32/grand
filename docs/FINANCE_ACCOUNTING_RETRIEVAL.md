# Accounting register and handoff retrieval

2026-09-22 development checkpoint, based on v0.7.124 / draft PR #86.
Branch: `codex/finance-accounting-retrieval`.

## Observed gap and repair

The Accounting workspace sliced journals at 100 and each awaiting voucher/remittance
handoff list at 50. There was no page navigation. The handoff badges called the
slice length the awaiting-work count, hiding older work and understating the queue.
Existing journal filters, source detail links and full filtered CSV export were
already implemented. Financial source creation/posting is reused unchanged.

Each list now uses deterministic 50-row pages, complete matching counts and visible
ranges. Independent page parameters preserve search and other list state. A separate
handoff search locates requested JEV numbers, voucher/remittance references and
payee/agency names. Search resets its handoff pages and leaves journal filters intact.
Journal search remains separate and CSV continues to include every matching journal,
regardless of the displayed page. Empty handoff searches retain the search and zero
counts. Users retain existing role-dependent creation/reconciliation buttons.

## Controls and limitations

Department scoping happens before searching and pagination. The awaiting status
set remains pending, failed and materialized; posted/cancelled handoffs stay outside
that queue. No financial models, amounts, persistence services, posting, independent
review, correction lineage or separate-database routing change. GET does not perform
financial actions. This is a retrieval repair, not official-output or LGU acceptance.

## Validation

PASS: focused HTTP/database tests for 111 journals, 61 voucher handoffs and 61
remittance handoffs, full filtered CSV, exact search, independent pagination,
read-only buttons and department isolation: 3/3, no skips, 5.040s, exit 0.
Command: `python .tmp/earlier_sqlite.py accounting.tests.StandaloneAccountingTests.test_workspace_retrieves_all_journals_and_preserves_filtered_export accounting.tests.StandaloneAccountingTests.test_workspace_retrieves_old_handoffs_and_scopes_search vouchers.test_remittance_register.RemittanceWorkRegisterTests.test_accounting_handoff_retrieval_reaches_every_remittance`.
Log: `.tmp/accounting-retrieval-focused.log`.

PASS: dependent Accounting controls, remittance register and Accounting work-task
regression: 66/66, no skips, 19.440s, exit 0.
Command: `python .tmp/earlier_sqlite.py accounting.tests vouchers.test_remittance_register finance.test_work_tasks.FinanceAccountingWorkTaskContractTests`.
Log: `.tmp/accounting-retrieval-regression.log`. Both fresh test aliases destroyed.

PASS: Playwright browser clicked through handoff page 2 (51-61 of 61) and journal
page 3 (101-111 of 111), then found the oldest handoff through its search form while
retaining journal page 3. This exposed inherited URL fragments after searching;
explicit form targets were added and verified in the browser after regression.
Desktop and 390px screenshots are retained in `output/playwright/accounting-*`;
viewport and document widths both 390px, tables retain horizontal scrolling.
The disposable `.tmp/accounting-browser-20260922` is an offline copy of the earlier
synthetic fixture with additional draft retrieval rows, not valid new financial
handoffs or a posted-volume performance benchmark. No creation buttons were used.
An initial browser URL missed the `/finance/` prefix and returned 404; the corrected
route passed. Browser and loopback server are stopped.

PASS: `git diff --check`; operator database SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
NOT RUN - OUT OF SCOPE: native MySQL and full-project local suites for this read-only
query/template change with no schema or persistence-service changes. The dependent
suite covers the affected financial controls and retrieval paths. New PR CI remains
separate evidence. No production migration, master merge, deployment or LGU acceptance.
An initial discovery attempt failed on an editor-generated non-UTF8 dash before
any tests ran. Files were corrected to UTF8 and the focused runner restarted.

## Remaining retrieval audit

A fixed-string source scan still finds 100-row caps in voucher workbench queues,
Budget annual proposals and allotment orders, Accounting period-close and bank
reconciliation workspaces. Each needs route-level inspection and repair where it
prevents complete retrieval. Reporting source-detail previews and template lists
also use caps; determine whether they have a complete alternative before classifying
these as missing retrieval. Do not claim repository-wide cap removal from this slice.
The foundation gap register tracks this as FG-11.

Next: inspect remaining ordinary-work register caps and
continue controlled-print/custody and exact-output proof. Local earmark basis and
LGU form acceptance remain unknown; eGAPS stays untouched.
