# Reviewed cash-purpose allocations

Development v0.7.76: `codex/finance-cash-allocations`, based on remotely verified v0.7.75 (`4f44642`). This advances M01 under the [functional-first priorities](FINANCE_MODERNIZATION_PRIORITIES.md). It does not establish complete statement coverage or production acceptance.

## Financial behavior

An authorized preparer opens **Cash-flow purposes / review** from a posted journal. The preparer allocates every cash line to one or more purposes, supplies a supporting document reference and submits it. A different authorized reviewer approves or returns the proposal. Approved allocations affect newly generated Cash Flow statements; the journal, voucher, payment, subsidiary ledger and original inline classifications remain unchanged.

| Case | Implemented behavior | Evidence |
|---|---|---|
| Historical blank cash purpose | Classify an already posted source without reopening its period, reactivating its cash account or creating a financial reversal. | Closed-period and retired-account regression; complete journal snapshot and entry count remain unchanged. |
| One mixed cash line | Positive cent-exact parts must total the entire cash line; non-cash and foreign lines cannot be allocated. | 90.00 payment split into 80.00 principal and 10.00 interest; output row assertions and cash closing 310.00 from opening 400.00. |
| Generated payment | Reviewed allocations supplement the actual released-check JEV, preserving its posting-rule and subsidiary evidence. | Real voucher workflow: release, generated payment JEV, independent posting and reconciliation; 900.00 becomes 400.00 capital and 500.00 operating cash flow. |
| Corrected allocation | A successor proposal names the approved version it replaces. Old proposals, decisions and report artifacts remain retained. | New report selects version 2; earlier report keeps version 1, exact file bytes and valid reproduction checksums. |
| Actual payment reversal | Inherit the nearest approved ancestor only through exact mirrored financial lines and the same fund. An entry's own approved classification takes precedence. | Actual reversal cancels the original allocated cash flow; inheritance checks every sequence, account, side, amount and responsibility center. |
| Independent review | Current Accounting source access and existing Finance reporting governance authority are required; current office and Finance UAT denial apply. | Self-review and UAT rejection, HTTP proposal/review and reassigned-office denial. Caller-modified objects are reloaded from storage. |
| Conflicting approvals | Lock the posted source before proposal/version or approval changes. A stale candidate must be returned and replaced. | Native MySQL competing approvals: exactly one approved record/current pointer and one still-submitted stale proposal. |
| Altered evidence | Reproduce original source, decision checksum and exact allocations before including a reviewed classification in a new report. | Deliberate test-only decision corruption makes generation fail. |

## Storage and authority

Migration `accounting/0015_reviewed_cash_classifications` adds proposal/decision records and one current-approved pointer per journal in the **Finance store**. No journal field or original financial transaction is rewritten. The current pointer has ordinary one-to-one database uniqueness; proposal versions have ordinary `(entry, version)` uniqueness. These do not depend on MySQL's unsupported conditional unique constraints. All service mutations use the same parent-journal lock.

Proposals pin a reviewed cash scope, full posted source snapshot/checksum, exact allocations, supporting reference, explanation and preparer. Approval pins the independent reviewer, date, basis and decision checksum. Pending or returned proposals do not affect reports. Changing the source, scope or approved base version before approval rejects that approval. A retired asset can remain in an explicit historical cash scope; this does not grant posting permission.

The report retains both original journal fields and the chosen allocation metadata, plus a separate classification source record. Retained report reproduction continues to use its own evidence and file, not the latest live classification. Allocation metadata does not create a second ledger or a configurable arithmetic engine.

## Validation

PASS: initial SQLite run, 6 tests in 5.167 seconds (the first three allocation cases plus three existing cash-flow cases discovered through a test-class import; the import was then changed to a module alias to avoid duplicate discovery).

PASS: focused SQLite run, 8 tests in 9.319 seconds, including four allocation tests, the three existing cash-flow tests and the real generated-payment scenario.

PASS: initial fresh MySQL 8.4.11 run, 5 tests in 5.798 seconds, including the four allocation cases and the competing-approval transaction test. This proves the particular classification lock path, not general Finance concurrency safety.

PASS: final expanded MySQL 8.4.11 run, all 8 tests in 11.459 seconds, including the six allocation tests, native competing approvals and real generated-payment scenario. The owned server was shut down after the final run.

PASS: broad SQLite regression, 518 discovered / 514 executed / four native-only skips in 243.957 seconds. The three pre-existing native-only cases remain separate from the new classification concurrency test executed on MySQL above. No broad-suite failures.

FAIL - CAUSED BY CURRENT WORK: the subsequent explicit-empty-purpose HTTP assertion used an incorrect formset initial count (0 rather than the rendered 1). Django treated the unchanged row as an empty extra row; submission was still rejected and no proposal was created, but the test incorrectly expected a field error. The fixture was corrected to match the actual form. PASS: corrected targeted HTTP test, 1 test in 1.209 seconds. This final UI change adds an explicit empty choice so historical cash cannot visually default to the first purpose. It does not alter persisted models, services or calculations, so the affected HTTP path was rerun without repeating the broader/native suites.

System checks, migration-drift checks, compilation, diff whitespace checks and 205 local links across nine documentation files have passed. All test processes and the owned MySQL server have ended. No migration has been applied to the user's stores. User database SHA-256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`.

Commands:

```powershell
.venv/Scripts/python.exe manage.py test accounting.test_cash_classifications --noinput
.venv/Scripts/python.exe manage.py test accounting.test_cash_classifications reporting.test_cash_flows vouchers.tests.VoucherWorkflowTests.test_payment_release_creates_event_jev_resumes_and_exports_register --noinput
.venv/Scripts/python.exe .tmp/portable_mysql.py test accounting.test_cash_classifications accounting.test_cash_classification_concurrency
.venv/Scripts/python.exe .tmp/portable_mysql.py test accounting.test_cash_classifications accounting.test_cash_classification_concurrency vouchers.tests.VoucherWorkflowTests.test_payment_release_creates_event_jev_resumes_and_exports_register
.venv/Scripts/python.exe manage.py test reporting accounting vouchers finance --noinput
.venv/Scripts/python.exe manage.py test accounting.test_cash_classifications.CashClassificationTests.test_http_proposal_review_and_current_office_boundary --noinput
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Native commands use the owned disposable loopback fixture and the committed [fresh two-store runner](FINANCE_NATIVE_TESTING.md). The additional final native cases cover HTTP/current-office authority, altered evidence, corrected-version reproduction and the real generated payment. Broad regression is warranted by the shared journal, mapping, report and voucher paths. Full-project release gates, whole-system concurrency, browser/printer/persona acceptance and eGAPS numerical parity remain unperformed; synthetic coverage is not LGU acceptance.

## Next functional work

The package target below has advanced in the [four-statement package work](FINANCE_STATEMENT_PACKAGE_2026-09-10.md). Its source inspection identifies common fund scoping/complete-row generation as the next M01 gap before M02. This allocation checkpoint's evidence remains unchanged.

Complete the statement-note/package and signed-reference paths for **all four statements**. Current `FinanceStatementNoteSet` fields, validation, source snapshots, forms and exports still assume Position/Performance. `STATEMENT_COMPARISON_CONTROLS` likewise omits Cash Flow and Net Assets. Include period/fund and comparative controls, retained source versions, approved outputs and actual package contents; preserving old two-statement evidence must not become a substitute for complete new packages.

Then continue M02 prior-payable linkage and the remaining ordinary office transactions. Actual local cash/equivalent/overdraft scope, required row detail, signatories, print layouts and office/LGU acceptance remain open. eGAPS has not been accessed or changed. The [printed comparison](../output/pdf/GRAND-eGAPS-Assessment-2026-09-10.pdf) remains the frozen v0.7.71 assessment.
