# Familiar Finance register navigation validation

Scope: M06's landing-page slice on `codex/finance-familiar-web-workspaces`, based on v0.7.71. This is not completion of eGAPS parity, financial workflow coverage, clerk acceptance or authorized WFH deployment. See [modernization priorities](FINANCE_MODERNIZATION_PRIORITIES.md).

## Behavior and access

Budget preparation/appropriations, allotments and OBR are separate shortcuts. Accounting offers JEVs, ledger, trial balance, payable/withholding schedules, reconciliation, beginning balances and period close. Treasury offers existing advice, cash/instrument and remittance workspaces. Each shortcut uses its destination's current access contract. No new role, financial record, status or permission is introduced.

Integration coverage checks eight separately protected destinations before and after their read grants, direct HTTP denial/allowance, permission revocation, base register reachability, UAT read-versus-mutation separation and the conjunction of remittance and Voucher Workbench access. Existing source department and mutation checks remain authoritative.

## Validation

- Initial focused run: **FAIL - CAUSED BY CURRENT WORK**. `python manage.py test finance.test_operations --noinput` ran 11 tests in 5.080 seconds with one error: the new UAT assertion used `can_review` instead of the view's actual `can_approve` context key. Corrected the assertion before the dependent run; no application permission repair was needed.
- **PASS:** `python manage.py test finance.test_operations finance.test_work_tasks vouchers budget accounting --noinput`: 314 tests discovered, 311 executed, three native-only tests skipped, 595.617 seconds; process exited 0. This covers navigation, personal work and the affected destination/access modules across both test-database aliases, including the corrected focused test. The skips are the existing bank concurrency case and the two unrelated local native-policy drafts; those drafts remain uncommitted.
- **PASS:** `python manage.py check`, `python manage.py makemigrations --check --dry-run`, compilation of the four changed Python files and `git diff --check`.
- **PASS:** local continuity/navigation document links resolve. The final template edit preceded test execution; final browser screenshots were captured from a restarted server.
- Full project and native runtime suites: **NOT RUN - OUT OF SCOPE** for this navigation-only slice, which changes no persistence or financial calculations. Existing native policy scrutiny remains **NOT RUN - ENVIRONMENTAL** under the separately retained Docker blocker. Neither is a production acceptance pass.

## Browser evidence

Playwright CLI with Edge used synthetic accounts and two isolated SQLite stores beneath `.tmp/finance-navigation-20260910`, served only on `127.0.0.1:8768`. The fixture explicitly disables dotenv loading and asserts both database paths; operator databases are not used. Initial missing public logo assets in the fixture were copied from the repository's existing defaults before the final browser checks.

- **PASS:** desktop at 1440 pixels; mobile at 390 and 320 pixels, with no horizontal page overflow. Final screenshots were refreshed after restarting the fixture server so the last navigation-spacing edit was loaded.
- **PASS:** Allotment Release Orders shortcut opens the existing register; ordinary requesting-office account sees its payable workspace and no administration group.
- **PASS:** keyboard Tab reaches the native disclosure summary; Enter opens it; the focus outline is visible at 3 pixels.
- **PASS:** final full-account browser console reports zero errors and zero warnings. Earlier requesting-office console check also reports zero.
- Screenshots: [desktop](../output/playwright/finance-familiar-navigation/desktop.png), [390-pixel mobile](../output/playwright/finance-familiar-navigation/mobile.png), [320-pixel mobile](../output/playwright/finance-familiar-navigation/narrow.png), [requesting office](../output/playwright/finance-familiar-navigation/requesting-office.png). Accounts and data are synthetic. Browser and fixture server were stopped after inspection.

## Evidence boundaries

The [printable comparison](../output/pdf/GRAND-eGAPS-Assessment-2026-09-10.pdf) is a frozen v0.7.71 assessment for colleague review; it precedes this navigation change. Seven landscape A4 pages were rendered and inspected, including the handwritten review worksheet. eGAPS was not modified and remains independent of GRAND. Actual clerk timings, forms, named-user remote exercises and LGU decisions remain open.

Operator `db.sqlite3` SHA-256 remains `C8255385F64732838F7D07A84C5587B5CE5BA2F708A566F96AFFF80D94E7374C`. Preserve that user's existing change and the separate `accounting/test_policy_concurrency.py` draft outside this checkpoint.
