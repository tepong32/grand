# Bank-match conflict and native-gate validation - 2026-09-09

Status: **FIN-GAP-035 VERIFIED in v0.7.70; production NO-GO**. The user cancelled the planned pause; bounded scrutiny continues after this checkpoint.

Bank matching now reports known conflicts after complete rollback, with an explicit reload/check/retry instruction and no implicit replay. Generated nullable keys enforce active bank-row and journal-line match identities while preserving superseded history. Migration accounting/0011 refuses historical duplicates before DDL. A committed fresh two-store MySQL runner and independent CI service job complement SQLite.

## Reproduction and repair

Two independently staged synthetic statements competed for one genuinely posted 100.00 bank line. The native service probe retained one match but returned MySQL deadlock 1213 to the losing caller. The actual authenticated endpoint reproduced HTTP 500/302 (FAIL - PRE-EXISTING, 1 test, 6.792 seconds). Native lock evidence showed a shared-to-exclusive journal-line lock upgrade; duplicate financial records were not reproduced by that experiment.

The retained native HTTP regression now requires HTTP 302 for both callers, exactly one stored match, and one explicit conflict message. Automatic-match failure injection after match/event writes proves rollback of retained matching evidence and state version, without automatic replay; an explicit new attempt succeeds. A separate connection-failure case remains an OperationalError instead of being misreported as a normal conflict. The existing two-month bank workflow tests direct duplicate-row insertion, attempted reactivation of a superseded match, correction, carry-forward, later clearance and reconciliation.

Initial repaired native selection: PASS, 3 tests in 19.963 seconds. SQLite selection: PASS for applicable tests, 3 discovered in 12.228 seconds with the native concurrency case skipped. The final suites include the additional unrelated-database-failure case.

## Final regression

PASS: full SQLite run, 711 tests discovered in 355.841 seconds (710 executed; one MySQL-only case skipped); full MySQL 8.4.12 run through the committed native runner, all 711 tests in 767.251 seconds. System, migration-drift, compilation and diff checks passed.

Commands: `.venv/Scripts/python.exe manage.py test --noinput` and `.venv/Scripts/python.exe scripts/run_mysql_tests.py`, with explicit disposable credentials and loopback port supplied only through the documented environment variables. The local helper granted only the two fixed test schemas on the owned server. See [FINANCE_NATIVE_TESTING.md](FINANCE_NATIVE_TESTING.md) for repeatable setup. Browser NOT RUN - OUT OF SCOPE for unchanged layout; actual authenticated HTTP requests cover the conflict response.

Remote CI: NOT RUN - ENVIRONMENTAL; GitHub CLI authentication for the configured account is invalid. Local execution of the same native runner passed; no remote workflow result is claimed. The workflow was manually reviewed against primary GitHub service-container syntax; optional local YAML parsers were unavailable. No new software was installed. No live/user database migration or real financial authority change. Production remains NO-GO.

## Migration and recovery

Inserted a duplicate only into the disposable pre-v70 restore fixture. Migration accounting/0011 refused it before DDL or migration recording; both synthetic rows remained unchanged. The fixture was then replaced by a new verified native restore, not a production deduplication.

Final native manifest SHA-256: `24648f078353eaa76aa8150e886b85695ca09dcb66fd372d51600941e8906ba5`. All 203 table controls matched after restore (159 default tables / 2,006 rows; 44 Finance tables / 233 rows). The active bank key and Budget generated keys survived. All ten stored file references matched. With original source runtime trees unavailable, restored evidence reproduced posted debit = credit 3,900.00, bank balance 1,100.00 with zero difference, and payment-report issued/released totals 900.00. Source runtime trees were returned to their original locations. This is same-host synthetic recovery, not approved off-host acceptance.

Owned rehearsal containers and network were removed after validation; synthetic private credential files were removed. Docker Desktop was returned to its originally stopped state. Ignored logs/receipts and image cache remain; no operator database was changed.

D-062/D-063 record decisions. Remaining native invariant audit, process/persona mapping and LGU discovery/form/opening/redacted-replay/printer/off-host/seven-party acceptance gates remain future work under the continued scrutiny gate.
