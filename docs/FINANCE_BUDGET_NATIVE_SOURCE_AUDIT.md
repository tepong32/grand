# Native Budget actuals: source and attribution audit — 2026-09-25

Development v0.7.152 audit on `codex/finance-budget-native-source-audit`, based on v0.7.151,
`1d289b58b070a21e044c5249a2820131a1172c60` ([draft PR #112](https://github.com/tepong32/grand/pull/112)).
No application calculation, schema or financial history changes. This audit
implements the evidence-first step of the [actuals contract](FINANCE_BUDGET_ACTUALS_CONTRACT.md)
after [external adoption](FINANCE_BUDGET_ACTUAL_ADOPTION.md). FG-03 remains partial.

## Reproduced ordinary source gap

The probe uses the existing independently posted advance, actual release,
liquidation, refund and deposit services in fresh synthetic default/Finance stores.
It adds an independently posted synthetic equipment journal and creates a Budget
comparison with matching ledger/fund/office/account identities. No financial source
is rewritten to make the comparison work.

| Posted source | Amount | Retained meaning and observed scope |
|---|---:|---|
| Original officer advance | 1,000.00 | Asset recognition, original officer subsidiary and payable; no expense recognition |
| Actual released payment | 1,000.00 | Settles the payable, with retained release evidence; not another expense |
| Accepted expense liquidation | 200.00 | Expense debit and original advance credit; the expense line has no responsibility center |
| Officer cash refund | 100.00 | Cash receipt against the same advance; no new expense |
| Deposit of that refund | 100.00 | Moves the same receipt to bank; no new expense |
| Synthetic equipment candidate | 500.00 | Asset debit against a payable, with explicit office; requires reviewed expenditure purpose |

Observed result: the ledger has a posted 200.00 expense, but the exact office-filtered
Budget comparison shows missing expense evidence. Its 500.00 capital row is also
outside the expense-only projection. Broadening the query to all expense and asset
debits would produce **1,900.00**, including 1,200.00 of advance/refund/deposit debits.
Neither 1,900.00 nor a guessed 700.00 is a certified expenditure total. The probe
establishes source facts and a coverage gap, not the applicable certification.

The missing office is a source fact, not merely a template issue:

- [Liquidation intake](../accounting/advance_views.py) captures account, amount and
  document reference, with no office field.
- [Liquidation preparation/materialization](../vouchers/advance_applications.py)
  retains those rows and the exact original advance; it creates expense lines without
  a responsibility center. The original advance itself is also a scalar asset line.
- [Proposal context](../budget/planning_context.py) correctly requires an exact
  responsibility-center match and therefore cannot attribute the expense.
- The [Budget-versus-actual report](../reporting/datasets.py) has a separate unmapped
  expense control. Do not claim every reporting route silently loses this amount.
- [Liquidation correction](../vouchers/liquidation_corrections.py) currently captures
  and mirrors account/amount/cash-purpose fields, without office attribution. Any
  future source-field extension must update correction validation and retained
  evidence together; historical posted lines must remain unchanged.

## Verified reference and limits

The already hashed official [2023 DBM manual](https://www.dbm.gov.ph/wp-content/uploads/Issuances/2023/Local-Budget-Circular/Budget%20Operations%20Manual%20for%20LGUs%2C%202023%20Edition.pdf)
was text-checked and visually reviewed at PDF pages 76, 217 and 322 (printed pages
61, 202 and 307). Form 1 uses applicable trial-balance evidence and joint officer
certification. Expenditure monitoring distinguishes appropriations, allotments,
obligations and disbursements. Its glossary includes loan repayment in debt service
and distinguishes capital outlays from current operations. Consequently, neither
an expense-account-only rule nor blanket exclusion of every liability debit is a
complete native expenditure basis. These references do not resolve every source's
classification or replace the [FY2027 Form 1/2 requirements](FINANCE_BUDGET_ACTUALS_SOURCE_AUDIT.md).

Do not turn an obligation, an accrual, a payment or a current balance into another
financial state just to populate the comparison. Recorded amounts, treatment and
certification must remain separately evidenced.

## Next implementation, grounded in the source trace

1. Capture an immutable posted-source cohort for an explicit ledger, fund and period.
   Include unattributed lines in the Accounting preparation work instead of filtering
   them away before review. Capture financial lines, posting purposes, original links,
   source snapshots, dated reversal lineage and current classification versions from
   one coherent read. A single joined statement is a candidate; prove consistency on
   native MySQL before relying on it. Do not change old cash-classification checksum
   formats to obtain new Budget metadata.
2. Provide specific, independently reviewed expenditure classification and office/
   object attribution over unchanged posted sources. Account type and generated
   source links can guide preparation, but cannot silently approve a purpose or
   assign an unrecorded office. In particular, do not copy the officer's employing
   office, DV office or original planned allocation into historical liquidation lines.
   Retain included, excluded and unresolved components and a reproducible bridge.
   Office allocations must share one reviewed source-line classification identity
   across office statements; independent per-office copies must not each consume
   the full amount of the same unassigned line. Exact component totals, original
   signs and classification versions must remain reproducible. Support ordinary
   batch preparation/review without making every journal a new manual worksheet.
3. Distinguish initial recognition, liquidation, settlement, refund, internal
   transfer, capital acquisition, debt service and nominal closing. A recognition
   and its later payment must not both become expenditure. Typed closing/opening
   exclusions and exact reversal inheritance require retained line-level proof.
4. Prepare a native office statement from one reviewed cohort, then obtain distinct
   authorized certification. External adoption permission and an existing posting
   role are not automatically native certification authority. Reuse the current
   actuals scope/current-version and Budget submission/export contracts without
   disguising generated data as an externally signed original.
5. Compare the current source/classification fingerprint at review and new Budget
   selection. Later or backdated posts must make changed coverage visible while
   preserving earlier certificates/proposals. Existing posting locks one journal;
   no universal period lock is established. Native races must demonstrate coherent
   capture and stale-source handling before completeness is claimed.

Acceptance must cover the reproduced liquidation and capital candidates, split or
missing office attribution, attempted duplicate attribution across offices,
prior-liability settlement, debit/credit corrections,
loan-principal/fee distinctions, nominal closing, new/backdated source changes,
external/native overlap, current read/export authority, independent certification,
UAT denial and retained proposal/output versions. Exact Form 1 office reconciliation
and joint certification remain subsequent required work. These are implementation
requirements, not delivered capabilities or an expansion to unrelated modules.

## Reproduction and validation

The [archival probe](../scripts/audits/budget_native_source_probe.py) is intentionally
outside automatic test discovery. Run its exact label only with fresh disposable
two-store test settings, such as the documented [native runner](FINANCE_NATIVE_TESTING.md):

```text
python scripts/run_mysql_tests.py scripts.audits.budget_native_source_probe.NativeActualSourceProbe.test_posted_sources_and_missing_office_context
```

It asserts the observed v0.7.151 limitation. A later repair must not preserve the
defect merely to keep this historical probe green. It freezes the synthetic source
clock at 2026-09-25 and evaluates the 2028 proposal's 2026 comparison as of 2027-08-01.
This hypothetical planning date is test context, not operator history.

PASS — initial observation probe against unchanged application code: one SQLite
probe, 3.204s, exit 0; both fresh test stores destroyed. This means the observation
was reproduced, not that the application covers native actuals. Final archived
probe PASS: one SQLite observation, 3.193s, exit 0; both fresh stores destroyed.
Command: `python .tmp/my_work_sqlite.py scripts.audits.budget_native_source_probe.NativeActualSourceProbe.test_posted_sources_and_missing_office_context`.
The [retained synthetic source evidence](evidence/finance-budget-native-source-audit.json)
contains the exact posted rows, original scope and observed proposal context.
PASS — source/form/posting/correction trace and official PDF text/render inspection.
PASS — 457 local documentation links across ten files and Git whitespace checks.
The canonical operator database SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
NOT RUN — OUT OF SCOPE: native, broad application and browser regression for this
audit-only checkpoint; no application or schema changed. Prior v0.7.151 validation
remains separate evidence. No operator-store writes, master merge or deployment.
Production and LGU acceptance remain NO-GO; completion remains open.
