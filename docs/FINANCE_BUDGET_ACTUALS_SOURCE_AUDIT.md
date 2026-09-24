# Budget historical actuals: source audit — 2026-09-24

FG-03 remains **PARTIALLY IMPLEMENTED**. This source audit informs the next Budget
checkpoint after retrieval; it does not certify any GRAND amounts or establish
local form acceptance. See [current planning context](FINANCE_BUDGET_PLANNING_CONTEXT.md)
and the [foundation gate](FINANCE_FOUNDATION_GATE.md).

## Verified national reference

DBM's [2023 Budget Operations Manual for LGUs](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf)
was retrieved directly from its published URL on 2026-09-24: HTTP 200,
7,524,425 bytes, 327 PDF pages, SHA-256
`16F23003C2ED3E5F5957CECE4A3512418912991782A1C3582414644F6DAE0575`.
The [DBM circular page](https://www.dbm.gov.ph/index.php/local-budget-circulars?catid=85&id=85&view=article)
identifies Local Budget Circular 152, dated 2023-08-02. This establishes the cited
edition's content; it is not a claim that every later issuance has been audited.

PDF text was extracted and the LBP Form 2 layout/instructions were rendered and
visually checked. Printed pages 62–63 are PDF pages 77–78 (one-based).
Printed page 61/PDF page 76 contains the preceding LBP Form 1 instructions.

| Source | Verified requirement |
|---|---|
| LBP Form 2, printed p. 62 | Department/office and account-code rows; past-year actual, current first-semester actual, second-semester estimate, current total and proposed-year amount. Categories include personal services, operating expenses, financial expenses, capital outlays and special-purpose appropriations. |
| LBP Form 2 instructions, p. 63 | Past-year column concerns expenditures incurred. First-semester actual expenditures require Local Accountant certification. The Department Head prepares second-semester estimates; office totals must reconcile with LBP Form 1. |
| LBP Form 2 signature block, p. 62 | Preparation by Department Head, review by Local Budget Officer and approval by Local Chief Executive are distinct from actual-expenditure certification. |
| LBP Form 1 instructions, p. 61 | Historical/first-semester receipts and expenditures use joint Local Treasurer/Local Accountant certification, based on the applicable trial balance. Its second-semester estimates are prepared by the Local Budget Officer. Do not copy Form 2's role boundary into Form 1. |

Local retained research files are `.tmp/dbm-budget-operations-2023.pdf`,
`.tmp/dbm-lbp-page77.png`, `.tmp/dbm-lbp-page78.png` and extracted text in
`.tmp/dbm-lbp-context.txt`. They are reference artifacts, not application records.
The web fetcher timed out on the PDF, but direct HTTPS retrieval succeeded; source
inspection above uses that actual file, not search snippets.

## Current code and concrete gap

Follow-up reference identified 2026-09-25: DBM's official
[Local Budget Memorandum 94 page](https://www.dbm.gov.ph/index.php?catid=453&id=4049%3Alocal-budget-memorandum-no-94&view=article)
identifies the June 10, 2026 memorandum for indicative FY2027 NTA and annual budget
preparation. Its complete PDF has **not** yet been inspected: the web reader rejected
the 19,442,172-byte resource, and the slow direct download was cancelled before a
complete file was retained. Check the actual provisions before claiming this issuance
confirms or changes the form requirements above; its title alone does not establish that.

`budget/planning_context.py::build_context` selects posted `JournalLine` records
only where the account type is `expense`, groups exact fund/office/account identities,
and excludes explicit opening/closing/direct-equity source purposes. It retains
individual dated source lines, estimates and original-authority evidence.
Submitted snapshots remain immutable through the existing Budget review lifecycle.

This is useful **posted expense activity**, but it cannot supply complete certified
budget actuals. Capital outlays can have asset-side ledger sources outside that
query; broadening it to every asset debit would also be wrong. A journal account
class does not establish expenditure purpose, complete coverage or certification.
Likewise a Budget approval is not the separate Local Accountant certification.
Do not convert missing historical data to zero or backfill historical approvals.

### Reproduced inconsistency in the existing Budget report

`reporting/datasets.py::BudgetVersusPostedActualDataset` also selects expense lines,
but currently does not apply the planning-context exclusion of typed nominal closing
entries. An isolated fresh two-store SQLite probe reused the existing Finance
reporting fixture, retained a balanced 20,000 expense posting and added a balanced
typed nominal closing entry against the same expense/office/fund:

| Observation | Before closing | After closing |
|---|---|---|
| Reported posted actual expense | 20,000.00 | 0.00 |
| Report control status | reconciled | reconciled |
| Original expense journal | posted | posted |

The closing journal's retained purpose was `closing`. No actual source correction
was performed. This is a confirmed reporting defect, not a certification-policy
uncertainty: nominal closure should not erase the period's expense activity.
The existing scoped/full passing tests did not include this Budget-report case.

Probe command: `.tmp/foundation_full_sqlite.py budget_actual_probe.BudgetActualClosingProbe.test_nominal_close_effect`.
The probe asserts the defective before/after values to verify reproduction; its
successful outcome is **not** an application-correctness pass. One probe, 1.165s,
exit 0, fresh test stores destroyed; `.tmp/budget-actual-closing-probe.log` retains
the JSON observation. No tracked application/test source changed.

Repair this existing report boundary after My Work, before expanding actuals
certification. Exercise nominal closing and its exact reversal lineage separately
from ordinary expense corrections; keep historical issued output unchanged and
retain explanatory source evidence. Opening/direct-equity treatment and explicit
Accounting-owner selection also need reconciliation with the established source
contracts rather than assumptions based on department labels.

The subsequent [expense-activity checkpoint](FINANCE_BUDGET_ACTUAL_ACTIVITY.md)
repairs the reproduced closing, lineage and empty-activity defects with SQLite/native
validation. The reproduction above describes the pre-repair revision. The subsequent
[owner checkpoint](FINANCE_BUDGET_ACTUAL_OWNERSHIP.md) replaces department-name guessing
with captured authorized fiscal-year ownership and separate ledger keys. Certified
expenditure and capital-outlay coverage remain open.

## Implementation requirements before changing the calculation

1. Trace the existing source and reporting contracts for actual expenditure by
   fund, office, period and object. Identify explicit treatment for capital outlays,
   corrections and non-expenditure movements; do not infer treatment from free text
   or equate all expense debits with certified budget expenditure.
2. Reuse the governed reporting/source-evidence mechanisms where they can retain
   an exact version, source identities, classification decisions, totals and evidence
   of completeness. Account for historical certified sources outside GRAND without
   inventing their journals or certification.
3. Represent actual certification separately from proposal preparation, estimate
   evidence and approval. Retain actor authority, period, source hash/version and
   correction/supersession history; enforce independent review and current visibility.
4. Proposal context must pin the certified version it used while keeping the
   existing narrower ledger projection plainly identifiable. Missing certification,
   uncovered dimensions and inconsistent totals must remain visible.
5. Verify all object classes, dated corrections, reused source lines, departmental
   boundaries and cross-office certification. Prove office totals reconcile with the
   applicable summary before calling the LBP comparison complete.

This is a design constraint list, not an approved schema or completed implementation.
Exact local classifications and evidence, current amendments, accepted forms and
named-officer acceptance remain open. Earmark capacity/consumption remains separately
unconfirmed; this manual inspection does not resolve that question.

## Validation boundary

PASS — direct PDF retrieval/hash, text inspection, visual review of the relevant
form/instructions and comparison against the current planning-context source.
NOT RUN — OUT OF SCOPE: Budget application/native tests for this research-only
document; no Budget code, model, data or financial calculation was changed.
