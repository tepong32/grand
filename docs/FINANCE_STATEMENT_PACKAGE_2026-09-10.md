# Four-statement notes, references and retained downloads

Development v0.7.77: `codex/finance-statement-package`, based on remotely verified v0.7.76 (`96e279a`). This advances M01 under the [functional-first priorities](FINANCE_MODERNIZATION_PRIORITIES.md). It does not establish complete eGAPS parity, accepted statutory layouts or production readiness.

## Operator result

New note packages select Position, Performance, Changes in Net Assets / Equity and Cash Flow for the same period. Thirteen editable disclosure prompts include net-assets movements and cash-flow classifications/non-cash transactions. A preparer completes the disclosures; a different authorized reviewer accepts working notes or approves locally confirmed notes under the existing authority rules.

Authorized note exporters with report-download permission and current visibility of every member can download a ZIP containing the **four original report files**, a standalone printable `notes.html`, and a manifest identifying the reports, review and SHA-256 of each file. This is an actual portable package, not only a list of report identifiers. Existing CSV note exports remain available for historical records.

| Requirement | Implemented behavior / proof |
|---|---|
| Complete new membership | Creation and submission require all four reports. Each member must belong to the same office, have the correct dataset, cover the exact period and reconcile. |
| Historical two-member records | New FKs are nullable; no historical member, approval or source snapshot is backfilled. Absent members are omitted from snapshot serialization, preserving the old shape/hash. An incomplete record cannot be newly submitted as a complete package. |
| Consistent financial evidence | Position, Net Assets and Cash Flow retain identical original posted journals; Performance retains their in-period subset. Reviewed cash metadata is supplementary and does not falsely make the original journals appear different. |
| Cross-statement totals | Position assets less liabilities equals closing Net Assets; Performance surplus equals the net-assets operating movement; Cash Flow and Net Assets have matching non-empty fund inventories; closing cash agrees to the retained Position cash ledger. |
| Complete visible Position/Performance rows | A package rejects a member that omits a mapped row or its operating-result row, duplicates line identities or omits amounts, even when its ledger control totals still say reconciled. |
| Authentic files | Submission checks retained report integrity. Initial bundle issuance verifies exact report file bytes/checksums before copying them. The first ZIP is stored with its checksum and date; later downloads return that immutable issued copy. Corrupt ZIP bytes or changed selected report identities fail closed. |
| Corrections and retention | New note versions and later source/report files do not rewrite an issued ZIP. A retained bundle can still reproduce its original contents if an external original-report file is later damaged. Its own checksum and note/member identity checks remain required. |
| Signed-reference comparisons | Cash Flow and Net Assets compare every retained row separately by fund and by current/comparative amount. Missing, duplicate or absent comparative identities are rejected. Independent reconciliation still requires exact zero differences and unchanged evidence. |
| Native competing approvals | Creation and review lock the existing department row before candidate/version rows. An older candidate cannot replace a newer approved version. The native race leaves only version 2 approved. This fixes this note-package service path; broader conditional-identity scrutiny remains open. |
| Printing | Standalone A4 notes use sequential note numbers, page counters and intact short disclosure sections. A synthetic five-page PDF was rendered in Edge/Chromium and all five page images inspected after correcting an orphaned heading. |

The source-to-output scenario independently posts an opening cash balance of 400.00 and a current tax collection of 100.00, generates all four statements, completes/reviews the notes, then compares each ZIP member byte-for-byte with its issued report. Additional cases reject mixed reporting cutoffs, missing members, mismatched periods, hidden Position rows and unauthorized report download, while retaining historical snapshot shape and detecting bundle corruption.

## Persistence and boundaries

`reporting/0014_complete_statement_members` adds the two nullable report references and note choices. `reporting/0015_retain_issued_statement_bundle` adds the immutable issued-file pointer, checksum and timestamp. These live with reporting in the default store; ledger/source data remain in the separate Finance store. No migration was applied to the user's databases.

An issued package retains the statement files in their original formats; it does not convert an XLSX into an accepted PDF form or merge reports into a falsely official document. Signed-reference checks remain separately retained report comparisons; they are not silently treated as printer/layout acceptance. Working notes remain visibly working/candidate. Existing actual local acceptance and official-template/report approval gates are preserved.

## Validation

- PASS: initial note-workflow SQLite run, 10 tests in 6.645 seconds.
- FAIL - CAUSED BY CURRENT WORK: initial three-case source/package run, 7.449 seconds; the old `ReportReferenceComparison.clean` whitelist still rejected Cash Flow/Net Assets. The whitelist was extended; no user data were touched.
- PASS: corrected combined SQLite run, 13 tests in 5.799 seconds. Workflow fixtures now contain actual files and consistent retained hashes instead of placeholder digests.
- PASS: native MySQL 8.4.11 run, all 14 tests in 9.117 seconds, including the real four-report bundle, note/reference workflows and competing approvals on fresh separate test stores.
- FAIL - CAUSED BY CURRENT WORK: broad SQLite run, 547 discovered / 541 passed / five native-only skips / one failed assertion in 264.392 seconds. The Accounting how-to intentionally advanced to version 14, but the template-promotion test still expected 13. The reporting-only run encountered the same assertion: 144 discovered / 142 passed / one native-only skip / one failure in 50.064 seconds. Neither run reported another failure.
- PASS: corrected guide-version assertion, 1 test in 1.284 seconds. Its role-separation assertions are unchanged. This test-only expectation correction was verified directly rather than repeating unchanged broad application suites.
- PASS: final native package cases, all 6 tests in 8.259 seconds, including the hidden-row guard, mixed cutoffs and historical members. The separate native approval-race result above remains applicable.
- PASS: final cached-member identity/file-corruption regression, 1 SQLite test in 1.117 seconds. This verifies the final additional cached-download identity guard without repeating unrelated suites.
- PASS: system checks, migration drift and Python compilation. PDF/Playwright QA: final A4 size 594.96 × 841.92 pt; all five pages inspected, with no clipping/overlap/orphaned short disclosures. The CLI's initial default Letter output was regenerated using `preferCSSPageSize`; the application HTML specifies A4. The isolated browser and loopback-only static server were closed. A favicon-only 404 did not affect rendering.

Commands:

```powershell
.venv/Scripts/python.exe manage.py test reporting.test_statement_notes --noinput
.venv/Scripts/python.exe manage.py test reporting.test_statement_bundle reporting.test_statement_notes --noinput
.venv/Scripts/python.exe .tmp/portable_mysql.py test reporting.test_statement_bundle reporting.test_statement_notes reporting.test_statement_package_concurrency
.venv/Scripts/python.exe manage.py test reporting accounting vouchers finance departments --noinput
.venv/Scripts/python.exe manage.py test reporting --noinput
.venv/Scripts/python.exe .tmp/portable_mysql.py test reporting.test_statement_bundle
.venv/Scripts/python.exe manage.py test reporting.test_statement_bundle.FourStatementPackageTests.test_posted_collection_to_four_original_files_and_printable_notes --noinput
.venv/Scripts/python.exe manage.py test reporting.test_template_promotions.ReportTemplatePromotionTests.test_finance_roles_and_department_guides_separate_promotion_duties --noinput
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Broad regression is warranted by reporting schema/services, department-aware download, Finance/source cross-checks and the updated existing Accounting how-to. Later coverage targets the additional package guards; full unrelated suites are not mechanically repeated for the final print-only CSS. Native testing uses the owned loopback fixture and [fresh two-store runner](FINANCE_NATIVE_TESTING.md). Full-project release gates, general concurrency, actual LGU/printer/WFH acceptance and exact eGAPS output equivalence are NOT RUN - OUT OF SCOPE for this functional checkpoint.

All test processes, the owned MySQL server, the isolated Playwright session and the static QA server have ended. Final diff whitespace and 215 local document links across ten files pass. No user-store migration or eGAPS access occurred. The user database SHA-256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`; its existing change and the unrelated policy-concurrency draft remain untouched.

## Remaining financial work

Source inspection found a further M01 issue: Position/Performance still use the older generic report-row filtering path, whereas Net Assets/Cash Flow support explicit fund-scoped source calculation. The new package guard rejects incomplete members; it does not repair standalone filtered reports or implement common fund selection. **Next: make source fund scope and complete financial-row generation consistent across all four statements**, with actual multi-fund numerical proof and retained historical runs. Then continue M02 prior-payable linkage and the remaining transaction/office scenarios.

The package download does not establish exact statutory form fidelity, signatories/copies, accepted note content, true local cash-equivalent/overdraft scope or LGU adoption. eGAPS remains disconnected and unchanged. The printable assessment remains its frozen v0.7.71 reference.
