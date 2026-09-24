# Reporting schedules and retained statement navigation — 2026-09-24

Development branch `codex/finance-reporting-schedule-retrieval`, based on v0.7.144
`a32a35c29aebcd8ee112591b2d9931ecf31406b7`, draft PR #105.

The schedule panel previously showed only eight active schedules. Inactive schedules
could be created but had no retrieval route. The existing department-scoped panel
now has ten-record pages, complete matching counts and explicit Active/Inactive/All
selection. Default remains Active; invalid selection shows no records with a clear
message. Navigation preserves report filters and independent pages. Inactive dates
are labelled retained due dates, not promises of execution. Viewing never runs a
schedule or changes its due date, state or template.

Statement notes already have a complete department-scoped list. Individual report
runs already expose all their signed-reference comparisons. The workspace now
labels its five-item evidence lists as recent previews and provides direct guidance
to those complete routes. Historical notes navigation remains visible when the
statement definitions become inactive, matching the existing notes-screen access
check. No acceptance, evidence mutation, execution or financial authority change.

## Validation

Baseline, before application edits: 2 tests, 2.994s, exit 1.
FAIL - PRE-EXISTING: schedule test reproduced eight records rather than a complete
page. ERROR - CAUSED BY CURRENT WORK (fixture): the evidence test called a helper
that always created comparison version 1. The helper now accepts an explicit
version; new volume coverage creates seven distinct versions. No production
constraint was changed. Log `.tmp/reporting-schedule-baseline.log`.

Regression command:
`python .tmp/earlier_sqlite.py reporting.tests reporting.test_run_retrieval reporting.test_statement_notes reporting.test_statement_bundle`.
PASS: 55/55, 38.249s, no skips, exit 0. Both test stores destroyed; runner
terminal. Log `.tmp/reporting-schedule-sqlite.log`. New checks cover all 23 active/two inactive schedules, all/invalid
selection, other-office exclusion, retained report filters, unchanged due dates and
no generated runs. Seven notes and seven comparisons exercise the existing complete
routes; inactive statement definitions must retain navigation. Existing workflow,
source package and export tests cover dependent Reporting contracts.

PASS: Playwright on disposable synthetic two-store data. Desktop 1440×1000 reaches
active records 21–23 and Previous to 11–20. Selecting Inactive through the form
shows both inactive records with truthful date labels; narrow 390×844 controls are
readable. Screenshots inspected:
[desktop](../output/playwright/report-schedules-desktop.png),
[narrow inactive schedules](../output/playwright/report-schedules-inactive-mobile.png).
Browser/server stopped. No fresh statement-evidence browser assertion; rendered
HTTP tests establish those navigation routes. No LGU acceptance claim.

PASS: `git diff --check` and changed-document local Markdown targets.
Operator DB SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

NOT RUN - OUT OF SCOPE: native MySQL and whole-project regression in this isolated
read/presentation checkpoint. No migration, financial calculation, mutation service
or lock change. Both default/Finance test aliases remain separate. Broader integrated
validation follows the retrieval reassessment and is not implied by scoped passes.

## Retrieval reassessment next

The source scan across Budget, Accounting, vouchers, Finance and Reporting now
distinguishes actual record caps from recent previews, single-identity subqueries,
bounded exception samples and string-length limits. Reporting's 15-run and recent
approved previews have the complete run register; notes and comparisons have the
routes above. Finance My Work uses the task projection and a separately declared
export limit; assess its runtime behavior against the original requirements rather
than claiming completeness from a slice search alone.

Reconcile FG-11 and all retrieval requirements against current routes, evidence and
remaining volume/operational limits, then run broader integrated regression. Do not
let supporting retrieval work obscure Budget certified expenditure coverage,
unconfirmed earmark rules and exact required outputs/human acceptance. See the
[foundation gate](FINANCE_FOUNDATION_GATE.md). Overall goal active; production
NO-GO. No master merge or deployment.
