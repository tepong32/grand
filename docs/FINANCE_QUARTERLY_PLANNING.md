# Quarterly financial planning — foundation checkpoint 3A

2026-09-18, branch `codex/finance-quarterly-planning`, base v0.7.118 `07b9185`.
The [pre-implementation investigation](FINANCE_QUARTERLY_EARMARK_DESIGN.md) establishes
the planning/authority distinction. This is development evidence, not master
integration, an accepted LBE form or production authorization.

## What connects

Previously, GRAND had annual appropriation authority, allotment movements and
obligation certification, plus a quarterly-target form starter. It had no operational
quarterly schedule. New QuarterlyFinancialPlan/QuarterlyPlanLine records connect
the exact authorized schedule to Q1–Q4 allocations, basis and separate physical
indicator/unit/target fields. Each version includes the entire authority schedule.
Missing quarters remain missing; submission requires four explicit nonnegative
amounts and a basis on each line. Their sum cannot exceed that line's authority.
Zero is valid. The remainder is labelled unplanned, never a reserve or available cash.
Physical targets are optional planning evidence and are not aggregated across units.

Staff enter through the appropriation detail, prepare/correct the header and rows,
submit, receive an independent review, and create a successor when needed. Existing
Budget allotment preparer/reviewer permissions govern the route; UAT membership
continues to deny mutation. A creator, submitter or recorded editing contributor
cannot independently review the same plan. System approval is not an inferred wet
signature: preparation/approval-route references and decision basis remain explicit.

## Retention and concurrency

Submission retains the complete plan, authority checksum and dated control context.
Control totals include the exact allotment/obligation movement references available
at capture with effective dates through the preparation date. This is not a claim
about what users knew historically. Later financial postings do not overwrite it.
Approval verifies retained submission evidence and unchanged planning inputs, while
allowing new financial movements to remain separate. Approved plans and rows cannot
be edited; returned plans retain their previous submission events.

Creation and approval serialize on the existing appropriation authority. A successor
pins the currently approved predecessor; competing or stale approvals cannot replace
a newer plan. The authority holds the current approved-plan pointer, avoiding an
unsupported conditional unique constraint. Edit and submit share the plan lock.
No planning service creates allotment, obligation, payable or journal movements.

## ARO continuity and human friction removed

Draft AROs show the approved quarterly plan, release effects and cumulative releases
through their effective date. Submission retains that exact plan/version/checksum
and comparison. A positive release above its quarter plan needs a stated timing
deviation basis, not a new financial authority. Posting rechecks intervening releases
against the same retained plan under the existing appropriation-line locks; a newly
unexplained difference requires return/correction. A later approved plan cannot
silently replace the evidence used by an already submitted ARO.

This removes a separate spreadsheet lookup and makes the timing difference visible
before review. The existing annual authority, withholding, obligation, maker-checker
and immutable posting checks still apply. Older AROs without retained planning
evidence stay explicitly unavailable; they receive no fabricated historical plan.
An absent plan does not retrospectively invalidate an existing financial route.

Planning CSV archives the same displayed snapshot. Posted ARO CSV adds its retained
plan reference/version/checksum/quarter and deviation basis; archive metadata retains
the comparison. Existing financial movement checksums retain their original meaning.

## Validation

- PASS: initial `python .tmp/earlier_sqlite.py budget.test_quarterly`: 6/6, 3.436s.
- PASS: `python .tmp/earlier_sqlite.py budget finance.test_work_tasks.FinanceBudgetWorkTaskContractTests`:
  54 discovered, 51 passed, three native-only skips, 27.279s.
- PASS: initial fresh MySQL `python .tmp/retrieval_native.py budget.test_quarterly budget.test_quarterly_concurrency`:
  8/8, 9.228s, including approval/approval and edit/submit races.
- PASS: expanded fresh MySQL `python .tmp/retrieval_native.py budget finance.test_work_tasks.FinanceBudgetWorkTaskContractTests`:
  54/54, 46.087s, including the final dated-source/contributor checks and all three
  native Budget races. Both stores destroyed; owned MySQL stopped.
- PASS: isolated browser creates plan, enters quarters/targets, submits, independently
  approves and downloads CSV. ARO above plan is rejected without a basis, corrected,
  independently posted and downloaded with exact retained plan identity. Desktop
  1440px and narrow 390px checked; narrow document width stays 390px. Browser/server
  stopped. Evidence: `output/playwright/quarterly-plan-desktop.png`,
  `quarterly-plan-narrow.png`, `quarterly-aro-retained.png`. Final template review
  corrected inherited minimum card heights and posted-state guidance.
- PASS: final reviewer-button visibility regression, `python .tmp/earlier_sqlite.py budget.test_quarterly`: 7/7, 4.066s, exit 0. Contributors see independent-review waiting guidance; the service denial remains enforced.
- PASS: full SQLite regression, `python .tmp/earlier_sqlite.py`: 1,499 discovered, 1,376 passed, 123 skipped, 815.100s, exit 0. Both test stores destroyed; log `.tmp/quarterly-full-sqlite.log`. The final reviewer-button change is covered by the separate seven-test run above; no financial service changed after the broad run began. Skips are not passes.
- NOT RUN — OUT OF SCOPE: production migration, exact local form/signatory acceptance,
  physical printing, LGU operational acceptance. Migration 0010 reached disposable
  native/SQLite/browser fixtures only; operator databases remain untouched.

## Still open

FG-04 now has an operational schedule and ARO connection. Exact local reserved-column
meaning, form acceptance and ordinary office acceptance remain open. This does not
claim a legally mandatory quarter cap, automatic cash program, physical accomplishment
tracking or certificate lifecycle. FG-05 earmark capacity, identity, consumption and
dated correction still require the separate semantic work. Historical expenditure
coverage, exact outputs and the full Finance completion/production gates remain open.
