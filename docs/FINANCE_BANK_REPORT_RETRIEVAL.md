# Bank candidates and report generation history — 2026-09-24

Development branch `codex/finance-bank-report-retrieval`, based on v0.7.143
`e677ff9eea63bb571d7bd27c5003ad40040260ab`, draft PR #104.

Bank reconciliation exposed manual match actions only for the first 30 eligible
journal lines per statement row. Each row now has independent ten-candidate pages,
complete counts and previous/next links that retain the other rows' pages. Existing
bank/office/date/amount/direction selection and global reserved-line exclusion stay
intact. The posted match still uses the original governed service and source locks.
Paging is read-only and never automatically matches a line. Wider match cells keep
reference/basis controls readable within the existing horizontally scrolling table.

Reporting definition detail remains a 15-run preview, now with the full visible
count and a direct link to its definition-filtered, paginated run register. The link
lands at that register. Own/department run visibility is unchanged; neither counts
nor preview links disclose another user's hidden runs. No generation, approval,
download, posting, schema or persistence contract change.

## Validation

FAIL - PRE-EXISTING: two baseline tests reproduced the missing retrieval before
application edits, 19.763s, exit 1. Bank returned only 30 candidates, and report
preview omitted its complete visible count/navigation.
Log `.tmp/bank-report-retrieval-baseline.log`.

Regression command:
`python .tmp/earlier_sqlite.py accounting.tests reporting.tests reporting.test_run_retrieval`.
PASS: 97/97, 48.767s, no skips, exit 0. Both default/Finance test stores destroyed;
runner terminal. Log `.tmp/bank-report-retrieval-sqlite.log`.
Bank coverage traverses all 61 eligible candidates, excludes an
already reserved source, keeps a second row's page, confirms no audit writes from
navigation and actually matches a later candidate through the existing POST route.
Reporting coverage follows the definition-scoped link to page 3, checking full
counts, selected definition and user/office exclusion. Existing Accounting and
Reporting tests cover dependent controls and the unchanged default page size.

PASS: Playwright synthetic two-store fixture, desktop 1440×1000 and narrow 390×844.
Navigate between candidate pages 6 and 7 while the second row stays on page 2;
select the final candidate with a recorded basis and observe retained manual-match
evidence. Narrow inspection exposed a cramped column; an 18rem minimum width
resolved it within the existing scrollable table. Final screenshots inspected:
[desktop](../output/playwright/bank-candidates-last-desktop.png),
[narrow](../output/playwright/bank-candidates-last-mobile.png).
Browser/server stopped. Reporting's small link/count addition is covered by rendered
HTTP assertions; no fresh Reporting browser claim. No LGU acceptance claim.

PASS: `git diff --check` and changed-document local Markdown targets.
Operator database SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

NOT RUN - OUT OF SCOPE: native MySQL and full cross-module regression. This change
paginates an already selected candidate list and adds read counts/navigation, with
no financial calculation, mutation, lock or schema change. Existing default
and Finance test stores remain separate. Wider production-load and human acceptance
remain distinct requirements.

## Remaining retrieval assessment

FG-11 remains partial. A broader source scan finds Reporting workspace previews of
eight active schedules, five statement-note sets and five reference comparisons.
Individual report runs expose their complete reference-comparison histories;
verify clear continuation from previews. Older statement-note sets and schedules
need complete route/retrieval assessment. Do not classify filename/search-string
slices as record truncation, or a recent preview as missing data without checking
its full navigation path.

After resolving those findings, reconcile retrieval against the complete foundation
requirements and broaden integrated validation. Keep Budget certified expenditure
coverage, unknown earmark semantics and exact outputs/human acceptance visible in
the [foundation gate](FINANCE_FOUNDATION_GATE.md). No master merge or deployment;
production NO-GO and overall goal active.
