# Common fund selection and complete financial statements

Development v0.7.78 on `codex/finance-statement-funds`, based on remotely verified v0.7.77 (`49a58eb`). This advances M01 financial calculations; it does not establish statutory layout acceptance or complete eGAPS parity.

## Financial behavior

All four statements now select ledger funds before calculating balances, movements, controls or retained source records. The existing report-definition form accepts one exact fund code or a comma-separated list; leaving the filter blank includes all funds. Selection is saved in the existing definition and pinned into each new run. It is not a new per-run selector or a new configuration system.

Position and Performance aggregate the selected funds. Net Assets and Cash Flow retain their existing per-fund current/comparative rows. The native report title and mapped-template title metadata identify the selected funds. Approved mapped templates still control whether and where that metadata is displayed; exact local layouts need separate acceptance.

| Case | Position assets / closing net assets | Period surplus | Original posted journals |
|---|---:|---:|---|
| General Fund only | 500.00 | 100.00 | GF opening 400.00 plus receipt 100.00 |
| Special Education Fund only | 970.00 | 70.00 | SEF opening 900.00 plus receipt 70.00 |
| Both funds / unfiltered | 1,470.00 | 170.00 | Both openings and receipts |

The synthetic scenario posts through independent Accounting approval, generates actual XLSX files, checks every retained row against exported amounts, reviews all four reports together in notes, and verifies original files/checksums after definition changes. Performance retains only in-period journals; the other three retain the opening sources too. These are synthetic tests, not LGU-approved accounting examples.

## Required rows and source boundaries

- A report cannot filter financial line codes, group financial rows, add generic subtotals, reorder rows or omit/duplicate required columns. Validation occurs when definitions are checked and again during generation, including definitions saved by older code or direct updates.
- Supported source filters are `fund_code`, `fund_code__exact` and `fund_code__in`. Only one filter is accepted. Empty/malformed lists and unknown or other-office fund codes fail generation instead of returning an apparently reconciled empty statement.
- Nonstatement datasets retain existing row filtering/grouping behavior. Historical generated files, selected definitions, source snapshots and checksums are not rewritten. A failed new generation retains the existing failed-run audit behavior.
- Active selected funds without transactions still need movement opening/comparative evidence. Inactive funds with posted history remain represented. Zero-opening declarations are office-wide evidence with no fund field; their existing review/checksum rules remain in effect.
- No migration, financial mutation, new permissions or concurrent financial decision path is introduced. eGAPS remains disconnected and untouched; production remains NO-GO.

## Validation

- PASS: `.venv/Scripts/python.exe manage.py test reporting.test_statement_funds reporting.test_statement_bundle --noinput` - initial eight focused tests in 8.564 seconds. This run preceded the added form-submission test.
- PASS: `.venv/Scripts/python.exe .tmp/portable_mysql.py test reporting.test_statement_funds reporting.test_statement_bundle` - eight tests on MySQL 8.4.11 in 10.601 seconds, fresh separate default/Finance schemas.
- PASS: final native `.venv/Scripts/python.exe .tmp/portable_mysql.py test reporting.test_statement_funds` - all three current fund tests in 6.520 seconds, including the form path and actual exported titles. The owned native server was shut down after the runner ended.
- PASS: broader `.venv/Scripts/python.exe manage.py test reporting accounting vouchers finance departments --noinput` - 551 discovered, 546 executed successfully and five native-only skips in 304.638 seconds. Covers shared definition validation/render metadata and dependent financial reports, source permissions and package flows. All runner processes ended.
- PASS: `manage.py check`, `manage.py makemigrations --check --dry-run` (no changes), compilation of the six affected Python files, `git diff --check`, and 223 local document links across 11 files.
- PASS: synthetic Position and Cash Flow A4 landscape PDFs generated with the actual native renderer from unsaved model objects, rendered with Poppler and visually inspected (one page each). Both show GF/SEF clearly without clipping/overlap; this is title-layout QA, not another source-calculation test or statutory acceptance. Poppler reported unavailable fallback fonts; the rendered pages have no missing glyphs.
- NOT RUN - OUT OF SCOPE: full-project/native concurrency/recovery and human printer/LGU acceptance gates. No new persistence or concurrent mutation path was introduced. The existing native source-calculation and broader regression scope is proportional to this change.
- User database SHA-256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`; no user-store migration or eGAPS access. The unrelated policy concurrency draft remains untouched. No remote CI result is claimed.

## Next work

Proceed to M02 earlier-payable recognition and settlement linkage, including partial settlements and corrections without double recognition. M01 exact local forms, signed comparisons and real office acceptance remain open under the [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md). Complete actual eGAPS inventory, ordinary office scenarios, exact outputs, usability and operational/LGU gates in the authorized order. No overall completion claim follows from this calculation repair.
