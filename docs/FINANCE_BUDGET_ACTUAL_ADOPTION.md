# External Budget actuals adoption — implementation checkpoint

Development v0.7.151 on `codex/finance-budget-actual-adoption`, based on v0.7.150.
This implements the first route in the [actuals contract](FINANCE_BUDGET_ACTUALS_CONTRACT.md).
It does not complete FG-03, native expenditure classification, joint Form 1
certification, local form acceptance or the [foundation gate](FINANCE_FOUNDATION_GATE.md).

## Scope and retained controls

Accounting captures a completed full-year or first-semester external office
certificate with explicit ledger, fund, office, receiving Budget department,
original Accountant, date, authority, coverage, signed control total and source
page/row references. Original PDF/PNG/JPEG bytes are retained in the Finance database
(maximum 8 MiB), behind current scoped read/export permissions; no public media URL.
Leaf account amounts must equal the signed total. Explicit zero is evidence;
an omitted account is missing. Capital objects use explicit certificate rows,
not blanket inclusion of asset debits.

Specific preparation and review permissions are assigned to the corresponding
standard Accounting roles; posting permission alone does not confer adoption.
Another actor reviews adoption, keeping the original signer/date distinct.
UAT membership denies mutation even with operational grants. Source download and
register CSV require separate export permission, revalidate retained checksums,
and use the existing export archive. The receiving Budget office may read adopted
versions through its proposal/audit permissions; this does not grant file export.

An ordinary unique Finance scope and version identity work on MySQL. Writers lock
the existing Fund, then scope, then decision version. Stale submission tokens and
older submitted versions cannot replace newer evidence. Submitted payload/file
and prior decisions are immutable; corrections retain a successor and prior head.
This lock does not claim to serialize unrelated financial postings.

Budget draft context captures a single adopted version per exact scope, validates
office/object ownership and class, and retains coverage, signed total, original
and adoption evidence with hashes. External actuals remain separate from ledger
expense activity. Submission freezes them; later adoption cannot rewrite a prior
proposal. Historical contexts without certification remain missing. Register and
version history use full scoped pagination; matching CSV includes all versions.

## Validation

PASS — initial isolated SQLite `accounting.test_budget_actuals
budget.test_planning_context`: 14 tests, 14.406s, no skips. System check passed.
After review, added retained preparer identity checks, complete certificate coverage
in proposal snapshots, legacy missing-state coverage, changed classification tests
and native competing submission/review/capture tests.

PASS — final expanded isolated SQLite command:
`python .tmp/my_work_sqlite.py accounting budget reporting finance vouchers.tests`.
700 discovered, 673 passed, 27 native-only skips, 362.730s, exit 0. This covers affected
Accounting models/access, Budget proposals, dependent Reporting, Finance configuration
and standard voucher role/workflow contracts. Log: `.tmp/budget-adoption-regression.log`.

PASS — fresh MySQL 8.4.11 command:
`python .tmp/retrieval_native.py accounting.test_budget_actuals accounting.test_budget_actual_concurrency budget.test_planning_context budget.tests reporting.tests`.
88 passed, no skips, 53.706s, exit 0. The owned helper supplies private loopback test
credentials to the [committed runner](FINANCE_NATIVE_TESTING.md). Native evidence
includes >64 KiB original document round-trip, portable scope/version identities,
competing first submissions, competing decisions and proposal capture during a
successor adoption. Log: `.tmp/budget-adoption-native.log`. Existing unsupported
conditional-constraint warnings remain visible; these new identities use ordinary
unique constraints. This does not establish every unrelated native race.

PASS — system check and migration drift check through isolated
`.tmp/budget_actual_manage.py`; no pending model migration. Migration 0032 was
applied only to disposable stores, never operator databases.

PASS — browser rehearsal using synthetic isolated stores: source upload and explicit
140.00 row, independent reviewer adoption, Budget 140.00 + 40.00 estimate = 180.00,
missing native/prior evidence, proposal submission, retained context CSV download,
certificate register navigation and dynamic row addition. Desktop 1280×900 and
narrow 390×844 layouts were inspected; tables scroll inside their containers without
whole-page horizontal overflow. No browser console warnings/errors were recorded.
Retained synthetic artifacts: [adopted certificate](../output/playwright/budget-actual-adopted-desktop.png),
[Budget context](../output/playwright/budget-actual-context-desktop.png),
[narrow context](../output/playwright/budget-actual-certified-mobile.png),
[narrow form](../output/playwright/budget-actual-form-mobile.png) and
[downloaded planning CSV](../output/playwright/budget-actual-planning-context.csv).
The retained original PDF route returned HTTP 200, 1,574 bytes and SHA256
`47a089e149b6a63acbbc792c5016472e7eff30a3577972754313e5bb9abe11ae`, matching
the uploaded file and archive receipt, through authenticated HTTP.

NOT RUN TO COMPLETION — ENVIRONMENTAL: browser-managed PDF saving. IDM Advanced
Integration intercepted the attachment as HTTP 204, although the server returned
200. A separate isolated browser with extensions disabled was also intercepted.
No application workaround or user browser-setting change was made. This is distinct
from the passing authenticated byte-integrity test and working browser CSV download.

Owned browser sessions, fixture HTTP server and native MySQL stopped after terminal
results; ports 8787/33308 have no listener. Canonical operator database SHA256 remains
`C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
No master merge or deployment. Broader whole-project native/full regression is
NOT RUN — OUT OF SCOPE for this bounded external-adoption checkpoint; the prior
full baseline is separate evidence, not a current full-suite pass.

Remaining native classification/source-cohort certification, joint summary
reconciliation, exact print outputs and human acceptance stay open. Production NO-GO.
