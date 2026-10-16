# OBR to payable continuity — development checkpoint

## OBR entry and independent certification follow-up — 2026-10-17

The earlier browser checkpoint below started with an already certified OBR. This
follow-up enters the request and schedule through existing browser forms, submits
as the requesting office and certifies as a separate Budget actor. Authority and
ARO remain service-created synthetic setup, not a human-entered annual-budget
cycle or accepted paper authority. Synthetic sessions do not establish real login
or operator provisioning acceptance.

**LOW pre-existing usability defect repaired locally:** the authority selector
displayed `AppropriationAuthorization object (1)`, also present in accepted v172.
`ObligationRequestForm` now labels existing choices with ordinance number and
fiscal year using the already selected related objects. Its queryset, disabled
edit behavior, validation, permissions, persistence and financial services are
unchanged. The existing HTTP/source/export test now checks the readable label;
no test method or assertion was removed.

Actual browser proof: signed total 10,000 versus schedule 9,000 is rejected at
submission, preserving the draft/line and creating no movement. Correcting the
line to 10,000 permits submission; the requester sees no certification action and
the balance is still unchanged. Separate Budget certification creates exactly one
10,000 movement; released/executable allotment remains 60,000, obligated 10,000
and unobligated 50,000. Authority checksum and the same retained OBR identity are
preserved. Subsequent fixed-form GET creates no additional obligation or movement.

The requester follows the exact retained OBR's payable link. This fixture has no
active Accounting-approved Finance Setup release, so the existing intake guard
redirects with that explicit error. No case, payable allocation or JEV is created.
No extra setup/approval was fabricated to force continuation; successful intake
preselection remains covered by the earlier dedicated handoff evidence below.

**PASS — SQLite 3/3**, zero skips, 4.204s test execution, exit 0, both aliases
destroyed; terminal session 33375. Actual Python 3.11 command:

```text
python -B -X utf8 .tmp/intake_primary_sqlite.py budget.tests.AnnualBudgetPreparationTests.test_obligation_scope_guided_edit_and_tracesync_registry_export budget.tests.AnnualBudgetPreparationTests.test_uat_budget_actions_hidden_and_denied_while_reads_remain_available budget.tests.AnnualBudgetPreparationTests.test_budget_service_boundaries_reject_unauthorized_actors_without_writes --verbosity 2
```

Log `.tmp/obr-authority-label-sqlite-20261017.log`; exact UI states, source/image/log
hashes, resource closure, operator-store checks and limitations:
`.tmp/obr-entry-browser-evidence-20261017.json`. Current 1,193-file source freeze:
`.tmp/obr-authority-label-current-source-freeze-20261017.json`. Exactly two source
differences follow the previous reviewed source (`budget/forms.py`, `budget/tests.py`);
seven presentation/test files now postdate the broad full baseline. That earlier
full result is not full-current-source proof. Native/full reruns: **NOT RUN — OUT
OF SCOPE** for the form-label/HTTP-assertion change; no financial/persistence/query
contract changed and no current native pass is claimed.

Before/fixed desktop and fixed mobile forms were inspected. Mobile document and
viewport are both 390px; the native closed selector clips the end of the long
synthetic label, while its complete accessible option remains present. No custom
selector redesign is claimed. Five screenshots are retained in `output/playwright/`
under `obr-entry-*-20261017.png`, including mismatch and certification states.
Browser `grand-obr-entry`, both owned previews and the seed/test runners are
terminal; port 8799 was verified closed. Preview stop exits are not test failures.
Operator databases are unchanged; no actual signature, Treasury payment, production
deployment, local-form/printer or LGU acceptance occurred.

All changes remain unpublished. The older 95-path VM preview is stale and excludes
the two newly changed tracked files and five new screenshots; review the intended
payload and refresh/re-preview before actual VM commit/integration. Preserve the
publication boundary. Original certificate/form/deployment dependencies remain
open; do not replay this now-completed entry/certification branch as a new milestone.

## Earlier certified-OBR handoff checkpoint

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
