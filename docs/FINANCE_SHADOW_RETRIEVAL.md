# Shadow-cycle and retained-review retrieval — 2026-09-24

Development branch `codex/finance-shadow-retrieval`, based on v0.7.140
`16f74d6c4ce161108e59331b5ef733ac1e229aa5` and draft PR #101.
This is a supporting Finance acceptance capability, not cutover authorization.

The register previously displayed only its first 100 visible/filter-matching cycles
while exporting all matches. It now uses stable 50-row pages with complete matching
counts, retained filters and the existing full export. Visibility, next-action
calculation and stakeholder/authority rules remain unchanged.

Cycle details previously displayed only 20 evidence reviews/corrections, referring
to older audit history without a complete navigation route on the page. That same
event selection now has 20-row pages, truthful counts and direct previous/next
navigation. Department, cycle target and event-type filters precede pagination.
History remains immutable; no additional audit-event types become visible.

## Validation

Baseline FAIL - PRE-EXISTING: two tests reproduced the limits before application
edits, 16.852s, exit 1. The register returned 100 rather than 50 rows; later history
page requests repeated the same 20 events. Log `.tmp/shadow-retrieval-baseline.log`.

New coverage traverses 111 cycles without duplicate/missing identities and compares
the complete matching CSV source set. It checks foreign-office exclusion, retained
search/year/status filters and full export count. History coverage traverses 45
corrections plus the genuine plan-approval review (46 events) and excludes an
unrelated target, checking older-page navigation.

Initial regression — FAIL - CAUSED BY CURRENT WORK (test expectation):
`python .tmp/earlier_sqlite.py finance.test_cutover` ran 54 tests in 173.293s;
53 passed and the new history test failed, no skips, exit 1. Its fixture already
creates a retained plan-approval review; the expected set incorrectly omitted it.
The application correctly included that event. The expectation now explicitly
includes the original review, without changing application selection.
Log `.tmp/shadow-retrieval-sqlite.log`.

Final affected rerun — PASS: 2/2, 12.120s, no skips, exit 0. Command:
`python .tmp/earlier_sqlite.py finance.test_cutover.FinanceShadowCutoverTests.test_shadow_register_pages_cover_every_match_and_full_export finance.test_cutover.FinanceShadowCutoverTests.test_shadow_review_history_pages_retain_older_evidence`.
Log `.tmp/shadow-retrieval-final.log`. Fresh default test databases destroyed;
Finance alias remains separate and was not needed by this module. All runners
terminal. The other 53 tests passed against the same application code; the whole
module was not repeated after the test-only correction. No unresolved test failure.

PASS: `git diff --check`, changed-document local link targets and unchanged operator
database SHA256 `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

NOT RUN - OUT OF SCOPE: native MySQL, fresh browser/print checks and full cross-module
regression. This change uses ordinary ordered selection/count/pagination, with no
persistence, SQL aggregation, migration, financial lock or approval-service change.
The full shadow/cutover module exercises the affected routes and their dependent
authority controls; template assertions verify rendered counts and links. This does
not establish visual/office acceptance or a production-volume performance benchmark.

## Remaining retrieval audit

FG-11 remains partial. Source inspection identifies these follow-ups; they are not
new runtime reproductions or repaired capabilities:

- Budget proposal and quarterly decision displays retain first-30 event slices.
- Remittance audit display retains a first-50 slice. Its CSV exports allocations and
  posting evidence, not a complete audit-event listing.
- Accounting subsidiary-control reconciliation history retains first 25 runs; the
  screen offers individual exports but no continuation.
- Opening-balance detail explicitly discloses its first-500 row limit; row-level
  correction reachability and first-50 event history need assessment.
- Report-definition history retains 15 runs, but Reporting already has a complete
  paginated register with a definition filter. Assess clear navigation/disclosure
  instead of treating this as wholly inaccessible data.
- Bank matching's 30 candidates are a suggestion list, not a register. Verify full
  manual matching reachability before treating this limit as a retrieval defect.

Continue ordinary Budget/remittance/Accounting history access before more output
breadth. Keep certified Budget actuals, unknown earmark semantics, exact required
forms and human acceptance visible in the [foundation gate](FINANCE_FOUNDATION_GATE.md).
No master merge/deployment; production remains NO-GO and the overall goal incomplete.
