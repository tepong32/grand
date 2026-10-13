# Historical joint Budget actuals — development checkpoint, 2026-10-11

Branch `codex/finance-budget-attribution`, base v0.7.153 / `61e690e4`.
Uncommitted development, not a release, master integration or accepted Form 1.
Implements the historical-evidence route in the
[Form 1 source contract](FINANCE_FORM1_SOURCE_CONTRACT.md); native preparation,
cash restrictions, office reconciliation and issuance remain open.

## Implemented boundary

Migration `accounting/0036_budget_summary_actuals.py` adds Finance-store summary
scopes and immutable versions. Ordinary scope/version uniqueness works in MySQL;
new scopes and decisions use Fund then scope/version locks. Scope pins Accounting,
Budget and Treasury offices, explicit fund/entity and completed full-year or
January–June dates. A linked Budget call establishes the Budget/Accounting pairing;
the retained designation establishes the selected Treasury and reporting entity.
No office name or fund code is inferred as a legal designation.

Each submission retains original certificate and trial-balance/reconciliation
document bytes and hashes (PDF/PNG/JPEG, each up to 8 MiB), itemized receipt and
expenditure rows, signed controls, scope/coverage, source row references and separate
original Treasurer/Accountant names, dates and designations. Signed totals reproduce
their explicit leaf rows. Repeated source references, omitted sides, invalid
categories, foreign accounts and missing documents fail validation. Explicit zero
may omit an account; missing data never becomes zero. Negative source amounts remain
explicit rather than silently converted or clamped. Human review verifies the actual
source document and reconciliation; file signatures/checksums do not prove its
substantive certification or authenticity.

A distinct Accounting reviewer must confirm both original certifications, coverage
and reconciliation and retain adoption authority/reason. Original historical dates
are separate from GRAND's submission/adoption timestamps. Self-review, UAT mutation,
stale decisions and changed scope/account evidence are rejected. New submissions
cannot redirect an existing scope's offices or designation. Return/successor history
is retained; adoption does not post a journal or make the adopting user an original
signer. Older submissions cannot displace newer evidence.

Accounting has a searchable paginated register and detail/history screens, structured
entry rows, successor preparation with exact-document reuse, return/adoption controls
and archived certificate/trial-balance/JSON snapshot exports. Register/history pages
retain all accessible versions. Manual entry supports 100 rows within the normal
request-field limit. Explicit CSV replacement accepts up to 10,000 rows / 2 MiB;
malformed or invalid rows reject the entire submission. Account codes resolve only
in the owner's ledger and are rechecked under the submission lock. Original source
documents and normalized rows are retained; the transcription CSV itself is not.
Successors may retain every prior row without rendering a large manual form.
Source-row search and 100-row pages preserve full signed totals and exports.
An evidence ZIP bundles exact original documents and the complete decision/snapshot
under the same visibility and export controls, with safe fixed member names and
repeatable bytes. This is not an issued Form 1. Approved
history is readable by the linked Budget office under its
existing Budget permissions and by specifically authorized Treasury readers. Export
requires its own permission plus current record visibility. Standard Accounting role
definitions include the corresponding preparation or independent review access.
New permissions do not grant native certification or Form 1 issuance authority.

## Validation and observed repairs

- Large-schedule SQLite: `python .tmp/my_work_sqlite.py accounting.test_summary_csv`
  PASS 13/13, no skips, 12.596s, exit 0; `.tmp/summary-csv-sqlite.log`.
  Native: `python .tmp/retrieval_native.py accounting.test_summary_csv.SummaryCSVTests
  accounting.test_summary_actual_concurrency.SummaryActualConcurrencyTests` PASS
  15/15, no skips, 21.005s, exit 0; `.tmp/summary-csv-native.log`. Both stores
  destroyed. Includes full 1,001-row persistence, successor reuse, rejection of an
  invalid near-final row without partial writes, and existing decision races.
- Pagination follow-up: `python .tmp/my_work_sqlite.py
  accounting.test_summary_csv.SummaryCSVTests.test_large_http_import_review_and_successor_retain_all_rows`
  PASS 1/1, no skips, 3.598s, exit 0; `.tmp/summary-csv-pagination.log`.
- Synthetic browser CSV import, independent adoption, search, final page 11/11 and
  complete JSON download PASS. The synthetic 27-page source explicitly contains
  all 1,001 rows and trial-balance controls; this does not establish LGU acceptance.
  Screenshot `output/playwright/summary-csv-final-page.png` visually inspected.
- Evidence-package authenticated HTTP verification PASS: exact original PDFs,
  all 1,001 rows, adopted decision, repeatable ZIP bytes, export SHA and unauthorized
  Budget-reader 403. Browser ZIP download FAILS with `download.txt`, like the PDF
  discrepancy below; cause remains unestablished. Do not claim binary browser
  download acceptance. JSON browser download passes. No schema change for this
  extension; native runs precede the read-only pagination/ZIP additions.
- Final package regression using the same focused SQLite command above PASS 1/1,
  no skips, 3.273s, exit 0; `.tmp/summary-csv-package.log`, session 52369 collected,
  both stores destroyed. Asserts exact source members, complete snapshot and
  repeatable bytes after adoption. Compilation, whitespace and 491 documentation
  links pass; canonical operator DB hash unchanged. Isolated server stopped and
  browser closed; no owned listeners on 8791/33308 remain.

- First SQLite run: FAIL — CAUSED BY CURRENT WORK (test fixture): 8 tests, 14
  subtest/errors, 8.587s, exit 1. The fixture referenced an undefined Treasury office.
  Added an explicit synthetic Treasury. Session 29513 collected; both stores removed;
  `.tmp/summary-actuals-sqlite.log`.
- Browser found a real cross-store form bug: a Finance BudgetCall queryset was used
  as a default-store Department subquery. Materializing distinct office IDs before
  querying Departments fixed it; the HTTP create/successor test and browser passed.
- Final SQLite: `python .tmp/my_work_sqlite.py accounting.test_summary_actuals
  accounting.test_budget_actuals budget.test_resource_context` PASS, 31 tests,
  no skips, 29.735s, exit 0, both stores destroyed; session 45270 collected,
  `.tmp/summary-actuals-sqlite-final.log`.
- Native: `python .tmp/retrieval_native.py accounting.test_summary_actuals
  accounting.test_summary_actual_concurrency accounting.test_budget_actuals
  budget.test_resource_context` PASS, 34 tests, no skips, 44.337s, exit 0,
  both stores destroyed; session 28156 collected, `.tmp/summary-actuals-native.log`.
  Includes competing initial scope creation/reviews and successor-versus-approval.
- Tests cover source controls/roles/dates, self-review, explicit confirmation, UAT,
  latest-version checks, zero/missing, setup-change rejection, scope redirection,
  immutable versions/documents, old exports after successor/setup rename, checksum
  tampering, Budget read/export boundaries and 51-record register navigation.
- Final focused runs include explicit assigned-Treasury/outsider visibility, own-ledger
  review denial, UAT read/export with mutation denial, final MIME headers and updated
  synthetic receipt account: SQLite `python .tmp/my_work_sqlite.py
  accounting.test_summary_actuals.SummaryActualTests` PASS 9/9, no skips, 9.423s,
  exit 0, both stores destroyed; session 12462 collected,
  `.tmp/summary-actuals-sqlite-security.log`. MySQL `python .tmp/retrieval_native.py
  accounting.test_summary_actuals.SummaryActualTests
  accounting.test_summary_actual_concurrency.SummaryActualConcurrencyTests` PASS
  11/11, no skips, 16.243s, exit 0, both stores destroyed; session 63334 collected,
  `.tmp/summary-actuals-native-final.log`. Owned MySQL stopped afterward.
- Synthetic browser create → independent return → successor with retained files →
  independent adoption passed. Corrected the synthetic receipt-account selection in
  the successor, preserving the original return. Mobile/detail/history screenshots
  inspected: `output/playwright/summary-actuals-mobile.png` and
  `output/playwright/summary-actuals-adopted.png`.
- Authenticated HTTP downloads reproduce both uploaded documents byte for byte;
  snapshot retains the adopted decision and all export hashes match actual bytes.
  JSON snapshot also downloads successfully in Playwright. PDF browser download
  verification FAILS: ordinary navigation produced a browser-side 204/ERR_ABORTED
  while server logs and authenticated HTTP report 200 with exact PDF bytes; explicit
  download links produced canceled downloads / Chrome “Failed - No file”. MIME
  headers are now specific and download intent explicit, but neither resolved the
  observed discrepancy. Cause remains unestablished; do not claim completed browser
  PDF download or bypass browser controls. Retained endpoint bytes/hashes pass.
  Reproduce/isolate this discrepancy before output/browser acceptance.
- Compilation, isolated migration drift (no changes) and whitespace pass. No operator
  migration; canonical DB SHA-256 unchanged:
  `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.
  Browser/server closed. Documentation link check passes (491 links, 14 files).

NOT RUN — OUT OF SCOPE: full release regression, native receipt/cash preparation,
complete Form 1 output and real printer/LGU acceptance. These remain required; this
checkpoint supplies historical evidence only, not the full completion gate.
