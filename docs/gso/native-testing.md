# Native MySQL validation

Use an explicitly disposable MySQL server bound to loopback, separate from GRAND's
parallel Finance test server and all operator databases. Install optional dependencies
from `requirements-mysql-test.txt` in the development environment. PyMySQL matches the
inspected GRAND adapter; cryptography supports its MySQL authentication handshake.

Set `GSO_TEST_MYSQL_PORT`, `GSO_TEST_MYSQL_PASSWORD` and optionally
`GSO_TEST_MYSQL_USER` (default `root`) through the environment, never command arguments
or committed files. Run `python scripts/run_mysql_tests.py` for the full suite or
append Django test labels, for example `inventory.test_receiving_concurrency`.

The runner bypasses operator `.env`, forces loopback, verifies strict native MySQL,
and uses a new random schema each run. It isolates private/media files in ignored
`.tmp/mysql-tests-*`. It offers no keepdb or arbitrary settings override. Django drops
the test schema on normal completion; verify cleanup after interruption. Credentials
must be limited to the disposable server. Stop a server only if this task owns it.

Concurrency tests use separate connections and synchronized starts: competing
acceptance of one receipt, competing receipts with the same property tag, and ordinary
asset creation competing with receipt acceptance. They assert one retained material
result and one controlled validation conflict. SQLite skips them explicitly.

The final 2026-10-17 checkpoint passed all 45 tests on MySQL 8.4.11 with no skips or
warnings. Migration 0015 replaces inherited conditional uniqueness using GRAND's
generated nullable-marker pattern, with virtual markers for populated SQLite upgrades.
Preflight refuses duplicate open cases before schema changes. Tests cover concurrent
inserts, close/reopen semantics, populated upgrades and native duplicate preflight.
SQLite executes 39 tests and explicitly skips six native-only tests.
GRAND router/two-store tests,
named-time-zone reporting, real migrations and operational recovery remain separate
integration gates. See [validation](validation-2026-10-16.md).

## Actual GRAND integration harness

Use GRAND's dependency environment and an explicit clean source checkout:
`python scripts/run_grand_source_tests.py --grand-root PATH` uses fresh SQLite
default/finance databases. Add `--mysql` to use the same explicit disposable
loopback credentials above and two randomly named MySQL schemas. This loads GRAND's
actual settings/router and installs the GSO inventory app with private evidence
storage isolated under `.tmp`. It never loads either checkout's operator `.env`.

The harness exercises existing Finance source visibility and snapshot currentness,
plus receiving with GRAND users/departments and operational-store routing. The
MySQL-only source replacement test uses separate connections and the same case-lock/
line-replacement transaction shape as voucher preparation; it does not execute the
entire Finance preparation workflow. SQLite skips that test. Fresh schema success
does not prove populated data import, coordinated restore or route/UI integration.
Record actual results in the validation document before claiming these gates pass.
The native concurrency assertion inspects `performance_schema.data_lock_waits` and
`performance_schema.threads` to prove the reader was blocked; the disposable test
account needs read access to those tables. These are test privileges, not proposed
application-user grants.
