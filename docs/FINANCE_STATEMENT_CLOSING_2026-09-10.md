# Statement activity and nominal closing transfers

This is a functional prerequisite under M01, not completion of the missing Cash Flow or Changes in Net Assets/Equity statements. [Modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md) retain those deliverables and exact local-output acceptance.

## Reproduced defect

On v0.7.72, an independently submitted/posted closing JEV debiting revenue and crediting accumulated surplus for 1,250.00 caused the generated performance statement to report operating result **0.00**, despite 1,250.00 of period revenue. The only available manual classification was an ordinary adjustment; the statement summed the closing debit with activity. This is FIN-GAP-036.

The fresh native reproduction used MySQL 8.4.11 on the owned loopback fixture and the committed two-store runner: one test failed in 1.254 seconds with `0.00 != 1250.00`. Both test databases were destroyed afterward. Log: `.tmp/statement-closing-reproduction.log`. This is numerical source-to-posting-to-export evidence, not a menu comparison.

## Implemented behavior (verified in v0.7.73)

Journal preparers can explicitly choose **Nominal-account closing transfer** through the existing JEV form. Submission and posting validate that its lines move revenue/expense balances to equity and contain no assets or liabilities. Existing balancing, owning-office, UAT exclusion, independent posting and immutable-history controls remain authoritative. The migration adds the source choice without relabelling retained journals.

The performance statement excludes these transfers from period activity. Reversals follow the actual retained original-JEV chain, including an original outside the reporting date range; descriptions and user-supplied snapshot labels cannot decide the classification. All selected JEVs, including excluded closes, remain in report source evidence with their classification and checksums. Controls state the calculation basis and excluded-entry count. The position statement continues to use the complete posted ledger.

Existing reports retain their files, checksums and source snapshots. A corrected or later report is a new run. Historical closing entries previously encoded as manual/adjustment are **not silently inferred or relabelled**: an authorized correction must reverse the old entry and independently post an explicitly classified replacement in an allowed period before producing the corrected report. Signed-period reopening and local authority remain applicable. Actual historical corrections are not performed by this change.

## Checks

- **PASS:** focused SQLite tests, two tests in 2.259 seconds. The XLSX contains the original 1,250.00 surplus after a nominal close; the position statement shows 1,250.00 equity, zero unclosed result and zero equation difference. A subsequent closing reversal preserves period performance and all three source JEVs. The prior report checksum remains unchanged. A cash receipt cannot use the closing classification.
- **PASS:** system check, migration-drift check and `git diff --check`.
- **FAIL - CAUSED BY CURRENT WORK (fixture setup):** the first native affected run completed 87 tests in 42.496 seconds with one Treasury register failure. The new portable server had empty named time-zone tables; `CONVERT_TZ` returned NULL and the unchanged timestamp/date filter omitted the 900.00 instrument. This was not a closing-calculation failure. The runner now rejects that incomplete environment before creating schemas; Oracle's checksum-verified 2026c POSIX zone data was loaded only into the disposable server and it was restarted. UTC-to-Asia/Manila conversion then passed the runner preflight.
- **PASS:** `.venv/Scripts/python.exe manage.py test reporting accounting vouchers finance.test_work_tasks --noinput`: 394 discovered, 391 executed, three native-only skips, 174.151 seconds, process exit 0. Scope includes report retention/notes, downstream voucher posting and personal-work consumers. The skips are the existing bank concurrency case and two unrelated uncommitted policy drafts. No real LGU acceptance follows from this run.
- **PASS:** `.venv/Scripts/python.exe .tmp/portable_mysql.py test reporting.test_finance_reporting accounting.tests accounting.test_period_close`, using the committed fresh runner: all 87 tests on Windows MySQL 8.4.11 in 46.885 seconds, process exit 0. Log: `.tmp/statement-closing-native-final.log`. This reruns the original Treasury failure as well as closing, mapping, ordinary accounting, reversal and period-close controls with the corrected fixture.
- Full project/native suites: **NOT RUN - OUT OF SCOPE** for this bounded statement-activity distinction. Broad SQLite dependency coverage plus affected native persistence/report/close coverage passed; this does not establish unrelated concurrency, cash-flow, net-assets, payable linkage or release readiness. Browser/print-layout acceptance: **NOT RUN - OUT OF SCOPE**; no layout was changed and the generated XLSX amount was inspected programmatically. Exact local forms and human printer acceptance remain separate gates.
- The owned native server and test processes were stopped. Operator `db.sqlite3` SHA-256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. No eGAPS, live database or historical journal changes. The unrelated policy-test draft remains uncommitted.

## Remaining statement work

M01 still needs source-grounded net-assets movements and cash-flow classifications, reconciled opening/closing amounts, comparative periods, correction handling and accepted exact outputs. Inspect contra-account presentation as well: the existing statement engine uses account normal balances when aggregating types, which needs a specific contra-revenue/contra-asset reproduction before reliance. That observation is an unverified follow-up, not a newly established defect.

The [City of Naga financial-statements inventory](https://cityofnagacebu.gov.ph/financial-reports/) lists separate performance, position, cash-flow and net-assets/equity statements by fund. It supports retaining distinct deliverables; it does not establish the implementing municipality's exact accepted layouts or this code's compliance. Current applicable COA authority and local acceptance remain required. The COA reference pages attempted during this slice were unavailable; no new legal interpretation is claimed.
