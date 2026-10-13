# Controlled workbook print coverage

Development work, 2026-09-22, based on v0.7.131. The generated signing files were
inspected read-only. Their mapped gross/deduction/net values were 1,000/10/990.
They use a deliberately minimal test workbook, so this is source-placement evidence,
not accepted-form layout. Artifact Tool inspection/render produced a viewable PNG
but its process exited 1 without a diagnostic; that process is not recorded as PASS.
No issued XLSX was rewritten.

## Reproduced gap and intended correction

Preflight previously required a print area on every mapped sheet but did not check
its coverage. Three reproductions failed because no error was raised: a print area
ending at row 10 omitted controlled rows 12-20, split print areas omitted row 16,
and a merged controlled field extended beyond the print area. Baseline: 3 failures,
1.587s, exit 1, `.tmp/print-coverage-red.log`.

The shared inspector checks every required mapped range against printable regions,
including repeated title rows/columns and their corner. Split print areas can cover
ordinary table rows together. Each merged field must fit wholly within a single
print-area group, preventing fragments on separate areas from passing as complete.
Coverage uses rectangle boundaries, not enumeration of huge cell ranges.

The same existing inspector is used by preflight, approval/activation evidence
verification and new output generation. No schema or financial posting changes.
Existing snapshots, issued files and downloads remain unchanged. An old template
with omitted fields may now fail when reverified for a new operation; correct it
through the existing governed successor process, never by rewriting issued history.

## Validation

Initial Finance suite PASS: 27/27, no skips, 4.131s, exit 0.
First broad dependent suite PASS: 347/347, no skips, 189.120s, exit 0,
`.tmp/print-coverage-regression.log`.
After repeated-title and split-merged-field refinements, broad regression found
348 PASS and one FAIL - CAUSED BY CURRENT WORK (test fixture), 349 total,
189.846s, exit 1, `.tmp/print-coverage-final.log`. The negative fixture assigned
`print_title_cols=None`, but this openpyxl setter retained its prior columns.
Corrected by building a fresh workbook without those columns; application code
was unchanged after that run. Corrected Finance module PASS: 29/29, no skips, 4.108s, exit 0,
`.tmp/print-coverage-corrected-focus.log`. All runners terminal and stores destroyed.

Broad command: `python .tmp/earlier_sqlite.py finance vouchers.tests vouchers.test_signature_custody budget.tests reporting.test_local_form_acceptance`.
Finance command: `python .tmp/earlier_sqlite.py finance.tests`.
Rationale: shared template inspection serves setup, voucher outputs, Budget
sources and local-form acceptance. The final rerun targets the changed test
fixture; the other 348 checks exercised the unchanged final application code.
Native MySQL NOT RUN - OUT OF SCOPE for workbook geometry; no persistence/locking
changes. No full-project or actual printer pass is inferred.

Read-only checks PASS on both retained signing files: mapped identity, date, payee
and amounts equal the source; hashes equal v0.7.131 evidence. Both files and the
current editable starter pass coverage. See
`output/playwright/template-print-coverage-facts.json`. Starter print area is
A1:F31 with repeating rows 1:9. This verifies configuration, not physical pagination.

## Limits and next work

Coverage does not establish font legibility, hidden-row visibility, printer-specific
pagination, paper alignment, accepted fields, wet signatures or LGU acceptance.
The minimal fixture must not be confused with GRAND's editable starter builder or
an office-approved form. The starter's visible reference/context labels and their
mapping still need source-to-output inspection. No local earmark semantics are inferred.
Full Finance Completion Gate remains incomplete and production remains NO-GO.
