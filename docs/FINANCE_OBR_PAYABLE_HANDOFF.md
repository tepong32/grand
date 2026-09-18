# OBR to payable continuity — development checkpoint

The ordinary workflow already has a source-linked payable intake and a full service
replay through DV, recognition, Treasury advice/release, payment posting, bank
reconciliation and reporting. The certified OBR detail page did not expose that
continuation. Staff had to find the separate payable register and select the source
again. This checkpoint connects those existing screens without creating another
financial route.

## Connected behavior

- Certified original OBRs show current corrected obligation, active claim allocations
  and remaining claim capacity from the same calculation used by payable intake.
  These amounts do not establish Treasury cash or payment.
- Authorized requesting-office staff can open the existing payable form with this
  exact eligible OBR selected. No payee, invoice, claim amount or allocation amount is
  inferred. Invalid, foreign-office and exhausted source selections return 404.
- The OBR lists visible linked cases, including non-primary/consolidated allocation
  history and interrupted initial bindings. Each row links to the existing case,
  retained stage and current responsible office. Pending/failed bindings direct
  staff to recover that case rather than replace the claim.
- The list uses existing Voucher Workbench access and case scope, paginates at 20,
  and reports the full visible count. Historical allocations remain discoverable;
  the list is not a claim that every historical link is currently allocated.
- Finance UUIDs are materialized before reading the separate default store; there
  is no cross-database subquery or fictional shared transaction. Opening the OBR or
  intake performs no financial writes. Existing POST validation, allocations,
  independent review and recovery remain authoritative.
- UAT users cannot open or submit the payable preparation form, even with operational
  permission. Read access remains governed separately. The handoff does not bypass
  signatures, bank acknowledgement or physical release.

## Validation

PASS — `python .tmp/earlier_sqlite.py budget.test_payable_handoff`: 4/4, 3.160s,
exit 0. Covers exact source selection, absence of inferred claim amount/no financial
writes, invalid/foreign/exhausted sources, UAT GET/POST denial, pending/secondary
links, scope, partial capacity and complete 23-case retrieval across two pages.

PASS — fresh MySQL `python .tmp/retrieval_native.py budget.test_payable_handoff vouchers.tests.VoucherWorkflowTests.test_authoritative_budget_to_reconciled_treasury_report_replay`: 5/5, 18.964s, exit 0. Both test stores destroyed.

PASS — dependent SQLite `python .tmp/earlier_sqlite.py budget vouchers.tests finance.test_work_tasks.FinanceBudgetWorkTaskContractTests`: 149 discovered, 146 passed, three native-only skips, 89.869s, exit 0; both test stores destroyed. Broader scope includes all Budget and voucher
workflow tests plus Budget work-queue contracts. Native scope includes the four
new tests and the authoritative Budget-to-reconciled-Treasury-report replay.

PASS — isolated synthetic browser follows the OBR-to-intake link, verifies selected
source and blank claim/payee fields, returns to the OBR and opens the retained case.
Desktop 1440px and narrow 390px rendering checked; document width remains 390px.
A shared section minimum height created a gap; the new panel now overrides only
that minimum height. Evidence: `output/playwright/obr-payable-handoff-desktop.png`,
`obr-payable-handoff-narrow.png`, `obr-payable-source-selected.png`.

PASS — touched Python compilation and `git diff --check`.
NOT RUN — OUT OF SCOPE: production migration (no schema changes), new full-project
suite for this bounded read/navigation change, exact form/printer acceptance and
live LGU workflow observation. v0.7.119 full regression is prior baseline evidence,
not a new full-suite result for this checkpoint.

## Still open

FG-07 remains partial. This closes one observed navigation gap; service/browser
rehearsal is not named-office acceptance of the entire ordinary workflow. Next:
trace remaining real screen handoffs and required outputs against the accepted
Finance scope. Earmark capacity remains unconfirmed; no certificate balance rule
is introduced. Required-output inventory and exact office/form acceptance remain
separate from the existing candidate catalog and generic report capability.

Owned browser/server/MySQL stopped after verification.

User requested implementation pause after this development checkpoint (2026-09-18).
