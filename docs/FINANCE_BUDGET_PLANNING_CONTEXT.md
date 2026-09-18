# Budget historical planning context — 2026-09-18

Foundation checkpoint 2A, branch `codex/finance-budget-history`, based on remotely
verified v0.7.117 `f5f4d83`. See [the gap register](FINANCE_FOUNDATION_GATE.md), FG-03,
and D-105. This is development evidence, not master integration or LGU acceptance.

## Connected behavior

Proposal detail now shows dated comparison context using its explicit FiscalYear
Accounting department. For proposed year Y, prior activity is Y−2 and first-half
activity is January–June Y−1, bounded by capture date. Exact fund/office/account
groups prevent duplicated historical amounts across proposal PPAs. Journal lines
do not supply reliable PPA or funding-source attribution; neither is inferred.

Reuse posted expense lines, retaining source journal/line/date/reference and net
debit less credit. Exclude typed opening, nominal closing and direct-equity sources,
including their reversal lineage. Missing sources remain missing. This projection
is **posted expense activity, not certified expenditure**: capital outlay, coverage
and accepted expenditure certification remain open. Capture date records when the
system read available history; it does not reconstruct what staff knew at an old date.

Preparers may record an explicit second-half estimate (including zero), its current
planning-year preparation date and evidence basis on each proposal line. All lines
in a comparison group need estimates before the group estimate is complete. An
indicative sum appears only after the first half ends and both components exist.
It is not spending authority or certified full-year actual. Consolidation copies
the estimates and their basis with the proposal lines.

Original appropriation reuses retained authorized final schedules for the same
ledger, Budget office, year and dimension codes, effective by capture date. Multiple
original roots are shown as ambiguous. Supplemental and successor schedules remain
separate evidence; their presence does not invent an adjusted balance.

## Controls and evidence

Existing Budget permissions and office ownership govern access. Mutation retains
UAT denial and independent review. Estimate editing and submission lock the same
BudgetVersion parent. Submission freezes context in the version and audit event;
approval checks that retained copy against the submission event. Return/resubmit
captures a new copy while audit history retains the old one. Historical approvals
without a snapshot stay explicitly unavailable, never backfilled with today's data.

CSV export uses the same displayed snapshot and archives source metadata and hash
through the existing export facility. It is a planning aid, not an accepted LBP form.
No journals, spending authority, historical approvals or operator data are rewritten.
Migration 0009 adds nullable estimate evidence and an empty-default snapshot only.

## Reference boundary

The official DBM [2023 Budget Operations Manual](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf)
and [eBudget user manual](https://www.dbm.gov.ph/wp-content/uploads/LGRCB/eBudget-for-LGUs/DBM_E-BUDGET-for-LGUs_USERS-MANUAL_v2_20211123-%281%29.pdf)
identify the LBP comparison structure (past year, current first-half actual/second-half
estimate, proposed year). Search evidence supported that distinction; direct manual
retrieval was incomplete. This does not establish current local form acceptance or
authorize treating the narrower ledger projection as certified expenditure.

## Validation

- PASS: `python .tmp/earlier_sqlite.py budget finance.test_work_tasks.FinanceBudgetWorkTaskContractTests`:
  45 discovered, 44 passed, one native-only skip, 24.723s. Fresh default/Finance test
  stores destroyed. Initial focused failure was a missing required reversal-fixture
  argument; corrected before this run.
- PASS: `python .tmp/retrieval_native.py budget.test_planning_context budget.test_planning_concurrency`:
  6/6, 9.462s, fresh native two-store runner. Includes simultaneous estimate/submission,
  source dates, actual reversal exclusion, ambiguous authority roots, retained output,
  independent review, UAT/office denial and estimate validation. Owned MySQL stopped.
- PASS: isolated synthetic browser: enter estimate, submit, independent reviewer
  approves with required basis, download retained CSV. Desktop 1440px and narrow
  390px reviewed; document width remains 390px with the table contained horizontally.
  Screenshots: `output/playwright/planning-context-desktop.png` and
  `output/playwright/planning-context-narrow.png`. Browser/server stopped.
- PASS: `python .tmp/earlier_sqlite.py`: 1,490 discovered, 1,369 passed, 121 skipped,
  854.123s, exit 0. Full scope chosen for shared Budget submission/model contracts
  and the release checkpoint. Both test stores destroyed. Skips are not passes.
- PASS: system check, migration drift and staged diff check. Operator database SHA-256
  remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
- NOT RUN — OUT OF SCOPE: production migrations, LGU acceptance and formal output
  certification. Disposable browser fixture migrated; operator databases untouched.

Next: finish authoritative expenditure coverage/acceptance mapping for FG-03, and
trace existing quarterly-plan/earmark semantics before introducing domain objects.
