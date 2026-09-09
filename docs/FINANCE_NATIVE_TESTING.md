# Native Finance regression gate

SQLite remains the quick development backend. Finance persistence changes also require native MySQL validation: field capacity and conditional uniqueness behave differently. The v0.7.69 scrutiny reproduced both kinds of defect despite a passing SQLite suite. See [the scrutiny evidence](FINANCE_SCRUTINY_2026-09-09.md).

## Repeatable command

Use Python 3.11 with the repository requirements and a disposable MySQL server reachable through a loopback port. Supply only test credentials through `GRAND_TEST_MYSQL_USER` (default `root`), `GRAND_TEST_MYSQL_PASSWORD` and `GRAND_TEST_MYSQL_PORT`. The password and port are required; the runner does not read local `.env` settings.

Run `.venv/Scripts/python.exe scripts/run_mysql_tests.py` for the complete suite, or append Django labels such as `accounting.test_bank_concurrency` for a focused run. `--verbosity` and `--failfast` are supported. The runner always creates fresh test databases and never accepts a settings override or `--keepdb`.

The two database names that may be recreated are **`test_grand_ci_default` and `test_grand_ci_finance`**. Use a disposable server/account authorized to create and drop those names; scoped grants on those two schemas are sufficient. The ordinary connection labels `grand_ci_default` / `grand_ci_finance` are replaced by Django's explicit test names during setup. No access to the operator's application databases is required. Never point this command at a server where those test names hold retained data.

The runner requires native MySQL and strict SQL mode, binds the host to `127.0.0.1`, preserves the default/Finance router, and uses local-memory email. Each run receives a new ignored `.tmp/mysql-regression-*` directory for media, exports and backups. Repository-tracked default media is copied there. The path is printed for failure investigation; these are synthetic test artifacts, not accepted recovery sets. Passwords are never printed or placed in command arguments.

Fresh databases matter: Django transaction tests flush data while retaining migration records. Reusing that database can omit migration-seeded site configuration, shortcuts and leave policy. v0.7.69's retained-fixture failure and successful fresh rerun document this distinction. A focused pass on reused schemas is not a substitute for the fresh full gate.

## CI

The `mysql` job in [the regression workflow](../.github/workflows/security.yml) uses Python 3.11 and the pinned official MySQL Community image used in the local engineering rehearsal. It starts an isolated service with CI-only credentials and a random host port, then executes the same committed runner. The existing SQLite/security job remains independent.

Workflow triggers remain pull requests, pushes to master, the scheduled run and manual dispatch. A development-branch push alone is not a CI run. Record actual remote results separately; local execution of the same command is not a remote CI pass.

Primary configuration references: [GitHub service-container ports](https://docs.github.com/en/actions/tutorials/use-containerized-services/use-docker-service-containers) and [MySQL 8.4 container initialization](https://dev.mysql.com/doc/refman/8.4/en/docker-mysql-more-topics.html). The service's root access is confined to that disposable CI container. It does not establish a deployment credential policy.

## Coverage and limits

The native bank-concurrency test makes two authenticated requests against distinct statement batches for one posted journal line. It checks one retained match, two controlled HTTP responses and an explicit conflict message. SQLite skips this native-only case; rollback/no-replay and stored-identity checks run on both backends. Report the skip explicitly.

Full native regression still does not prove every concurrency invariant or provide named-user, printer, local-form, production-compatible off-host recovery or LGU acceptance. Preserve the [operational scrutiny](FINANCE_OPERATIONAL_SCRUTINY.md) and [backup acceptance](DATABASE_BACKUP.md) gates.


Validation: [v0.7.70 evidence and limitations](FINANCE_BANK_MATCH_VALIDATION_2026-09-09.md). PASS: full SQLite run, 711 tests discovered in 355.841 seconds (710 executed; one MySQL-only case skipped); full MySQL 8.4.12 run through the committed native runner, all 711 tests in 767.251 seconds. System, migration-drift, compilation and diff checks passed.
