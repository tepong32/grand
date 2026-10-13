# Accounting retained history and opening rows — 2026-09-24

Development branch `codex/finance-accounting-history` starts from v0.7.142
`659b4747dcce819012f4ccfb62fb8edb7a1967ed`, draft PR #103.

Reconciliation history previously stopped at 25 runs. Opening details stopped at
500 staged rows and 50 events; the disclosed row cap still prevented reaching later
row corrections through the screen. All three now reuse Accounting's existing
50-record pagination, complete matching counts and stable ordering. Each opening
list has an independent page parameter; links retain the other page and anchors.
Reconciliation navigation retains the selected as-of date without changing the
existing all-date history selection or current financial comparisons.

Department/record scope precedes pagination. Existing read, export and correction
permissions remain. Full opening exports, financial calculations, posting services,
maker-checker, UAT restrictions and immutable history are unchanged. No migration
or persistence/locking changes. Later rows use the original governed correction.

## Validation

FAIL - PRE-EXISTING: two baseline tests failed before application edits, 11.473s,
exit 1. Reconciliation returned 25 rather than 50 runs; opening rows had no history
page-preserving links. Log `.tmp/accounting-history-baseline.log`.

Initial regression: `python .tmp/earlier_sqlite.py accounting.tests`, 59 tests,
13.751s; 58 passed and one new test expectation failed, exit 1, no skips.
FAIL - CAUSED BY CURRENT WORK (test expectation): the no-write assertion ran after
CSV export, which correctly appends its existing `exported` audit event. Move the
no-write assertion before export, assert its retained checksum explicitly, and
include that event in later preservation checks. Application code unchanged.
Log `.tmp/accounting-history-sqlite.log`.

Final affected rerun PASS: 2/2, 16.229s, no skips, exit 0. Command:
`python .tmp/earlier_sqlite.py accounting.tests.StandaloneAccountingTests.test_control_reconciliation_history_reaches_all_scoped_runs accounting.tests.StandaloneAccountingTests.test_opening_detail_reaches_all_rows_events_and_later_correction`.
Log `.tmp/accounting-history-final.log`. Both default/Finance test stores destroyed;
runners terminal. The other 58 tests passed against the same application code;
the full module was not repeated after the test-only correction. No unresolved
local test failure. Prior PR #103 remote MySQL/verify checks remained pending at
inspection and are not counted as passes.

Coverage traverses 61 visible
reconciliations while excluding 61 foreign-office runs; retrieves and exports all
511 opening rows; traverses all 61 opening events; retains independent page/date
parameters; verifies permissions and no history writes from retrieval; performs a
source-reasoned correction to row 511 while retaining all previous events. Existing
Accounting tests cover dependent opening lifecycle, posting, control and access rules.

PASS: Playwright on disposable two-store synthetic data. Desktop 1440×1000 displays
rows 501–511 and their correction links; clicking row 511 opens its correction form.
Narrow 390×844 reconciliation history displays rows 51–61 and working Previous
navigation retaining the as-of date. Wide tables retain horizontal scrolling;
pagination remains visible below the table. Screenshots visually inspected:
[later opening rows](../output/playwright/accounting-opening-later-rows-desktop.png),
[narrow reconciliation history](../output/playwright/accounting-reconciliation-history-mobile.png).
Browser and its server stopped; this is synthetic inspection, not LGU acceptance.

PASS: `git diff --check` and changed-document local Markdown targets.
Operator database SHA256 unchanged:
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

NOT RUN - OUT OF SCOPE: native MySQL and full cross-module suites. The repair changes
ordinary ordered read selection and reuses existing presentation; no schema, locks,
aggregations or financial service changes. The full affected Accounting module is
the chosen regression scope, preserving default/Finance test-store separation.

## Remaining foundation work

FG-11 remains partial. Source review confirms that Reporting's definition detail
shows 15 runs with no direct complete-history link, although its existing paginated
run register accepts a definition filter. Add clear scoped navigation there.

Bank detail builds only 30 same-amount/direction match candidates per statement
row, and its visible manual actions are attached to those candidates. Reproduce
reachability beyond that cap before repairing it; the existence of a POST endpoint
alone does not prove an ordinary clerk can select every eligible source. Preserve
reserved-line exclusion, exact amount/direction, office/bank scope and match locks.

Keep Budget certified actuals/coverage, unconfirmed earmark semantics and exact
required outputs/human acceptance visible in the [foundation gate](FINANCE_FOUNDATION_GATE.md).
This checkpoint does not complete Finance. No master merge or deployment;
production remains NO-GO and overall goal active.
